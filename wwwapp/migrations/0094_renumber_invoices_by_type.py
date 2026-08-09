from django.db import migrations


INVOICE_TYPE_PREFIXES = {
    'KSEF': 'K',
    'OUTSIDE_KSEF': 'L',
    'RECEIPT_WITH_NIP': 'P',
    'NON_ACCOUNTING_RECEIPT': 'NP',
}
NUMBERED_STATUSES = ('APPROVED', 'PROCESSED')


def renumber_invoices_by_type(apps, schema_editor):
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
        prefix = INVOICE_TYPE_PREFIXES[invoice.invoice_type]
        key = (invoice.camp_id, invoice.invoice_type)
        allocated[key] = allocated.get(key, 0) + 1
        invoice.internal_number = (
            f'WWW_{invoice.camp_id}_{prefix}_{allocated[key]:04d}'
        )
        invoice.save(using=database, update_fields=['internal_number'])

    camp_ids = set(invoice.camp_id for invoice in invoices)
    camp_ids.update(
        InvoiceSequence.objects.using(database).values_list('camp_id', flat=True)
    )
    InvoiceSequence.objects.using(database).all().delete()
    for camp_id in camp_ids:
        for invoice_type in INVOICE_TYPE_PREFIXES:
            InvoiceSequence.objects.using(database).create(
                camp_id=camp_id,
                invoice_type=invoice_type,
                last_allocated=allocated.get((camp_id, invoice_type), 0),
            )


def restore_two_invoice_series(apps, schema_editor):
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
        series = 'FPZ' if invoice.invoice_type == 'NON_ACCOUNTING_RECEIPT' else 'FP'
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
    InvoiceSequence.objects.using(database).all().delete()
    for camp_id in camp_ids:
        for series in ('FP', 'FPZ'):
            InvoiceSequence.objects.using(database).create(
                camp_id=camp_id,
                invoice_type=series,
                last_allocated=allocated.get((camp_id, series), 0),
            )


def _replace_numbers_with_temporary_values(invoices, database):
    for invoice in invoices:
        if invoice.internal_number is not None:
            invoice.internal_number = f'__invoice_renumber_{invoice.pk}'
            invoice.save(using=database, update_fields=['internal_number'])


class Migration(migrations.Migration):
    dependencies = [
        ('wwwapp', '0093_alter_invoicesequence_series'),
    ]

    operations = [
        migrations.RunPython(
            renumber_invoices_by_type,
            restore_two_invoice_series,
        ),
    ]
