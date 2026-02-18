import io
import json
import shutil
import sqlite3
import zipfile
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from core.models import Card, Deck, ExternalId
from import_anki.services import process_apkg_archive

pytestmark = pytest.mark.django_db



def _build_apkg(
    tmp_path: Path,
    *,
    front: str,
    back: str,
    guid: str = 'guid123',
    media: dict[str, bytes] | None = None,
    card_values: dict | None = None,
    media_map_bytes: bytes | None = None,
    collection_filename: str = 'collection.anki2',
    deck_map: dict[int, str] | None = None,
) -> SimpleUploadedFile:
    media = media or {}
    card_values = card_values or {}
    deck_map = deck_map or {1: 'Default'}
    primary_deck_id = next(iter(deck_map.keys()))
    db_path = tmp_path / collection_filename
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.execute(
        'CREATE TABLE notes (id INTEGER PRIMARY KEY, guid TEXT, mid INTEGER, mod INTEGER, usn INTEGER, tags TEXT, flds TEXT, sfld INTEGER, csum INTEGER, flags INTEGER, data TEXT)'
    )
    conn.execute(
        'CREATE TABLE cards (id INTEGER PRIMARY KEY, nid INTEGER, did INTEGER, ord INTEGER, mod INTEGER, usn INTEGER, type INTEGER, queue INTEGER, due INTEGER, ivl INTEGER, factor INTEGER, reps INTEGER, lapses INTEGER, left INTEGER, odue INTEGER, odid INTEGER, flags INTEGER, data TEXT)'
    )
    conn.execute(
        'CREATE TABLE col (id INTEGER PRIMARY KEY, decks TEXT)'
    )
    decks_payload = {str(deck_id): {'name': name} for deck_id, name in deck_map.items()}
    conn.execute('INSERT INTO col (id, decks) VALUES (?, ?)', (1, json.dumps(decks_payload)))
    conn.execute(
        'INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
        (1, guid, 1, 0, 0, '', f'{front}{back}', 0, 0, 0, ''),
    )
    conn.execute(
        'INSERT INTO cards (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
        (
            1,
            1,
            card_values.get('did', primary_deck_id),
            0,
            0,
            0,
            0,
            card_values.get('queue', 2),
            card_values.get('due', 2),
            card_values.get('ivl', 5),
            card_values.get('factor', 2600),
            card_values.get('reps', 3),
            card_values.get('lapses', 1),
            0,
            0,
            0,
            0,
            '',
        ),
    )
    conn.commit()
    conn.close()

    media_map: dict[str, str] = {}
    for idx, (name, data) in enumerate(media.items()):
        source_name = str(idx)
        media_path = tmp_path / source_name
        if media_path.exists():
            media_path.unlink()
        media_path.write_bytes(data)
        media_map[source_name] = name

    media_json_path = tmp_path / 'media'
    if media_json_path.exists():
        if media_json_path.is_dir():
            shutil.rmtree(media_json_path)
        else:
            media_json_path.unlink()
    if media_map_bytes is not None:
        media_json_path.write_bytes(media_map_bytes)
    else:
        media_json_path.write_text(json.dumps(media_map))

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as zf:
        zf.write(db_path, arcname=collection_filename)
        zf.write(media_json_path, arcname='media')
        for idx in media_map.keys():
            zf.write(tmp_path / idx, arcname=idx)
    buffer.seek(0)
    return SimpleUploadedFile('sample.apkg', buffer.read(), content_type='application/octet-stream')




def test_apkg_collection_anki21_supported(user_factory, deck_factory, tmp_path):
    user = user_factory()
    deck = deck_factory(user=user)
    upload = _build_apkg(tmp_path, front='Front', back='Back', collection_filename='collection.anki21')
    record = process_apkg_archive(user=user, deck=deck, uploaded_file=upload)
    assert record.summary['created'] == 1
    card = Card.objects.get(user=user)
    assert card.front_md == 'Front'
def test_apkg_external_key_guid_ord(user_factory, deck_factory, tmp_path):
    user = user_factory()
    deck = deck_factory(user=user)
    upload = _build_apkg(tmp_path, front='Front', back='Back', guid='guid999')
    record = process_apkg_archive(user=user, deck=deck, uploaded_file=upload)
    assert record.summary['created'] == 1
    external = ExternalId.objects.get(system='anki')
    assert external.external_key == 'guid999:0'
    assert external.card.deck == deck


def test_apkg_update_does_not_reset_state(card_factory, tmp_path):
    card = card_factory()
    ExternalId.objects.create(card=card, system='anki', external_key='guid-update:0')
    state = card.scheduling_state
    state.queue_status = 'review'
    state.interval_days = 12
    state.ease = 2.4
    state.save()

    upload = _build_apkg(tmp_path, front='Updated front', back='Updated back', guid='guid-update')
    record = process_apkg_archive(user=card.user, deck=card.deck, uploaded_file=upload)
    card.refresh_from_db()
    state.refresh_from_db()
    assert record.summary['updated'] == 1
    assert card.front_md == 'Updated front'
    assert state.interval_days == 12
    assert state.ease == pytest.approx(2.4)


def test_apkg_deck_mapping_and_media(user_factory, deck_factory, settings, tmp_path):
    user = user_factory()
    deck = deck_factory(user=user)
    media_data = {'diagram.png': b'fake-bytes'}
    upload = _build_apkg(tmp_path, front='<img src="0">', back='Practice', media=media_data)
    record = process_apkg_archive(user=user, deck=deck, uploaded_file=upload)
    card = Card.objects.get(user=user)
    assert record.summary['created'] == 1
    assert card.deck == deck
    assert settings.MEDIA_URL in card.front_md
    assert card.media and card.media[0]['url'].startswith(settings.MEDIA_URL)


def test_apkg_media_map_non_utf8(user_factory, deck_factory, tmp_path):
    user = user_factory()
    deck = deck_factory(user=user)
    raw_map = json.dumps({'0': 'audio.mp3'}).encode('utf-8') + b'\xb5'
    media_data = {'audio.mp3': b'binary-audio'}
    upload = _build_apkg(tmp_path, front='[sound:0]', back='Answer', media=media_data, media_map_bytes=raw_map)
    record = process_apkg_archive(user=user, deck=deck, uploaded_file=upload)
    card = Card.objects.get(user=user)
    assert record.summary['created'] == 1
    assert any(item['name'] == 'audio.mp3' for item in card.media)
