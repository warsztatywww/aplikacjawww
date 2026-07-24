Aplikacja WWW
=============

[![Python test](https://github.com/warsztatywww/aplikacjawww/workflows/Python%20test/badge.svg)](https://github.com/warsztatywww/aplikacjawww/actions?query=branch%3Amaster+workflow%3A%22Python+test%22)
[![codecov](https://codecov.io/gh/warsztatywww/aplikacjawww/branch/master/graph/badge.svg?token=xqOEznDxRX)](https://codecov.io/gh/warsztatywww/aplikacjawww)

Django-based application to manage registration of people for [scientific summer school](https://warsztatywww.pl/).

### Setup:
- install `python3`, `pip3` and `npm`
- `python3 -m venv venv` - create a virtual python environment for the app
- `source venv/bin/activate` - activate venv
- `npm install` - download js/css dependencies
- `npm run build` - run webpack to build the static js/css files (you can use `build-dev` instead during development - it's faster and doesn't minify)
- `./manage.py migrate` - apply DB migrations
- `./manage.py createsuperuser` - script to create a superuser that can modify DB contents via admin panel
- `./manage.py populate_with_test_data` - script to populate the database with data for development

### Run:
- activate virtualenv (if not yet activated)
- `pip install -r requirements.txt`
- `./manage.py runserver`

### Cost invoices and reimbursements

Users submit invoices from **Moje koszty** (`/costs/`). Before adding an
invoice they must save an account number for the current camp at
`/costs/settlement-details/`. The account number is per user and camp.

An invoice needs a document number, issue date, positive amount, document
type, description, and one or more cost-item allocations. The allocations
must add up exactly to the invoice amount. Each allocation has a category and
can optionally be assigned to a workshop in the same camp. Accepted
attachments are PDF, JPG, and JPEG files up to 50 MiB; their MIME type and
file signature are checked.

The application assigns a camp-scoped number in the form
`WWW_<year>_FP_<number>`. Invoice statuses follow this sequence:

- `RECEIVED` can be approved or rejected.
- `APPROVED` can be processed or rejected.
- `REJECTED` becomes `RECEIVED` when its owner edits and resubmits it.
- `PROCESSED` is final and cannot be edited or reverted.

Owners can view and download only their invoices. Files are served through the
authenticated attachment route, never as public upload URLs. Replacing an
attachment removes the superseded file after the database change commits.

Cost administrators use `/costs/admin/` to filter invoices and may export
CSV. Assign the following Django permissions directly or through project
groups:

- `wwwapp.view_all_costs` — open the administration page and other users'
  attachments.
- `wwwapp.approve_costs` — approve or reject invoices.
- `wwwapp.process_costs` — mark approved invoices as processed.
- `wwwapp.export_costs` — export invoice cost items as CSV.
- `wwwapp.register_reimbursements` — register reimbursements at
  `/costs/reimbursements/`.
- `wwwapp.view_cost_statistics` — view `/costs/statistics/`.

The CSV export has one row per cost item, not one row per invoice. Its columns
are `internal_number`, `document_number`, `issue_date`, `user`,
`invoice_type`, `status`, `invoice_amount`, `category`, `context_type`,
`context_id`, `context_name`, `item_amount`, and `description`. With no
selection it exports approved invoices; selecting invoices exports only the
selected records.

Reimbursements record the selected recipient's current account number as an
immutable snapshot. A recipient's balance is approved and processed invoice
value minus registered reimbursements; the screen warns when a new payment is
larger than the pre-payment balance. Cost statistics aggregate cost-item
amounts, so split invoices are counted once through their individual items.
By default they include approved and processed invoices and can be filtered by
camp, status, category, and workshop-versus-camp context.

#### INTERNETy

For the INTERNETy resources authentication a /resource\_auth endpoint is provided. An example nginx config is in `nginx.conf.example` file.

### Online version:
App currently available at https://warsztatywww.pl/
