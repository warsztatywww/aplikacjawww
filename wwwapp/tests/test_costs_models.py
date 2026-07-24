import os
from decimal import Decimal
from threading import Barrier, Thread
from tempfile import TemporaryDirectory

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings

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
from wwwapp.costs import (
    balance_for,
    create_invoice,
    invoice_csv_rows,
    pending_total_for,
    transition_invoices,
    update_invoice,
)


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
            internal_number='WWW_2026_FP_0001',
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

    def test_reimbursement_uses_an_account_number_snapshot(self):
        self.assertIsNotNone(Reimbursement._meta.get_field('account_number_snapshot'))

    def test_invoice_queryset_deletion_is_prohibited(self):
        with self.assertRaises(ValidationError):
            Invoice.objects.filter(pk=self.invoice.pk).delete()

        self.assertTrue(Invoice.objects.filter(pk=self.invoice.pk).exists())

    def test_rejected_invoice_becomes_received_when_edited(self):
        self.invoice.status = Invoice.Status.REJECTED
        self.invoice.save()

        update_invoice(
            invoice=self.invoice,
            user=self.user,
            invoice_data=self.data,
            cost_items_data=[self.item],
        )

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.RECEIVED)

    def test_update_rejects_a_different_same_camp_user(self):
        with self.assertRaises(ValidationError):
            update_invoice(
                invoice=self.invoice,
                user=self.other_user,
                invoice_data=self.data,
                cost_items_data=[self.item],
            )

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.description, 'Materiały do warsztatów')

    def test_update_rejects_approved_and_processed_invoices(self):
        for status in (Invoice.Status.APPROVED, Invoice.Status.PROCESSED):
            with self.subTest(status=status):
                self.invoice.status = status
                self.invoice.save()

                with self.assertRaises(ValidationError):
                    update_invoice(
                        invoice=self.invoice,
                        user=self.user,
                        invoice_data=self.data,
                        cost_items_data=[self.item],
                    )

    def test_replacing_an_attachment_deletes_the_old_upload_after_commit(self):
        with TemporaryDirectory() as upload_root, override_settings(SENDFILE_ROOT=upload_root):
            field = Invoice._meta.get_field('attachment')
            original_storage = field.storage
            field.storage = UploadStorage()
            try:
                self.invoice.attachment.storage = field.storage
                self.invoice.attachment.save('old.pdf', ContentFile(b'%PDF-old'), save=True)
                old_path = self.invoice.attachment.path
                self.assertTrue(os.path.exists(old_path))

                with self.captureOnCommitCallbacks(execute=True):
                    updated_invoice = update_invoice(
                        invoice=self.invoice,
                        user=self.user,
                        invoice_data={
                            **self.data,
                            'attachment': ContentFile(b'%PDF-new', name='new.pdf'),
                        },
                        cost_items_data=[self.item],
                    )

                self.assertFalse(os.path.exists(old_path))
                self.assertTrue(os.path.exists(updated_invoice.attachment.path))
            finally:
                field.storage = original_storage

    def test_create_requires_settlement_details(self):
        user_without_details = User.objects.create_user(username='no-details')

        with self.assertRaises(ValidationError):
            create_invoice(
                user=user_without_details,
                camp=self.camp,
                invoice_data=self.data,
                cost_items_data=[self.item],
            )

    def test_create_rejects_blank_settlement_account(self):
        SettlementDetails.objects.filter(user=self.other_user, camp=self.camp).update(
            account_number=' ',
        )

        with self.assertRaises(ValidationError):
            create_invoice(
                user=self.other_user,
                camp=self.camp,
                invoice_data=self.data,
                cost_items_data=[self.item],
            )

    def test_create_requires_at_least_one_cost_item(self):
        with self.assertRaises(ValidationError):
            create_invoice(
                user=self.user,
                camp=self.camp,
                invoice_data=self.data,
                cost_items_data=[],
            )

    def test_create_requires_cost_items_to_match_invoice_total(self):
        with self.assertRaises(ValidationError):
            create_invoice(
                user=self.user,
                camp=self.camp,
                invoice_data=self.data,
                cost_items_data=[{**self.item, 'amount': Decimal('9.99')}],
            )

    def test_batch_transition_rolls_back_when_one_invoice_is_ineligible(self):
        received = create_invoice(
            user=self.user,
            camp=self.camp,
            invoice_data=self.data,
            cost_items_data=[self.item],
        )
        processed = create_invoice(
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

    def test_transition_allows_only_the_defined_state_graph(self):
        allowed = {
            (Invoice.Status.RECEIVED, Invoice.Status.APPROVED),
            (Invoice.Status.RECEIVED, Invoice.Status.REJECTED),
            (Invoice.Status.APPROVED, Invoice.Status.PROCESSED),
            (Invoice.Status.APPROVED, Invoice.Status.REJECTED),
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
        invoice = create_invoice(
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
        approved = create_invoice(
            user=self.user,
            camp=self.camp,
            invoice_data=self.data,
            cost_items_data=[self.item],
        )
        approved.status = Invoice.Status.APPROVED
        approved.save()
        processed = create_invoice(
            user=self.user,
            camp=self.camp,
            invoice_data={**self.data, 'document_number': 'FV/2/2026', 'amount': Decimal('4.00')},
            cost_items_data=[{**self.item, 'amount': Decimal('4.00')}],
        )
        processed.status = Invoice.Status.PROCESSED
        processed.save()
        create_invoice(
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
            executed_date='2026-07-25',
            registered_by=self.admin,
            account_number_snapshot='PL61109010140000071219812874',
        )

        self.assertEqual(balance_for(user=self.user, camp=self.camp), Decimal('11.00'))
        self.assertEqual(pending_total_for(user=self.user, camp=self.camp), Decimal('6.00'))

    def test_invoice_csv_rows_split_an_invoice_into_cost_items(self):
        invoice = create_invoice(
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
                'status', 'invoice_amount', 'category', 'context_type', 'context_id',
                'context_name', 'item_amount',
                'description',
            ),
        )
        self.assertEqual(rows[0]['internal_number'], invoice.internal_number)
        self.assertEqual(rows[0]['document_number'], invoice.document_number)
        self.assertEqual(rows[0]['item_amount'], Decimal('10.00'))
        self.assertEqual(rows[0]['context_type'], 'camp')
        self.assertEqual(rows[1]['category'], CostItem.Category.OUTINGS)

    def test_invoice_csv_rows_escape_formula_leading_user_text(self):
        CostItem.objects.create(
            invoice=self.invoice,
            amount=self.invoice.amount,
            category=CostItem.Category.OUTINGS,
        )
        self.invoice.description = '+description'
        self.invoice.save(update_fields=['description'])
        self.user.username = '-username'
        self.user.save(update_fields=['username'])

        for formula_prefix in ('=', '+', '-', '@'):
            with self.subTest(formula_prefix=formula_prefix):
                self.invoice.document_number = f'{formula_prefix}formula'
                self.invoice.save(update_fields=['document_number'])

                row = next(
                    invoice_csv_rows(invoices=Invoice.objects.filter(pk=self.invoice.pk)),
                )

                self.assertEqual(row['document_number'], f"'{formula_prefix}formula")
                self.assertEqual(row['description'], "'+description")
                self.assertEqual(row['user'], "'-username")


class InvoiceSequenceConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.camp = Camp.objects.create(year=2030)
        self.user = User.objects.create_user(username='sequence-user')
        SettlementDetails.objects.create(
            user=self.user,
            camp=self.camp,
            account_number='PL61109010140000071219812874',
        )

    def test_concurrent_creates_allocate_unique_contiguous_numbers(self):
        barrier = Barrier(2)
        numbers = []
        errors = []
        data = {
            'issue_date': '2030-01-01',
            'amount': Decimal('1.00'),
            'invoice_type': Invoice.Type.KSEF,
            'attachment': 'invoices/sequence.pdf',
            'description': 'Test',
        }
        item = {'amount': Decimal('1.00'), 'category': CostItem.Category.WORKSHOPS}

        def create(number):
            close_old_connections()
            try:
                barrier.wait()
                invoice = create_invoice(
                    user=User.objects.get(pk=self.user.pk),
                    camp=Camp.objects.get(pk=self.camp.pk),
                    invoice_data={**data, 'document_number': f'FV/{number}/2030'},
                    cost_items_data=[item],
                )
                numbers.append(invoice.internal_number)
            except Exception as error:
                errors.append(error)
            finally:
                close_old_connections()

        threads = [Thread(target=create, args=(number,)) for number in (1, 2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(set(numbers), {'WWW_2030_FP_0001', 'WWW_2030_FP_0002'})
