from django import template
from django.utils.html import mark_safe
from wwwapp.models import WorkshopUserProfile


register = template.Library()


@register.filter
def person_status(value):
    if value == WorkshopUserProfile.STATUS_ACCEPTED:
        return mark_safe('<span class="qualified">Zakwalifikowany</span>')
    elif value == WorkshopUserProfile.STATUS_REJECTED:
        return mark_safe('<span class="not-qualified">Odrzucony</span>')
    else:
        return ''


@register.filter
def qualified_mark(value):
    if value is None:
        return mark_safe('<span class="maybe-qualified">?</span>')
    elif value is True:
        return mark_safe('<span class="qualified">✔</span> TAK')
    else:
        return mark_safe('<span class="not-qualified">✘</span> NIE')


@register.filter
def question_mark_on_none_value(value):
    if value is None:
        return mark_safe('<span class="maybe-qualified">?</span>')
    return value


@register.filter
def question_mark_on_empty_string(value):
    if value == '':
        return '?'
    return value
