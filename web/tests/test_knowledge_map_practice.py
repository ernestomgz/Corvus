import json

import pytest
from django.urls import reverse

from core.services.knowledge_maps import import_knowledge_map_from_payload

pytestmark = pytest.mark.django_db


def _payload():
    return {
        'map': {'slug': 'english', 'name': 'English', 'description': 'Levels'},
        'nodes': [{'key': 'a1', 'title': 'A1', 'children': [{'key': 'a1.verbs', 'title': 'Basic verbs'}]}],
    }


def test_practice_link_in_detail(client, user_factory):
    user = user_factory()
    client.force_login(user)
    result = import_knowledge_map_from_payload(user=user, payload=_payload())
    node_tag = result.knowledge_map.nodes.get(identifier='a1.verbs').tag_value

    response = client.get(reverse('knowledge_maps:detail', args=[result.knowledge_map.slug]))
    assert response.status_code == 200
    body = response.content.decode('utf-8')
    assert 'Practice this node' in body
    assert f'?tag={node_tag}' in body or f'?tag={node_tag.replace(":", "%3A")}' in body or f'?tag={node_tag.replace(":", "%3a")}' in body
