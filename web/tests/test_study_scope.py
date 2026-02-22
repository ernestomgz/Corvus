import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_study_scope_filters_by_tag(client, user_factory, deck_factory, card_factory):
    user = user_factory()
    deck = deck_factory(user=user)
    tag_value = 'km:english:a1.basic-verbs'
    matching = card_factory(user=user, deck=deck, front_md='Verb card', tags=[tag_value])
    card_factory(user=user, deck=deck, front_md='Other card', tags=['km:math:calc'])
    assert client.login(email=user.email, password='password123')

    url = reverse('review:next') + f'?tag={tag_value}'
    response = client.get(url)
    assert response.status_code == 200
    assert 'Verb card' in response.content.decode('utf-8')
    assert 'Other card' not in response.content.decode('utf-8')


def test_study_page_renders_with_scope(client, user_factory, deck_factory):
    user = user_factory()
    deck = deck_factory(user=user)
    assert client.login(email=user.email, password='password123')
    url = reverse('review:study') + f'?deck_id={deck.id}'
    response = client.get(url)
    assert response.status_code == 200
    body = response.content.decode('utf-8')
    assert 'Focused review' in body
    assert str(deck.full_path()) in body
