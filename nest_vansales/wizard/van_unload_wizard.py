# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class VanUnloadWizardLine(models.TransientModel):
    _name = 'vansales.van.unload.wizard.line'
    _description = 'Van Unload Wizard Line'

    wizard_id = fields.Many2one('vansales.van.unload.wizard', ondelete='cascade')
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


class VanUnloadWizard(models.TransientModel):
    """
    Wizard: Unload Van – transfer remaining/excess stock from van WH back to MAINW.

    Useful at end-of-day or end-of-route to return unsold goods to the
    main warehouse.

    TODO: Optionally auto-validate picking.
    """
    _name = 'vansales.van.unload.wizard'
    _description = 'Van Unload Wizard'

    van_id = fields.Many2one(
        'vansales.van',
        string='Van',
        required=True,
    )
    source_location_id = fields.Many2one(
        'stock.location',
        string='Source Location (Van)',
        compute='_compute_locations',
        store=True,
        readonly=False,
    )
    dest_location_id = fields.Many2one(
        'stock.location',
        string='Destination Location (Main WH)',
        compute='_compute_locations',
        store=True,
        readonly=False,
    )
    scheduled_date = fields.Datetime(
        string='Scheduled Date',
        default=fields.Datetime.now,
    )
    line_ids = fields.One2many(
        'vansales.van.unload.wizard.line',
        'wizard_id',
        string='Products to Unload',
    )

    @api.depends('van_id')
    def _compute_locations(self):
        for wiz in self:
            if wiz.van_id:
                wiz.source_location_id = (
                    wiz.van_id.warehouse_id.lot_stock_id
                    if wiz.van_id.warehouse_id
                    else False
                )
                wiz.dest_location_id = (
                    wiz.van_id.main_warehouse_id.lot_stock_id
                    if wiz.van_id.main_warehouse_id
                    else False
                )
            else:
                wiz.source_location_id = False
                wiz.dest_location_id = False

    def action_create_transfer(self):
        """Create internal picking from van WH back to main WH."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Please add at least one product to unload.'))
        if not self.source_location_id:
            raise UserError(_('Source (van) location is not set.'))
        if not self.dest_location_id:
            raise UserError(_('Destination (main WH) location is not set. Please configure the main warehouse on the van.'))

        picking_type = self.env['stock.picking.type'].search([
            ('warehouse_id', '=', self.van_id.warehouse_id.id),
            ('code', '=', 'internal'),
        ], limit=1)
        if not picking_type:
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'internal'),
                ('company_id', '=', self.van_id.company_id.id),
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
                'location_id': self.source_location_id.id,
                'location_dest_id': self.dest_location_id.id,
            })

        if not move_vals:
            raise UserError(_('All quantities are zero.'))

        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id if picking_type else False,
            'location_id': self.source_location_id.id,
            'location_dest_id': self.dest_location_id.id,
            'scheduled_date': self.scheduled_date,
            'origin': _('Van Unload – %s') % self.van_id.code,
            'move_ids': [(0, 0, mv) for mv in move_vals],
        })
        picking.action_confirm()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Van Unload Transfer'),
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
        }
