import json

import pytest

pytestmark = pytest.mark.django_db


def test_review_flow_cycle(api_client, user_factory, deck_factory, card_factory):
    user = user_factory()
    deck = deck_factory(user=user)
    card = card_factory(user=user, deck=deck)

    api_client.force_login(user)

    next_resp = api_client.post('/api/v1/review/next', data=json.dumps({'deck_id': deck.id}), content_type='application/json')
    assert next_resp.status_code == 200
    card_id = next_resp.json()['card_id']
    assert card_id == str(card.id)

    reveal_resp = api_client.post('/api/v1/review/reveal', data=json.dumps({'card_id': card_id}), content_type='application/json')
    assert reveal_resp.status_code == 200
    assert 'back_md' in reveal_resp.json()

    grade_resp = api_client.post(
        '/api/v1/review/grade',
        data=json.dumps({'card_id': card_id, 'rating': 2, 'deck_id': deck.id}),
        content_type='application/json',
    )
    assert grade_resp.status_code == 200
    assert grade_resp.json()['next_available'] is False
