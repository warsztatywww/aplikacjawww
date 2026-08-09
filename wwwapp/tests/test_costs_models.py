from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import RequestFactory, TestCase

from wwwapp.models import (
    Camp,
    CostItem,
    Invoice,
    InvoiceSequence,
    Reimbursement,
    SettlementDetails,
    Workshop,
    WorkshopType,
)
from wwwapp.costs import (
    allocate_invoice_number,
    balance_for,
    invoice_csv_rows,
    pending_total_for,
    transition_invoices,
)
from wwwapp.admin import InvoiceAdmin


class CostModelTests(TestCase):
    def setUp(self):
        Camp.objects.all().update(year=2026)
        self.camp = Camp.objects.get()
        self.other_camp = Camp.objects.create(year=2027)
        self.user = User.objects.create_user(username='user')
        self.other_user = User.objects.create_user(username='other-user')
        self.admin = User.objects.create_user(username='admin')
        SettlementDetails.objects.create(
            user=self.user,
            camp=self.camp,
            account_number='PL61109010140000071219812874',
        )
        SettlementDetails.objects.create(
            user=self.other_user,
            camp=self.camp,
            account_number='PL27114020040000300201355387',
        )
        self.invoice = Invoice.objects.create(
            user=self.user,
            camp=self.camp,
            document_number='FV/1/2026',
            issue_date='2026-07-24',
            amount=Decimal('10.00'),
            invoice_type=Invoice.Type.KSEF,
            attachment='invoices/fv-1.pdf',
            description='Materiały do warsztatów',
            internal_number='WWW_2026_K_0001',
        )
        InvoiceSequence.objects.create(
            camp=self.camp,
            invoice_type=Invoice.Type.KSEF,
            last_allocated=1,
        )
        workshop_type = WorkshopType.objects.create(year=self.other_camp, name='Type')
        self.other_workshop = Workshop.objects.create(
            year=self.other_camp,
            type=workshop_type,
            name='other-workshop',
            title='Other workshop',
        )
        self.data = {
            'document_number': 'FV/1/2026',
            'issue_date': '2026-07-24',
            'amount': Decimal('10.00'),
            'invoice_type': Invoice.Type.KSEF,
            'attachment': 'invoices/fv-1.pdf',
            'description': 'Materiały do warsztatów',
        }
        self.item = {
            'amount': Decimal('10.00'),
            'category': CostItem.Category.WORKSHOPS,
        }

    def test_cost_item_rejects_workshop_from_another_camp(self):
        item = CostItem(invoice=self.invoice, workshop=self.other_workshop,
                        amount=Decimal('1.00'), category=CostItem.Category.WORKSHOPS)

        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_settlement_details_are_unique_per_user_and_camp(self):
        with self.assertRaises(IntegrityError):
            SettlementDetails.objects.create(user=self.user, camp=self.camp,
                                             account_number='PL27114020040000300201355387')

    def test_admin_cannot_add_an_invoice(self):
        site = AdminSite()
        request = RequestFactory().get('/')
        request.user = User.objects.create_superuser('financial-admin', 'admin@example.com', 'password')

        self.assertFalse(InvoiceAdmin(Invoice, site).has_add_permission(request))

    def test_admin_approval_allocates_an_invoice_number(self):
        invoice = Invoice.objects.create(
            user=self.user,
            camp=self.other_camp,
            document_number='FV/admin/2027',
            issue_date='2027-07-24',
            amount=Decimal('1.00'),
            invoice_type=Invoice.Type.NON_ACCOUNTING_RECEIPT,
            attachment='invoices/admin.pdf',
            description='Admin approval',
            internal_number=None,
            status=Invoice.Status.APPROVED,
        )
        request = RequestFactory().post('/')
        request.user = self.admin

        InvoiceAdmin(Invoice, AdminSite()).save_model(
            request,
            invoice,
            form=None,
            change=True,
        )

        invoice.refresh_from_db()
        self.assertEqual(invoice.internal_number, 'WWW_2027_NP_0001')

    def test_admin_can_reject_numbered_invoice(self):
        self.invoice.status = Invoice.Status.REJECTED
        request = RequestFactory().post('/')
        request.user = self.admin

        InvoiceAdmin(Invoice, AdminSite()).save_model(
            request,
            self.invoice,
            form=None,
            change=True,
        )

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.REJECTED)
        self.assertEqual(self.invoice.internal_number, 'WWW_2026_K_0001')

    def test_invoice_with_cost_items_is_protected_from_deletion(self):
        CostItem.objects.create(invoice=self.invoice, amount=Decimal('10.00'),
                                category=CostItem.Category.WORKSHOPS)

        with self.assertRaises(ProtectedError):
            with transaction.atomic():
                self.invoice.delete()

        self.assertTrue(Invoice.objects.filter(pk=self.invoice.pk).exists())

    def test_settlement_details_accept_formatted_nrb_and_iban_numbers(self):
        for account_number in (
            'PL 61 1090 1014 0000 0712 1981 2874',
            '61 1090 1014 0000 0712 1981 2874',
        ):
            with self.subTest(account_number=account_number):
                details = SettlementDetails(
                    user=self.user,
                    camp=self.other_camp,
                    account_number=account_number,
                )

                details.full_clean()

                self.assertEqual(details.account_number, 'PL61109010140000071219812874')

    def test_settlement_details_normalize_on_save(self):
        details = SettlementDetails(
            user=self.user,
            camp=self.other_camp,
            account_number='61 1090 1014 0000 0712 1981 2874',
        )

        details.save()

        self.assertEqual(details.account_number, 'PL61109010140000071219812874')

    def test_invoice_exposes_when_the_owner_can_edit_it(self):
        self.assertTrue(self.invoice.can_user_edit)

        self.invoice.status = Invoice.Status.APPROVED

        self.assertFalse(self.invoice.can_user_edit)

    def test_invoice_summarizes_distinct_workshops_and_categories(self):
        workshop_type = WorkshopType.objects.create(year=self.camp, name='Warsztaty')
        workshop = Workshop.objects.create(
            year=self.camp,
            type=workshop_type,
            name='workshop-a',
            title='Warsztat A',
        )
        CostItem.objects.create(
            invoice=self.invoice,
            amount=Decimal('5.00'),
            category=CostItem.Category.WORKSHOPS,
            workshop=workshop,
        )
        CostItem.objects.create(
            invoice=self.invoice,
            amount=Decimal('3.00'),
            category=CostItem.Category.WORKSHOPS,
            workshop=workshop,
        )
        CostItem.objects.create(
            invoice=self.invoice,
            amount=Decimal('2.00'),
            category=CostItem.Category.OUTINGS,
        )

        self.assertEqual(self.invoice.workshops_summary, 'Warsztat A')
        self.assertEqual(self.invoice.categories_summary, 'Warsztaty, Wyjścia')

    def test_invoice_summaries_are_empty_without_cost_items(self):
        self.assertEqual(self.invoice.workshops_summary, '')
        self.assertEqual(self.invoice.categories_summary, '')

    def test_invoice_numbers_start_from_one_when_the_sequence_is_created(self):
        other_invoice = Invoice.objects.create(
            user=self.user,
            camp=self.other_camp,
            document_number='FV/1/2027',
            issue_date='2027-07-24',
            amount=Decimal('1.00'),
            invoice_type=Invoice.Type.KSEF,
            attachment='invoices/other.pdf',
            description='Other edition',
            internal_number='WWW_2027_K_0041',
        )
        InvoiceSequence.objects.create(
            camp=self.other_camp,
            invoice_type=Invoice.Type.KSEF,
            last_allocated=41,
        )
        empty_camp = Camp.objects.create(year=2028)

        first_number = allocate_invoice_number(camp=self.camp, invoice_type=Invoice.Type.KSEF)
        second_number = allocate_invoice_number(camp=self.camp, invoice_type=Invoice.Type.KSEF)
        other_number = allocate_invoice_number(
            camp=self.other_camp,
            invoice_type=Invoice.Type.KSEF,
        )
        empty_camp_number = allocate_invoice_number(
            camp=empty_camp,
            invoice_type=Invoice.Type.KSEF,
        )

        self.assertEqual(first_number, 'WWW_2026_K_0002')
        self.assertEqual(second_number, 'WWW_2026_K_0003')
        self.assertEqual(other_number, 'WWW_2027_K_0042')
        self.assertEqual(empty_camp_number, 'WWW_2028_K_0001')
        self.assertEqual(
            InvoiceSequence.objects.get(
                camp=self.camp,
                invoice_type=Invoice.Type.KSEF,
            ).last_allocated,
            3,
        )
        self.assertEqual(
            InvoiceSequence.objects.get(
                camp=other_invoice.camp,
                invoice_type=Invoice.Type.KSEF,
            ).last_allocated,
            42,
        )

    def test_invoice_types_use_separate_numbering_series(self):
        expected_numbers = {
            Invoice.Type.KSEF: 'WWW_2026_K_0002',
            Invoice.Type.OUTSIDE_KSEF: 'WWW_2026_L_0001',
            Invoice.Type.RECEIPT_WITH_NIP: 'WWW_2026_P_0001',
            Invoice.Type.NON_ACCOUNTING_RECEIPT: 'WWW_2026_NP_0001',
        }

        allocated_numbers = {
            invoice_type: allocate_invoice_number(
                camp=self.camp,
                invoice_type=invoice_type,
            )
            for invoice_type in expected_numbers
        }

        self.assertEqual(allocated_numbers, expected_numbers)
        self.assertEqual(
            set(InvoiceSequence.objects.filter(camp=self.camp).values_list(
                'invoice_type',
                'last_allocated',
            )),
            {
                (Invoice.Type.KSEF, 2),
                (Invoice.Type.OUTSIDE_KSEF, 1),
                (Invoice.Type.RECEIPT_WITH_NIP, 1),
                (Invoice.Type.NON_ACCOUNTING_RECEIPT, 1),
            },
        )

    def test_allocate_invoice_number_recovers_from_a_concurrent_sequence_creation(self):
        camp = Camp.objects.create(year=2028)
        InvoiceSequence.objects.create(
            camp=camp,
            invoice_type=Invoice.Type.KSEF,
            last_allocated=1,
        )

        with patch.object(
            InvoiceSequence.objects,
            'get_or_create',
            side_effect=lambda **kwargs: InvoiceSequence.objects.create(**kwargs),
        ):
            allocated = allocate_invoice_number(camp=camp, invoice_type=Invoice.Type.KSEF)

        self.assertEqual(allocated, 'WWW_2028_K_0002')
        self.assertEqual(
            InvoiceSequence.objects.get(
                camp=camp,
                invoice_type=Invoice.Type.KSEF,
            ).last_allocated,
            2,
        )

    def test_batch_transition_rolls_back_when_one_invoice_is_ineligible(self):
        received = self.create_invoice(
            user=self.user,
            camp=self.camp,
            invoice_data=self.data,
            cost_items_data=[self.item],
        )
        processed = self.create_invoice(
            user=self.user,
            camp=self.camp,
            invoice_data={**self.data, 'document_number': 'FV/2/2026'},
            cost_items_data=[self.item],
        )
        processed.status = Invoice.Status.PROCESSED
        processed.save()

        with self.assertRaises(ValidationError):
            transition_invoices(
                invoices=Invoice.objects.filter(pk__in=[received.pk, processed.pk]),
                target_status=Invoice.Status.APPROVED,
                changed_by=self.admin,
            )

        received.refresh_from_db()
        self.assertEqual(received.status, Invoice.Status.RECEIVED)

    def test_approval_allocates_numbers_from_the_invoice_type_series(self):
        camp = Camp.objects.create(year=2028)
        expected_numbers = (
            (Invoice.Type.KSEF, 'WWW_2028_K_0001'),
            (Invoice.Type.OUTSIDE_KSEF, 'WWW_2028_L_0001'),
            (Invoice.Type.RECEIPT_WITH_NIP, 'WWW_2028_P_0001'),
            (Invoice.Type.NON_ACCOUNTING_RECEIPT, 'WWW_2028_NP_0001'),
        )

        for index, (invoice_type, expected_number) in enumerate(expected_numbers):
            invoice = Invoice.objects.create(
                user=self.user,
                camp=camp,
                attachment=f'invoices/{index}.pdf',
                document_number=f'FV/{index}/2028',
                issue_date='2028-07-24',
                amount=Decimal('10.00'),
                invoice_type=invoice_type,
                description='Approval numbering test',
                internal_number='',
            )

            transition_invoices(
                invoices=Invoice.objects.filter(pk=invoice.pk),
                target_status=Invoice.Status.APPROVED,
                changed_by=self.admin,
            )

            invoice.refresh_from_db()
            self.assertEqual(invoice.internal_number, expected_number)

        self.assertEqual(
            set(InvoiceSequence.objects.filter(camp=camp).values_list(
                'invoice_type',
                'last_allocated',
            )),
            {
                (Invoice.Type.KSEF, 1),
                (Invoice.Type.OUTSIDE_KSEF, 1),
                (Invoice.Type.RECEIPT_WITH_NIP, 1),
                (Invoice.Type.NON_ACCOUNTING_RECEIPT, 1),
            },
        )

    def test_transition_allows_only_the_defined_state_graph(self):
        allowed = {
            (Invoice.Status.RECEIVED, Invoice.Status.APPROVED),
            (Invoice.Status.RECEIVED, Invoice.Status.REJECTED),
            (Invoice.Status.APPROVED, Invoice.Status.PROCESSED),
            (Invoice.Status.REJECTED, Invoice.Status.APPROVED),
        }

        for index, source in enumerate(Invoice.Status.values):
            for target in Invoice.Status.values:
                with self.subTest(source=source, target=target):
                    invoice = self._invoice_with_status(source, index)
                    if (source, target) in allowed:
                        transition_invoices(
                            invoices=Invoice.objects.filter(pk=invoice.pk),
                            target_status=target,
                            changed_by=self.admin,
                        )
                        invoice.refresh_from_db()
                        self.assertEqual(invoice.status, target)
                    else:
                        with self.assertRaises(ValidationError):
                            transition_invoices(
                                invoices=Invoice.objects.filter(pk=invoice.pk),
                                target_status=target,
                                changed_by=self.admin,
                            )

    def _invoice_with_status(self, status, index):
        invoice = self.create_invoice(
            user=self.user,
            camp=self.camp,
            invoice_data={**self.data, 'document_number': f'FV/{index + 10}/2026'},
            cost_items_data=[self.item],
        )
        invoice.status = status
        invoice.save()
        return invoice

    def test_balance_and_pending_totals_use_the_expected_statuses(self):
        self.invoice.status = Invoice.Status.REJECTED
        self.invoice.save()
        approved = self.create_invoice(
            user=self.user,
            camp=self.camp,
            invoice_data=self.data,
            cost_items_data=[self.item],
        )
        approved.status = Invoice.Status.APPROVED
        approved.save()
        processed = self.create_invoice(
            user=self.user,
            camp=self.camp,
            invoice_data={**self.data, 'document_number': 'FV/2/2026', 'amount': Decimal('4.00')},
            cost_items_data=[{**self.item, 'amount': Decimal('4.00')}],
        )
        processed.status = Invoice.Status.PROCESSED
        processed.save()
        self.create_invoice(
            user=self.user,
            camp=self.camp,
            invoice_data={**self.data, 'document_number': 'FV/3/2026', 'amount': Decimal('6.00')},
            cost_items_data=[{**self.item, 'amount': Decimal('6.00')}],
        )
        Reimbursement.objects.create(
            user=self.user,
            camp=self.camp,
            amount=Decimal('3.00'),
            type=Reimbursement.Type.ASSOCIATION,
            execution_date='2026-07-25',
            registered_by=self.admin,
        )

        self.assertEqual(balance_for(user=self.user, camp=self.camp), Decimal('11.00'))
        self.assertEqual(pending_total_for(user=self.user, camp=self.camp), Decimal('6.00'))

    def test_invoice_csv_rows_split_an_invoice_into_cost_items(self):
        invoice = self.create_invoice(
            user=self.user,
            camp=self.camp,
            invoice_data={**self.data, 'amount': Decimal('10.01')},
            cost_items_data=[
                self.item,
                {'amount': Decimal('0.01'), 'category': CostItem.Category.OUTINGS},
            ],
        )

        rows = list(invoice_csv_rows(invoices=Invoice.objects.filter(pk=invoice.pk)))

        self.assertEqual(len(rows), 2)
        self.assertEqual(
            tuple(rows[0]),
            (
                'internal_number', 'document_number', 'issue_date', 'user', 'invoice_type',
                'status', 'invoice_amount', 'category', 'workshop', 'item_amount',
                'description',
            ),
        )
        self.assertEqual(rows[0]['internal_number'], invoice.internal_number)
        self.assertEqual(rows[0]['document_number'], invoice.document_number)
        self.assertEqual(rows[0]['item_amount'], Decimal('10.00'))
        self.assertEqual(rows[0]['workshop'], '')
        self.assertEqual(rows[1]['category'], CostItem.Category.OUTINGS)

    def test_invoice_csv_rows_escape_formula_leading_user_text(self):
        CostItem.objects.create(
            invoice=self.invoice,
            amount=self.invoice.amount,
            category=CostItem.Category.OUTINGS,
        )
        self.invoice.description = '+description'
        self.invoice.save(update_fields=['description'])
        self.user.first_name = '-name'
        self.user.save(update_fields=['first_name'])

        for formula_prefix in ('=', '+', '-', '@'):
            with self.subTest(formula_prefix=formula_prefix):
                self.invoice.document_number = f'{formula_prefix}formula'
                self.invoice.save(update_fields=['document_number'])

                row = next(
                    invoice_csv_rows(invoices=Invoice.objects.filter(pk=self.invoice.pk)),
                )

                self.assertEqual(row['document_number'], f"'{formula_prefix}formula")
                self.assertEqual(row['description'], "'+description")
                self.assertEqual(row['user'], "'-name")

    def create_invoice(self, *, user, camp, invoice_data, cost_items_data):
        invoice = Invoice.objects.create(
            user=user,
            camp=camp,
            internal_number=f'WWW_{camp.year}_K_{Invoice.objects.count() + 1:04d}',
            **invoice_data,
        )
        for cost_item_data in cost_items_data:
            CostItem.objects.create(invoice=invoice, **cost_item_data)
        return invoice
