# -*- coding: utf-8 -*-
from odoo import models, fields


class VansalesSyncBatch(models.Model):
    """
    Van Sales Sync Batch / Log.

    Tracks each sync batch submitted by a mobile device.  Used to:
    - Audit what was received and when.
    - Track processing state (received → processed / failed).
    - Store references to created records.
    - Support replay / deduplication by payload hash.
    """
    _name = 'vansales.sync.batch'
    _description = 'Van Sales Sync Batch'
    _rec_name = 'name'
    _order = 'received_at desc, id desc'

    name = fields.Char(
        string='Batch Reference',
        readonly=True,
        copy=False,
        default='/',
    )
    device_id = fields.Char(
        string='Device ID',
        index=True,
        required=True,
    )
    van_id = fields.Many2one(
        'vansales.van',
        string='Van',
        index=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Submitted By',
        default=lambda self: self.env.user,
    )
    received_at = fields.Datetime(
        string='Received At',
        required=True,
        default=fields.Datetime.now,
        readonly=True,
    )
    payload_hash = fields.Char(
        string='Payload Hash (SHA-256)',
        index=True,
        help='SHA-256 hash of the raw JSON payload for deduplication.',
    )
    state = fields.Selection(
        selection=[
            ('received', 'Received'),
            ('processing', 'Processing'),
            ('processed', 'Processed'),
            ('failed', 'Failed'),
        ],
        string='State',
        default='received',
        required=True,
        index=True,
    )
    message = fields.Text(
        string='Message / Error',
        help='Processing result or error details.',
    )

    # ── References (JSON-encoded summary of created record IDs) ───────────────
    created_order_ids_json = fields.Text(
        string='Created Order IDs (JSON)',
        help='JSON array of sale.order IDs created in this batch.',
    )
    created_receipt_ids_json = fields.Text(
        string='Created Receipt IDs (JSON)',
        help='JSON array of vansales.receipt IDs created in this batch.',
    )

    # ── Raw payload (optional, for debugging) ─────────────────────────────────
    raw_payload = fields.Text(
        string='Raw Payload',
        help='Full JSON payload received (stored for debugging; '
             'remove in production if storage is a concern).',
    )
