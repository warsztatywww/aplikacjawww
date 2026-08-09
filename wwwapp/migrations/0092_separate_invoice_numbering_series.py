from django.db import migrations, models
import django.db.models.deletion


FP = 'FP'
FPZ = 'FPZ'
NON_ACCOUNTING_RECEIPT = 'NON_ACCOUNTING_RECEIPT'
NUMBERED_STATUSES = ('APPROVED', 'PROCESSED')


def renumber_invoices(apps, schema_editor):
    Invoice = apps.get_model('wwwapp', 'Invoice')
    InvoiceSequence = apps.get_model('wwwapp', 'InvoiceSequence')
    database = schema_editor.connection.alias
    invoices = list(
        Invoice.objects.using(database).order_by('camp_id', 'created_at', 'pk')
    )

    _replace_numbers_with_temporary_values(invoices, database)
    allocated = {}
    for invoice in invoices:
        if invoice.status not in NUMBERED_STATUSES:
            invoice.internal_number = None
            invoice.save(using=database, update_fields=['internal_number'])
            continue
        series = FPZ if invoice.invoice_type == NON_ACCOUNTING_RECEIPT else FP
        key = (invoice.camp_id, series)
        allocated[key] = allocated.get(key, 0) + 1
        invoice.internal_number = (
            f'WWW_{invoice.camp_id}_{series}_{allocated[key]:04d}'
        )
        invoice.save(using=database, update_fields=['internal_number'])

    camp_ids = set(invoice.camp_id for invoice in invoices)
    camp_ids.update(
        InvoiceSequence.objects.using(database).values_list('camp_id', flat=True)
    )
    for camp_id in camp_ids:
        for series in (FP, FPZ):
            InvoiceSequence.objects.using(database).update_or_create(
                camp_id=camp_id,
                series=series,
                defaults={'last_allocated': allocated.get((camp_id, series), 0)},
            )


def restore_single_invoice_series(apps, schema_editor):
    Invoice = apps.get_model('wwwapp', 'Invoice')
    InvoiceSequence = apps.get_model('wwwapp', 'InvoiceSequence')
    database = schema_editor.connection.alias
    invoices = list(
        Invoice.objects.using(database).order_by('camp_id', 'created_at', 'pk')
    )

    _replace_numbers_with_temporary_values(invoices, database)
    allocated = {}
    for invoice in invoices:
        allocated[invoice.camp_id] = allocated.get(invoice.camp_id, 0) + 1
        invoice.internal_number = (
            f'WWW_{invoice.camp_id}_{FP}_{allocated[invoice.camp_id]:04d}'
        )
        invoice.save(using=database, update_fields=['internal_number'])

    camp_ids = set(invoice.camp_id for invoice in invoices)
    camp_ids.update(
        InvoiceSequence.objects.using(database).values_list('camp_id', flat=True)
    )
    InvoiceSequence.objects.using(database).filter(series=FPZ).delete()
    for camp_id in camp_ids:
        InvoiceSequence.objects.using(database).update_or_create(
            camp_id=camp_id,
            series=FP,
            defaults={'last_allocated': allocated.get(camp_id, 0)},
        )


def _replace_numbers_with_temporary_values(invoices, database):
    for invoice in invoices:
        invoice.internal_number = f'__invoice_renumber_{invoice.pk}'
        invoice.save(using=database, update_fields=['internal_number'])


class Migration(migrations.Migration):
    dependencies = [
        (
            'wwwapp',
            '0091_costitem_invoice_invoicesequence_reimbursement_settlementdetails',
        ),
    ]

    operations = [
        migrations.AddField(
            model_name='invoicesequence',
            name='series',
            field=models.CharField(
                choices=[('FP', 'FP'), ('FPZ', 'FPZ')],
                default='FP',
                max_length=3,
            ),
        ),
        migrations.AlterField(
            model_name='invoicesequence',
            name='camp',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='invoice_sequences',
                to='wwwapp.camp',
            ),
        ),
        migrations.AddConstraint(
            model_name='invoicesequence',
            constraint=models.UniqueConstraint(
                fields=('camp', 'series'),
                name='unique_invoice_sequence_series_per_camp',
            ),
        ),
        migrations.AlterField(
            model_name='invoice',
            name='internal_number',
            field=models.CharField(
                blank=True,
                editable=False,
                max_length=30,
                null=True,
                unique=True,
            ),
        ),
        migrations.RunPython(renumber_invoices, restore_single_invoice_series),
    ]
