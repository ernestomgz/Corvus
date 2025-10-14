import io
import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from core.models import Card, Deck
from import_md.services import apply_markdown_session, prepare_markdown_session, process_markdown_archive

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


def test_prepare_markdown_session_creates_payload(user_factory, deck_factory):
    user = user_factory()
    deck = deck_factory(user=user)
    archive = _build_zip({'cards/note.md': '#card Sample\nid:: example\n\nBack content'})
    session = prepare_markdown_session(user=user, deck=deck, uploaded_file=archive)
    assert session.status == 'ready'
    assert session.total == 1
    payload = session.payload
    assert payload['cards'][0]['external_key']
    assert payload['cards'][0]['deck_path'] == ['cards']


def test_apply_markdown_session_respects_decision(card_factory, external_id_factory):
    existing_card = card_factory(front_md='Original', back_md='Answer')
    external_id_factory(card=existing_card, system='logseq', external_key='c_existing')
    markdown = '#card Updated\nid:: c_existing\n\nReplacement'
    archive = _build_zip({'note.md': markdown})
    session = prepare_markdown_session(user=existing_card.user, deck=existing_card.deck, uploaded_file=archive)
    index = session.payload['cards'][0]['index']
    apply_markdown_session(session, decisions={index: 'existing'})
    existing_card.refresh_from_db()
    assert existing_card.front_md == 'Original'
    assert existing_card.back_md == 'Answer'


def test_apply_markdown_session_creates_child_decks(user_factory, deck_factory):
    user = user_factory()
    root_deck = deck_factory(user=user)
    markdown = '#card Child card\n\nContent'
    archive = _build_zip({'Sciences/Math/note.md': markdown})
    session = prepare_markdown_session(user=user, deck=root_deck, uploaded_file=archive)
    record = apply_markdown_session(session)
    assert record.summary['created'] == 1
    assert record.summary['decks_created'] >= 2
    sciences = Deck.objects.get(user=user, parent=root_deck, name='Sciences')
    math = Deck.objects.get(user=user, parent=sciences, name='Math')
    card = Card.objects.get(user=user)
    assert card.deck == math


def test_md_card_marker_variations(user_factory, deck_factory):
    user = user_factory()
    deck = deck_factory(user=user)
    markdown = "# Question 1 #card\nFirst answer\n\n# Question 2\n#card\nSecond answer"
    archive = _build_zip({'notes.md': markdown})
    record = process_markdown_archive(user=user, deck=deck, uploaded_file=archive)
    assert record.summary['created'] == 2
    cards = Card.objects.filter(user=user).order_by('created_at')
    fronts = [card.front_md for card in cards]
    backs = [card.back_md for card in cards]
    assert fronts[0] == 'Question 1'
    assert backs[0] == 'First answer'
    assert fronts[1] == 'Question 2'
    assert backs[1] == 'Second answer'
