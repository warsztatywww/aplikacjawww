import csv
import os
from decimal import Decimal
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.urls import reverse

from wwwapp.forms import (
    CostItemFormSet,
    InvoiceForm,
    ReimbursementForm,
    ReimbursementUserForm,
    SettlementDetailsForm,
)
from wwwapp.models import (
    Camp,
    CostItem,
    Invoice,
    Reimbursement,
    SettlementDetails,
    UploadStorage,
    Workshop,
    WorkshopType,
)


CSV_HEADER = [
    'internal_number', 'document_number', 'issue_date', 'user', 'invoice_type', 'status',
    'invoice_amount', 'category', 'camp', 'workshop', 'item_amount',
    'description',
]


class InvoiceFormTests(TestCase):
    def setUp(self):
        Camp.objects.all().update(year=2026)
        self.camp = Camp.objects.get()
        self.other_camp = Camp.objects.create(year=2027)
        self.user = User.objects.create_user(username='user')
        self.invoice = Invoice.objects.create(
            user=self.user,
            camp=self.camp,
            attachment='invoices/existing.pdf',
            document_number='FV/1/2026',
            issue_date='2026-07-24',
            amount=Decimal('10.00'),
            invoice_type=Invoice.Type.KSEF,
            description='Workshop materials',
            internal_number='WWW_2026_FP_0001',
        )
        workshop_type = WorkshopType.objects.create(year=self.camp, name='Type')
        self.workshop = Workshop.objects.create(
            year=self.camp,
            type=workshop_type,
            name='workshop',
            title='Workshop',
        )
        other_type = WorkshopType.objects.create(year=self.other_camp, name='Other type')
        self.other_workshop = Workshop.objects.create(
            year=self.other_camp,
            type=other_type,
            name='other-workshop',
            title='Other workshop',
        )
        self.data = {
            'document_number': 'FV/2/2026',
            'issue_date': '2026-07-24',
            'amount': '10.00',
            'invoice_type': Invoice.Type.KSEF,
            'description': 'Workshop materials',
        }
        self.split_post = {
            'cost_items-TOTAL_FORMS': '2',
            'cost_items-INITIAL_FORMS': '0',
            'cost_items-MIN_NUM_FORMS': '0',
            'cost_items-MAX_NUM_FORMS': '1000',
            'cost_items-0-workshop': str(self.workshop.pk),
            'cost_items-0-amount': '4.00',
            'cost_items-0-category': CostItem.Category.WORKSHOPS,
            'cost_items-1-workshop': '',
            'cost_items-1-amount': '5.99',
            'cost_items-1-category': CostItem.Category.REGULAR_PURCHASES,
        }

    def test_attachment_accepts_a_pdf_based_on_its_filename(self):
        form = InvoiceForm(
            data=self.data,
            files={
                'attachment': SimpleUploadedFile(
                    'invoice.pdf', b'not a document', content_type='application/pdf'
                )
            },
            user=self.user,
            camp=self.camp,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_attachment_accepts_pdf_and_jpeg_signatures(self):
        for name, content, content_type in (
            ('invoice.pdf', b'%PDF-1.7', 'application/pdf'),
            ('invoice.jpeg', b'\xff\xd8\xff\xe0', 'image/jpeg'),
        ):
            with self.subTest(name=name):
                form = InvoiceForm(
                    data=self.data,
                    files={
                        'attachment': SimpleUploadedFile(name, content, content_type=content_type)
                    },
                    user=self.user,
                    camp=self.camp,
                )

                self.assertTrue(form.is_valid(), form.errors)

    def test_attachment_rejects_an_unsupported_filename_or_oversize_upload(self):
        cases = (
            ('invoice.txt', b'%PDF-1.7', 'application/pdf'),
            ('invoice.pdf', b'%PDF-' + b'x' * (50 * 1024 * 1024), 'application/pdf'),
        )
        for name, content, content_type in cases:
            with self.subTest(name=name, content_type=content_type):
                form = InvoiceForm(
                    data=self.data,
                    files={
                        'attachment': SimpleUploadedFile(name, content, content_type=content_type)
                    },
                    user=self.user,
                    camp=self.camp,
                )

                self.assertFalse(form.is_valid())
                self.assertIn('attachment', form.errors)

    def test_cost_item_formset_rejects_unequal_total(self):
        formset = CostItemFormSet(self.split_post, instance=self.invoice)

        self.assertFalse(formset.is_valid())

    def test_cost_item_formset_requires_a_non_deleted_row(self):
        data = {
            **self.split_post,
            'cost_items-0-DELETE': 'on',
            'cost_items-1-DELETE': 'on',
        }
        formset = CostItemFormSet(data, instance=self.invoice)

        self.assertFalse(formset.is_valid())
        self.assertTrue(formset.non_form_errors())

    def test_cost_item_formset_rejects_workshop_from_another_camp(self):
        data = {
            **self.split_post,
            'cost_items-0-workshop': str(self.other_workshop.pk),
            'cost_items-0-amount': '10.00',
            'cost_items-1-DELETE': 'on',
        }
        formset = CostItemFormSet(data, instance=self.invoice)

        self.assertFalse(formset.is_valid())
        self.assertIn('workshop', formset.forms[0].errors)


class SettlementAndReimbursementFormTests(TestCase):
    def setUp(self):
        Camp.objects.all().update(year=2026)
        self.camp = Camp.objects.get()
        self.user = User.objects.create_user(username='user')
        self.registered_by = User.objects.create_user(username='admin')

    def test_settlement_details_form_is_scoped_to_user_and_camp(self):
        form = SettlementDetailsForm(
            data={'account_number': 'PL61109010140000071219812874'},
            user=self.user,
            camp=self.camp,
        )

        self.assertTrue(form.is_valid(), form.errors)
        details = form.save()
        self.assertEqual(details.user, self.user)
        self.assertEqual(details.camp, self.camp)

    def test_reimbursement_form_sets_the_registration_context(self):
        form = ReimbursementForm(
            data={
                'amount': '10.00',
                'type': Reimbursement.Type.ASSOCIATION,
                'comment': 'Transfer',
                'execution_date': '2026-07-24',
            },
            user=self.user,
            camp=self.camp,
            registered_by=self.registered_by,
        )

        self.assertTrue(form.is_valid(), form.errors)
        reimbursement = form.save()
        self.assertEqual(reimbursement.user, self.user)
        self.assertEqual(reimbursement.camp, self.camp)
        self.assertEqual(reimbursement.registered_by, self.registered_by)

    def test_reimbursement_form_uses_polish_labels(self):
        form = ReimbursementForm(
            user=self.user,
            camp=self.camp,
            registered_by=self.registered_by,
        )

        self.assertEqual(
            {name: field.label for name, field in form.fields.items()},
            {
                'amount': 'Kwota',
                'type': 'Typ zwrotu',
                'comment': 'Komentarz',
                'execution_date': 'Data wykonania',
            },
        )

    def test_reimbursement_user_form_uses_full_names(self):
        self.user.first_name = 'Jan'
        self.user.last_name = 'Kowalski'
        self.user.save(update_fields=['first_name', 'last_name'])

        form = ReimbursementUserForm(users=User.objects.filter(pk=self.user.pk))

        self.assertEqual(form.fields['user'].label_from_instance(self.user), 'Jan Kowalski')


class OwnCostsViewsTests(TestCase):
    def setUp(self):
        Camp.objects.all().update(year=2026)
        self.camp = Camp.objects.get()
        self.user = User.objects.create_user(username='user')
        self.other_user = User.objects.create_user(username='other-user')
        self.invoice = Invoice.objects.create(
            user=self.user,
            camp=self.camp,
            attachment='invoices/fv-1.pdf',
            document_number='FV/1/2026',
            issue_date='2026-07-24',
            amount=Decimal('10.00'),
            invoice_type=Invoice.Type.KSEF,
            description='Workshop materials',
            internal_number='WWW_2026_FP_0001',
        )

    def invoice_post_data(self, **overrides):
        data = {
            'document_number': 'FV/2/2026',
            'issue_date': '2026-07-24',
            'amount': '10.00',
            'invoice_type': Invoice.Type.KSEF,
            'description': 'Workshop materials',
            'cost_items-TOTAL_FORMS': '1',
            'cost_items-INITIAL_FORMS': '0',
            'cost_items-MIN_NUM_FORMS': '0',
            'cost_items-MAX_NUM_FORMS': '1000',
            'cost_items-0-workshop': '',
            'cost_items-0-amount': '10.00',
            'cost_items-0-category': CostItem.Category.REGULAR_PURCHASES,
        }
        return {**data, **overrides}

    def test_cost_list_shows_own_confirmed_and_pending_totals(self):
        self.invoice.status = Invoice.Status.APPROVED
        self.invoice.save()
        Invoice.objects.create(
            user=self.user,
            camp=self.camp,
            attachment='invoices/fv-2.pdf',
            document_number='FV/2/2026',
            issue_date='2026-07-24',
            amount=Decimal('4.00'),
            invoice_type=Invoice.Type.KSEF,
            description='Pending invoice',
            internal_number='WWW_2026_FP_0002',
        )
        Invoice.objects.create(
            user=self.other_user,
            camp=self.camp,
            attachment='invoices/fv-3.pdf',
            document_number='FV/3/2026',
            issue_date='2026-07-24',
            amount=Decimal('99.00'),
            invoice_type=Invoice.Type.KSEF,
            description='Other user invoice',
            internal_number='WWW_2026_FP_0003',
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('costs_mine', args=[self.camp.pk]))

        self.assertEqual(response.status_code, 200)
        pending_invoice = Invoice.objects.get(internal_number='WWW_2026_FP_0002')
        self.assertEqual(list(response.context['invoices']), [pending_invoice, self.invoice])
        self.assertEqual(response.context['approved_total'], Decimal('10.00'))
        self.assertEqual(response.context['reimbursed_total'], Decimal('0.00'))
        self.assertEqual(response.context['remaining_total'], Decimal('10.00'))
        self.assertEqual(response.context['pending_total'], Decimal('4.00'))

    def test_invoice_add_requires_settlement_details(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('costs_invoice_add', args=[self.camp.pk]))

        self.assertRedirects(
            response,
            f"{reverse('costs_mine', args=[self.camp.pk])}?add_invoice=1",
        )

    def test_mine_page_saves_account_and_returns_to_invoice_form(self):
        self.client.force_login(self.user)

        response = self.client.post(
            f"{reverse('costs_mine', args=[self.camp.pk])}?add_invoice=1",
            {'account_number': 'PL61109010140000071219812874'},
        )

        self.assertRedirects(response, reverse('costs_invoice_add', args=[self.camp.pk]))
        self.assertEqual(
            SettlementDetails.objects.get(user=self.user, camp=self.camp).account_number,
            'PL61109010140000071219812874',
        )

    def test_mine_page_displays_saved_account_details(self):
        SettlementDetails.objects.create(
            user=self.user,
            camp=self.camp,
            account_number='PL61109010140000071219812874',
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('costs_mine', args=[self.camp.pk]))

        self.assertContains(response, 'Dane rachunku bankowego')
        self.assertContains(response, 'PL61109010140000071219812874')

    def test_mydata_navigation_shows_own_costs_after_first_invoice(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('mydata_forms'))

        page = response.content.decode()
        self.assertIn(reverse('costs_mine', args=[self.camp.pk]), page)
        self.assertLess(page.index('Formularze'), page.index(reverse('costs_mine', args=[self.camp.pk])))

    def test_cost_forms_render_polish_labels_and_submit_control(self):
        SettlementDetails.objects.create(
            user=self.user,
            camp=self.camp,
            account_number='PL61109010140000071219812874',
        )
        self.client.force_login(self.user)

        invoice_response = self.client.get(reverse('costs_invoice_add', args=[self.camp.pk]))
        settlement_response = self.client.get(reverse('costs_mine', args=[self.camp.pk]))

        for label in (
            'Załącznik',
            'Numer dokumentu',
            'Data wystawienia',
            'Kwota',
            'Typ dokumentu',
            'Opis',
            'Warsztat',
            'Kategoria',
        ):
            self.assertContains(invoice_response, label)
        self.assertContains(settlement_response, 'Numer rachunku bankowego')
        self.assertContains(settlement_response, 'Zapisz')

    def test_invoice_add_renders_dynamic_cost_item_formset(self):
        SettlementDetails.objects.create(
            user=self.user,
            camp=self.camp,
            account_number='PL61109010140000071219812874',
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('costs_invoice_add', args=[self.camp.pk]))

        self.assertContains(response, 'id="cost-item-forms"')
        self.assertContains(response, 'id="cost-item-empty-form"')
        self.assertContains(response, 'name="cost_items-__prefix__-amount"')
        self.assertContains(response, 'id="add-cost-item"')
        self.assertContains(response, 'data-sync-invoice-amount')

    def test_invoice_add_displays_allocation_errors(self):
        SettlementDetails.objects.create(
            user=self.user,
            camp=self.camp,
            account_number='PL61109010140000071219812874',
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('costs_invoice_add', args=[self.camp.pk]),
            {
                **self.invoice_post_data(**{'cost_items-0-amount': '9.00'}),
                'attachment': SimpleUploadedFile(
                    'invoice.pdf', b'%PDF-1.7', content_type='application/pdf',
                ),
            },
        )

        self.assertContains(response, 'Suma pozycji kosztowych musi być równa kwocie faktury.')

    def test_invoice_add_creates_invoice_with_a_cost_item(self):
        SettlementDetails.objects.create(
            user=self.user,
            camp=self.camp,
            account_number='PL61109010140000071219812874',
        )
        self.client.force_login(self.user)

        response = self.client.post(reverse('costs_invoice_add', args=[self.camp.pk]), {
            **self.invoice_post_data(),
            'attachment': SimpleUploadedFile(
                'invoice.pdf', b'%PDF-1.7', content_type='application/pdf'
            ),
        })

        self.assertRedirects(response, reverse('costs_mine', args=[self.camp.pk]))
        invoice = Invoice.objects.get(internal_number='WWW_2026_FP_0002')
        self.assertEqual(invoice.user, self.user)
        self.assertEqual(invoice.cost_items.get().amount, Decimal('10.00'))

    def test_rejected_invoice_edit_resets_it_to_received(self):
        SettlementDetails.objects.create(
            user=self.user,
            camp=self.camp,
            account_number='PL61109010140000071219812874',
        )
        self.invoice.status = Invoice.Status.REJECTED
        self.invoice.save()
        CostItem.objects.create(
            invoice=self.invoice,
            amount=Decimal('10.00'),
            category=CostItem.Category.REGULAR_PURCHASES,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('costs_invoice_edit', args=[self.camp.pk, self.invoice.pk]),
            self.invoice_post_data(),
        )

        self.assertRedirects(response, reverse('costs_mine', args=[self.camp.pk]))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.RECEIVED)

    def test_invoice_edit_replaces_an_attachment_with_the_same_filename(self):
        CostItem.objects.create(
            invoice=self.invoice,
            amount=Decimal('10.00'),
            category=CostItem.Category.REGULAR_PURCHASES,
        )
        self.client.force_login(self.user)
        field = Invoice._meta.get_field('attachment')
        original_storage = field.storage

        with TemporaryDirectory() as sendfile_root:
            with override_settings(SENDFILE_ROOT=sendfile_root):
                test_storage = UploadStorage()
                field.storage = test_storage
                self.invoice.attachment.save(
                    'old.pdf',
                    SimpleUploadedFile('old.pdf', b'%PDF-old', content_type='application/pdf'),
                    save=True,
                )
                old_attachment_path = self.invoice.attachment.path

                try:
                    with self.captureOnCommitCallbacks(execute=True):
                        response = self.client.post(
                            reverse('costs_invoice_edit', args=[self.camp.pk, self.invoice.pk]),
                            {
                                **self.invoice_post_data(
                                    **{
                                        'cost_items-INITIAL_FORMS': '1',
                                        'cost_items-0-id': self.invoice.cost_items.get().pk,
                                    }
                                ),
                                'attachment': SimpleUploadedFile(
                                    'old.pdf', b'%PDF-new', content_type='application/pdf',
                                ),
                            },
                        )
                finally:
                    field.storage = original_storage

                self.assertRedirects(response, reverse('costs_mine', args=[self.camp.pk]))
                self.invoice.refresh_from_db()
                self.assertNotEqual(self.invoice.attachment.name, 'invoices/old.pdf')
                self.assertFalse(os.path.exists(old_attachment_path))
                with test_storage.open(self.invoice.attachment.name, 'rb') as attachment:
                    self.assertEqual(attachment.read(), b'%PDF-new')

    def test_invoice_edit_is_not_available_to_another_user(self):
        self.client.force_login(self.other_user)

        response = self.client.get(reverse('costs_invoice_edit', args=[self.camp.pk, self.invoice.pk]))

        self.assertEqual(response.status_code, 404)

    def test_approved_and_processed_invoices_cannot_be_edited(self):
        self.client.force_login(self.user)

        for status in (Invoice.Status.APPROVED, Invoice.Status.PROCESSED):
            with self.subTest(status=status):
                self.invoice.status = status
                self.invoice.save()

                response = self.client.get(reverse('costs_invoice_edit', args=[self.camp.pk, self.invoice.pk]))

                self.assertEqual(response.status_code, 404)

    @patch('wwwapp.views.sendfile', return_value=HttpResponse())
    def test_owner_can_get_attachment(self, _sendfile_response):
        self.client.force_login(self.user)

        response = self.client.get(reverse('costs_invoice_attachment', args=[self.camp.pk, self.invoice.pk]))

        self.assertEqual(response.status_code, 200)

    @patch('wwwapp.views.sendfile', return_value=HttpResponse())
    def test_only_all_costs_permission_can_get_another_users_attachment(self, _sendfile_response):
        self.client.force_login(self.other_user)

        response = self.client.get(reverse('costs_invoice_attachment', args=[self.camp.pk, self.invoice.pk]))

        self.assertEqual(response.status_code, 404)
        self.other_user.user_permissions.add(Permission.objects.get(codename='view_all_costs'))
        response = self.client.get(reverse('costs_invoice_attachment', args=[self.camp.pk, self.invoice.pk]))
        self.assertEqual(response.status_code, 200)


class CostAdministrationViewsTests(TestCase):
    def setUp(self):
        Camp.objects.all().update(year=2026)
        self.camp = Camp.objects.get()
        self.other_camp = Camp.objects.create(year=2027)
        self.owner = User.objects.create_user(username='cost-owner')
        self.admin = User.objects.create_user(username='cost-admin')
        self.csv_user = User.objects.create_user(username='cost-csv')
        self.process_user = User.objects.create_user(username='cost-process')
        self.approve_permission = Permission.objects.get(codename='approve_costs')
        self.view_permission = Permission.objects.get(codename='view_all_costs')
        self.process_permission = Permission.objects.get(codename='process_costs')
        self.admin.user_permissions.add(self.view_permission, self.approve_permission)
        self.csv_user.user_permissions.add(self.view_permission)
        self.process_user.user_permissions.add(self.view_permission, self.process_permission)
        SettlementDetails.objects.create(
            user=self.owner,
            camp=self.camp,
            account_number='PL61109010140000071219812874',
        )
        self.received_invoice = self.create_invoice(
            document_number='FV/received', internal_number='WWW_2026_FP_0001',
        )
        self.approved_invoice = self.create_invoice(
            document_number='FV/approved', internal_number='WWW_2026_FP_0002',
            status=Invoice.Status.APPROVED,
        )
        self.split_invoice = self.create_invoice(
            document_number='FV/split', internal_number='WWW_2026_FP_0003',
            status=Invoice.Status.APPROVED,
            first_item_amount=Decimal('6.00'),
        )
        self.processed_invoice = self.create_invoice(
            document_number='FV/processed', internal_number='WWW_2027_FP_0002',
            status=Invoice.Status.PROCESSED,
            camp=self.other_camp,
        )
        CostItem.objects.create(
            invoice=self.split_invoice,
            amount=Decimal('4.00'),
            category=CostItem.Category.OUTINGS,
        )

    def create_invoice(
        self,
        *,
        document_number,
        internal_number,
        amount=Decimal('10.00'),
        camp=None,
        first_item_amount=None,
        invoice_type=Invoice.Type.KSEF,
        status=Invoice.Status.RECEIVED,
        user=None,
    ):
        invoice = Invoice.objects.create(
            user=user or self.owner,
            camp=camp or self.camp,
            attachment='invoices/cost.pdf',
            document_number=document_number,
            issue_date='2026-07-24',
            amount=amount,
            invoice_type=invoice_type,
            description='Cost administration test',
            internal_number=internal_number,
            status=status,
        )
        CostItem.objects.create(
            invoice=invoice,
            amount=first_item_amount or amount,
            category=CostItem.Category.REGULAR_PURCHASES,
        )
        return invoice

    def test_administration_requires_view_permission(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse('costs_admin', args=[self.camp.pk]))

        self.assertEqual(response.status_code, 403)

    def test_administration_filters_invoices_by_status(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('costs_admin', args=[self.camp.pk]),
            {'status': Invoice.Status.APPROVED},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['invoices']), [self.split_invoice, self.approved_invoice])

    def test_administration_filters_invoices_by_camp_user_and_type(self):
        other_owner = User.objects.create_user(username='other-cost-owner')
        other_invoice = self.create_invoice(
            camp=self.other_camp,
            document_number='FV/other',
            internal_number='WWW_2027_FP_0001',
            invoice_type=Invoice.Type.OUTSIDE_KSEF,
            user=other_owner,
        )
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('costs_admin', args=[self.other_camp.pk]),
            {
                'user': other_owner.pk,
                'invoice_type': Invoice.Type.OUTSIDE_KSEF,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['invoices']), [other_invoice])

    def test_filter_choices_include_polish_all_option(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('costs_admin', args=[self.camp.pk]))

        for field_name in ('status', 'invoice_type'):
            with self.subTest(field_name=field_name):
                choices = response.context['filter_form'].fields[field_name].choices
                self.assertEqual(choices[0], ('', 'Wszystkie'))

    def test_administration_links_to_protected_invoice_attachments(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('costs_admin', args=[self.camp.pk]))

        self.assertContains(
            response,
            reverse('costs_invoice_attachment', args=[self.camp.pk, self.received_invoice.pk]),
        )

    def test_approval_transition_requires_approval_permission(self):
        self.client.force_login(self.csv_user)

        response = self.client.post(
            reverse('costs_admin_transition', args=[self.camp.pk]),
            {'invoice_ids': [self.received_invoice.pk], 'status': Invoice.Status.APPROVED},
        )

        self.assertEqual(response.status_code, 403)
        self.received_invoice.refresh_from_db()
        self.assertEqual(self.received_invoice.status, Invoice.Status.RECEIVED)

    def test_batch_transition_rolls_back_when_any_invoice_cannot_transition(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('costs_admin_transition', args=[self.camp.pk]),
            {
                'invoice_ids': [self.received_invoice.pk, self.approved_invoice.pk],
                'status': Invoice.Status.APPROVED,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.received_invoice.refresh_from_db()
        self.assertEqual(self.received_invoice.status, Invoice.Status.RECEIVED)

    def test_processed_transition_requires_processing_permission(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('costs_admin_transition', args=[self.camp.pk]),
            {'invoice_ids': [self.approved_invoice.pk], 'status': Invoice.Status.PROCESSED},
        )

        self.assertEqual(response.status_code, 403)

    def test_processing_transition_processes_approved_invoice(self):
        self.client.force_login(self.process_user)

        response = self.client.post(
            reverse('costs_admin_transition', args=[self.camp.pk]),
            {'invoice_ids': [self.approved_invoice.pk], 'status': Invoice.Status.PROCESSED},
        )

        self.assertRedirects(response, reverse('costs_admin', args=[self.camp.pk]))
        self.approved_invoice.refresh_from_db()
        self.assertEqual(self.approved_invoice.status, Invoice.Status.PROCESSED)

    def test_processed_invoice_cannot_be_edited_or_reverted(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse('costs_invoice_edit', args=[self.other_camp.pk, self.processed_invoice.pk]),
            {
                'document_number': 'FV/processed',
                'issue_date': '2026-07-24',
                'amount': '10.00',
                'invoice_type': Invoice.Type.KSEF,
                'description': 'Cost administration test',
                'cost_items-TOTAL_FORMS': '1',
                'cost_items-INITIAL_FORMS': '1',
                'cost_items-MIN_NUM_FORMS': '0',
                'cost_items-MAX_NUM_FORMS': '1000',
                'cost_items-0-id': self.processed_invoice.cost_items.get().pk,
                'cost_items-0-workshop': '',
                'cost_items-0-amount': '10.00',
                'cost_items-0-category': CostItem.Category.REGULAR_PURCHASES,
            },
        )

        self.assertEqual(response.status_code, 403)
        self.processed_invoice.refresh_from_db()
        self.assertEqual(self.processed_invoice.status, Invoice.Status.PROCESSED)

    def test_default_csv_exports_only_approved_invoice_cost_items(self):
        self.client.force_login(self.csv_user)

        response = self.client.post(reverse('costs_csv_export', args=[self.camp.pk]))
        rows = list(csv.reader(response.content.decode().splitlines()))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(rows[0], CSV_HEADER)
        self.assertEqual(len(rows), 4)
        self.assertNotIn(self.received_invoice.internal_number, [row[0] for row in rows[1:]])

    def test_selected_csv_exports_only_selected_invoice_cost_items(self):
        self.client.force_login(self.csv_user)

        response = self.client.post(
            reverse('costs_csv_export', args=[self.camp.pk]), {'invoice_ids': [self.split_invoice.pk]},
        )
        rows = list(csv.reader(response.content.decode().splitlines()))

        self.assertEqual(rows[0], CSV_HEADER)
        self.assertEqual(len(rows), 3)
        self.assertEqual({row[0] for row in rows[1:]}, {self.split_invoice.internal_number})

    def test_csv_export_requires_view_permission(self):
        self.client.force_login(self.admin)

        response = self.client.post(reverse('costs_csv_export', args=[self.camp.pk]))

        self.assertEqual(response.status_code, 200)

    def test_csv_export_does_not_mutate_invoice_status(self):
        self.client.force_login(self.csv_user)

        response = self.client.post(reverse('costs_csv_export', args=[self.camp.pk]))

        self.assertEqual(response.status_code, 200)
        self.approved_invoice.refresh_from_db()
        self.assertEqual(self.approved_invoice.status, Invoice.Status.APPROVED)


class ReimbursementAndStatisticsViewsTests(TestCase):
    def setUp(self):
        Camp.objects.all().update(year=2026)
        self.camp = Camp.objects.get()
        self.other_camp = Camp.objects.create(year=2025)
        self.recipient = User.objects.create_user(username='reimbursement-recipient')
        self.reimbursement_user = User.objects.create_user(username='reimbursement-user')
        self.statistics_user = User.objects.create_user(username='statistics-user')
        self.reimbursement_user.user_permissions.add(
            Permission.objects.get(codename='register_reimbursements'),
        )
        self.statistics_user.user_permissions.add(
            Permission.objects.get(codename='view_all_costs'),
        )
        self.details = SettlementDetails.objects.create(
            user=self.recipient,
            camp=self.camp,
            account_number='PL61109010140000071219812874',
        )
        self.approved_invoice = self.create_invoice(
            amount=Decimal('30.00'),
            status=Invoice.Status.APPROVED,
        )
        self.over_balance_post = {
            'user_id': self.recipient.pk,
            'amount': '40.00',
            'type': Reimbursement.Type.ASSOCIATION,
            'comment': 'Transfer',
            'execution_date': '2026-07-24',
        }

    def create_invoice(
        self,
        *,
        amount,
        status,
        camp=None,
        category=CostItem.Category.WORKSHOPS,
    ):
        invoice = Invoice.objects.create(
            user=self.recipient,
            camp=camp or self.camp,
            attachment='invoices/statistics.pdf',
            document_number=f'FV/{Invoice.objects.count() + 1}/2026',
            issue_date='2026-07-24',
            amount=amount,
            invoice_type=Invoice.Type.KSEF,
            description='Statistics test',
            internal_number=f'WWW_2026_FP_{Invoice.objects.count() + 1:04d}',
            status=status,
        )
        CostItem.objects.create(invoice=invoice, amount=amount, category=category)
        return invoice

    def test_reimbursement_uses_current_account_and_warns_above_balance(self):
        self.client.force_login(self.reimbursement_user)

        response = self.client.post(
            reverse('costs_reimbursements', args=[self.camp.pk]),
            self.over_balance_post,
        )

        reimbursement = Reimbursement.objects.get()
        expected_url = (
            f"{reverse('costs_reimbursements', args=[self.camp.pk])}?user={self.recipient.pk}"
        )
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)

        follow_response = self.client.get(expected_url)

        self.assertEqual(follow_response.context['balance_before'], Decimal('-10.00'))
        self.assertIsNone(follow_response.context['balance_after'])
        self.assertContains(follow_response, 'przekracza saldo')
        self.assertContains(follow_response, self.details.account_number)
        self.assertEqual(Reimbursement.objects.count(), 1)

        self.client.get(expected_url)

        self.assertEqual(Reimbursement.objects.count(), 1)

    def test_reimbursement_page_lists_each_recipient_summary(self):
        self.client.force_login(self.reimbursement_user)

        response = self.client.get(reverse('costs_reimbursements', args=[self.camp.pk]))

        self.assertEqual(
            response.context['reimbursement_summary'],
            [
                {
                    'user': self.recipient,
                    'account_number': self.details.account_number,
                    'approved_total': Decimal('30.00'),
                    'reimbursed_total': Decimal('0.00'),
                    'remaining_total': Decimal('30.00'),
                },
            ],
        )

    def test_reimbursements_require_registration_permission(self):
        self.client.force_login(self.recipient)

        response = self.client.get(reverse('costs_reimbursements', args=[self.camp.pk]))

        self.assertEqual(response.status_code, 403)

    def test_statistics_sum_split_cost_items_once(self):
        split_invoice = self.create_invoice(
            amount=Decimal('20.00'),
            status=Invoice.Status.PROCESSED,
            category=CostItem.Category.REGULAR_PURCHASES,
        )
        split_invoice.cost_items.update(amount=Decimal('10.00'))
        CostItem.objects.create(
            invoice=split_invoice,
            amount=Decimal('10.00'),
            category=CostItem.Category.WORKSHOPS,
        )
        self.client.force_login(self.statistics_user)

        response = self.client.get(reverse('costs_statistics', args=[self.camp.pk]))

        self.assertEqual(
            response.context['category_totals'][CostItem.Category.WORKSHOPS],
            Decimal('40.00'),
        )
        self.assertEqual(
            response.context['category_percentages'][CostItem.Category.WORKSHOPS],
            Decimal('80.00'),
        )

    def test_statistics_default_to_approved_and_processed_items(self):
        self.create_invoice(
            amount=Decimal('100.00'),
            status=Invoice.Status.RECEIVED,
            category=CostItem.Category.OUTINGS,
        )
        self.client.force_login(self.statistics_user)

        response = self.client.get(reverse('costs_statistics', args=[self.camp.pk]))

        self.assertEqual(response.context['total'], Decimal('30.00'))
        self.assertEqual(
            response.context['category_totals'][CostItem.Category.OUTINGS],
            Decimal('0.00'),
        )

    def test_statistics_filter_by_status_and_context(self):
        workshop_type = WorkshopType.objects.create(year=self.camp, name='Statistics type')
        workshop = Workshop.objects.create(
            year=self.camp,
            type=workshop_type,
            name='statistics-workshop',
            title='Statistics workshop',
        )
        workshop_item = self.approved_invoice.cost_items.get()
        workshop_item.workshop = workshop
        workshop_item.save()
        other_category_invoice = self.create_invoice(
            amount=Decimal('5.00'),
            status=Invoice.Status.APPROVED,
            category=CostItem.Category.OUTINGS,
        )
        other_category_invoice.cost_items.update(workshop=workshop)
        camp_context_invoice = self.create_invoice(
            amount=Decimal('7.00'),
            status=Invoice.Status.APPROVED,
            category=CostItem.Category.WORKSHOPS,
        )
        processed_invoice = self.create_invoice(
            amount=Decimal('11.00'),
            status=Invoice.Status.PROCESSED,
            category=CostItem.Category.WORKSHOPS,
        )
        processed_invoice.cost_items.update(workshop=workshop)
        other_workshop_type = WorkshopType.objects.create(
            year=self.other_camp,
            name='Other statistics type',
        )
        other_workshop = Workshop.objects.create(
            year=self.other_camp,
            type=other_workshop_type,
            name='other-statistics-workshop',
            title='Other statistics workshop',
        )
        other_camp_invoice = self.create_invoice(
            amount=Decimal('13.00'),
            status=Invoice.Status.APPROVED,
            camp=self.other_camp,
            category=CostItem.Category.WORKSHOPS,
        )
        other_camp_invoice.cost_items.update(workshop=other_workshop)
        self.client.force_login(self.statistics_user)

        response = self.client.get(
            reverse('costs_statistics', args=[self.camp.pk]),
            {
                'status': Invoice.Status.APPROVED,
                'context': 'workshop',
            },
        )

        self.assertEqual(response.context['total'], Decimal('35.00'))

    def test_statistics_render_empty_chart_for_no_matching_items(self):
        self.client.force_login(self.statistics_user)

        response = self.client.get(
            reverse('costs_statistics', args=[self.camp.pk]),
            {
                'status': Invoice.Status.RECEIVED,
            },
        )

        self.assertFalse(response.context['has_statistics_data'])
        self.assertContains(response, 'Brak danych do wyświetlenia wykresu.')

    def test_statistics_require_permission(self):
        self.client.force_login(self.recipient)

        response = self.client.get(reverse('costs_statistics', args=[self.camp.pk]))

        self.assertEqual(response.status_code, 403)
