from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse

from wwwapp.forms import (
    CostItemFormSet,
    InvoiceForm,
    ReimbursementForm,
    SettlementDetailsForm,
)
from wwwapp.models import (
    Camp,
    CostItem,
    Invoice,
    Reimbursement,
    SettlementDetails,
    Workshop,
    WorkshopType,
)


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

    def test_attachment_rejects_non_pdf_or_jpeg_signature(self):
        form = InvoiceForm(
            data=self.data,
            files={
                'attachment': SimpleUploadedFile(
                    'invoice.pdf', b'not a document', content_type='application/pdf'
                )
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn('attachment', form.errors)

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
                )

                self.assertTrue(form.is_valid(), form.errors)

    def test_attachment_rejects_wrong_suffix_mime_and_oversize(self):
        cases = (
            ('invoice.txt', b'%PDF-1.7', 'application/pdf'),
            ('invoice.pdf', b'%PDF-1.7', 'image/jpeg'),
            ('invoice.pdf', b'%PDF-' + b'x' * (50 * 1024 * 1024), 'application/pdf'),
        )
        for name, content, content_type in cases:
            with self.subTest(name=name, content_type=content_type):
                form = InvoiceForm(
                    data=self.data,
                    files={
                        'attachment': SimpleUploadedFile(name, content, content_type=content_type)
                    },
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

    def test_reimbursement_form_saves_current_settlement_account_snapshot(self):
        SettlementDetailsForm(
            data={'account_number': 'PL61109010140000071219812874'},
            user=self.user,
            camp=self.camp,
        ).save()
        form = ReimbursementForm(
            data={
                'amount': '10.00',
                'type': Reimbursement.Type.ASSOCIATION,
                'comment': 'Transfer',
                'executed_date': '2026-07-24',
            },
            user=self.user,
            camp=self.camp,
            registered_by=self.registered_by,
        )

        self.assertTrue(form.is_valid(), form.errors)
        reimbursement = form.save()
        self.assertEqual(reimbursement.account_number_snapshot, 'PL61109010140000071219812874')


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

        response = self.client.get(reverse('costs_mine'))

        self.assertEqual(response.status_code, 200)
        pending_invoice = Invoice.objects.get(internal_number='WWW_2026_FP_0002')
        self.assertEqual(list(response.context['invoices']), [pending_invoice, self.invoice])
        self.assertEqual(response.context['confirmed_total'], Decimal('10.00'))
        self.assertEqual(response.context['pending_total'], Decimal('4.00'))

    def test_invoice_add_requires_settlement_details(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('costs_invoice_add'))

        self.assertRedirects(response, reverse('costs_settlement_details'))

    def test_invoice_add_creates_invoice_with_a_cost_item(self):
        SettlementDetails.objects.create(
            user=self.user,
            camp=self.camp,
            account_number='PL61109010140000071219812874',
        )
        self.client.force_login(self.user)

        response = self.client.post(reverse('costs_invoice_add'), {
            **self.invoice_post_data(),
            'attachment': SimpleUploadedFile(
                'invoice.pdf', b'%PDF-1.7', content_type='application/pdf'
            ),
        })

        self.assertRedirects(response, reverse('costs_mine'))
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
            reverse('costs_invoice_edit', args=[self.invoice.pk]),
            self.invoice_post_data(),
        )

        self.assertRedirects(response, reverse('costs_mine'))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.RECEIVED)

    def test_invoice_edit_is_not_available_to_another_user(self):
        self.client.force_login(self.other_user)

        response = self.client.get(reverse('costs_invoice_edit', args=[self.invoice.pk]))

        self.assertEqual(response.status_code, 404)

    @patch('wwwapp.views.sendfile', return_value=HttpResponse())
    def test_only_owner_or_all_costs_permission_can_get_attachment(self, sendfile_response):
        self.client.force_login(self.other_user)

        response = self.client.get(reverse('costs_invoice_attachment', args=[self.invoice.pk]))

        self.assertEqual(response.status_code, 404)
        self.other_user.user_permissions.add(Permission.objects.get(codename='view_all_costs'))
        response = self.client.get(reverse('costs_invoice_attachment', args=[self.invoice.pk]))
        self.assertEqual(response.status_code, 200)
