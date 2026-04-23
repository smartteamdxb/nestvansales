# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class VanReturnWizardLine(models.TransientModel):
    _name = 'vansales.van.return.wizard.line'
    _description = 'Van Return Wizard Line'

    wizard_id = fields.Many2one('vansales.van.return.wizard', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    quantity = fields.Float(string='Quantity', required=True, default=1.0)
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        compute='_compute_uom',
        store=True,
        readonly=False,
    )

    @api.depends('product_id')
    def _compute_uom(self):
        for line in self:
            line.uom_id = line.product_id.uom_id if line.product_id else False


class VanReturnWizard(models.TransientModel):
    """
    Wizard: Customer Return – restock the van warehouse first.

    Per business decision: customer returns go back into the van warehouse
    stock (not directly to main WH).  At unload time the van WH stock is
    returned to MAINW via the Unload wizard.

    Creates a return incoming picking with destination = van WH stock.

    TODO: Optionally create credit note (account.move refund) linked to the
          original invoice.
    """
    _name = 'vansales.van.return.wizard'
    _description = 'Van Return Wizard'

    van_id = fields.Many2one(
        'vansales.van',
        string='Van',
        required=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
    )
    origin_sale_id = fields.Many2one(
        'sale.order',
        string='Original Sale Order',
        domain="[('van_id', '=', van_id), ('state', 'in', ['sale', 'done'])]",
    )
    return_location_id = fields.Many2one(
        'stock.location',
        string='Destination (Van Stock)',
        compute='_compute_return_location',
        store=True,
        readonly=False,
    )
    reason = fields.Text(string='Return Reason')
    scheduled_date = fields.Datetime(
        string='Date',
        default=fields.Datetime.now,
    )
    line_ids = fields.One2many(
        'vansales.van.return.wizard.line',
        'wizard_id',
        string='Return Lines',
    )

    @api.depends('van_id')
    def _compute_return_location(self):
        for wiz in self:
            wiz.return_location_id = (
                wiz.van_id.warehouse_id.lot_stock_id
                if wiz.van_id and wiz.van_id.warehouse_id
                else False
            )

    def action_create_return(self):
        """
        Create a receipt / return picking into the van warehouse stock.
        """
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Please add at least one product to return.'))
        if not self.return_location_id:
            raise UserError(_('Van return location is not set.'))

        # Use the van warehouse receipts picking type (incoming from customer)
        picking_type = self.env['stock.picking.type'].search([
            ('warehouse_id', '=', self.van_id.warehouse_id.id),
            ('code', '=', 'incoming'),
        ], limit=1)
        if not picking_type:
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'incoming'),
                ('company_id', '=', self.van_id.company_id.id),
            ], limit=1)

        # Customer location (virtual)
        customer_location = self.env.ref('stock.stock_location_customers', raise_if_not_found=False)
        if not customer_location:
            customer_location = self.env['stock.location'].search([
                ('usage', '=', 'customer'),
            ], limit=1)

        move_vals = []
        for line in self.line_ids:
            if line.quantity <= 0:
                continue
            move_vals.append({
                'name': line.product_id.display_name,
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity,
                'product_uom': line.uom_id.id or line.product_id.uom_id.id,
                'location_id': customer_location.id if customer_location else self.return_location_id.id,
                'location_dest_id': self.return_location_id.id,
            })

        if not move_vals:
            raise UserError(_('All quantities are zero.'))

        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id if picking_type else False,
            'location_id': customer_location.id if customer_location else self.return_location_id.id,
            'location_dest_id': self.return_location_id.id,
            'partner_id': self.partner_id.id,
            'scheduled_date': self.scheduled_date,
            'origin': _('Return – %s – %s') % (self.van_id.code, self.partner_id.name),
            'move_ids': [(0, 0, mv) for mv in move_vals],
        })
        picking.action_confirm()

        # TODO: Optionally create credit note:
        #   if self.origin_sale_id and invoice:
        #       invoice._reverse_moves(...)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Customer Return Picking'),
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
        }
