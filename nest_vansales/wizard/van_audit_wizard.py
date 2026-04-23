# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class VanAuditWizard(models.TransientModel):
    """
    Wizard: Generate a Van Audit snapshot.

    Reads current stock.quant records for the van warehouse and creates a
    vansales.audit record with pre-populated system quantities.
    The auditor then enters counted quantities and reviews variances.
    """
    _name = 'vansales.audit.wizard'
    _description = 'Van Audit Wizard'

    van_id = fields.Many2one(
        'vansales.van',
        string='Van',
        required=True,
    )
    notes = fields.Text(string='Notes / Remarks')

    def action_generate_audit(self):
        """Create a new vansales.audit and generate lines from quants."""
        self.ensure_one()
        if not self.van_id.warehouse_id:
            raise UserError(_('Van has no warehouse configured.'))

        audit = self.env['vansales.audit'].create({
            'van_id': self.van_id.id,
            'notes': self.notes or '',
        })
        audit.action_generate_lines()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Van Audit'),
            'res_model': 'vansales.audit',
            'res_id': audit.id,
            'view_mode': 'form',
        }
