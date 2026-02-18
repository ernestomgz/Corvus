from __future__ import annotations

import re
from typing import Optional, Tuple

from django.utils.text import slugify

KNOWLEDGE_TAG_PREFIX = 'km'
MAP_SLUG_PATTERN = re.compile(r'^[a-z0-9][a-z0-9_-]{0,63}$')
NODE_IDENTIFIER_PATTERN = re.compile(r'^[a-z0-9][a-z0-9._-]{0,95}$')
TAG_PATTERN = re.compile(
    rf'^{KNOWLEDGE_TAG_PREFIX}:(?P<map>[a-z0-9][a-z0-9_-]{{0,63}}):(?P<node>[a-z0-9][a-z0-9._-]{{0,95}})$'
)


def normalise_map_slug(raw: str) -> str:
    slug = slugify(raw or '')
    if not slug:
        raise ValueError('knowledge map slug cannot be empty')
    if len(slug) > 64:
        raise ValueError('knowledge map slug must be <= 64 characters')
    if not MAP_SLUG_PATTERN.match(slug):
        raise ValueError('knowledge map slug must contain only lowercase letters, numbers, hyphen, or underscore')
    return slug


def normalise_node_identifier(raw: str) -> str:
    value = (raw or '').strip().lower()
    value = value.replace(' ', '-').replace('/', '.')
    if not value:
        raise ValueError('knowledge node key cannot be empty')
    normalised = re.sub(r'[^a-z0-9._-]', '-', value)
    normalised = re.sub(r'-{2,}', '-', normalised)
    normalised = normalised.strip('-')
    if not normalised:
        raise ValueError('knowledge node key normalised to empty value')
    if len(normalised) > 96:
        raise ValueError('knowledge node key must be <= 96 characters')
    if not NODE_IDENTIFIER_PATTERN.match(normalised):
        raise ValueError('knowledge node key must contain letters, numbers, ".", "_" or "-"')
    return normalised


def build_knowledge_tag(map_slug: str, node_identifier: str) -> str:
    if not MAP_SLUG_PATTERN.match(map_slug):
        raise ValueError('invalid knowledge map slug for tag')
    if not NODE_IDENTIFIER_PATTERN.match(node_identifier):
        raise ValueError('invalid knowledge node identifier for tag')
    return f'{KNOWLEDGE_TAG_PREFIX}:{map_slug}:{node_identifier}'


def parse_knowledge_tag(tag_value: str) -> Optional[Tuple[str, str]]:
    match = TAG_PATTERN.match(tag_value or '')
    if not match:
        return None
    return match.group('map'), match.group('node')
