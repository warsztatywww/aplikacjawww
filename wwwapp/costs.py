"""Domain services for invoices and reimbursements."""

from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from wwwapp.models import Camp, CostItem, Invoice, InvoiceSequence, Reimbursement, SettlementDetails


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
