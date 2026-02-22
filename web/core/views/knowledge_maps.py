from __future__ import annotations

import json
from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import KnowledgeMapImportForm
from ..models import KnowledgeMap
from ..services.knowledge_maps import KnowledgeMapImportError, import_knowledge_map_from_payload


def _build_node_tree(knowledge_map: KnowledgeMap) -> list[dict]:
    nodes = list(
        knowledge_map.nodes.order_by('parent_id', 'display_order', 'title', 'id')
    )
    children: dict[int | None, list] = defaultdict(list)
    for node in nodes:
        children[node.parent_id].append(node)

    def serialise(node):
        metadata_json = ''
        if node.metadata:
            try:
                metadata_json = json.dumps(node.metadata, indent=2)
            except (TypeError, ValueError):
                metadata_json = str(node.metadata)
        child_nodes = sorted(
            children.get(node.id, []),
            key=lambda item: (item.display_order, item.title.lower()),
        )
        return {
            'node': node,
            'children': [serialise(child) for child in child_nodes],
            'metadata_json': metadata_json,
        }

    root_nodes = sorted(
        children.get(None, []),
        key=lambda item: (item.display_order, item.title.lower()),
    )
    return [serialise(node) for node in root_nodes]


@login_required
def knowledge_map_list(request: HttpRequest) -> HttpResponse:
    maps = (
        KnowledgeMap.objects.for_user(request.user)
        .annotate(node_count=Count('nodes'))
        .order_by('name')
    )
    form = KnowledgeMapImportForm(request.POST or None, request.FILES or None)
    if request.method == 'POST':
        if form.is_valid():
            payload = form.cleaned_data['payload']
            try:
                result = import_knowledge_map_from_payload(user=request.user, payload=payload)
            except KnowledgeMapImportError as exc:
                form.add_error(None, str(exc))
            else:
                verb = 'created' if result.created_map else 'updated'
                messages.success(
                    request,
                    f'Knowledge map "{result.knowledge_map.name}" {verb} '
                    f'with {result.created_nodes} nodes.',
                )
                return redirect('knowledge_maps:detail', slug=result.knowledge_map.slug)
        else:
            messages.error(request, 'Please correct the errors below.')
    context = {
        'maps': maps,
        'form': form,
    }
    return render(request, 'core/knowledge_maps/list.html', context)


@login_required
def knowledge_map_detail(request: HttpRequest, slug: str) -> HttpResponse:
    knowledge_map = get_object_or_404(KnowledgeMap, user=request.user, slug=slug)
    node_tree = _build_node_tree(knowledge_map)
    metadata_preview = ''
    if knowledge_map.metadata:
        metadata_preview = json.dumps(knowledge_map.metadata, indent=2)
    first_node = knowledge_map.nodes.order_by('parent_id', 'display_order', 'title').first()
    graph_nodes = [
        {
            'id': node.id,
            'parent_id': node.parent_id,
            'title': node.title,
            'tag': node.tag_value,
            'definition': node.definition,
            'guidance': node.guidance,
        }
        for node in knowledge_map.nodes.order_by('parent_id', 'display_order', 'title')
    ]
    context = {
        'knowledge_map': knowledge_map,
        'node_tree': node_tree,
        'node_count': knowledge_map.nodes.count(),
        'metadata_preview': metadata_preview,
        'graph_nodes': graph_nodes,
        'first_node_tag': first_node.tag_value if first_node else '',
    }
    return render(request, 'core/knowledge_maps/detail.html', context)
