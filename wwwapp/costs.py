"""Domain services for invoices and reimbursements."""

from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from wwwapp.models import Camp, CostItem, Invoice, InvoiceSequence, Reimbursement, SettlementDetails


INVOICE_FIELDS = (
    'attachment',
    'document_number',
    'issue_date',
    'amount',
    'invoice_type',
    'description',
)
COST_ITEM_FIELDS = ('workshop', 'amount', 'category')
CSV_FIELDS = (
    'internal_number',
    'document_number',
    'issue_date',
    'user',
    'invoice_type',
    'status',
    'invoice_amount',
    'category',
    'camp',
    'workshop',
    'item_amount',
    'description',
)


def create_invoice(*, user, camp, invoice_data, cost_items_data):
    """Create a received invoice with validated cost items and a camp number."""
    return _create_invoice(
        user=user,
        camp=camp,
        invoice_data=invoice_data,
        cost_items_data=cost_items_data,
    )


@transaction.atomic
def allocate_invoice_number(*, camp):
    """Allocate the next internal invoice number for a workshop edition."""
    try:
        sequence = InvoiceSequence.objects.select_for_update().get(camp=camp)
    except InvoiceSequence.DoesNotExist:
        sequence = InvoiceSequence.objects.create(
            camp=camp,
            last_allocated=_highest_allocated_number(camp=camp),
        )
    sequence.last_allocated += 1
    sequence.save(update_fields=['last_allocated'])
    return f'WWW_{camp.year}_FP_{sequence.last_allocated:04d}'


@transaction.atomic
def _create_invoice(*, user, camp, invoice_data, cost_items_data):
    locked_camp = Camp.objects.get(pk=camp.pk)
    items = _build_cost_items(cost_items_data=cost_items_data)
    amount = invoice_data.get('amount')
    _validate_cost_item_total(items=items, amount=amount)

    try:
        sequence = InvoiceSequence.objects.select_for_update().get(camp=locked_camp)
    except InvoiceSequence.DoesNotExist:
        sequence = InvoiceSequence.objects.create(
            camp=locked_camp,
            last_allocated=_highest_allocated_number(camp=locked_camp),
        )
    sequence.last_allocated += 1
    sequence.save(update_fields=['last_allocated'])
    invoice = Invoice(
        user=user,
        camp=locked_camp,
        internal_number=f'WWW_{locked_camp.year}_FP_{sequence.last_allocated:04d}',
        **_invoice_values(invoice_data),
    )
    invoice.full_clean()
    invoice.save()
    _save_cost_items(invoice=invoice, items=items)
    return invoice


@transaction.atomic
def update_invoice(*, invoice, user, invoice_data, cost_items_data):
    """Replace editable invoice data and item allocation atomically."""
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if invoice.user_id != user.pk:
        raise ValidationError('Fakturę może edytować wyłącznie użytkownik, który ją dodał.')
    if invoice.status not in (Invoice.Status.RECEIVED, Invoice.Status.REJECTED):
        raise ValidationError('Można edytować tylko faktury otrzymane lub odrzucone.')
    items = _build_cost_items(cost_items_data=cost_items_data)
    _validate_cost_item_total(items=items, amount=invoice_data.get('amount'))
    old_attachment_name = invoice.attachment.name

    for field, value in _invoice_values(invoice_data).items():
        setattr(invoice, field, value)
    if invoice.status == Invoice.Status.REJECTED:
        invoice.status = Invoice.Status.RECEIVED
        invoice.admin_modified_at = None
        invoice.admin_modified_by = None
    invoice.full_clean()
    invoice.save()
    if old_attachment_name and invoice.attachment.name != old_attachment_name:
        transaction.on_commit(lambda: invoice.attachment.storage.delete(old_attachment_name))
    invoice.cost_items.all().delete()
    _save_cost_items(invoice=invoice, items=items)
    return invoice


@transaction.atomic
def transition_invoices(*, invoices, target_status, changed_by):
    """Move all selected invoices to one valid next status, or none of them."""
    locked = list(
        invoices.select_for_update().select_related('user', 'camp').prefetch_related('cost_items'),
    )
    if any(not _can_transition(invoice.status, target_status) for invoice in locked):
        raise ValidationError('Co najmniej jedna faktura nie może przejść do wybranego stanu.')
    for invoice in locked:
        invoice.status = target_status
        invoice.admin_modified_by = changed_by
        invoice.admin_modified_at = timezone.now()
        invoice.save()


def balance_for(*, user, camp):
    """Return approved and processed invoice value less reimbursements."""
    return approved_total_for(user=user, camp=camp) - reimbursed_total_for(user=user, camp=camp)


def approved_total_for(*, user, camp):
    """Return the value of approved and processed invoices."""
    return _total_for_invoices(
        user=user,
        camp=camp,
        statuses=(Invoice.Status.APPROVED, Invoice.Status.PROCESSED),
    )


def reimbursed_total_for(*, user, camp):
    """Return reimbursements registered for a participant and edition."""
    total = Reimbursement.objects.filter(user=user, camp=camp).aggregate(total=Sum('amount'))['total']
    return total or Decimal('0.00')


def pending_total_for(*, user, camp):
    """Return the total value of received invoices."""
    return _total_for_invoices(user=user, camp=camp, statuses=(Invoice.Status.RECEIVED,))


def invoice_csv_rows(*, invoices):
    """Yield one stable export dictionary per cost item."""
    for invoice in invoices.select_related('user', 'camp').prefetch_related('cost_items__workshop'):
        for item in invoice.cost_items.all():
            row = {
                'internal_number': invoice.internal_number,
                'document_number': invoice.document_number,
                'issue_date': invoice.issue_date,
                'user': invoice.user.get_full_name(),
                'invoice_type': invoice.invoice_type,
                'status': invoice.status,
                'invoice_amount': invoice.amount,
                'category': item.category,
                'camp': str(invoice.camp),
                'workshop': str(item.workshop) if item.workshop_id else '',
                'item_amount': item.amount,
                'description': invoice.description,
            }
            yield {field: _escape_csv_formula(row[field]) for field in CSV_FIELDS}


def _escape_csv_formula(value):
    if isinstance(value, str) and value.startswith(('=', '+', '-', '@')):
        return f"'{value}"
    return value


def _invoice_values(invoice_data):
    return {field: invoice_data[field] for field in INVOICE_FIELDS if field in invoice_data}


def _build_cost_items(*, cost_items_data):
    items = [CostItem(**_cost_item_values(item)) for item in cost_items_data]
    if not items:
        raise ValidationError('Faktura musi zawierać co najmniej jedną pozycję kosztową.')
    for item in items:
        item.full_clean(exclude=['invoice'])
    return items


def _cost_item_values(item):
    if isinstance(item, CostItem):
        return {field: getattr(item, field) for field in COST_ITEM_FIELDS}
    return {field: item[field] for field in COST_ITEM_FIELDS if field in item}


def _validate_cost_item_total(*, items, amount):
    total = sum((item.amount for item in items), Decimal('0.00'))
    if amount is None or total != amount:
        raise ValidationError('Suma pozycji kosztowych musi być równa kwocie faktury.')


def _save_cost_items(*, invoice, items):
    for item in items:
        item.invoice = invoice
        item.full_clean()
        item.save()


def _validate_settlement_details(*, user, camp):
    details = SettlementDetails.objects.filter(user=user, camp=camp).first()
    if details is None or not details.account_number.strip():
        raise ValidationError('Dane rachunku bankowego dla tego obozu są wymagane.')


def _validate_invoice_items(*, invoice):
    items = list(invoice.cost_items.all())
    if not items:
        raise ValidationError('Faktura musi zawierać co najmniej jedną pozycję kosztową.')
    _validate_cost_item_total(items=items, amount=invoice.amount)


def _can_transition(current_status, target_status):
    transitions = {
        Invoice.Status.RECEIVED: (Invoice.Status.APPROVED, Invoice.Status.REJECTED),
        Invoice.Status.APPROVED: (Invoice.Status.PROCESSED, Invoice.Status.REJECTED),
        Invoice.Status.REJECTED: (Invoice.Status.APPROVED,),
    }
    return target_status in transitions.get(current_status, ())


def _total_for_invoices(*, user, camp, statuses):
    total = Invoice.objects.filter(user=user, camp=camp, status__in=statuses).aggregate(
        total=Sum('amount'),
    )['total']
    return total or Decimal('0.00')


def _highest_allocated_number(*, camp):
    prefix = f'WWW_{camp.year}_FP_'
    numbers = Invoice.objects.filter(camp=camp, internal_number__startswith=prefix).values_list(
        'internal_number', flat=True,
    )
    allocated = [
        int(number.removeprefix(prefix))
        for number in numbers
        if number.removeprefix(prefix).isdigit()
    ]
    return max(allocated, default=0)
