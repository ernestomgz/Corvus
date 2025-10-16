from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from django.contrib.auth.decorators import login_required
from django.db.models.functions import ExtractYear
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from ..models import Card, Deck, Review, SchedulingState
from ..scheduling import ensure_state
from ..services.review import build_rating_previews, get_next_card, get_today_summary, grade_card_for_user

REVIEW_HISTORY_SESSION_KEY = 'review_history'
REVIEW_HISTORY_DECK_KEY = 'review_history_deck'
REVIEW_HISTORY_LIMIT = 20


def _serialize_state(state: SchedulingState) -> Dict[str, Any]:
    return {
        'queue_status': state.queue_status,
        'interval_days': state.interval_days,
        'ease': state.ease,
        'reps': state.reps,
        'lapses': state.lapses,
        'due_at': state.due_at.isoformat() if state.due_at else None,
        'learning_step_index': state.learning_step_index,
        'last_rating': state.last_rating,
    }


def _restore_state_from_snapshot(state: SchedulingState, snapshot: Dict[str, Any]) -> None:
    state.queue_status = snapshot.get('queue_status', state.queue_status)
    state.interval_days = int(snapshot.get('interval_days', state.interval_days or 0))
    state.ease = float(snapshot.get('ease', state.ease))
    state.reps = int(snapshot.get('reps', state.reps or 0))
    state.lapses = int(snapshot.get('lapses', state.lapses or 0))
    state.learning_step_index = int(snapshot.get('learning_step_index', state.learning_step_index or 0))
    last_rating = snapshot.get('last_rating')
    state.last_rating = int(last_rating) if last_rating is not None else None
    due_at = snapshot.get('due_at')
    if due_at:
        try:
            state.due_at = datetime.fromisoformat(due_at)
        except (TypeError, ValueError):
            state.due_at = state.due_at
    else:
        state.due_at = None
    state.save()


def _get_review_history(request: HttpRequest) -> List[Dict[str, Any]]:
    history = request.session.get(REVIEW_HISTORY_SESSION_KEY, [])
    if not isinstance(history, list):
        history = []
    return history


def _set_review_history(request: HttpRequest, history: List[Dict[str, Any]]) -> None:
    request.session[REVIEW_HISTORY_SESSION_KEY] = history
    request.session.modified = True


def _push_review_history_entry(request: HttpRequest, entry: Dict[str, Any]) -> None:
    history = list(_get_review_history(request))
    history.append(entry)
    if len(history) > REVIEW_HISTORY_LIMIT:
        history = history[-REVIEW_HISTORY_LIMIT:]
    _set_review_history(request, history)


def _pop_review_history_entry(request: HttpRequest, deck: Optional[Deck] = None) -> Optional[Dict[str, Any]]:
    history = list(_get_review_history(request))
    deck_key = deck.id if deck else None
    if not history:
        return None
    while history:
        entry = history.pop()
        if deck_key is None or entry.get('filter_deck_id') == deck_key:
            _set_review_history(request, history)
            return entry
    _set_review_history(request, history)
    return None


def _ensure_history_scope(request: HttpRequest, deck: Optional[Deck]) -> None:
    deck_key = deck.id if deck else None
    last_key = request.session.get(REVIEW_HISTORY_DECK_KEY)
    if last_key != deck_key:
        _set_review_history(request, [])
    request.session[REVIEW_HISTORY_DECK_KEY] = deck_key
    request.session.modified = True


def _resolve_deck(request: HttpRequest):
    deck_id = request.POST.get('deck_id') or request.GET.get('deck_id')
    if not deck_id:
        return None
    try:
        return Deck.objects.get(id=deck_id, user=request.user)
    except Deck.DoesNotExist as exc:  # pragma: no cover
        raise Http404('Deck not found') from exc


@login_required
def review_today(request: HttpRequest) -> HttpResponse:
    deck = None
    deck_id = request.GET.get('deck_id')
    if deck_id:
        deck = get_object_or_404(Deck, id=deck_id, user=request.user)
    _ensure_history_scope(request, deck)
    decks = Deck.objects.for_user(request.user)
    summary = get_today_summary(request.user, deck)
    current_year = timezone.now().year
    selected_year_raw = request.GET.get('year')
    try:
        selected_year = int(selected_year_raw) if selected_year_raw else current_year
    except (TypeError, ValueError):
        selected_year = current_year
    deck_scope_ids = deck.descendant_ids() if deck else None
    review_years_qs = Review.objects.filter(user=request.user)
    due_years_qs = SchedulingState.objects.filter(card__user=request.user, due_at__isnull=False)
    if deck_scope_ids:
        review_years_qs = review_years_qs.filter(card__deck_id__in=deck_scope_ids)
        due_years_qs = due_years_qs.filter(card__deck_id__in=deck_scope_ids)
    review_years = set(review_years_qs.annotate(year=ExtractYear('reviewed_at')).values_list('year', flat=True))
    due_years = set(due_years_qs.annotate(year=ExtractYear('due_at')).values_list('year', flat=True))
    available_years = {int(year) for year in review_years.union(due_years) if year is not None}
    available_years.update({current_year, selected_year})
    year_options = sorted(available_years, reverse=True) or [current_year]
    context = {
        'decks': decks,
        'active_deck': deck,
        'summary': summary,
        'heatmap_years': year_options,
        'selected_year': selected_year,
        'user_selected_year': bool(selected_year_raw),
    }
    return render(request, 'core/review/today.html', context)


@login_required
def review_next(request: HttpRequest) -> HttpResponse:
    deck = _resolve_deck(request)
    card = get_next_card(request.user, deck)
    summary = get_today_summary(request.user, deck)
    can_undo = bool(_get_review_history(request))
    if not card:
        return render(
            request,
            'core/review/partials/empty.html',
            {
                'summary': summary,
                'deck': deck,
                'can_undo': can_undo,
            },
        )
    ensure_state(card)
    now = timezone.now()
    rating_previews = build_rating_previews(card, now=now)
    return render(
        request,
        'core/review/partials/front.html',
            {
                'card': card,
                'deck': deck,
                'summary': summary,
                'rating_previews': rating_previews,
                'can_undo': can_undo,
            },
        )


@login_required
def review_reveal(request: HttpRequest) -> HttpResponse:
    card_id = request.POST.get('card_id')
    if not card_id:
        raise Http404('card not provided')
    card = get_object_or_404(Card.objects.select_related('deck', 'scheduling_state'), id=card_id, user=request.user)
    deck = _resolve_deck(request)
    summary = get_today_summary(request.user, deck)
    ensure_state(card)
    now = timezone.now()
    rating_previews = build_rating_previews(card, now=now)
    can_undo = bool(_get_review_history(request))
    return render(
        request,
        'core/review/partials/back.html',
        {
            'card': card,
            'deck': deck,
            'summary': summary,
            'rating_previews': rating_previews,
            'can_undo': can_undo,
        },
    )


@login_required
def review_grade(request: HttpRequest) -> HttpResponse:
    card_id = request.POST.get('card_id')
    rating = request.POST.get('rating')
    if card_id is None or rating is None:
        raise Http404('Missing card or rating')
    deck = _resolve_deck(request)
    now = timezone.now()
    try:
        rating_value = int(rating)
    except (TypeError, ValueError):
        raise Http404('Invalid rating')
    card = get_object_or_404(
        Card.objects.select_related('deck', 'scheduling_state'),
        id=card_id,
        user=request.user,
    )
    state_before = ensure_state(card)
    state_snapshot = _serialize_state(state_before)
    tags_before = list(card.tags)
    _, review_record = grade_card_for_user(user=request.user, card_id=card_id, rating=rating_value, now=now)
    _push_review_history_entry(
        request,
        {
            'card_id': str(card.id),
            'filter_deck_id': deck.id if deck else None,
            'card_deck_id': card.deck_id,
            'state': state_snapshot,
            'tags': tags_before,
            'review_id': review_record.id,
            'rating': rating_value,
        },
    )
    next_card = get_next_card(request.user, deck)
    summary = get_today_summary(request.user, deck)
    can_undo = bool(_get_review_history(request))
    if not next_card:
        return render(
            request,
            'core/review/partials/empty.html',
            {
                'summary': summary,
                'deck': deck,
                'can_undo': can_undo,
            },
        )
    ensure_state(next_card)
    rating_previews = build_rating_previews(next_card, now=now)
    return render(
        request,
        'core/review/partials/front.html',
        {
            'card': next_card,
            'deck': deck,
            'summary': summary,
            'rating_previews': rating_previews,
            'can_undo': can_undo,
        },
    )


@login_required
def review_undo(request: HttpRequest) -> HttpResponse:
    deck = _resolve_deck(request)
    entry = _pop_review_history_entry(request, deck)
    if not entry:
        return review_next(request)
    card = get_object_or_404(
        Card.objects.select_related('deck', 'scheduling_state'),
        id=entry.get('card_id'),
        user=request.user,
    )
    state = ensure_state(card)
    snapshot = entry.get('state', {})
    if isinstance(snapshot, dict):
        _restore_state_from_snapshot(state, snapshot)
    tags_before = entry.get('tags')
    if isinstance(tags_before, list):
        card.tags = list(tags_before)
        card.save(update_fields=['tags'])
    review_id = entry.get('review_id')
    if review_id:
        Review.objects.filter(id=review_id, user=request.user).delete()
    summary = get_today_summary(request.user, deck)
    now = timezone.now()
    rating_previews = build_rating_previews(card, now=now)
    can_undo = bool(_get_review_history(request))
    return render(
        request,
        'core/review/partials/front.html',
        {
            'card': card,
            'deck': deck,
            'summary': summary,
            'rating_previews': rating_previews,
            'can_undo': can_undo,
        },
    )
