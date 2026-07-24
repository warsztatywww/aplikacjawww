from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from wwwapp.forms import (
    CostItemFormSet,
    InvoiceForm,
    ReimbursementForm,
    SettlementDetailsForm,
)
from wwwapp.models import Camp, CostItem, Invoice, Reimbursement, Workshop, WorkshopType


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
