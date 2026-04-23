# Nest Van Sales – Warehouse (`nest_vansales`)

**Odoo 19 Community Edition – MVP Skeleton**

Van Sales module for field sales operations using a separate Odoo warehouse per van.

---

## Overview

| Feature | Status |
|---|---|
| Van master (separate warehouse per van) | ✅ MVP |
| Two pricelists (retail / wholesale) | ✅ MVP |
| Invoice per order | ✅ MVP |
| Dedicated Van Receipt object | ✅ MVP (stub – payment posting TODO) |
| Returns restock van first | ✅ MVP |
| Load / Unload stock transfers | ✅ MVP |
| Audit / Qty balance check | ✅ MVP |
| Offline PWA sync API | ✅ MVP (idempotent by external_uid) |
| Payment reconciliation | 🔲 Phase 2 |
| Daily closing / session | 🔲 Phase 2 |
| Mobile PWA front-end | 🔲 Phase 3 |

---

## Installation

1. Copy the `nest_vansales` directory into your Odoo addons path.
2. Update the addons list (Settings → Technical → Update Apps List).
3. Install **Nest Van Sales – Warehouse** from the Apps menu.

### Dependencies
- `sale_management`
- `stock`
- `account`
- `sale_stock`

---

## Initial Configuration

### 1. Main Warehouse (MAINW)

The module expects a warehouse with the short code **`MAINW`**.

> Inventory → Configuration → Warehouses → New
> - Name: `Main Warehouse`
> - Short Name: `MAINW`

If a warehouse named MAINW is not found, set `main_warehouse_id` manually on each Van record.

### 2. Van Warehouses

For each van (up to 10), create a dedicated warehouse:

> Inventory → Configuration → Warehouses → New
> - Name: `Van 01`
> - Short Name: `VAN01`

Repeat for VAN02 … VAN10.

### 3. Pricelists

Enable pricelists: **Sales → Configuration → Settings → Pricing → Pricelists**

Create two pricelists:
- **Retail Pricelist** – standard / customer prices
- **Wholesale Pricelist** – discounted / trade prices

### 4. Van Records

> Van Sales → Vans → New

For each van set:
| Field | Value |
|---|---|
| Van Code | `VAN01` (unique per company) |
| Van Name | `Van 01` |
| Driver / Salesperson | assigned user |
| Van Warehouse | the dedicated van warehouse |
| Main Warehouse (Supply) | `MAINW` |
| Retail Pricelist | your retail pricelist |
| Wholesale Pricelist | your wholesale pricelist |
| Cash Journal | cash journal for this van |
| Bank Journal | bank journal |
| Visa Journal | card terminal journal |
| Mastercard Journal | card terminal journal |
| Allow Negative Stock | `True` (default – recommended for field sales) |

### 5. User Groups

| Group | Access |
|---|---|
| **Van Sales User** | Own van records, orders, receipts, transfers |
| **Van Sales Manager** | All records, audit adjustments, sync logs |

---

## Operational Workflow

### Load Van
1. Van Sales → Transfers → Load Van
2. Select van and products to load
3. Click **Create Transfer** – an internal picking is created from MAINW → Van WH
4. Validate the transfer in Inventory

### Van Sale
1. Van Sales → Van Orders → New
2. Set **Van** and **Sale Mode** (retail / wholesale)
3. Pricelist and warehouse are set automatically
4. Confirm order → delivery from van warehouse is created
5. Validate delivery

### Van Receipt (Payment)
1. Van Sales → Van Receipts → New
2. Set van, customer, payment method
3. Add invoice allocation lines
4. Click **Post** (TODO: actual payment/reconciliation in Phase 2)

### Customer Return
1. Van Sales → Returns
2. Select van, customer, products
3. Click **Create Return** – stock goes back to van warehouse first

### Unload Van (End of Day)
1. Van Sales → Transfers → Unload Van
2. Select van and products to return to MAINW

### Audit
1. Van Sales → Audit → (or wizard from van form)
2. Click **Generate Lines** to snapshot current van stock
3. Enter **Counted Qty** for each product
4. **Confirm** to lock snapshot
5. (Manager only) **Apply Adjustments** if variances need correction

---

## Sync API (Mobile / PWA)

### POST `/vansales/api/sync/batch`

Submit a batch of orders and receipts from a mobile device.
Idempotent by `external_uid`.

**Request:**
```json
{
  "device_id": "android-uuid-xxxx",
  "van_code": "VAN01",
  "orders": [
    {
      "external_uid": "uuid-...",
      "partner_id": 42,
      "sale_mode": "retail",
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
      "lines": [{"invoice_id": 101, "amount_applied": 46.5}]
    }
  ]
}
```

**Response:**
```json
{
  "status": "ok",
  "batch_id": 7,
  "orders": {"uuid-...": {"id": 55, "name": "S00055"}},
  "receipts": {"uuid-...": {"id": 12, "name": "VSR00012"}}
}
```

### GET/POST `/vansales/api/config`

Returns van configuration for the authenticated user.

```json
{
  "user_id": 3,
  "user_name": "John Driver",
  "van": {
    "id": 1,
    "code": "VAN01",
    "warehouse_id": 5,
    "pricelist_retail_id": 2,
    "pricelist_wholesale_id": 3,
    "cash_journal_id": 7,
    "allow_negative_stock": true
  }
}
```

---

## Known TODOs (Phase 2)

- `vansales/models/receipt.py` → `action_post`: create `account.payment` and reconcile against invoices.
- `vansales/models/audit.py` → `action_apply_adjustments`: create inventory adjustment moves via `stock.quant`.
- `vansales/wizard/van_load_wizard.py` / `van_unload_wizard.py`: optional auto-validation of internal pickings.
- `vansales/wizard/van_return_wizard.py`: optional credit note creation on customer return.
- `vansales/controllers/mobile_sync.py`: token-based auth for PWA without browser session.
- Daily van session / closing report.
- Barcode scanning support.
- Mobile PWA front-end.

---

## Changelog

### 19.0.1.0.0 (2024)
- Initial MVP skeleton release.
