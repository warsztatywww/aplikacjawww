# Invoice Takeover Design

## Goal

Add a cost takeover workflow in `wwwapp`. Users submit a financial document
and its cost allocation for a Camp. Authorized administrators review, export,
process, and report the data; reimbursements remain an independent audit log.

## Scope and boundaries

The feature remains in the existing `wwwapp` Django application. Models use
English identifiers, while all user-facing labels are Polish. No new Django app
or dependency is introduced.

`wwwapp/costs.py` will contain domain operations shared by views and tests:
invoice numbering, state transitions, balance calculations, CSV generation,
and permission-aware queryset helpers. Models stay in `wwwapp/models.py`,
forms in `wwwapp/forms.py`, and views in `wwwapp/views.py` to follow the
repository's existing layout.

## Data model

### Invoice

`Invoice` stores the document-level data: submitting user, Camp, required
attachment, supplier document number, issue date, gross amount in PLN, invoice
type, description, status, and immutable internal number. It also stores
`created_at`, `updated_at`, `admin_changed_at`, and `admin_changed_by`.

Invoice types are `KSEF`, `OUTSIDE_KSEF`, `RECEIPT_WITH_NIP`, and
`NON_ACCOUNTING_RECEIPT`. Statuses are `RECEIVED`, `APPROVED`, `PROCESSED`, and
`REJECTED`. The initial status is `RECEIVED`. Deletion is prohibited.

The `attachment` accepts only PDF or JPEG (`.jpg`/`.jpeg`) documents up to
50 MiB. Validation checks extension, reported content type, and file signature
(`%PDF-` for PDF or JPEG SOI bytes). Files use the existing `UploadStorage`;
they never receive a public media URL.

`InvoiceSequence` has a one-to-one relationship with `Camp` and stores the
last allocated integer. Creation locks the sequence row in a transaction and
increments it, yielding `WWW_<Camp.year>_FP_<sequence:04d>`. The sequence row
is retained if an invoice is deleted through direct database maintenance, so
numbers are never reused.

### Cost items

`CostItem` belongs to one invoice and stores an amount, category, and either a
Camp-wide context or a concrete `Workshop`. It has no nullable Camp relation:
the parent invoice supplies the Camp-wide context. A null workshop means the
whole Camp; a non-null workshop must belong to the invoice's Camp.

Categories are a code enum with Polish labels:

- `WORKSHOPS` — Warsztaty
- `OUTINGS` — Wyjścia
- `LUNCHES` — Obiady
- `BREAKFASTS` — Śniadania
- `REGULAR_PURCHASES` — Zakupy stałe
- `SUPPORTING_AND_TECHNICAL_MATERIALS` — Materiały pomocnicze i techniczne

All money fields use `DecimalField(max_digits=12, decimal_places=2)` and PLN.
The invoice form and service validate that at least one cost item exists and
the exact item sum equals the invoice amount. This invariant is checked before
every user save and administrative state change.

### Settlement details and reimbursements

`SettlementDetails` is unique per `(user, camp)` and holds the bank account
number with created and updated timestamps. A submission requires the matching
record and a non-empty account number.

`Reimbursement` stores user, Camp, amount, type (`ASSOCIATION` or `OTHER`),
optional comment, executed date, registering user, and an immutable snapshot of
the bank account. It is not connected to individual invoices. The reimbursement
form presents the confirmed balance before and after saving and displays a
warning when the amount exceeds the pre-reimbursement balance.

## Rules and operations

User edits are allowed only for received and rejected invoices. Saving an
edited rejected invoice changes it to received. Processed invoices cannot be
edited or transitioned through normal operations. Valid administrative
transitions are received to approved or rejected, and approved to processed or
rejected. Batch actions lock selected invoices, validate every transition and
allocation before updating any row, then apply all changes atomically.

Confirmed balance is the sum of approved and processed invoices, minus every
reimbursement for the user and Camp. Received invoices appear separately as
pending costs and do not change that balance.

The system defines separate Django permissions for viewing every document,
approving/rejecting, CSV export, processing, registering reimbursements, and
viewing statistics. Groups are composed from these permissions. Without an
administrative permission, a user only sees their own invoices, settlement
details, and balances.

## Screens and data flow

The own-costs screen lists a user's invoices, confirmed balance, and secondary
pending total. Its form starts with one cost-item row equal to the invoice
amount and permits dynamic additional rows. It provides a protected attachment
preview/download.

The administrative costs screen filters by Camp, status, user, type, and
category; supports selection and batch state actions; previews attachments; and
offers CSV export. A default export includes every approved invoice. A selected
export contains only selected, permission-visible invoices and emits one row
per cost item.

The fixed CSV header is:

```text
internal_number,document_number,issue_date,user,invoice_type,status,
invoice_amount,category,context_type,context_id,context_name,item_amount,
description
```

Rows repeat the invoice values for split items. `context_type` is `camp` or
`workshop`; a Camp-wide row uses the invoice Camp's primary key and display
name. CSV export never changes invoice status.

The reimbursement screen lists historical records and adds a reimbursement
after showing before/after balances. The statistics screen aggregates
`CostItem.amount`, rather than invoice amounts, into a pie chart and table of
values and percentages. It defaults to approved plus processed invoices and
filters by Camp, status, category, and context.

## Access and attachment delivery

An attachment request resolves the invoice and authorizes it on every request:
the owner may access it, as may a user with the all-costs viewing permission.
Unauthorized users receive a 404 to avoid exposing document existence. The
response delegates to the existing internal file-serving configuration and sets
the content type from the validated stored document.

## Verification

Focused Django tests cover file validation, allocation totals, cross-Camp
workshop rejection, sequence uniqueness under concurrent allocation, state
rules and atomic batch actions, permissions, protected documents, balances,
CSV rows and filters, reimbursements, and statistics without double-counting
split invoices. Migration checks confirm the final schema.

README.md documents setup and user-facing cost workflows. DEV.md documents the
new models, service responsibilities, routes, protected attachment behavior,
and CSV contract.
