from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class InvoiceNumberingMigrationTests(TransactionTestCase):
    migrate_from = [(
        'wwwapp',
        '0091_costitem_invoice_invoicesequence_reimbursement_settlementdetails',
    )]
    migrate_to = [('wwwapp', '0092_separate_invoice_numbering_series')]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        self._create_old_invoices(old_apps)

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        self.apps = executor.loader.project_state(self.migrate_to).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_existing_invoices_are_renumbered_with_independent_series(self):
        Invoice = self.apps.get_model('wwwapp', 'Invoice')
        InvoiceSequence = self.apps.get_model('wwwapp', 'InvoiceSequence')

        numbers_by_type = dict(Invoice.objects.values_list('invoice_type', 'internal_number'))

        self.assertEqual(numbers_by_type, {
            'KSEF': 'WWW_2026_FP_0001',
            'NON_ACCOUNTING_RECEIPT': 'WWW_2026_FPZ_0001',
            'RECEIPT_WITH_NIP': 'WWW_2026_FP_0002',
        })
        self.assertEqual(
            set(InvoiceSequence.objects.filter(camp_id=2026).values_list(
                'series',
                'last_allocated',
            )),
            {('FP', 2), ('FPZ', 1)},
        )

    def _create_old_invoices(self, apps):
        User = apps.get_model('auth', 'User')
        Camp = apps.get_model('wwwapp', 'Camp')
        Invoice = apps.get_model('wwwapp', 'Invoice')
        InvoiceSequence = apps.get_model('wwwapp', 'InvoiceSequence')
        user = User.objects.create(username='migration-user')
        camp, _ = Camp.objects.get_or_create(year=2026)
        for sequence, invoice_type in enumerate(
            ('KSEF', 'NON_ACCOUNTING_RECEIPT', 'RECEIPT_WITH_NIP'),
            start=1,
        ):
            Invoice.objects.create(
                user=user,
                camp=camp,
                attachment=f'invoices/{sequence}.pdf',
                document_number=f'TEST/{sequence}/2026',
                issue_date='2026-07-24',
                amount='10.00',
                invoice_type=invoice_type,
                description='Migration test',
                internal_number=f'WWW_2026_FP_{sequence:04d}',
            )
        InvoiceSequence.objects.create(camp=camp, last_allocated=3)
