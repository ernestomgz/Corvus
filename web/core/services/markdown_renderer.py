from __future__ import annotations

import re
from functools import lru_cache

import bleach
from markdown_it import MarkdownIt
from mdit_py_plugins.dollarmath import dollarmath_plugin


_MATH_BLOCK_PATTERN = re.compile(r"\[\$\$](?P<body>.+?)\[/\$\$]", re.DOTALL)
_HTML_SNIFFER = re.compile(r"<\s*([a-zA-Z!/?])")
MATH_SIGNAL_PATTERN = re.compile(r'(\\[a-zA-Z]+|\$|\\\[|\\\]|\^|\\\(|\\\)|\\\{|\\\}|\\\/)')

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

_MATH_PLUGIN_CANDIDATES: tuple[dict[str, bool], ...] = (
    {'allow_inline': True, 'allow_display': True},
    {'allow_inline': True, 'allow_block': True},
    {'allow_block': True},
    {},
)


def _new_markdown_instance() -> MarkdownIt:
    md = MarkdownIt('commonmark', {'html': True, 'linkify': True, 'breaks': True})
    md.enable('table')
    md.enable('strikethrough')
    return md


def _build_markdown() -> MarkdownIt:
    for options in _MATH_PLUGIN_CANDIDATES:
        md = _new_markdown_instance()
        try:
            md.use(dollarmath_plugin, **options)
        except TypeError:
            continue
        return md
    md = _new_markdown_instance()
    md.use(dollarmath_plugin)
    return md


_markdown = _build_markdown()


def _contains_math_markup(value: str) -> bool:
    return bool(MATH_SIGNAL_PATTERN.search(value))


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
    html = re.sub(r'<script.*?>.*?</script>', '', html, flags=re.IGNORECASE | re.DOTALL)
    cleaned = bleach.clean(html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRIBUTES, protocols=_ALLOWED_PROTOCOLS, strip=True)
    if _contains_math_markup(content) and 'math' not in cleaned:
        inner = cleaned.strip()
        if inner.startswith('<p>') and inner.endswith('</p>'):
            inner = inner[3:-4]
        cleaned = f'<span class="math math-inline">{inner}</span>'
    return cleaned
