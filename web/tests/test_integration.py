import io
import zipfile
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from core.models import Card
from import_anki.services import process_apkg_archive
from import_md.services import process_markdown_archive

from .test_import_anki import _build_apkg

pytestmark = pytest.mark.django_db


def _markdown_zip(text: str) -> SimpleUploadedFile:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as zf:
        zf.writestr('note.md', text)
    buffer.seek(0)
    return SimpleUploadedFile('cards.zip', buffer.read(), content_type='application/zip')


def _apkg(tmp_path: Path, front: str, back: str, guid: str = 'guid-int') -> SimpleUploadedFile:
    return _build_apkg(tmp_path, front=front, back=back, guid=guid)


def test_markdown_import_review_update(user_factory, deck_factory):
    user = user_factory()
    deck = deck_factory(user=user)
    archive = _markdown_zip('#card Fact\nid:: c_md\n\nAnswer')
    record = process_markdown_archive(user=user, deck=deck, uploaded_file=archive)
    assert record.summary['created'] == 1
    card = Card.objects.get(user=user)
    state = card.scheduling_state
    state.queue_status = 'review'
    state.interval_days = 5
    state.ease = 2.3
    state.save()

    updated_archive = _markdown_zip('#card Fact updated\nid:: c_md\n\nNew answer')
    record2 = process_markdown_archive(user=user, deck=deck, uploaded_file=updated_archive)
    card.refresh_from_db()
    state.refresh_from_db()
    assert record2.summary['updated'] == 1
    assert 'updated' in card.front_md
    assert state.interval_days == 5
    assert state.ease == pytest.approx(2.3)


def test_apkg_import_reimport_preserves_state(user_factory, deck_factory, tmp_path):
    user = user_factory()
    deck = deck_factory(user=user)
    upload = _apkg(tmp_path, front='Front', back='Back', guid='guid-int')
    record = process_apkg_archive(user=user, deck=deck, uploaded_file=upload)
    assert record.summary['created'] == 1
    card = Card.objects.get(user=user)
    state = card.scheduling_state
    state.queue_status = 'review'
    state.interval_days = 9
    state.ease = 2.6
    state.save()

    upload2 = _apkg(tmp_path, front='Front updated', back='Back', guid='guid-int')
    record2 = process_apkg_archive(user=user, deck=deck, uploaded_file=upload2)
    card.refresh_from_db()
    state.refresh_from_db()
    assert record2.summary['updated'] == 1
    assert 'updated' in card.front_md
    assert state.interval_days == 9
    assert state.ease == pytest.approx(2.6)
