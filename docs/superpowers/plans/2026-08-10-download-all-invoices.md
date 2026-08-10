# Download All Invoices Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let costs administrators download every invoice document for one camp in one flat ZIP.

**Architecture:** Add a permission-protected Django view that reads invoice attachments through
Django storage and streams them into a temporary ZIP file. Return that file through Django. Use one
private filename helper so individual and ZIP downloads follow the same naming rule.

**Tech Stack:** Django 3.2, Python standard-library file and ZIP modules, Django test runner.

## Global Constraints

- Base the feature branch on `master` and work in an isolated worktree.
- Put every invoice document for the selected camp directly in one ZIP, with no directories.
- Name ZIP members like individual invoice downloads.
- Add a numbered suffix only when duplicate normal-download names would overwrite a document.
- Return the archive from Python without nginx sendfile support.
- Require only `wwwapp.view_all_costs`, the permission used to view all invoices.
- Put the download control in the custom costs administration page.

---

### Task 1: Invoice ZIP endpoint and naming

**Files:**
- Modify: `wwwapp/views.py`
- Modify: `wwwapp/urls.py`
- Test: `wwwapp/tests/test_costs_views.py`

**Interfaces:**
- Consumes: `Invoice.attachment`, `Invoice.internal_number`, and `wwwapp.view_all_costs`.
- Produces: `_invoice_attachment_filename(invoice)` and `costs_invoice_archive_view(request, year)`.

- [x] **Step 1: Write failing endpoint tests**

Add tests that request `costs_invoice_archive`, inspect the returned ZIP, and assert that it
contains all and only the selected camp's documents. Assert numbered and unnumbered member names,
file bytes, flat paths, the ZIP response headers, and a `403` response without `view_all_costs`.

- [x] **Step 2: Run the endpoint tests and verify RED**

Run:
`./.venv/bin/python manage.py test wwwapp.tests.test_costs_views.CostAdministrationViewsTests -v 2`

Expected: failure because the `costs_invoice_archive` URL does not exist.

- [x] **Step 3: Implement the minimal archive response**

Add a URL under `/<year>/costs/admin/`. Add a login- and `view_all_costs`-protected GET view that
loads every invoice for the requested camp. Stream each attachment into a temporary `ZipFile` using
`_invoice_attachment_filename(invoice)`. Return an `application/zip` `FileResponse` named
`faktury-<camp year>.zip`. Refactor the individual download view to call the same filename helper.

- [x] **Step 4: Run the endpoint tests and verify GREEN**

Run:
`./.venv/bin/python manage.py test wwwapp.tests.test_costs_views.CostAdministrationViewsTests -v 2`

Expected: all costs-administration tests pass.

### Task 2: Costs administration control and documentation

**Files:**
- Modify: `templates/costs_admin.html`
- Modify: `wwwapp/tests/test_costs_views.py`
- Modify: `README.md`
- Create: `DEV.md`

**Interfaces:**
- Consumes: the `costs_invoice_archive` named URL from Task 1.
- Produces: a visible “Pobierz wszystkie dokumenty” link in the custom costs administration page.

- [x] **Step 1: Write a failing page test**

Assert that the costs administration page contains the archive URL and Polish download label.

- [x] **Step 2: Run the page test and verify RED**

Run:

```bash
.venv/bin/python manage.py test \
  wwwapp.tests.test_costs_views.CostAdministrationViewsTests.test_administration_uses_datatables \
  -v 2
```

Expected: failure because the archive control is absent.

- [x] **Step 3: Add the control and documentation**

Add a normal link above the invoice table so it does not submit selected invoice IDs. Document the
costs administration archive in `README.md`, and document the repository structure and archive
request flow in `DEV.md`.

- [x] **Step 4: Run focused and migration verification**

Run:
`./.venv/bin/python manage.py test wwwapp.tests.test_costs_views.CostAdministrationViewsTests -v 2`

Run:
`./.venv/bin/python manage.py makemigrations --check --dry-run`

Expected: tests pass and Django reports no model changes.

- [x] **Step 5: Review the diff**

Run `git diff --check`, inspect `git diff`, and confirm that the implementation is limited to the
archive endpoint, its control, tests, and documentation.
