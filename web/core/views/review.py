from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from ..models import Card, Deck
from ..scheduling import ensure_state
from ..services.review import get_next_card, get_today_summary, grade_card_for_user


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
    decks = Deck.objects.for_user(request.user)
    summary = get_today_summary(request.user, deck)
    context = {
        'decks': decks,
        'active_deck': deck,
        'summary': summary,
    }
    return render(request, 'core/review/today.html', context)


@login_required
def review_next(request: HttpRequest) -> HttpResponse:
    deck = _resolve_deck(request)
    card = get_next_card(request.user, deck)
    summary = get_today_summary(request.user, deck)
    if not card:
        return render(
            request,
            'core/review/partials/empty.html',
            {
                'summary': summary,
                'deck': deck,
            },
        )
    ensure_state(card)
    return render(
        request,
        'core/review/partials/front.html',
        {
            'card': card,
            'deck': deck,
            'summary': summary,
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
    return render(
        request,
        'core/review/partials/back.html',
        {
            'card': card,
            'deck': deck,
            'summary': summary,
        },
    )


@login_required
def review_grade(request: HttpRequest) -> HttpResponse:
    card_id = request.POST.get('card_id')
    rating = request.POST.get('rating')
    if card_id is None or rating is None:
        raise Http404('Missing card or rating')
    deck = _resolve_deck(request)
    grade_card_for_user(user=request.user, card_id=card_id, rating=int(rating), now=timezone.now())
    next_card = get_next_card(request.user, deck)
    summary = get_today_summary(request.user, deck)
    if not next_card:
        return render(
            request,
            'core/review/partials/empty.html',
            {
                'summary': summary,
                'deck': deck,
            },
        )
    ensure_state(next_card)
    return render(
        request,
        'core/review/partials/front.html',
        {
            'card': next_card,
            'deck': deck,
            'summary': summary,
        },
    )
