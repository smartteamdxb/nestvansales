# -*- coding: utf-8 -*-
{
    'name': 'Nest Van Sales – Warehouse',
    'version': '19.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Van Sales module using separate warehouse per van – MVP skeleton',
    'description': """
Nest Van Sales – Warehouse
==========================
Van Sales module for Odoo 19 Community Edition.

Key features (MVP skeleton):
- Each van is an independent Odoo warehouse (separate stock).
- Invoice per order (always).
- Two pricelists: retail / wholesale.
- Dedicated Van Receipt object that supports allocations across multiple invoices.
- Returns restock the van warehouse first.
- Internal transfers to load/unload stock between MAINWH and van warehouses.
- Offline-friendly PWA sync API endpoints (idempotent by external_uid).
- Audit / qty balance check snapshots per van.

See README.md for configuration instructions.
    """,
    'author': 'SmartTeam Dubai',
    'website': 'https://smartteamdxb.com',
    'license': 'LGPL-3',
    'depends': [
        'sale_management',
        'stock',
        'account',
        'sale_stock',
    ],
    'data': [
        # Security – load first
        'security/vansales_groups.xml',
        'security/ir.model.access.csv',
        'security/vansales_record_rules.xml',

        # Data
        'data/sequence.xml',
        'data/payment_methods.xml',
        'data/defaults.xml',

        # Views
        'views/van_views.xml',
        'views/sale_order_views.xml',
        'views/van_receipt_views.xml',
        'views/audit_views.xml',
        'views/sync_log_views.xml',
        'views/wizard_views.xml',
        'views/mobile_dashboard.xml',
        'views/vansales_menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
