import json

import pytest
from django.urls import reverse

from core.models import KnowledgeMap
from core.services.knowledge_maps import KnowledgeMapImportError, import_knowledge_map_from_payload
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def _sample_payload():
    return {
        'map': {
            'slug': 'demo-grid',
            'name': 'Demo Grid',
            'description': 'Example map',
            'metadata': {'version': 1},
        },
        'nodes': [
            {
                'key': 'root',
                'title': 'Root Node',
                'definition': 'Top level branch',
                'guidance': 'Use sparingly',
                'children': [
                    {'key': 'root.scope', 'title': 'Scope', 'definition': 'Covers limits'},
                    {'key': 'root.depth', 'title': 'Depth', 'definition': 'Covers mastery tiers'},
                ],
            }
        ],
    }


def test_import_knowledge_map_creates_tree(user_factory):
    user = user_factory()
    payload = _sample_payload()

    result = import_knowledge_map_from_payload(user=user, payload=payload)

    assert result.created_map is True
    assert result.created_nodes == 3
    knowledge_map = result.knowledge_map
    assert knowledge_map.slug == 'demo-grid'
    assert knowledge_map.nodes.count() == 3
    root_node = knowledge_map.nodes.get(identifier='root')
    child_node = knowledge_map.nodes.get(identifier='root.scope')
    assert child_node.parent_id == root_node.id
    assert child_node.tag_value == 'km:demo-grid:root.scope'


def test_import_replaces_existing_map(user_factory):
    user = user_factory()
    payload = _sample_payload()
    import_knowledge_map_from_payload(user=user, payload=payload)

    payload['nodes'] = [
        {'key': 'updated', 'title': 'Updated Root', 'definition': 'New tree'},
    ]
    result = import_knowledge_map_from_payload(user=user, payload=payload)

    assert result.created_map is False
    assert result.replaced_nodes == 3
    assert result.created_nodes == 1
    knowledge_map = KnowledgeMap.objects.get(user=user, slug='demo-grid')
    assert knowledge_map.nodes.count() == 1
    node = knowledge_map.nodes.first()
    assert node and node.identifier == 'updated'


def test_import_rejects_duplicate_node_keys(user_factory):
    user = user_factory()
    payload = _sample_payload()
    payload['nodes'].append({'key': 'root', 'title': 'Duplicate', 'definition': 'invalid'})

    with pytest.raises(KnowledgeMapImportError):
        import_knowledge_map_from_payload(user=user, payload=payload)


def test_api_import_and_fetch_knowledge_map(api_client):
    user = UserFactory()
    api_client.force_login(user)
    payload = _sample_payload()

    response = api_client.post(
        '/api/knowledge-maps/import',
        data=json.dumps(payload),
        content_type='application/json',
    )
    assert response.status_code == 201
    body = response.json()
    assert body['slug'] == 'demo-grid'
    assert body['node_count'] == 3

    list_response = api_client.get('/api/knowledge-maps/')
    assert list_response.status_code == 200
    listed = list_response.json()
    assert listed and listed[0]['slug'] == 'demo-grid'
    assert listed[0]['tag_prefix'] == 'km:demo-grid:'

    detail_response = api_client.get('/api/knowledge-maps/demo-grid')
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail['slug'] == 'demo-grid'
    assert detail['nodes'][0]['children'][0]['tag'] == 'km:demo-grid:root.scope'


def test_knowledge_map_ui_import_flow(client):
    user = UserFactory()
    client.force_login(user)
    payload = _sample_payload()

    response = client.post(
        reverse('knowledge_maps:list'),
        {'json_text': json.dumps(payload)},
    )

    assert response.status_code == 302
    assert KnowledgeMap.objects.filter(user=user, slug='demo-grid').exists()


def test_knowledge_map_detail_view_displays_tree(client):
    user = UserFactory()
    result = import_knowledge_map_from_payload(user=user, payload=_sample_payload())
    client.force_login(user)

    response = client.get(reverse('knowledge_maps:detail', args=[result.knowledge_map.slug]))

    assert response.status_code == 200
    body = response.content.decode()
    assert 'Root Node' in body
    assert 'km:demo-grid:root.scope' in body
