from django import template
from django.utils.safestring import mark_safe

register = template.Library()


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
