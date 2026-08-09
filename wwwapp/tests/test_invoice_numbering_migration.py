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

        numbers_by_document = dict(Invoice.objects.values_list(
            'document_number',
            'internal_number',
        ))

        self.assertEqual(numbers_by_document, {
            'TEST/1/2026': 'WWW_2026_FP_0001',
            'TEST/2/2026': None,
            'TEST/3/2026': 'WWW_2026_FPZ_0001',
            'TEST/4/2026': 'WWW_2026_FP_0002',
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
        invoice_data = (
            ('KSEF', 'APPROVED'),
            ('NON_ACCOUNTING_RECEIPT', 'RECEIVED'),
            ('NON_ACCOUNTING_RECEIPT', 'APPROVED'),
            ('RECEIPT_WITH_NIP', 'PROCESSED'),
        )
        for sequence, (invoice_type, status) in enumerate(
            invoice_data,
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
                status=status,
                description='Migration test',
                internal_number=f'WWW_2026_FP_{sequence:04d}',
            )
        InvoiceSequence.objects.create(camp=camp, last_allocated=4)


class InvoiceTypeNumberingMigrationTests(TransactionTestCase):
    migrate_from = [('wwwapp', '0092_separate_invoice_numbering_series')]
    migrate_to = [('wwwapp', '0093_alter_invoicesequence_series')]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        self._create_invoices(old_apps)

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        self.apps = executor.loader.project_state(self.migrate_to).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_existing_invoices_are_renumbered_for_each_invoice_type(self):
        Invoice = self.apps.get_model('wwwapp', 'Invoice')
        InvoiceSequence = self.apps.get_model('wwwapp', 'InvoiceSequence')

        numbers_by_document = dict(Invoice.objects.values_list(
            'document_number',
            'internal_number',
        ))

        self.assertEqual(numbers_by_document, {
            'TEST/K/1': 'WWW_2026_K_0001',
            'TEST/L/1': 'WWW_2026_L_0001',
            'TEST/P/1': 'WWW_2026_P_0001',
            'TEST/NP/1': 'WWW_2026_NP_0001',
            'TEST/K/2': 'WWW_2026_K_0002',
            'TEST/RECEIVED': None,
        })
        self.assertEqual(
            set(InvoiceSequence.objects.filter(camp_id=2026).values_list(
                'series',
                'last_allocated',
            )),
            {('K', 2), ('L', 1), ('P', 1), ('NP', 1)},
        )

    def _create_invoices(self, apps):
        User = apps.get_model('auth', 'User')
        Camp = apps.get_model('wwwapp', 'Camp')
        Invoice = apps.get_model('wwwapp', 'Invoice')
        InvoiceSequence = apps.get_model('wwwapp', 'InvoiceSequence')
        user = User.objects.create(username='invoice-type-migration-user')
        camp, _ = Camp.objects.get_or_create(year=2026)
        invoice_data = (
            ('KSEF', 'APPROVED', 'TEST/K/1'),
            ('OUTSIDE_KSEF', 'APPROVED', 'TEST/L/1'),
            ('RECEIPT_WITH_NIP', 'PROCESSED', 'TEST/P/1'),
            ('NON_ACCOUNTING_RECEIPT', 'APPROVED', 'TEST/NP/1'),
            ('KSEF', 'PROCESSED', 'TEST/K/2'),
            ('OUTSIDE_KSEF', 'RECEIVED', 'TEST/RECEIVED'),
        )
        for sequence, (invoice_type, status, document_number) in enumerate(
            invoice_data,
            start=1,
        ):
            Invoice.objects.create(
                user=user,
                camp=camp,
                attachment=f'invoices/type-{sequence}.pdf',
                document_number=document_number,
                issue_date='2026-07-24',
                amount='10.00',
                invoice_type=invoice_type,
                status=status,
                description='Invoice type migration test',
                internal_number=(
                    f'WWW_2026_FPZ_{sequence:04d}'
                    if invoice_type == 'NON_ACCOUNTING_RECEIPT'
                    else f'WWW_2026_FP_{sequence:04d}'
                ),
            )
        InvoiceSequence.objects.create(camp=camp, series='FP', last_allocated=5)
        InvoiceSequence.objects.create(camp=camp, series='FPZ', last_allocated=1)
