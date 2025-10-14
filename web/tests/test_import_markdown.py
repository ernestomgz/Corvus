import io
import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from core.models import Card
from import_md.services import process_markdown_archive

pytestmark = pytest.mark.django_db


def _build_zip(contents: dict[str, str], media: dict[str, bytes] | None = None) -> SimpleUploadedFile:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as zf:
        for path, text in contents.items():
            zf.writestr(path, text)
        if media:
            for path, data in media.items():
                zf.writestr(path, data)
    buffer.seek(0)
    return SimpleUploadedFile('cards.zip', buffer.read(), content_type='application/zip')


def test_md_card_extraction(user_factory, deck_factory):
    user = user_factory()
    deck = deck_factory(user=user)
    archive = _build_zip({'notes/sample.md': '#card What is 2+2?\n\nFour'})
    record = process_markdown_archive(user=user, deck=deck, uploaded_file=archive)
    assert record.summary['created'] == 1
    card = Card.objects.get(user=user)
    assert card.front_md.startswith('What is')
    assert card.back_md == 'Four'
    assert card.deck == deck


def test_md_upsert_preserves_state(card_factory, external_id_factory):
    card = card_factory()
    external_id_factory(card=card, system='logseq', external_key='c_test')
    state = card.scheduling_state
    state.queue_status = 'review'
    state.interval_days = 10
    state.ease = 2.0
    state.save()

    markdown = '#card Updated front\nid:: c_test\n\nUpdated back'
    archive = _build_zip({'file.md': markdown})
    record = process_markdown_archive(user=card.user, deck=card.deck, uploaded_file=archive)
    card.refresh_from_db()
    state.refresh_from_db()
    assert record.summary['updated'] == 1
    assert card.front_md == 'Updated front'
    assert state.interval_days == 10
    assert state.queue_status == 'review'


def test_md_external_id_matching(external_id_factory):
    card = external_id_factory(system='logseq', external_key='c_match').card
    markdown = '#card Replacement\nid:: c_match\n\nAnswer'
    archive = _build_zip({'file.md': markdown})
    record = process_markdown_archive(user=card.user, deck=card.deck, uploaded_file=archive)
    card.refresh_from_db()
    assert record.summary['updated'] == 1
    assert card.front_md == 'Replacement'


def test_md_media_copy_and_rewrite(user_factory, deck_factory, settings):
    user = user_factory()
    deck = deck_factory(user=user)
    image_bytes = b'fake-image-bytes'
    markdown = '#card Diagram\n\n![alt](assets/diagram.png)'
    archive = _build_zip({'note.md': markdown}, media={'assets/diagram.png': image_bytes})
    record = process_markdown_archive(user=user, deck=deck, uploaded_file=archive)
    card = Card.objects.get(user=user)
    assert record.summary['created'] == 1
    assert card.media
    media_entry = card.media[0]
    assert media_entry['url'].startswith(settings.MEDIA_URL)
    assert 'diagram' in media_entry['name']
    assert media_entry['hash']
    assert '![' in card.back_md and settings.MEDIA_URL in card.back_md
