from __future__ import annotations

from django import forms

from core.models import Deck


class AnkiImportForm(forms.Form):
    deck = forms.ModelChoiceField(queryset=Deck.objects.none())
    package = forms.FileField()

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['deck'].queryset = Deck.objects.for_user(user).order_by('name')
        self.fields['deck'].widget.attrs.update({'class': 'w-full rounded border p-2'})
        self.fields['package'].widget.attrs.update({'class': 'w-full rounded border p-2 bg-white'})
