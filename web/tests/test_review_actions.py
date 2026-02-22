import pytest
from django.urls import reverse
from django.utils import timezone

from core.models import Card

pytestmark = pytest.mark.django_db


def test_defer_card_updates_due_date(client, card_factory):
    card = card_factory()
    assert client.login(email=card.user.email, password='password123')
    url = reverse('review:defer')
    before = timezone.now()
    response = client.post(url, {'card_id': str(card.id), 'days': 1})
    assert response.status_code == 200
    card.refresh_from_db()
    state = card.scheduling_state
    assert state.due_at is not None
    assert state.due_at >= before + timezone.timedelta(days=1)
    assert state.queue_status == 'review'


def test_delete_card_removes_record_and_advances(client, card_factory):
    card = card_factory()
    assert client.login(email=card.user.email, password='password123')
    url = reverse('review:delete')
    response = client.post(url, {'card_id': str(card.id)})
    assert response.status_code == 200
    assert not Card.objects.filter(id=card.id).exists()
