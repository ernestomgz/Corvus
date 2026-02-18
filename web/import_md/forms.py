from __future__ import annotations

from django import forms

from core.models import Deck


class MarkdownImportForm(forms.Form):
    deck = forms.ModelChoiceField(queryset=Deck.objects.none(), required=False)
    archive = forms.FileField()

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['deck'].queryset = Deck.objects.for_user(user).order_by('name')
        self.fields['deck'].widget.attrs.update({'class': 'w-full rounded border p-2'})
        self.fields['archive'].widget.attrs.update({'class': 'w-full rounded border p-2 bg-white'})


class MarkdownImportResult:
    def __init__(self, *, created: int, updated: int, skipped: int, media_copied: int):
        self.created = created
        self.updated = updated
        self.skipped = skipped
        self.media_copied = media_copied

    def to_dict(self) -> dict:
        return {
            'created': self.created,
            'updated': self.updated,
            'skipped': self.skipped,
            'media_copied': self.media_copied,
        }
