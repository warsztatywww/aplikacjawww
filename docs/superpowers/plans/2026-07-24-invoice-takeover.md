# Invoice Takeover Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

Goal: Build invoice submission, review, reimbursement, export, and reporting in wwwapp.

Architecture: Keep models in wwwapp.models, forms in wwwapp.forms, and views in wwwapp.views. Create wwwapp.costs for atomic domain operations shared by user and administration views. Templates remain in templates; attachments use UploadStorage and django_sendfile.

Tech Stack: Python, Django 3.2, Django ORM, django-crispy-forms, Bootstrap, Django test runner.

## Global Constraints

- Code identifiers are English; UI labels are Polish.
- A required attachment is PDF or JPG/JPEG, at most 50 MiB, stored through UploadStorage.
- PLN monetary fields use two-place Decimal values.
- Internal numbers are WWW_<Camp.year>_FP_<sequence:04d> and never reused.
- Invoices cannot be deleted; user edits are only valid in received or rejected state.
- CSV header is internal_number,document_number,issue_date,user,invoice_type,status,invoice_amount,category,context_type,context_id,context_name,item_amount,description.
- No dependency is added.

---

## File structure

- wwwapp/models.py: financial records, constraints, choices, permissions.
- wwwapp/costs.py: sequences, transitions, totals, balance queries, CSV rows.
- wwwapp/forms.py: file validation, invoice/formset, settlement, reimbursement, filters.
- wwwapp/views.py and wwwapp/urls.py: authenticated cost workflows and routes.
- wwwapp/admin.py: financial records visible with deletion disabled.
- templates/costs_*.html: own costs, invoice form, administration, reimbursements, statistics.
- wwwapp/tests/test_costs_models.py and wwwapp/tests/test_costs_views.py: behavior tests.
- wwwapp/migrations/0091_invoice_takeover.py: generated schema migration.
- README.md and DEV.md: operational and technical documentation.

### Task 1: Add financial records and schema protections

Files: modify wwwapp/models.py; create wwwapp/tests/test_costs_models.py and generated migration wwwapp/migrations/0091_invoice_takeover.py.

Interfaces: Produce Invoice, CostItem, SettlementDetails, Reimbursement, InvoiceSequence; TextChoices enums for invoice status/type, cost category, reimbursement type; and six independent permissions.

- [ ] Step 1: Write failing model tests.

~~~python
def test_cost_item_rejects_workshop_from_another_camp(self):
    item = CostItem(invoice=self.invoice, workshop=self.other_workshop,
                    amount=Decimal('1.00'), category=CostItem.Category.WORKSHOPS)
    with self.assertRaises(ValidationError):
        item.full_clean()

def test_settlement_details_are_unique_per_user_and_camp(self):
    SettlementDetails.objects.create(user=self.user, camp=self.camp,
                                     account_number='PL61109010140000071219812874')
    with self.assertRaises(IntegrityError):
        SettlementDetails.objects.create(user=self.user, camp=self.camp,
                                         account_number='PL27114020040000300201355387')
~~~

- [ ] Step 2: Run ./manage.py test wwwapp.tests.test_costs_models.CostModelTests -v 2; confirm it fails because the models are absent.

- [ ] Step 3: Implement document data, required attachment, audit fields, choices, protected foreign keys, money validators, Camp sequence, settlement uniqueness, reimbursement account snapshot, permissions, and Invoice.delete() raising ValidationError. Make CostItem.clean() reject a workshop whose Camp differs from its invoice. Generate the migration with ./manage.py makemigrations wwwapp.

- [ ] Step 4: Run ./manage.py test wwwapp.tests.test_costs_models.CostModelTests -v 2 && ./manage.py makemigrations --check --dry-run; expect passing tests and no missing migration.

- [ ] Step 5: Commit with subject feat: add invoice cost models.

### Task 2: Add atomic invoice, balance, and CSV services

Files: create wwwapp/costs.py; modify wwwapp/tests/test_costs_models.py.

Interfaces: Consume Task 1 models. Produce create_invoice, update_invoice, transition_invoices, balance_for, pending_total_for, and invoice_csv_rows.

- [ ] Step 1: Write failing domain tests.

~~~python
def test_rejected_invoice_becomes_received_when_edited(self):
    self.invoice.status = Invoice.Status.REJECTED
    self.invoice.save()
    update_invoice(invoice=self.invoice, user=self.user,
                   invoice_data=self.data, cost_items_data=[self.item])
    self.invoice.refresh_from_db()
    self.assertEqual(self.invoice.status, Invoice.Status.RECEIVED)

def test_batch_transition_rolls_back_when_one_invoice_is_ineligible(self):
    with self.assertRaises(ValidationError):
        transition_invoices(
            invoices=Invoice.objects.filter(pk__in=[self.received.pk, self.processed.pk]),
            target_status=Invoice.Status.APPROVED, changed_by=self.admin)
    self.received.refresh_from_db()
    self.assertEqual(self.received.status, Invoice.Status.RECEIVED)
~~~

- [ ] Step 2: Run ./manage.py test wwwapp.tests.test_costs_models -v 2; confirm it fails for absent wwwapp.costs.

- [ ] Step 3: Implement services.

~~~python
@transaction.atomic
def transition_invoices(*, invoices, target_status, changed_by):
    locked = list(invoices.select_for_update().prefetch_related('cost_items'))
    if any(not invoice.can_transition_to(target_status) for invoice in locked):
        raise ValidationError('Co najmniej jedna faktura nie może przejść do wybranego stanu.')
    for invoice in locked:
        invoice.set_admin_status(target_status, changed_by)
        invoice.save()
~~~

Lock the Camp sequence during allocation; validate settlement account, at least one item, and exact item total before every create/update/state change; allow only received→approved/rejected and approved→processed/rejected; calculate confirmed balance as approved+processed minus reimbursements; calculate pending as received; emit one fixed-contract row per CostItem.

- [ ] Step 4: Run ./manage.py test wwwapp.tests.test_costs_models -v 2, including a TransactionTestCase with concurrent creates for one Camp; expect unique, contiguous numbers plus passing state, balance, and split-CSV tests.

- [ ] Step 5: Commit with subject feat: add invoice domain rules.

### Task 3: Add invoice, settlement, and reimbursement forms

Files: modify wwwapp/forms.py; create wwwapp/tests/test_costs_views.py.

Interfaces: Consume Tasks 1–2. Produce InvoiceForm, CostItemFormSet, SettlementDetailsForm, ReimbursementForm, and CostFilterForm.

- [ ] Step 1: Write failing form tests.

~~~python
def test_attachment_rejects_non_pdf_or_jpeg_signature(self):
    form = InvoiceForm(data=self.data, files={
        'attachment': SimpleUploadedFile('invoice.pdf', b'not a document',
                                         content_type='application/pdf')})
    self.assertFalse(form.is_valid())
    self.assertIn('attachment', form.errors)

def test_cost_item_formset_rejects_unequal_total(self):
    formset = CostItemFormSet(self.split_post, instance=self.invoice)
    self.assertFalse(formset.is_valid())
~~~

- [ ] Step 2: Run ./manage.py test wwwapp.tests.test_costs_views.InvoiceFormTests -v 2; confirm imports fail.

- [ ] Step 3: Implement filename suffix, supplied MIME, 50 MiB, and PDF/JPEG signature validation. Require one non-deleted formset row and exact Decimal total; limit and validate workshop choices against Camp; save the settlement account into each reimbursement snapshot.

- [ ] Step 4: Run ./manage.py test wwwapp.tests.test_costs_views.InvoiceFormTests -v 2; expect valid PDF/JPEG and invalid signature, oversize, wrong-Camp, and unequal-total cases to pass.

- [ ] Step 5: Commit with subject feat: add invoice forms.

### Task 4: Implement own-cost screens and protected attachments

Files: modify wwwapp/views.py, wwwapp/urls.py, templates/base.html; create templates/costs_mine.html and templates/costs_invoice_form.html; modify wwwapp/tests/test_costs_views.py.

Interfaces: Consume Tasks 2–3. Produce routes costs_mine, costs_invoice_add, costs_invoice_edit, costs_settlement_details, and costs_invoice_attachment.

- [ ] Step 1: Write failing access tests.

~~~python
def test_only_owner_or_all_costs_permission_can_get_attachment(self):
    self.client.force_login(self.other_user)
    response = self.client.get(reverse('costs_invoice_attachment', args=[self.invoice.pk]))
    self.assertEqual(response.status_code, 404)
    self.other_user.user_permissions.add(Permission.objects.get(codename='view_all_costs'))
    response = self.client.get(reverse('costs_invoice_attachment', args=[self.invoice.pk]))
    self.assertEqual(response.status_code, 200)
~~~

- [ ] Step 2: Run ./manage.py test wwwapp.tests.test_costs_views.OwnCostsViewsTests -v 2; confirm route resolution fails.

- [ ] Step 3: Implement authenticated list/form routes with default one item, separate confirmed/pending totals, account prerequisite, received/rejected-only edits, rejected-to-received reset, and protected sendfile response. Return 404 for an unauthorized attachment request. Add user navigation.

- [ ] Step 4: Run ./manage.py test wwwapp.tests.test_costs_views.OwnCostsViewsTests -v 2; expect account, edit-state, access, and totals tests to pass.

- [ ] Step 5: Commit with subject feat: add own invoice cost workflow.

### Task 5: Implement permissioned cost administration and CSV

Files: modify wwwapp/views.py, wwwapp/urls.py, wwwapp/admin.py; create templates/costs_admin.html; modify wwwapp/tests/test_costs_views.py.

Interfaces: Consume Task 2 services. Produce routes costs_admin, costs_admin_transition, and costs_csv_export.

- [ ] Step 1: Write failing administration tests.

~~~python
def test_selected_csv_exports_only_selected_invoice_cost_items(self):
    self.client.force_login(self.csv_user)
    response = self.client.post(reverse('costs_csv_export'),
                                {'invoice_ids': [self.split_invoice.pk]})
    rows = list(csv.reader(response.content.decode().splitlines()))
    self.assertEqual(rows[0], CSV_HEADER)
    self.assertEqual(len(rows), 3)
~~~

- [ ] Step 2: Run ./manage.py test wwwapp.tests.test_costs_views.CostAdministrationViewsTests -v 2; confirm routes are absent.

- [ ] Step 3: Implement filters by Camp/status/user/type/category, checkbox selection, separate permission checks for view/approve-export/process, atomic batch transition service, approved-only default CSV, selected permission-visible CSV, and no export state mutation. Register models with deletion disabled and audit fields readonly.

- [ ] Step 4: Run ./manage.py test wwwapp.tests.test_costs_views.CostAdministrationViewsTests -v 2; expect denial, filters, rollback, default/selection export, and one-row-per-item assertions to pass.

- [ ] Step 5: Commit with subject feat: add invoice administration and export.

### Task 6: Implement reimbursement history and item-level statistics

Files: modify wwwapp/views.py and wwwapp/urls.py; create templates/costs_reimbursements.html and templates/costs_statistics.html; modify wwwapp/tests/test_costs_views.py.

Interfaces: Consume Tasks 2–3. Produce routes costs_reimbursements and costs_statistics.

- [ ] Step 1: Write failing reimbursement and aggregation tests.

~~~python
def test_reimbursement_saves_account_snapshot_and_warns_above_balance(self):
    self.client.force_login(self.reimbursement_user)
    response = self.client.post(reverse('costs_reimbursements'), self.over_balance_post)
    self.assertEqual(Reimbursement.objects.get().account_number_snapshot,
                     self.details.account_number)
    self.assertContains(response, 'przekracza saldo')

def test_statistics_sum_split_cost_items_once(self):
    response = self.client.get(reverse('costs_statistics'), {'camp': self.camp.pk})
    self.assertEqual(response.context['category_totals'][CostItem.Category.WORKSHOPS],
                     Decimal('30.00'))
~~~

- [ ] Step 2: Run ./manage.py test wwwapp.tests.test_costs_views.ReimbursementAndStatisticsViewsTests -v 2; confirm routes are absent.

- [ ] Step 3: Implement before/after balances plus non-blocking excess warning and account snapshot under register_reimbursement. Aggregate CostItem.amount, defaulting to approved/processed; filter Camp, status, category, and Camp/workshop context; expose values and percentages in an accessible table and dependency-free pie display under view_cost_statistics.

- [ ] Step 4: Run ./manage.py test wwwapp.tests.test_costs_views.ReimbursementAndStatisticsViewsTests -v 2; expect snapshot, warning, permission, default-state, filter, percentage, and no-double-count tests to pass.

- [ ] Step 5: Commit with subject feat: add reimbursements and cost statistics.

### Task 7: Document and verify the finished module

Files: modify README.md, wwwapp/tests/test_costs_models.py, and wwwapp/tests/test_costs_views.py; create DEV.md.

Interfaces: Consume all previous tasks and produce user documentation, technical architecture documentation, and verification evidence.

- [ ] Step 1: Write final regression test.

~~~python
def test_processed_invoice_cannot_be_edited_or_reverted(self):
    self.client.force_login(self.owner)
    response = self.client.post(reverse('costs_invoice_edit',
                                        args=[self.processed_invoice.pk]),
                                self.invoice_post)
    self.assertEqual(response.status_code, 403)
~~~

- [ ] Step 2: Run ./manage.py test wwwapp.tests.test_costs_models wwwapp.tests.test_costs_views -v 2; fix only any identified remaining rule gap.

- [ ] Step 3: Document account setup, accepted documents, splits, statuses, protected files, permissions/groups, CSV contract, reimbursement balances, statistic behavior, routes, and wwwapp.costs responsibilities.

- [ ] Step 4: Run ./manage.py test wwwapp.tests.test_costs_models wwwapp.tests.test_costs_views -v 2 && ./manage.py makemigrations --check --dry-run && ./type_check.sh; expect all relevant tests and checks to pass.

- [ ] Step 5: Commit with subject docs: document invoice cost workflows.

## Plan self-review

Tasks 1–7 cover schema, integrity, atomically allocated numbers, state rules, account prerequisite, attachment security, own and administrative access, CSV rows, reimbursements, balances, item-level statistics, permissions, migrations, and documentation. Interfaces are introduced before later tasks consume them, and no task leaves deferred work.

