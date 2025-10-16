from __future__ import annotations

from django import template
from django.utils.safestring import mark_safe

from ..services.markdown_renderer import render_to_html

register = template.Library()


@register.filter(name='render_card')
def render_card(value: str | None) -> str:
    html = render_to_html(value)
    return mark_safe(html)
