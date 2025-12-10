from __future__ import annotations

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import CardImportFormatFormSet, CardTypeForm
from ..models import CardType


def _accessible_types(user):
    return CardType.objects.filter(Q(user=user) | Q(user__isnull=True)).order_by('name')


@login_required
def list_card_types(request: HttpRequest) -> HttpResponse:
    types = list(_accessible_types(request.user).prefetch_related('import_formats'))
    custom_types = [card_type for card_type in types if card_type.user_id == request.user.id]
    builtin_types = [card_type for card_type in types if card_type.user_id is None]
    return render(
        request,
        'core/card_types/list.html',
        {'custom_types': custom_types, 'builtin_types': builtin_types},
    )


@login_required
def create_card_type(request: HttpRequest) -> HttpResponse:
    card_type = CardType(user=request.user)
    initial = {}
    if request.method != 'POST':
        source_id = request.GET.get('source')
        if source_id:
            source = _accessible_types(request.user).filter(id=source_id).first()
            if source:
                initial = {
                    'name': f"{source.name} Copy",
                    'description': source.description,
                    'front_template': source.front_template,
                    'back_template': source.back_template,
                    'field_schema': json.dumps(source.field_schema or [], indent=2),
                }
    form = CardTypeForm(request.POST or None, instance=card_type, initial=initial)
    formset = CardImportFormatFormSet(request.POST or None, instance=card_type, prefix='formats')
    if request.method == 'POST' and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            instance = form.save(commit=False)
            instance.user = request.user
            instance.save()
            formset.instance = instance
            formset.save()
        messages.success(request, 'Card type created.')
        return redirect('card_types:list')
    return render(
        request,
        'core/card_types/form.html',
        {'form': form, 'formset': formset, 'card_type': None, 'can_edit': True},
    )


@login_required
def edit_card_type(request: HttpRequest, pk: int) -> HttpResponse:
    card_type = get_object_or_404(CardType, pk=pk, user=request.user)
    form = CardTypeForm(request.POST or None, instance=card_type)
    formset = CardImportFormatFormSet(request.POST or None, instance=card_type, prefix='formats')
    if request.method == 'POST' and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            form.save()
            formset.save()
        messages.success(request, 'Card type updated.')
        return redirect('card_types:list')
    return render(
        request,
        'core/card_types/form.html',
        {'form': form, 'formset': formset, 'card_type': card_type, 'can_edit': True},
    )


@login_required
def view_card_type(request: HttpRequest, pk: int) -> HttpResponse:
    card_type = get_object_or_404(_accessible_types(request.user), pk=pk)
    if card_type.user_id == request.user.id:
        return redirect('card_types:edit', pk=card_type.pk)
    can_edit = False
    form = CardTypeForm(instance=card_type)
    formset = CardImportFormatFormSet(instance=card_type, prefix='formats')
    return render(
        request,
        'core/card_types/form.html',
        {'form': form, 'formset': formset, 'card_type': card_type, 'can_edit': can_edit},
    )


@login_required
def delete_card_type(request: HttpRequest, pk: int) -> HttpResponse:
    card_type = get_object_or_404(CardType, pk=pk, user=request.user)
    if request.method == 'POST':
        if card_type.cards.exists():
            messages.error(request, 'Cannot delete a card type that is in use.')
            return redirect('card_types:list')
        card_type.delete()
        messages.success(request, 'Card type deleted.')
        return redirect('card_types:list')
    return render(request, 'core/card_types/confirm_delete.html', {'card_type': card_type})
