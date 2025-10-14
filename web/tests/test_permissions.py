import json

import pytest

from core.services.review import get_next_card, grade_card_for_user
from core.models import Card

pytestmark = pytest.mark.django_db


def test_user_isolation_on_cards_and_reviews(user_factory, deck_factory, card_factory):
    user_a = user_factory()
    user_b = user_factory()
    deck_a = deck_factory(user=user_a)
    deck_b = deck_factory(user=user_b)
    card_a = card_factory(user=user_a, deck=deck_a)
    card_b = card_factory(user=user_b, deck=deck_b)

    next_card = get_next_card(user_a)
    assert next_card == card_a

    with pytest.raises(Card.DoesNotExist):
        grade_card_for_user(user=user_a, card_id=card_b.id, rating=2)


def test_review_endpoints_scope_user_data_only(api_client, user_factory, deck_factory, card_factory):
    user = user_factory()
    other = user_factory()
    deck_user = deck_factory(user=user)
    deck_other = deck_factory(user=other)
    card_user = card_factory(user=user, deck=deck_user)
    card_other = card_factory(user=other, deck=deck_other)

    api_client.force_login(user)
    response = api_client.post('/api/v1/review/next', data=json.dumps({}), content_type='application/json')
    assert response.status_code == 200
    data = response.json()
    assert data['card_id'] == str(card_user.id)

    response = api_client.post(
        '/api/v1/review/grade',
        data=json.dumps({'card_id': str(card_other.id), 'rating': 2}),
        content_type='application/json',
    )
    assert response.status_code == 404
