from __future__ import annotations

import re
from functools import lru_cache

import bleach
from markdown_it import MarkdownIt
from mdit_py_plugins.dollarmath import dollarmath_plugin


_MATH_BLOCK_PATTERN = re.compile(r"\[\$\$](?P<body>.+?)\[/\$\$]", re.DOTALL)
_HTML_SNIFFER = re.compile(r"<\s*([a-zA-Z!/?])")

_ALLOWED_TAGS = sorted(
    {
        *bleach.sanitizer.ALLOWED_TAGS,
        'p', 'pre', 'code', 'span', 'div', 'img', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'ul', 'ol', 'li', 'blockquote', 'hr', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
        'em', 'strong', 'a', 'br', 'sup', 'sub', 'figure', 'figcaption', 'audio', 'source',
    }
)

_ALLOWED_ATTRIBUTES = {
    **bleach.sanitizer.ALLOWED_ATTRIBUTES,
    'a': ['href', 'title', 'name', 'target', 'rel'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    'span': ['class'],
    'div': ['class'],
    'code': ['class'],
    'pre': ['class'],
    'audio': ['src', 'controls'],
    'source': ['src', 'type'],
}

_ALLOWED_PROTOCOLS = ['http', 'https', 'data']

_MATH_PLUGIN_OPTIONS = {'allow_inline': True, 'allow_display': True}

_markdown = (
    MarkdownIt('commonmark', {'html': True, 'linkify': True, 'breaks': True})
    .enable('table')
    .enable('strikethrough')
)
_markdown.use(dollarmath_plugin, MATH_PLUGIN_OPTIONS)


def _normalise_legacy_math(text: str) -> str:
    def _replace(match: re.Match) -> str:
        return f"$$\n{match.group('body').strip()}\n$$"

    return _MATH_BLOCK_PATTERN.sub(_replace, text)


def _looks_like_html(value: str) -> bool:
    return bool(_HTML_SNIFFER.search(value))


@lru_cache(maxsize=256)
def _render_markdown_cached(raw: str) -> str:
    prepared = _normalise_legacy_math(raw)
    rendered = _markdown.render(prepared)
    return rendered


def render_to_html(content: str | None) -> str:
    if not content:
        return ''
    if _looks_like_html(content):
        html = content
    else:
        html = _render_markdown_cached(content)
    cleaned = bleach.clean(html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRIBUTES, protocols=_ALLOWED_PROTOCOLS, strip=True)
    return cleaned
