"""Renumber invoices into K, FVP, and NP series and remove stored counters."""

from django.db import migrations


NUMBERED_STATUSES = ('APPROVED', 'PROCESSED')
NEW_SERIES_BY_TYPE = {
    'KSEF': 'K',
    'OUTSIDE_KSEF': 'FVP',
    'RECEIPT_WITH_NIP': 'FVP',
    'NON_ACCOUNTING_RECEIPT': 'NP',
}
OLD_SERIES_BY_TYPE = {
    'KSEF': 'K',
    'OUTSIDE_KSEF': 'L',
    'RECEIPT_WITH_NIP': 'P',
    'NON_ACCOUNTING_RECEIPT': 'NP',
}


def renumber_invoices_to_fvp(apps, schema_editor):
    """Apply the K, FVP, and NP numbering rule to stored invoices."""
    _renumber_invoices(apps, schema_editor, NEW_SERIES_BY_TYPE)


def restore_invoice_type_series(apps, schema_editor):
    """Restore the four per-type series used by migration 0094."""
    allocated = _renumber_invoices(apps, schema_editor, OLD_SERIES_BY_TYPE)
    Invoice = apps.get_model('wwwapp', 'Invoice')
    InvoiceSequence = apps.get_model('wwwapp', 'InvoiceSequence')
    database = schema_editor.connection.alias
    camp_ids = Invoice.objects.using(database).values_list('camp_id', flat=True).distinct()

    for camp_id in camp_ids:
        for invoice_type in OLD_SERIES_BY_TYPE:
            series = OLD_SERIES_BY_TYPE[invoice_type]
            InvoiceSequence.objects.using(database).create(
                camp_id=camp_id,
                invoice_type=invoice_type,
                last_allocated=allocated.get((camp_id, series), 0),
            )


def _renumber_invoices(apps, schema_editor, series_by_type):
    Invoice = apps.get_model('wwwapp', 'Invoice')
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
        series = series_by_type[invoice.invoice_type]
        key = (invoice.camp_id, series)
        allocated[key] = allocated.get(key, 0) + 1
        invoice.internal_number = (
            f'WWW_{invoice.camp_id}_{series}_{allocated[key]:04d}'
        )
        invoice.save(using=database, update_fields=['internal_number'])
    return allocated


def _replace_numbers_with_temporary_values(invoices, database):
    for invoice in invoices:
        if invoice.internal_number is not None:
            invoice.internal_number = f'__invoice_renumber_{invoice.pk}'
            invoice.save(using=database, update_fields=['internal_number'])


class Migration(migrations.Migration):
    dependencies = [
        ('wwwapp', '0094_renumber_invoices_by_type'),
    ]

    operations = [
        migrations.RunPython(
            renumber_invoices_to_fvp,
            restore_invoice_type_series,
        ),
        migrations.DeleteModel(name='InvoiceSequence'),
    ]
