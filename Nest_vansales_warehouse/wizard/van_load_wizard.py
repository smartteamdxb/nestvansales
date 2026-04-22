# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class VanLoadWizardLine(models.TransientModel):
    _name = 'vansales.van.load.wizard.line'
    _description = 'Van Load Wizard Line'

    wizard_id = fields.Many2one('vansales.van.load.wizard', ondelete='cascade')
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


class VanLoadWizard(models.TransientModel):
    """
    Wizard: Load Van – transfer stock from MAINWH to the van warehouse.

    Creates an internal stock.picking from the main warehouse stock location
    to the van warehouse stock location.

    TODO: Optionally auto-validate the picking (currently left in 'confirmed'
          state so warehouse staff can review and validate).
    """
    _name = 'vansales.van.load.wizard'
    _description = 'Van Load Wizard'

    van_id = fields.Many2one(
        'vansales.van',
        string='Van',
        required=True,
    )
    source_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Source Warehouse (Supply)',
        compute='_compute_locations',
        store=True,
        readonly=False,
    )
    source_location_id = fields.Many2one(
        'stock.location',
        string='Source Location',
        compute='_compute_locations',
        store=True,
        readonly=False,
    )
    dest_location_id = fields.Many2one(
        'stock.location',
        string='Destination Location (Van)',
        compute='_compute_locations',
        store=True,
        readonly=False,
    )
    scheduled_date = fields.Datetime(
        string='Scheduled Date',
        default=fields.Datetime.now,
    )
    line_ids = fields.One2many(
        'vansales.van.load.wizard.line',
        'wizard_id',
        string='Products to Load',
    )

    @api.depends('van_id')
    def _compute_locations(self):
        for wiz in self:
            if wiz.van_id:
                wiz.source_warehouse_id = wiz.van_id.main_warehouse_id
                wiz.source_location_id = (
                    wiz.van_id.main_warehouse_id.lot_stock_id
                    if wiz.van_id.main_warehouse_id
                    else False
                )
                wiz.dest_location_id = (
                    wiz.van_id.warehouse_id.lot_stock_id
                    if wiz.van_id.warehouse_id
                    else False
                )
            else:
                wiz.source_warehouse_id = False
                wiz.source_location_id = False
                wiz.dest_location_id = False

    def action_create_transfer(self):
        """Create internal picking from main WH to van WH."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Please add at least one product to load.'))
        if not self.source_location_id:
            raise UserError(_('Source location is not set. Please configure the main warehouse on the van.'))
        if not self.dest_location_id:
            raise UserError(_('Destination (van) location is not set. Please configure the van warehouse.'))

        # Find an internal picking type for the source warehouse
        picking_type = self.env['stock.picking.type'].search([
            ('warehouse_id', '=', self.source_warehouse_id.id),
            ('code', '=', 'internal'),
        ], limit=1)
        if not picking_type:
            # Fallback: look in van warehouse
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
            raise UserError(_('All quantities are zero. Please enter valid quantities.'))

        picking_vals = {
            'picking_type_id': picking_type.id if picking_type else False,
            'location_id': self.source_location_id.id,
            'location_dest_id': self.dest_location_id.id,
            'scheduled_date': self.scheduled_date,
            'origin': _('Van Load – %s') % self.van_id.code,
            'move_ids': [(0, 0, mv) for mv in move_vals],
        }
        picking = self.env['stock.picking'].create(picking_vals)
        picking.action_confirm()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Van Load Transfer'),
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
        }
