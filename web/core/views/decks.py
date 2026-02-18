from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import DeckForm, StudySetForm
from ..models import Deck, StudySet
from ..services.decks import build_deck_tree
from ..services.study_sets import fetch_study_sets_with_summaries


@login_required
def deck_list(request: HttpRequest) -> HttpResponse:
    deck_tree = build_deck_tree(request.user)
    form = DeckForm(request.POST or None, user=request.user)
    study_set_form = StudySetForm(user=request.user)
    study_sets, study_set_summaries = fetch_study_sets_with_summaries(request.user)
    deck_study_sets = {
        study_set.deck_id: study_set
        for study_set in study_sets
        if study_set.kind == StudySet.KIND_DECK and study_set.deck_id
    }
    favorite_deck_ids = [deck_id for deck_id, study_set in deck_study_sets.items() if study_set.is_favorite]
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, 'Deck created.')
            deck_tree = build_deck_tree(request.user)
            if getattr(request, 'htmx', False):
                return render(
                    request,
                    'core/decks/partials/deck_list.html',
                    {
                        'deck_tree': deck_tree,
                        'deck_study_sets': deck_study_sets,
                        'favorite_deck_ids': favorite_deck_ids,
                    },
                )
            return redirect('decks:list')
        elif getattr(request, 'htmx', False):
            return render(request, 'core/decks/partials/deck_form.html', {'form': form})
    context = {
        'deck_tree': deck_tree,
        'form': form,
        'study_set_form': study_set_form,
        'study_sets': study_sets,
        'study_set_summaries': study_set_summaries,
        'deck_study_sets': deck_study_sets,
        'favorite_deck_ids': favorite_deck_ids,
    }
    return render(request, 'core/decks/list.html', context)


@login_required
def deck_update(request: HttpRequest, pk: int) -> HttpResponse:
    deck = get_object_or_404(Deck, pk=pk, user=request.user)
    form = DeckForm(request.POST or None, instance=deck, user=request.user)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, 'Deck updated.')
            deck_tree = build_deck_tree(request.user)
            if getattr(request, 'htmx', False):
                study_sets, _ = fetch_study_sets_with_summaries(request.user)
                deck_study_sets = {
                    study_set.deck_id: study_set
                    for study_set in study_sets
                    if study_set.kind == StudySet.KIND_DECK and study_set.deck_id
                }
                favorite_deck_ids = [deck_id for deck_id, study_set in deck_study_sets.items() if study_set.is_favorite]
                return render(
                    request,
                    'core/decks/partials/deck_list.html',
                    {
                        'deck_tree': deck_tree,
                        'deck_study_sets': deck_study_sets,
                        'favorite_deck_ids': favorite_deck_ids,
                    },
                )
            return redirect('decks:list')
        elif getattr(request, 'htmx', False):
            return render(request, 'core/decks/partials/deck_form.html', {'form': form, 'deck': deck})
    return render(request, 'core/decks/edit.html', {'form': form, 'deck': deck})


@login_required
def deck_delete(request: HttpRequest, pk: int) -> HttpResponse:
    deck = get_object_or_404(Deck, pk=pk, user=request.user)
    if request.method == 'POST':
        deck.delete()
        messages.success(request, 'Deck deleted.')
        deck_tree = build_deck_tree(request.user)
        if getattr(request, 'htmx', False):
            study_sets, _ = fetch_study_sets_with_summaries(request.user)
            deck_study_sets = {
                study_set.deck_id: study_set
                for study_set in study_sets
                if study_set.kind == StudySet.KIND_DECK and study_set.deck_id
            }
            favorite_deck_ids = [deck_id for deck_id, study_set in deck_study_sets.items() if study_set.is_favorite]
            return render(
                request,
                'core/decks/partials/deck_list.html',
                {
                    'deck_tree': deck_tree,
                    'deck_study_sets': deck_study_sets,
                    'favorite_deck_ids': favorite_deck_ids,
                },
            )
        return redirect('decks:list')
    return render(request, 'core/decks/confirm_delete.html', {'deck': deck})
