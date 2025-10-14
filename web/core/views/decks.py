from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import DeckForm
from ..models import Deck
from ..services.decks import build_deck_tree


@login_required
def deck_list(request: HttpRequest) -> HttpResponse:
    deck_tree = build_deck_tree(request.user)
    form = DeckForm(request.POST or None, user=request.user)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, 'Deck created.')
            deck_tree = build_deck_tree(request.user)
            if getattr(request, 'htmx', False):
                return render(request, 'core/decks/partials/deck_list.html', {'deck_tree': deck_tree})
            return redirect('decks:list')
        elif getattr(request, 'htmx', False):
            return render(request, 'core/decks/partials/deck_form.html', {'form': form})
    context = {'deck_tree': deck_tree, 'form': form}
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
                return render(request, 'core/decks/partials/deck_list.html', {'deck_tree': deck_tree})
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
            return render(request, 'core/decks/partials/deck_list.html', {'deck_tree': deck_tree})
        return redirect('decks:list')
    return render(request, 'core/decks/confirm_delete.html', {'deck': deck})
