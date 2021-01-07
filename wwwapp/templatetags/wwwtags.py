from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def qualified_mark(value):
    if value is None:
        return mark_safe('<span class="text-warning"><i class="fas fa-question-circle"></i></span>')
    elif value is True:
        return mark_safe('<span class="text-success"><i class="fas fa-check-circle"></i> TAK</span>')
    else:
        return mark_safe('<span class="text-danger"><i class="fas fa-minus-circle"></i> NIE</span>')


@register.filter
def question_mark_on_none_value(value):
    if value is None:
        return mark_safe('<span class="text-warning font-weight-bolder">?</span>')
    return value


@register.filter
def question_mark_on_empty_string(value):
    if value == '':
        return '?'
    return value


@register.filter
def split(value, key):
    return value.split(key)


@register.filter
def provider_friendly_name(value):
    return value.split("-")[0]


@register.filter
def provider_signin_text(value):
    # Polska język trudna język
    if value == "facebook":
        # this is their official translation when you use the JS SDK with locale set to PL
        return "Zaloguj się przez Facebooka"
    return "Zaloguj się przez " + provider_friendly_name(value).title()
