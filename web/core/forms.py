from __future__ import annotations

import json
from typing import Iterable

from django import forms
from django.db.models import Q
from django.forms import inlineformset_factory

from .models import Card, Deck, CardType, CardImportFormat, StudySet


def _normalise_tags(raw: Iterable[str]) -> list[str]:
    cleaned = []
    for item in raw:
        trimmed = item.strip()
        if trimmed and trimmed not in cleaned:
            cleaned.append(trimmed)
    return cleaned


class DeckForm(forms.ModelForm):
    class Meta:
        model = Deck
        fields = ['name', 'parent', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full border rounded p-2'}),
            'parent': forms.Select(attrs={'class': 'w-full border rounded p-2'}),
            'description': forms.Textarea(attrs={'class': 'w-full border rounded p-2', 'rows': 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        parent_field = self.fields['parent']
        if user is not None:
            queryset = Deck.objects.for_user(user).order_by('name')
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            parent_field.queryset = queryset
        else:
            parent_field.queryset = Deck.objects.none()
        parent_field.empty_label = 'No parent (top level)'

    def save(self, commit: bool = True):
        deck = super().save(commit=False)
        if self.user is not None:
            deck.user = self.user
        if commit:
            deck.save()
        return deck


class StudySetForm(forms.ModelForm):
    class Meta:
        model = StudySet
        fields = ['name', 'kind', 'deck', 'tag']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full border rounded p-2'}),
            'kind': forms.RadioSelect(attrs={'class': 'flex gap-4 text-sm'}),
            'deck': forms.Select(attrs={'class': 'w-full border rounded p-2'}),
            'tag': forms.TextInput(attrs={'class': 'w-full border rounded p-2', 'placeholder': 'e.g. physics'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user is not None:
            self.fields['deck'].queryset = Deck.objects.for_user(user).order_by('name')
        else:
            self.fields['deck'].queryset = Deck.objects.none()
        self.fields['deck'].required = False
        self.fields['tag'].required = False

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get('kind')
        deck = cleaned.get('deck')
        tag = (cleaned.get('tag') or '').strip()
        name = (cleaned.get('name') or '').strip()
        if kind == StudySet.KIND_DECK:
            if not deck:
                self.add_error('deck', 'Select a deck to study.')
            elif not name:
                cleaned['name'] = deck.full_path()
        elif kind == StudySet.KIND_TAG:
            if not tag:
                self.add_error('tag', 'Enter a tag to study.')
            else:
                cleaned['tag'] = tag
                if not name:
                    cleaned['name'] = f"Tag: {tag}"
        else:
            self.add_error('kind', 'Choose how you want to study.')
        return cleaned

    def save(self, commit: bool = True):
        study_set = super().save(commit=False)
        if self.user is not None:
            study_set.user = self.user
        if commit:
            study_set.save()
        return study_set


class CardForm(forms.ModelForm):
    tags = forms.CharField(
        required=False,
        help_text='Comma-separated tags',
        widget=forms.TextInput(attrs={'class': 'w-full border rounded p-2'}),
    )
    card_type = forms.ModelChoiceField(
        queryset=CardType.objects.none(),
        widget=forms.Select(attrs={'class': 'w-full border rounded p-2'}),
    )

    class Meta:
        model = Card
        fields = ['deck', 'card_type', 'front_md', 'back_md', 'tags']
        widgets = {
            'deck': forms.Select(attrs={'class': 'w-full border rounded p-2'}),
            'front_md': forms.Textarea(attrs={'class': 'w-full border rounded p-2 font-mono', 'rows': 5}),
            'back_md': forms.Textarea(attrs={'class': 'w-full border rounded p-2 font-mono', 'rows': 5}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user is not None:
            self.fields['deck'].queryset = Deck.objects.for_user(user).order_by('name')
            type_queryset = CardType.objects.filter(Q(user=user) | Q(user__isnull=True)).order_by('name')
            self.fields['card_type'].queryset = type_queryset
        else:
            self.fields['deck'].queryset = Deck.objects.none()
            self.fields['card_type'].queryset = CardType.objects.none()
        if self.instance.pk:
            self.initial['tags'] = ', '.join(self.instance.tags)
        elif user is not None:
            default_type = self.fields['card_type'].queryset.filter(slug='basic').first()
            if default_type and 'card_type' not in self.initial:
                self.initial['card_type'] = default_type.pk

    def clean_tags(self):
        raw = self.cleaned_data.get('tags', '')
        if isinstance(raw, list):
            return _normalise_tags(raw)
        parts = raw.split(',') if raw else []
        return _normalise_tags(parts)

    def save(self, commit: bool = True):
        card = super().save(commit=False)
        if self.user is not None:
            card.user = self.user
        card.tags = self.cleaned_data.get('tags', [])
        if commit:
            card.save()
        return card


class CardFilterForm(forms.Form):
    deck = forms.ModelChoiceField(queryset=Deck.objects.none(), required=False)
    tag = forms.CharField(required=False)
    q = forms.CharField(required=False, label='Search')

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['deck'].queryset = Deck.objects.filter(user=user).order_by('name')
        self.fields['deck'].widget.attrs.update({'class': 'border rounded p-2'})
        self.fields['tag'].widget.attrs.update({'class': 'border rounded p-2', 'placeholder': 'Tag'})
        self.fields['q'].widget.attrs.update({'class': 'border rounded p-2', 'placeholder': 'Search text'})


class CardTypeForm(forms.ModelForm):
    field_schema = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'w-full border rounded p-2 font-mono', 'rows': 4}),
        help_text='JSON list describing the fields for this card type.',
    )

    class Meta:
        model = CardType
        fields = ['name', 'slug', 'description', 'front_template', 'back_template', 'field_schema']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full border rounded p-2'}),
            'slug': forms.TextInput(attrs={'class': 'w-full border rounded p-2'}),
            'description': forms.Textarea(attrs={'class': 'w-full border rounded p-2', 'rows': 3}),
            'front_template': forms.Textarea(attrs={'class': 'w-full border rounded p-2 font-mono', 'rows': 4}),
            'back_template': forms.Textarea(attrs={'class': 'w-full border rounded p-2 font-mono', 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and 'field_schema' not in self.initial:
            schema = self.instance.field_schema or []
            self.initial['field_schema'] = json.dumps(schema, indent=2)

    def clean_field_schema(self):
        raw = self.cleaned_data.get('field_schema')
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f'Field schema must be valid JSON: {exc}') from exc
        if not isinstance(parsed, list):
            raise forms.ValidationError('Field schema must be a JSON array.')
        return parsed


class CardImportFormatForm(forms.ModelForm):
    options = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'w-full border rounded p-2 font-mono', 'rows': 3}),
        help_text='Optional JSON metadata for this import format.',
    )

    class Meta:
        model = CardImportFormat
        fields = ['name', 'format_kind', 'template', 'options']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full border rounded p-2'}),
            'format_kind': forms.Select(attrs={'class': 'w-full border rounded p-2'}),
            'template': forms.Textarea(attrs={'class': 'w-full border rounded p-2 font-mono', 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and 'options' not in self.initial:
            self.initial['options'] = json.dumps(self.instance.options or {}, indent=2)

    def clean_options(self):
        raw = self.cleaned_data.get('options')
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f'Options must be valid JSON: {exc}') from exc
        if not isinstance(parsed, dict):
            raise forms.ValidationError('Options must be a JSON object.')
        return parsed


CardImportFormatFormSet = inlineformset_factory(
    CardType,
    CardImportFormat,
    form=CardImportFormatForm,
    extra=1,
    can_delete=True,
)
