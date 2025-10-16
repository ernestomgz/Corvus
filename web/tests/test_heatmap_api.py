from datetime import timedelta

import pytest
from django.utils import timezone

from core.models import Review, SchedulingState

pytestmark = pytest.mark.django_db


def test_heatmap_summary_returns_data(client, card_factory):
    card = card_factory()
    client.force_login(card.user)
    now = timezone.now()
    Review.objects.create(
        card=card,
        user=card.user,
        rating=3,
        reviewed_at=now,
        elapsed_days=0,
        interval_before=0,
        interval_after=1,
        ease_before=2.5,
        ease_after=2.6,
    )
    state = card.scheduling_state
    state.queue_status = 'review'
    state.due_at = now + timedelta(days=2)
    state.save()

    response = client.get('/api/v1/analytics/heatmap/')
    assert response.status_code == 200
    data = response.json()
    assert 'days' in data
    assert any(day['reviewed'] for day in data['days'])
    assert any(day['due'] for day in data['days'])
