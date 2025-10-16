from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from ..models import Card, Deck, Review, SchedulingState
from ..scheduling import (
    GradeResult,
    SchedulerConfig,
    ensure_state,
    get_scheduler_config,
    grade_card,
    simulate_rating,
)

RATING_LABELS = {
    0: 'Again',
    1: 'Hard',
    2: 'Good',
    3: 'Easy',
}


@dataclass(frozen=True)
class TodaySummary:
    new_count: int
    review_count: int
    due_count: int


def _scoped_states(user, deck: Optional[Deck] = None):
    qs = SchedulingState.objects.select_related('card', 'card__deck').filter(card__user=user)
    if deck is not None:
        qs = qs.filter(card__deck_id__in=deck.descendant_ids())
    return qs


def get_today_summary(user, deck: Optional[Deck] = None, *, now=None) -> TodaySummary:
    now = now or timezone.now()
    states = _scoped_states(user, deck)
    learning_due = states.filter(queue_status__in=['learn', 'relearn'], due_at__lte=now)
    review_due = states.filter(queue_status='review', due_at__lte=now)
    new_cards = states.filter(queue_status='new')
    return TodaySummary(
        new_count=new_cards.count(),
        review_count=review_due.count(),
        due_count=learning_due.count() + review_due.count(),
    )


def get_next_card(user, deck: Optional[Deck] = None, *, config: Optional[SchedulerConfig] = None, now=None) -> Optional[Card]:
    now = now or timezone.now()
    config = config or get_scheduler_config()
    states = _scoped_states(user, deck)

    learning = states.filter(queue_status__in=['learn', 'relearn'], due_at__lte=now).order_by('due_at', 'card__created_at')
    state = learning.first()
    if state:
        return state.card

    review_due = states.filter(queue_status='review', due_at__lte=now).order_by('due_at', 'card__created_at').first()
    if review_due:
        return review_due.card

    if config.new_limit <= 0:
        return None

    new_cards_qs = states.filter(Q(queue_status='new') | Q(due_at__isnull=True, queue_status='new')).order_by('card__created_at')
    limited = new_cards_qs[: config.new_limit]
    first_state = limited.first()
    if first_state:
        return first_state.card
    return None


@transaction.atomic
def grade_card_for_user(
    *,
    user,
    card_id,
    rating: int,
    now=None,
    config: Optional[SchedulerConfig] = None,
) -> tuple[GradeResult, Review]:
    card = Card.objects.select_for_update().select_related('deck').get(id=card_id, user=user)
    config = config or get_scheduler_config()
    ensure_state(card, config)
    result = grade_card(card, rating, now=now, config=config)

    review = Review.objects.create(
        card=card,
        user=user,
        rating=rating,
        reviewed_at=now or timezone.now(),
        elapsed_days=result.elapsed_days,
        interval_before=result.interval_before,
        interval_after=result.interval_after,
        ease_before=result.ease_before,
        ease_after=result.ease_after,
    )

    return result, review


def build_rating_previews(card: Card, *, now=None, config: Optional[SchedulerConfig] = None) -> dict[int, dict[str, str]]:
    config = config or get_scheduler_config()
    now = now or timezone.now()
    state = ensure_state(card, config)
    previews: dict[int, dict[str, str]] = {}
    for rating in range(4):
        simulated_state = simulate_rating(state, rating, now=now, config=config)
        due_at = simulated_state.due_at
        previews[rating] = {
            'label': RATING_LABELS[rating],
            'due_at': due_at.isoformat() if due_at else None,
            'humanized': _humanize_due(now, due_at),
        }
    return previews


def _humanize_due(now, due_at: Optional[datetime]) -> str:
    if due_at is None:
        return 'Later'
    delta = due_at - now
    seconds = int(delta.total_seconds())
    if seconds <= 0:
        return 'Now'
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} h"
    days = hours // 24
    if days < 7:
        return f"{days} d"
    weeks = days // 7
    if weeks < 8:
        return f"{weeks} w"
    months = days // 30
    if months < 18:
        return f"{months} mo"
    years = days // 365
    return f"{years} y"
