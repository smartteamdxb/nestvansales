# -*- coding: utf-8 -*-
"""
Van Sales Mobile Sync API

Provides JSON endpoints for the offline PWA / mobile client:

  POST /vansales/api/sync/batch
      Accept batched orders and receipts from the device.
      Idempotent by external_uid – records already created are skipped.
      Returns mapping of external_uid → server record ids.

  GET  /vansales/api/config
      Return van configuration for the currently authenticated user.
      Used by the mobile app to bootstrap pricelist / journal IDs.

Authentication:
    Standard Odoo session cookie (HTTP Basic or API key also work if
    configured on the Odoo instance).  CORS and auth are handled by Odoo's
    http layer – no custom auth middleware is required here.

TODO: Add token-based authentication for use without browser session.
TODO: Add pagination to /config product catalogue if needed.
"""
import hashlib
import json
import logging

from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)


class VansalesMobileSyncController(http.Controller):

    # ──────────────────────────────────────────────────────────────────────────
    # POST /vansales/api/sync/batch
    # ──────────────────────────────────────────────────────────────────────────
    @http.route(
        '/vansales/api/sync/batch',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def sync_batch(self, **kwargs):
        """
        Accept a sync batch from a mobile device.

        Expected JSON body::

            {
                "device_id": "android-uuid-xxxxx",
                "van_code": "VAN01",          // or "van_id": 5
                "orders": [
                    {
                        "external_uid": "uuid-...",
                        "partner_id": 42,
                        "sale_mode": "retail",
                        "date_order": "2024-01-15T08:30:00",
                        "order_lines": [
                            {"product_id": 10, "product_uom_qty": 3, "price_unit": 15.5}
                        ]
                    }
                ],
                "receipts": [
                    {
                        "external_uid": "uuid-...",
                        "partner_id": 42,
                        "payment_method": "cash",
                        "amount_total": 46.5,
                        "date": "2024-01-15T09:00:00",
                        "lines": [
                            {"invoice_id": 101, "amount_applied": 46.5}
                        ]
                    }
                ]
            }

        Returns::

            {
                "status": "ok",
                "batch_id": 7,
                "orders": {"uuid-...": {"id": 55, "name": "S00055"}},
                "receipts": {"uuid-...": {"id": 12, "name": "VSR00012"}}
            }
        """
        env = request.env
        data = request.get_json_data() if hasattr(request, 'get_json_data') else (request.jsonrequest or {})

        device_id = data.get('device_id', '')
        van_code = data.get('van_code')
        van_id_val = data.get('van_id')

        # Resolve van
        van = False
        if van_id_val:
            van = env['vansales.van'].browse(int(van_id_val)).exists()
        elif van_code:
            van = env['vansales.van'].search([('code', '=', van_code)], limit=1)

        # Compute payload hash for deduplication
        raw = json.dumps(data, sort_keys=True, default=str)
        payload_hash = hashlib.sha256(raw.encode()).hexdigest()

        # Create sync batch log
        batch = env['vansales.sync.batch'].create({
            'device_id': device_id or 'unknown',
            'van_id': van.id if van else False,
            'payload_hash': payload_hash,
            'raw_payload': raw[:65535],  # truncate for safety
            'state': 'processing',
        })

        order_results = {}
        receipt_results = {}
        errors = []

        # ── Process orders ────────────────────────────────────────────────────
        for order_data in data.get('orders', []):
            ext_uid = order_data.get('external_uid')
            if not ext_uid:
                errors.append('Order missing external_uid – skipped.')
                continue

            # Idempotency: check if already created
            existing = env['sale.order'].search([('external_uid', '=', ext_uid)], limit=1)
            if existing:
                order_results[ext_uid] = {'id': existing.id, 'name': existing.name, 'skipped': True}
                continue

            try:
                partner_id = order_data.get('partner_id')
                sale_mode = order_data.get('sale_mode', 'retail')
                order_vals = {
                    'partner_id': partner_id,
                    'is_van_sale': True,
                    'van_id': van.id if van else False,
                    'sale_mode': sale_mode,
                    'external_uid': ext_uid,
                    'source_device_id': device_id,
                    'warehouse_id': van.warehouse_id.id if van else False,
                    'pricelist_id': (
                        van.pricelist_wholesale_id.id
                        if sale_mode == 'wholesale' and van
                        else (van.pricelist_retail_id.id if van else False)
                    ),
                }
                if order_data.get('date_order'):
                    order_vals['date_order'] = order_data['date_order']

                order_lines = []
                for line in order_data.get('order_lines', []):
                    order_lines.append((0, 0, {
                        'product_id': line.get('product_id'),
                        'product_uom_qty': line.get('product_uom_qty', 1),
                        'price_unit': line.get('price_unit', 0),
                    }))
                if order_lines:
                    order_vals['order_line'] = order_lines

                order = env['sale.order'].create(order_vals)
                order_results[ext_uid] = {'id': order.id, 'name': order.name}
            except Exception as exc:
                _logger.exception('Error creating order ext_uid=%s', ext_uid)
                errors.append('Order %s: %s' % (ext_uid, str(exc)))

        # ── Process receipts ──────────────────────────────────────────────────
        for receipt_data in data.get('receipts', []):
            ext_uid = receipt_data.get('external_uid')
            if not ext_uid:
                errors.append('Receipt missing external_uid – skipped.')
                continue

            existing = env['vansales.receipt'].search([('external_uid', '=', ext_uid)], limit=1)
            if existing:
                receipt_results[ext_uid] = {'id': existing.id, 'name': existing.name, 'skipped': True}
                continue

            try:
                receipt_vals = {
                    'van_id': van.id if van else False,
                    'partner_id': receipt_data.get('partner_id'),
                    'payment_method': receipt_data.get('payment_method', 'cash'),
                    'external_uid': ext_uid,
                    'device_id': device_id,
                    'state': 'pending_sync',
                }
                if receipt_data.get('date'):
                    receipt_vals['date'] = receipt_data['date']

                receipt_lines = []
                for rl in receipt_data.get('lines', []):
                    receipt_lines.append((0, 0, {
                        'invoice_id': rl.get('invoice_id'),
                        'amount_applied': rl.get('amount_applied', 0),
                    }))
                if receipt_lines:
                    receipt_vals['line_ids'] = receipt_lines

                receipt = env['vansales.receipt'].create(receipt_vals)
                receipt_results[ext_uid] = {'id': receipt.id, 'name': receipt.name}
            except Exception as exc:
                _logger.exception('Error creating receipt ext_uid=%s', ext_uid)
                errors.append('Receipt %s: %s' % (ext_uid, str(exc)))

        # ── Update batch log ──────────────────────────────────────────────────
        final_state = 'failed' if (errors and not order_results and not receipt_results) else 'processed'
        batch.write({
            'state': final_state,
            'message': '\n'.join(errors) if errors else 'OK',
            'created_order_ids_json': json.dumps(list(order_results.values())),
            'created_receipt_ids_json': json.dumps(list(receipt_results.values())),
        })

        return {
            'status': 'ok' if not errors else 'partial',
            'batch_id': batch.id,
            'orders': order_results,
            'receipts': receipt_results,
            'errors': errors,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # GET /vansales/api/config
    # ──────────────────────────────────────────────────────────────────────────
    @http.route(
        '/vansales/api/config',
        type='json',
        auth='user',
        methods=['GET', 'POST'],
        csrf=False,
    )
    def get_config(self, **kwargs):
        """
        Return van configuration for the currently authenticated user.

        The mobile app calls this on startup / after login to get the
        current user's van assignment and associated configuration IDs.

        Returns::

            {
                "user_id": 3,
                "user_name": "John Driver",
                "van": {
                    "id": 1,
                    "name": "Van 01",
                    "code": "VAN01",
                    "warehouse_id": 5,
                    "pricelist_retail_id": 2,
                    "pricelist_wholesale_id": 3,
                    "cash_journal_id": 7,
                    "bank_journal_id": 8,
                    "visa_journal_id": 9,
                    "mastercard_journal_id": 9,
                    "allow_negative_stock": true
                }
            }
        """
        env = request.env
        user = env.user
        van = env['vansales.van'].search([
            ('user_id', '=', user.id),
            ('active', '=', True),
        ], limit=1)

        van_data = False
        if van:
            van_data = {
                'id': van.id,
                'name': van.name,
                'code': van.code,
                'warehouse_id': van.warehouse_id.id,
                'warehouse_name': van.warehouse_id.name,
                'main_warehouse_id': van.main_warehouse_id.id if van.main_warehouse_id else False,
                'pricelist_retail_id': van.pricelist_retail_id.id if van.pricelist_retail_id else False,
                'pricelist_retail_name': van.pricelist_retail_id.name if van.pricelist_retail_id else False,
                'pricelist_wholesale_id': van.pricelist_wholesale_id.id if van.pricelist_wholesale_id else False,
                'pricelist_wholesale_name': van.pricelist_wholesale_id.name if van.pricelist_wholesale_id else False,
                'cash_journal_id': van.cash_journal_id.id if van.cash_journal_id else False,
                'bank_journal_id': van.bank_journal_id.id if van.bank_journal_id else False,
                'visa_journal_id': van.visa_journal_id.id if van.visa_journal_id else False,
                'mastercard_journal_id': van.mastercard_journal_id.id if van.mastercard_journal_id else False,
                'allow_negative_stock': van.allow_negative_stock,
            }

        return {
            'user_id': user.id,
            'user_name': user.name,
            'van': van_data,
        }
