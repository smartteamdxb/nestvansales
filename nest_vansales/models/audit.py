# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class VansalesAudit(models.Model):
    """
    Van Sales Audit – Quantity Balance Check.

    A snapshot of the van warehouse's stock at a point in time.
    Allows salesperson / manager to count physical stock, review variances,
    and optionally apply inventory adjustments.

    States:
        draft     – lines generated, can be edited.
        confirmed – locked, variances reviewed.
        adjusted  – inventory adjustment moves created (manager only).
        done      – audit closed.
    """
    _name = 'vansales.audit'
    _description = 'Van Sales Audit'
    _rec_name = 'name'
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Audit Reference',
        readonly=True,
        copy=False,
        default='/',
    )
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )
    van_id = fields.Many2one(
        'vansales.van',
        string='Van',
        required=True,
        index=True,
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Van Warehouse',
        related='van_id.warehouse_id',
        store=True,
        readonly=True,
    )
    date = fields.Datetime(
        string='Audit Date',
        required=True,
        default=fields.Datetime.now,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Audited By',
        required=True,
        default=lambda self: self.env.user,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('adjusted', 'Adjusted'),
            ('done', 'Done'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )
    notes = fields.Text(string='Notes')
    line_ids = fields.One2many(
        'vansales.audit.line',
        'audit_id',
        string='Audit Lines',
    )
    line_count = fields.Integer(
        string='Lines',
        compute='_compute_line_count',
    )

    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    # ── Actions ───────────────────────────────────────────────────────────────
    def action_generate_lines(self):
        """
        Snapshot current stock.quant records for the van warehouse stock location
        and populate audit lines with system quantities.
        """
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Lines can only be generated for draft audits.'))

        warehouse = self.van_id.warehouse_id
        if not warehouse:
            raise UserError(_('Van has no warehouse configured.'))

        stock_location = warehouse.lot_stock_id
        quants = self.env['stock.quant'].search([
            ('location_id', 'child_of', stock_location.id),
            ('quantity', '!=', 0),
        ])

        # Remove existing lines and regenerate
        self.line_ids.unlink()
        lines = []
        for quant in quants:
            lines.append({
                'audit_id': self.id,
                'product_id': quant.product_id.id,
                'lot_id': quant.lot_id.id if quant.lot_id else False,
                'location_id': quant.location_id.id,
                'uom_id': quant.product_id.uom_id.id,
                'qty_system': quant.quantity,
                'qty_counted': 0.0,
            })
        self.env['vansales.audit.line'].create(lines)

        if self.name == '/':
            self.name = self.env['ir.sequence'].next_by_code('vansales.audit') or '/'

    def action_confirm(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Only draft audits can be confirmed.'))
        if not self.line_ids:
            raise UserError(_('Please generate audit lines first.'))
        self.state = 'confirmed'

    def action_apply_adjustments(self):
        """
        Apply inventory adjustments for lines with variances.

        TODO: Create stock.inventory.adjustment (or stock.quant write) for each
              line where qty_diff != 0.  Requires manager group.
        """
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError(_('Only confirmed audits can be adjusted.'))

        # TODO: For each line with qty_diff != 0, create an inventory adjustment:
        #   self.env['stock.quant']._update_available_quantity(
        #       product, location, qty_diff, lot_id=lot)
        # This requires careful handling of Odoo 19 inventory adjustment API.

        self.state = 'adjusted'

    def action_done(self):
        self.ensure_one()
        if self.state not in ('confirmed', 'adjusted'):
            raise UserError(_('Audit must be confirmed or adjusted before closing.'))
        self.state = 'done'


class VansalesAuditLine(models.Model):
    """
    Single product line within a Van Sales Audit snapshot.
    """
    _name = 'vansales.audit.line'
    _description = 'Van Sales Audit Line'

    audit_id = fields.Many2one(
        'vansales.audit',
        string='Audit',
        required=True,
        ondelete='cascade',
        index=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='Lot / Serial',
    )
    location_id = fields.Many2one(
        'stock.location',
        string='Location',
    )
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
    )
    qty_system = fields.Float(
        string='System Qty',
        digits='Product Unit of Measure',
        readonly=True,
    )
    qty_counted = fields.Float(
        string='Counted Qty',
        digits='Product Unit of Measure',
        default=0.0,
    )
    qty_diff = fields.Float(
        string='Variance',
        digits='Product Unit of Measure',
        compute='_compute_qty_diff',
        store=True,
    )

    @api.depends('qty_counted', 'qty_system')
    def _compute_qty_diff(self):
        for line in self:
            line.qty_diff = line.qty_counted - line.qty_system
