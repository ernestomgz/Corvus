import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_public_pages(client):
    for url in [reverse('accounts:login'), reverse('accounts:register')]:
        response = client.get(url)
        assert response.status_code == 200


def test_authenticated_pages(client, user_factory, deck_factory, card_factory):
    user = user_factory()
    deck = deck_factory(user=user)
    card_factory(user=user, deck=deck)
    assert client.login(email=user.email, password='password123')

    protected_urls = [
        reverse('decks:list'),
        reverse('cards:list'),
        reverse('review:today'),
        reverse('imports:dashboard'),
    ]
    for url in protected_urls:
        response = client.get(url)
        assert response.status_code == 200


@pytest.mark.django_db
def test_logout_redirect(client, user_factory):
    user = user_factory()
    assert client.login(email=user.email, password='password123')
    response = client.get(reverse('accounts:logout'), follow=True)
    assert response.status_code == 200
    assert response.request['PATH_INFO'] == reverse('accounts:login')
