from __future__ import annotations

from typing import Iterable

from django import forms

from .models import Card, Deck


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


class CardForm(forms.ModelForm):
    tags = forms.CharField(
        required=False,
        help_text='Comma-separated tags',
        widget=forms.TextInput(attrs={'class': 'w-full border rounded p-2'}),
    )

    class Meta:
        model = Card
        fields = ['deck', 'card_type', 'front_md', 'back_md', 'tags']
        widgets = {
            'deck': forms.Select(attrs={'class': 'w-full border rounded p-2'}),
            'card_type': forms.Select(attrs={'class': 'w-full border rounded p-2'}),
            'front_md': forms.Textarea(attrs={'class': 'w-full border rounded p-2 font-mono', 'rows': 5}),
            'back_md': forms.Textarea(attrs={'class': 'w-full border rounded p-2 font-mono', 'rows': 5}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user is not None:
            self.fields['deck'].queryset = Deck.objects.for_user(user).order_by('name')
        else:
            self.fields['deck'].queryset = Deck.objects.none()
        if self.instance.pk:
            self.initial['tags'] = ', '.join(self.instance.tags)

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
