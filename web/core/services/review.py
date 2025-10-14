from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from ..models import Card, Deck, Review, SchedulingState
from ..scheduling import GradeResult, SchedulerConfig, get_scheduler_config, grade_card, ensure_state


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
def grade_card_for_user(*, user, card_id, rating: int, now=None, config: Optional[SchedulerConfig] = None) -> GradeResult:
    card = Card.objects.select_for_update().select_related('deck').get(id=card_id, user=user)
    config = config or get_scheduler_config()
    ensure_state(card, config)
    result = grade_card(card, rating, now=now, config=config)

    Review.objects.create(
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

    return result
