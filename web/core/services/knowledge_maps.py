from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable

from django.db import transaction

from core.knowledge_tags import normalise_map_slug, normalise_node_identifier
from core.models import KnowledgeMap, KnowledgeNode


class KnowledgeMapImportError(ValueError):
    """Raised when a knowledge map payload cannot be ingested."""


@dataclass
class KnowledgeMapImportResult:
    knowledge_map: KnowledgeMap
    created_nodes: int
    replaced_nodes: int
    created_map: bool


def _coerce_metadata(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    return {}


def _coerce_text(value: Any) -> str:
    if value is None:
        return ''
    return str(value).strip()


def _normalise_sources(value: Any) -> list[dict]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [{'label': text}] if text else []
    if isinstance(value, dict):
        cleaned = {
            str(key): _coerce_text(val)
            for key, val in value.items()
            if isinstance(key, str) and _coerce_text(val)
        }
        return [cleaned] if cleaned else []
    if isinstance(value, list):
        compiled: list[dict] = []
        for entry in value:
            if isinstance(entry, str):
                text = entry.strip()
                if text:
                    compiled.append({'label': text})
                continue
            if isinstance(entry, dict):
                cleaned = {
                    str(key): _coerce_text(val)
                    for key, val in entry.items()
                    if isinstance(key, str) and _coerce_text(val)
                }
                if cleaned:
                    compiled.append(cleaned)
                continue
            raise KnowledgeMapImportError('sources entries must be strings or objects')
        return compiled
    raise KnowledgeMapImportError('sources must be a string, object, or array')


def _extract_children(data: dict) -> list[dict]:
    children = data.get('children', [])
    if children is None:
        return []
    if not isinstance(children, list):
        raise KnowledgeMapImportError('children must be a list')
    return [child for child in children if isinstance(child, dict)]


def _node_title(data: dict) -> str:
    title = data.get('title') or data.get('name')
    title_text = _coerce_text(title)
    if not title_text:
        raise KnowledgeMapImportError('each knowledge node requires a title')
    return title_text


def _node_guidance(data: dict) -> str:
    guidance = data.get('guidance') or data.get('instructions') or data.get('notes')
    return _coerce_text(guidance)


def _node_identifier(data: dict) -> str:
    candidate = data.get('key') or data.get('identifier') or data.get('id')
    if not candidate:
        raise KnowledgeMapImportError('each knowledge node requires a "key" field')
    return normalise_node_identifier(str(candidate))


def _node_metadata(data: dict) -> dict:
    meta = data.get('metadata') or data.get('attributes') or {}
    return _coerce_metadata(meta)


def _create_node(
    *,
    knowledge_map: KnowledgeMap,
    parent: KnowledgeNode | None,
    node_data: dict,
    order: int,
    seen_identifiers: set[str],
    summary: dict,
) -> None:
    identifier = _node_identifier(node_data)
    if identifier in seen_identifiers:
        raise KnowledgeMapImportError(f'duplicate node key detected: {identifier}')
    seen_identifiers.add(identifier)
    node = KnowledgeNode.objects.create(
        knowledge_map=knowledge_map,
        parent=parent,
        identifier=identifier,
        title=_node_title(node_data),
        definition=_coerce_text(node_data.get('definition')),
        guidance=_node_guidance(node_data),
        sources=_normalise_sources(node_data.get('sources')),
        metadata=_node_metadata(node_data),
        display_order=order,
    )
    summary['created_nodes'] += 1
    for child_order, child in enumerate(_extract_children(node_data)):
        _create_node(
            knowledge_map=knowledge_map,
            parent=node,
            node_data=child,
            order=child_order,
            seen_identifiers=seen_identifiers,
            summary=summary,
        )


@transaction.atomic
def import_knowledge_map_from_payload(*, user, payload: dict) -> KnowledgeMapImportResult:
    if not isinstance(payload, dict):
        raise KnowledgeMapImportError('payload must be a JSON object')
    map_info = payload.get('map')
    if not isinstance(map_info, dict):
        raise KnowledgeMapImportError('"map" object is required')
    name = _coerce_text(map_info.get('name'))
    if not name:
        raise KnowledgeMapImportError('map.name is required')
    slug_source = map_info.get('slug') or name
    slug = normalise_map_slug(slug_source)
    description = _coerce_text(map_info.get('description'))
    metadata = _coerce_metadata(map_info.get('metadata'))

    nodes_data = payload.get('nodes')
    if not isinstance(nodes_data, list):
        raise KnowledgeMapImportError('"nodes" must be a list')
    if not nodes_data:
        raise KnowledgeMapImportError('at least one knowledge node is required')

    knowledge_map, created = KnowledgeMap.objects.get_or_create(
        user=user,
        slug=slug,
        defaults={'name': name, 'description': description, 'metadata': metadata},
    )
    replaced_nodes = 0
    if not created:
        replaced_nodes = knowledge_map.nodes.count()
        knowledge_map.name = name
        knowledge_map.description = description
        knowledge_map.metadata = metadata
        knowledge_map.save(update_fields=['name', 'description', 'metadata', 'updated_at'])
        knowledge_map.nodes.all().delete()

    summary = {'created_nodes': 0}
    seen_identifiers: set[str] = set()
    for order, node_data in enumerate(nodes_data):
        if not isinstance(node_data, dict):
            raise KnowledgeMapImportError('nodes must be objects')
        _create_node(
            knowledge_map=knowledge_map,
            parent=None,
            node_data=node_data,
            order=order,
            seen_identifiers=seen_identifiers,
            summary=summary,
        )

    knowledge_map.refresh_from_db()
    return KnowledgeMapImportResult(
        knowledge_map=knowledge_map,
        created_nodes=summary['created_nodes'],
        replaced_nodes=replaced_nodes,
        created_map=created,
    )
