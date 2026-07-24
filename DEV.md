# Development notes

## Project layout

- `wwwapp/` contains the Django application. The invoice domain models live in
  `wwwapp/models.py`, forms in `wwwapp/forms.py`, URL definitions in
  `wwwapp/urls.py`, and request handlers in `wwwapp/views.py`.
- `wwwapp/costs.py` contains the invoice and reimbursement domain services;
  views should call these services instead of duplicating their state and
  integrity rules.
- `wwwapp/tests/test_costs_models.py` tests domain services and model-level
  integrity. `wwwapp/tests/test_costs_views.py` tests forms, routes,
  permission checks, and rendered workflow behavior.
- `templates/costs_*.html` render the user, administration, reimbursement,
  and statistics screens. Frontend source is in `frontend/`; do not edit
  generated `static/dist/` files.

## Cost workflow architecture

`Invoice` is owned by a user and a camp. `InvoiceSequence` allocates its
camp-scoped internal number inside the creation transaction. `CostItem` holds
the invoice's allocations: each amount is positive, optional workshop links
must use the same camp, and the item total must equal the invoice amount.
`SettlementDetails` is unique for a user/camp and is required before invoice
creation or editing.

`wwwapp.costs.create_invoice()` locks the camp and sequence while allocating a
number, validates settlement details and allocations, then writes the invoice
and its items atomically. `update_invoice()` locks the invoice, checks its
owner and editable state, replaces allocations atomically, and resets a
rejected invoice to received. It schedules deletion of a replaced attachment
only after commit. `transition_invoices()` validates every requested status
change before applying any of them, so an invalid batch cannot partly change.

Invoice state transitions are `RECEIVED → APPROVED|REJECTED`,
`APPROVED → PROCESSED|REJECTED`, and `REJECTED → RECEIVED` on owner edit.
`PROCESSED` is terminal. The edit route returns 403 for a processed or
approved owner's POST, preventing an attempted resubmission from changing or
reverting it; non-editable GETs and other users' invoices remain unavailable.

`invoice_csv_rows()` exports one row per item and includes either workshop or
camp context fields. `balance_for()` subtracts reimbursement amounts from
approved and processed invoice totals, while `pending_total_for()` reports
received invoices. Reimbursements retain an account-number snapshot taken
when registered. Statistics aggregate `CostItem` rows, which makes split
invoices contribute exactly their allocated amounts.

## Cost routes and access control

| Route | Purpose | Required access |
| --- | --- | --- |
| `/costs/` | Current user's invoices and balances | Authenticated user |
| `/costs/settlement-details/` | Current camp account number | Authenticated user |
| `/costs/invoices/add/` | Add invoice and allocations | Authenticated user with account details |
| `/costs/invoices/<id>/edit/` | Edit owner's received/rejected invoice | Authenticated owner |
| `/costs/invoices/<id>/attachment/` | Download protected attachment | Owner or `view_all_costs` |
| `/costs/admin/` | Filter cost administration | `view_all_costs` |
| `/costs/admin/transition/` | Approve, reject, or process batch | `view_all_costs` plus approval/processing permission |
| `/costs/admin/export/` | CSV cost-item export | `view_all_costs` and `export_costs` |
| `/costs/reimbursements/` | Record reimbursement | `register_reimbursements` |
| `/costs/statistics/` | Item-level financial report | `view_cost_statistics` |

Use Django groups to assign the six custom invoice permissions:
`view_all_costs`, `approve_costs`, `process_costs`, `export_costs`,
`register_reimbursements`, and `view_cost_statistics`. The code deliberately
does not prescribe group names; deployments can map these permissions to
their existing finance roles.

## Verification

For the cost workflow, run:

```bash
./manage.py test wwwapp.tests.test_costs_models wwwapp.tests.test_costs_views -v 2
./manage.py makemigrations --check --dry-run
./type_check.sh
```

When changing frontend source, rebuild with `npm run build-dev` before testing
the Django pages.
