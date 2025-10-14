from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from django.conf import settings
from django.utils import timezone

from .models import Card, SchedulingState


@dataclass(frozen=True)
class SchedulerConfig:
    learning_steps_minutes: list[int]
    graduating_interval_days: int
    easy_bonus_days: int
    initial_ease: float
    lapse_step_minutes: int
    leech_threshold: int
    bury_siblings: bool
    day_cutoff_hour: int
    new_limit: int
    review_limit: int


@dataclass
class GradeResult:
    state: SchedulingState
    interval_before: int
    interval_after: int
    ease_before: float
    ease_after: float
    elapsed_days: int
    rating: int
    became_leech: bool
    was_lapse: bool


def get_scheduler_config() -> SchedulerConfig:
    cfg = settings.SCHEDULER_DEFAULTS
    return SchedulerConfig(
        learning_steps_minutes=list(cfg['learning_steps_minutes']),
        graduating_interval_days=cfg['graduating_interval_days'],
        easy_bonus_days=cfg['easy_bonus_days'],
        initial_ease=cfg['initial_ease'],
        lapse_step_minutes=cfg['lapse_step_minutes'],
        leech_threshold=cfg['leech_threshold'],
        bury_siblings=cfg['bury_siblings'],
        day_cutoff_hour=cfg['day_cutoff_hour'],
        new_limit=cfg['new_limit'],
        review_limit=cfg['review_limit'],
    )


def _minutes_delta(minutes: int) -> timedelta:
    return timedelta(minutes=minutes)


def _elapsed_days(state: SchedulingState, now: datetime) -> int:
    if state.due_at is None:
        return 0
    delta = timezone.localtime(now) - timezone.localtime(state.due_at)
    return max(0, int(delta.total_seconds() // 86400))


def ensure_state(card: Card, config: Optional[SchedulerConfig] = None) -> SchedulingState:
    config = config or get_scheduler_config()
    state, _ = SchedulingState.objects.get_or_create(
        card=card,
        defaults={
            'ease': config.initial_ease,
            'queue_status': 'new',
        },
    )
    return state


def grade_card(card: Card, rating: int, *, now: Optional[datetime] = None, config: Optional[SchedulerConfig] = None) -> GradeResult:
    if rating not in (0, 1, 2, 3):
        raise ValueError('rating must be 0..3')
    config = config or get_scheduler_config()
    now = now or timezone.now()
    state = ensure_state(card, config)

    interval_before = state.interval_days
    ease_before = state.ease
    elapsed_days = _elapsed_days(state, now)
    became_leech = False
    was_lapse = False

    if state.queue_status in ('new', 'learn'):
        _handle_learning(card, state, rating, now, config)
    elif state.queue_status == 'review':
        was_lapse = _handle_review(card, state, rating, now, config)
    elif state.queue_status == 'relearn':
        _handle_relearn(card, state, rating, now, config)
    else:
        _handle_learning(card, state, rating, now, config)

    if state.lapses >= config.leech_threshold and 'leech' not in card.tags:
        card.tags.append('leech')
        card.save(update_fields=['tags'])
        became_leech = True

    state.last_rating = rating
    state.save()

    return GradeResult(
        state=state,
        interval_before=interval_before,
        interval_after=state.interval_days,
        ease_before=ease_before,
        ease_after=state.ease,
        elapsed_days=elapsed_days,
        rating=rating,
        became_leech=became_leech,
        was_lapse=was_lapse,
    )


def _handle_learning(card: Card, state: SchedulingState, rating: int, now: datetime, config: SchedulerConfig) -> None:
    steps = config.learning_steps_minutes or [1]

    if rating == 0:  # Again
        state.queue_status = 'learn'
        state.learning_step_index = 0
        state.due_at = now + _minutes_delta(steps[0])
        return

    if rating == 1:  # Hard
        state.queue_status = 'learn'
        index = min(max(state.learning_step_index, 0), len(steps) - 1)
        state.learning_step_index = index
        state.due_at = now + _minutes_delta(steps[index])
        return

    if rating == 2:  # Good
        index = max(state.learning_step_index, 0)
        if index >= len(steps):
            _graduate_to_review(state, now, config, config.graduating_interval_days)
            return
        index = min(index, len(steps) - 1)
        state.queue_status = 'learn'
        state.due_at = now + _minutes_delta(steps[index])
        state.learning_step_index = index + 1
        return

    if rating == 3:  # Easy
        _graduate_to_review(state, now, config, config.easy_bonus_days)


def _graduate_to_review(state: SchedulingState, now: datetime, config: SchedulerConfig, interval_days: int) -> None:
    state.queue_status = 'review'
    state.learning_step_index = 0
    state.reps += 1
    state.interval_days = max(1, interval_days)
    state.due_at = now + timedelta(days=state.interval_days)


def _handle_review(card: Card, state: SchedulingState, rating: int, now: datetime, config: SchedulerConfig) -> bool:
    if rating == 0:  # Again
        state.reps += 1
        state.lapses += 1
        state.queue_status = 'relearn'
        state.learning_step_index = 0
        state.due_at = now + _minutes_delta(config.lapse_step_minutes)
        state.ease = max(1.3, state.ease - 0.2)
        return True

    state.reps += 1
    if rating == 1:  # Hard
        state.ease = max(1.3, state.ease - 0.15)
        new_interval = max(1, int(round(max(state.interval_days, 1) * 1.2)))
    elif rating == 2:  # Good
        base = max(state.interval_days, config.graduating_interval_days)
        new_interval = max(1, int(round(base * state.ease)))
    else:  # Easy
        state.ease = max(1.3, state.ease + 0.15)
        base = max(state.interval_days, config.graduating_interval_days)
        good_interval = max(1, int(round(base * state.ease)))
        new_interval = good_interval + config.easy_bonus_days

    state.interval_days = new_interval
    state.queue_status = 'review'
    state.learning_step_index = 0
    state.due_at = now + timedelta(days=state.interval_days)
    return False


def _handle_relearn(card: Card, state: SchedulingState, rating: int, now: datetime, config: SchedulerConfig) -> None:
    if rating in (0, 1):
        state.due_at = now + _minutes_delta(config.lapse_step_minutes)
        state.learning_step_index = 0
        return

    previous_interval = max(state.interval_days, 1)
    if rating == 2:
        new_interval = max(1, int(round(previous_interval * 0.7)))
    else:
        state.ease = max(1.3, state.ease + 0.15)
        new_interval = max(1, int(round(previous_interval * 0.7))) + config.easy_bonus_days

    state.interval_days = new_interval
    state.queue_status = 'review'
    state.learning_step_index = 0
    state.due_at = now + timedelta(days=state.interval_days)
    state.reps += 1
