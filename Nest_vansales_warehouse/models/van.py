# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class VansalesVan(models.Model):
    """
    Represents a Van in the Van Sales module.

    Each van is associated with a dedicated Odoo warehouse (van warehouse)
    and linked to a main/supply warehouse (MAINWH by default).  The van
    master record ties together:
      - assigned salesperson / driver
      - retail and wholesale pricelists
      - cash / bank / card journals for payment capture
    """
    _name = 'vansales.van'
    _description = 'Van Sales – Van'
    _rec_name = 'name'

    # ── Identity ──────────────────────────────────────────────────────────────
    name = fields.Char(
        string='Van Name',
        required=True,
    )
    code = fields.Char(
        string='Van Code',
        required=True,
        copy=False,
        help='Unique short code for this van (e.g. VAN01).',
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )

    # ── People ────────────────────────────────────────────────────────────────
    user_id = fields.Many2one(
        'res.users',
        string='Driver / Salesperson',
        required=True,
        domain="[('company_ids', 'in', company_id)]",
    )

    # ── Warehouses ────────────────────────────────────────────────────────────
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Van Warehouse',
        required=True,
        help='Dedicated Odoo warehouse representing this van\'s stock.',
    )
    main_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Main Warehouse (Supply)',
        help='Supply / main warehouse (typically MAINWH). '
             'Used as source for load transfers.',
    )

    # ── Pricing ───────────────────────────────────────────────────────────────
    pricelist_retail_id = fields.Many2one(
        'product.pricelist',
        string='Retail Pricelist',
    )
    pricelist_wholesale_id = fields.Many2one(
        'product.pricelist',
        string='Wholesale Pricelist',
    )

    # ── Journals / Payment ────────────────────────────────────────────────────
    cash_journal_id = fields.Many2one(
        'account.journal',
        string='Cash Journal',
        domain="[('type', '=', 'cash'), ('company_id', '=', company_id)]",
    )
    bank_journal_id = fields.Many2one(
        'account.journal',
        string='Bank Journal',
        domain="[('type', '=', 'bank'), ('company_id', '=', company_id)]",
    )
    visa_journal_id = fields.Many2one(
        'account.journal',
        string='Visa Journal',
        domain="[('type', 'in', ['bank', 'cash']), ('company_id', '=', company_id)]",
        help='Journal used for Visa card payments.',
    )
    mastercard_journal_id = fields.Many2one(
        'account.journal',
        string='Mastercard Journal',
        domain="[('type', 'in', ['bank', 'cash']), ('company_id', '=', company_id)]",
        help='Journal used for Mastercard payments.',
    )

    # ── Operational ───────────────────────────────────────────────────────────
    allow_negative_stock = fields.Boolean(
        string='Allow Negative Stock',
        default=True,
        help='When enabled, van sale orders can be confirmed even if '
             'the van warehouse has insufficient stock (no blocking).',
    )

    # ── Computed helpers (smart buttons) ─────────────────────────────────────
    sale_order_count = fields.Integer(
        string='Van Orders',
        compute='_compute_counts',
    )
    receipt_count = fields.Integer(
        string='Receipts',
        compute='_compute_counts',
    )

    # ── Constraints ───────────────────────────────────────────────────────────
    _sql_constraints = [
        (
            'code_company_uniq',
            'UNIQUE(code, company_id)',
            'Van code must be unique per company.',
        ),
    ]

    @api.constrains('code')
    def _check_code(self):
        for rec in self:
            if not rec.code or not rec.code.strip():
                raise ValidationError(_('Van Code cannot be empty.'))

    # ── Computes ──────────────────────────────────────────────────────────────
    def _compute_counts(self):
        SaleOrder = self.env['sale.order']
        Receipt = self.env['vansales.receipt']
        for van in self:
            van.sale_order_count = SaleOrder.search_count([('van_id', '=', van.id)])
            van.receipt_count = Receipt.search_count([('van_id', '=', van.id)])

    # ── Actions (smart buttons) ───────────────────────────────────────────────
    def action_view_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Van Orders'),
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('van_id', '=', self.id)],
            'context': {
                'default_is_van_sale': True,
                'default_van_id': self.id,
            },
        }

    def action_view_receipts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Van Receipts'),
            'res_model': 'vansales.receipt',
            'view_mode': 'list,form',
            'domain': [('van_id', '=', self.id)],
            'context': {'default_van_id': self.id},
        }

    def action_van_load(self):
        """Open the Van Load wizard."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Load Van'),
            'res_model': 'vansales.van.load.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_van_id': self.id},
        }

    def action_van_unload(self):
        """Open the Van Unload wizard."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Unload Van'),
            'res_model': 'vansales.van.unload.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_van_id': self.id},
        }

    def action_van_audit(self):
        """Open the Van Audit wizard."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Van Audit'),
            'res_model': 'vansales.audit.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_van_id': self.id},
        }
