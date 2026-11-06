from decimal import Decimal
from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()
ICONS = {
    "grid": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h5"/>',
    "bell": '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "search": '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/>',
    "arrow": '<path d="M5 12h14m-5-5 5 5-5 5"/>',
    "down": '<path d="M12 3v12m-5-5 5 5 5-5M5 16v5h14v-5"/>',
    "check": '<path d="m5 12 4 4L19 6"/>',
    "alert": '<path d="m12 3 10 18H2L12 3zM12 9v4M12 17h.01"/>',
    "infinity": '<path d="M12 12c-2-3-3-4-5-4a4 4 0 1 0 0 8c2 0 3-1 5-4zm0 0c2-3 3-4 5-4a4 4 0 1 1 0 8c-2 0-3-1-5-4z"/>',
    "logout": '<path d="M9 4H4v16h5M9 12h12m-4-4 4 4-4 4"/>',
    "key": '<circle cx="8" cy="8" r="5"/><path d="m12 12 9 9m-4-4 3-3m-6 0 3-3"/>',
    "edit": '<path d="m16 3 5 5-12 12-6 1 1-6L16 3zM13 6l5 5"/>',
    "repeat": '<path d="m17 2 4 4-4 4M3 11V6h18M7 22l-4-4 4-4m14-1v5H3"/>',
    "close": '<path d="m6 6 12 12M6 18 18 6"/>',
    "menu": '<path d="M4 6h16M4 12h16M4 18h16"/>',
}


@register.simple_tag
def icon(name):
    return format_html('<svg class="icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{}</svg>', mark_safe(ICONS.get(name, ICONS["file"])))


@register.filter
def money(value):
    return f"{Decimal(value or 0):,.2f}".replace(",", "\u00a0").replace(".", ",")


@register.simple_tag(takes_context=True)
def query_url(context, **kwargs):
    params = context["request"].GET.copy()
    for key, value in kwargs.items():
        if value is None:
            params.pop(key, None)
        else:
            params[key] = value
    return "?" + params.urlencode()
