import bleach
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

ALLOWED_TAGS = [
    "p", "br", "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "strong", "em", "b", "i", "u",
    "blockquote", "a", "img", "table", "thead", "tbody",
    "tr", "th", "td", "div", "span", "hr",
]

ALLOWED_ATTRIBUTES = {
    "*": ["class"],
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "title", "width", "height"],
    "th": ["colspan", "rowspan"],
    "td": ["colspan", "rowspan"],
}

ALLOWED_PROTOCOLS = ["http", "https", "mailto", "tel"]


@register.filter(name="sanitize_html")
def sanitize_html(value):
    cleaned = bleach.clean(
        value or "",
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )
    return mark_safe(cleaned)
