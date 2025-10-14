from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.models import Card, Deck, ExternalId, Import, ImportSession
from core.services.cards import infer_card_type
from core.services.decks import ensure_deck_path

OBSIDIAN_LINK_PATTERN = re.compile(r'!\[\[(?P<path>[^\]]+)\]\]')
ID_PATTERN = re.compile(r'^\s*id::\s*(?P<id>[\w:-]+)', re.IGNORECASE)
TAGS_PATTERN = re.compile(r'^\s*tags::\s*(?P<tags>.+)$', re.IGNORECASE)
MEDIA_PATTERN = re.compile(r'!\[[^\]]*\]\(([^)]+)\)')


@dataclass
class ParsedCard:
    front_md: str
    back_md: str
    source_path: str
    source_anchor: str | None
    external_key: str
    tags: list[str]
    media: list[dict]
    deck_path: list[str]


class MarkdownImportError(Exception):
    """Raised when the markdown importer encounters an unrecoverable problem."""


def _normalise_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    tags = [tag.strip() for tag in re.split(r'[;,]', raw) if tag.strip()]
    unique: list[str] = []
    for tag in tags:
        if tag not in unique:
            unique.append(tag)
    return unique


def _generate_external_key(source_path: str, line_no: int, front_md: str) -> str:
    data = f"{source_path}:{line_no}:{front_md.strip().lower()}".encode('utf-8', 'ignore')
    digest = hashlib.sha1(data).hexdigest()
    return f"c_{digest}"


def _ensure_media_directory(user_id: int) -> Path:
    user_media_dir = Path(settings.MEDIA_ROOT) / str(user_id)
    user_media_dir.mkdir(parents=True, exist_ok=True)
    return user_media_dir


def _copy_media(user_id: int, zip_file: zipfile.ZipFile, asset_path: str) -> Tuple[str, dict] | None:
    normalised_asset = asset_path.lstrip('./')
    try:
        data = zip_file.read(normalised_asset)
    except KeyError:
        return None
    digest = hashlib.sha1(data).hexdigest()
    suffix = Path(normalised_asset).suffix or ''
    filename = f"{digest}{suffix}"
    destination_dir = _ensure_media_directory(user_id)
    destination_path = destination_dir / filename
    if not destination_path.exists():
        destination_path.write_bytes(data)
    url = f"{settings.MEDIA_URL}{user_id}/{filename}".replace('//', '/')
    return url, {'name': Path(normalised_asset).name, 'url': url, 'hash': digest}


def _rewrite_media_links(text: str, *, user_id: int, zip_file: zipfile.ZipFile, summary: dict) -> Tuple[str, list[dict]]:
    media_items: list[dict] = []

    def _register(asset: str) -> tuple[str, dict] | None:
        asset_path = str(Path(asset).as_posix()).lstrip('/')
        result = _copy_media(user_id, zip_file, asset_path)
        if result is None:
            return None
        url, media_meta = result
        if media_meta not in media_items:
            media_items.append(media_meta)
            summary['media_copied'] += 1
        return url, media_meta

    def markdown_replacer(match: re.Match) -> str:
        original_path = match.group(1)
        registered = _register(original_path)
        if not registered:
            return match.group(0)
        url, _meta = registered
        return match.group(0).replace(original_path, url)

    def obsidian_replacer(match: re.Match) -> str:
        original_path = match.group('path')
        registered = _register(original_path)
        if not registered:
            return match.group(0)
        url, _meta = registered
        alt = Path(original_path).stem or 'image'
        return f'![{alt}]({url})'

    rewritten = MEDIA_PATTERN.sub(markdown_replacer, text)
    rewritten = OBSIDIAN_LINK_PATTERN.sub(obsidian_replacer, rewritten)
    return rewritten, media_items


def _parse_markdown_cards(
    content: str,
    source_path: str,
    *,
    user_id: int,
    zip_file: zipfile.ZipFile,
    summary: dict,
    deck_path: list[str] | None = None,
) -> List[ParsedCard]:
    lines = content.splitlines()
    parsed_cards: list[ParsedCard] = []
    deck_parts = list(deck_path or [])
    i = 0
    while i < len(lines):
        line = lines[i]
        line_lower = line.lower()
        marker_index = line_lower.find('#card')
        if marker_index == -1:
            i += 1
            continue

        line_no = i + 1
        front_before = line[:marker_index].strip()
        front_after = line[marker_index + len('#card'):].strip()
        front_content = front_before or front_after

        if not front_content:
            j = i - 1
            collected: list[str] = []
            while j >= 0 and lines[j].strip():
                collected.insert(0, lines[j].strip())
                j -= 1
            front_content = '\n'.join(collected).strip()

        i += 1
        anchor = None
        tags: list[str] = []

        if i < len(lines):
            anchor_match = ID_PATTERN.match(lines[i])
            if anchor_match:
                anchor = anchor_match.group('id').strip()
                i += 1

        if i < len(lines):
            tags_match = TAGS_PATTERN.match(lines[i])
            if tags_match:
                tags = _normalise_tags(tags_match.group('tags'))
                i += 1

        while i < len(lines) and not lines[i].strip():
            i += 1

        back_lines: list[str] = []
        while i < len(lines) and lines[i].strip():
            back_lines.append(lines[i])
            i += 1

        back_md_raw = '\n'.join(back_lines).strip()
        if not front_content:
            front_content = back_md_raw[:120]

        front_md, media_front = _rewrite_media_links(front_content, user_id=user_id, zip_file=zip_file, summary=summary)
        back_md, media_back = _rewrite_media_links(back_md_raw, user_id=user_id, zip_file=zip_file, summary=summary)

        media: list[dict] = []
        for item in media_front + media_back:
            if item not in media:
                media.append(item)

        external_key = anchor or _generate_external_key(source_path, line_no, front_md)
        parsed_cards.append(
            ParsedCard(
                front_md=front_md,
                back_md=back_md,
                source_path=source_path,
                source_anchor=anchor,
                external_key=external_key,
                tags=tags,
                media=media,
                deck_path=list(deck_parts),
            )
        )
    return parsed_cards


def _collect_markdown_cards(*, user_id: int, uploaded_file) -> Tuple[List[ParsedCard], dict]:
    summary = {'media_copied': 0}
    data = uploaded_file.read()
    try:
        primary_buffer = io.BytesIO(data)
        archive = zipfile.ZipFile(primary_buffer)
        buffers: list[io.BytesIO] = [primary_buffer]
    except zipfile.BadZipFile:
        filename = getattr(uploaded_file, 'name', None) or 'notes.md'
        if not filename.lower().endswith('.md'):
            filename = f"{filename}.md"
        text_data = data.decode('utf-8', 'ignore')
        temp_buffer = io.BytesIO()
        with zipfile.ZipFile(temp_buffer, 'w') as tmp_zip:
            tmp_zip.writestr(filename, text_data)
        temp_buffer.seek(0)
        archive = zipfile.ZipFile(temp_buffer)
        buffers = [temp_buffer]
    parsed_cards: list[ParsedCard] = []
    with archive:
        for info in archive.infolist():
            if info.is_dir() or not info.filename.lower().endswith('.md'):
                continue
            raw_bytes = archive.read(info)
            try:
                markdown_text = raw_bytes.decode('utf-8')
            except UnicodeDecodeError:
                markdown_text = raw_bytes.decode('utf-8', 'ignore')
            deck_parts = [part for part in Path(info.filename).parts[:-1] if part]
            parsed_cards.extend(
                _parse_markdown_cards(
                    markdown_text,
                    info.filename,
                    user_id=user_id,
                    zip_file=archive,
                    summary=summary,
                    deck_path=deck_parts,
                )
            )
    for buffer in buffers:
        buffer.close()
    return parsed_cards, summary


def prepare_markdown_session(*, user, deck: Deck, uploaded_file) -> ImportSession:
    parsed_cards, parse_summary = _collect_markdown_cards(user_id=user.id, uploaded_file=uploaded_file)
    if not parsed_cards:
        raise MarkdownImportError('No cards detected in the provided file.')

    external_keys = [card.external_key for card in parsed_cards]
    existing_map = {
        external.external_key: external
        for external in ExternalId.objects.select_related('card', 'card__deck').filter(
            system='logseq', external_key__in=external_keys
        )
    }

    session_cards: list[dict] = []
    create_count = 0
    update_count = 0
    diff_count = 0

    for index, parsed in enumerate(parsed_cards):
        external = existing_map.get(parsed.external_key)
        existing_payload = None
        has_changes = False
        if external and external.card.user == user:
            existing_card = external.card
            existing_payload = {
                'card_id': str(existing_card.id),
                'deck_id': existing_card.deck_id,
                'deck_path': existing_card.deck.full_path().split('/'),
                'front_md': existing_card.front_md,
                'back_md': existing_card.back_md,
                'tags': existing_card.tags,
                'media': existing_card.media,
                'card_type': existing_card.card_type,
            }
            has_changes = (
                existing_card.front_md != parsed.front_md
                or existing_card.back_md != parsed.back_md
                or existing_card.tags != parsed.tags
                or existing_card.media != parsed.media
            )
            update_count += 1
            if has_changes:
                diff_count += 1
        else:
            existing_payload = None
            has_changes = True
            create_count += 1

        session_cards.append(
            {
                'index': index,
                'external_key': parsed.external_key,
                'front_md': parsed.front_md,
                'back_md': parsed.back_md,
                'tags': parsed.tags,
                'media': parsed.media,
                'source_path': parsed.source_path,
                'source_anchor': parsed.source_anchor,
                'deck_path': parsed.deck_path,
                'existing': existing_payload,
                'has_changes': has_changes,
            }
        )

    session = ImportSession.objects.create(
        user=user,
        kind='markdown',
        status='ready',
        source_name=getattr(uploaded_file, 'name', ''),
        total=len(session_cards),
        processed=len(session_cards),
        payload={
            'root_deck_id': deck.id,
            'cards': session_cards,
            'summary': {
                'creates': create_count,
                'updates': update_count,
                'conflicts': diff_count,
                'media_copied': parse_summary.get('media_copied', 0),
            },
        },
    )
    return session


def apply_markdown_session(session: ImportSession, *, decisions: Dict[int, str] | None = None) -> Import:
    if session.status != 'ready':
        raise MarkdownImportError('Import session is not ready to apply.')

    payload = dict(session.payload or {})
    cards_payload = list(payload.get('cards', []))
    if not cards_payload:
        raise MarkdownImportError('Import session payload is empty.')

    try:
        root_deck = Deck.objects.get(id=payload.get('root_deck_id'), user=session.user)
    except Deck.DoesNotExist as exc:
        raise MarkdownImportError('Root deck no longer exists.') from exc

    decisions = decisions or {}
    summary = {
        'created': 0,
        'updated': 0,
        'skipped': 0,
        'media_copied': payload.get('summary', {}).get('media_copied', 0),
        'decks_created': 0,
    }

    deck_cache: dict[tuple[str, ...], Deck] = {(): root_deck}

    def resolve_deck(parts: list[str]) -> tuple[Deck, list[Deck]]:
        key = tuple(parts)
        if key in deck_cache:
            return deck_cache[key], []
        target, created = ensure_deck_path(session.user, root_deck, parts)
        deck_cache[key] = target
        return target, created

    with transaction.atomic():
        for card_data in cards_payload:
            index = card_data.get('index')
            decision = decisions.get(index, 'imported')
            deck_parts = card_data.get('deck_path', [])
            target_deck, created_decks = resolve_deck(deck_parts)
            if created_decks:
                summary['decks_created'] += len(created_decks)

            existing_payload = card_data.get('existing')
            if not existing_payload:
                if decision == 'existing':
                    summary['skipped'] += 1
                    continue
                card = Card.objects.create(
                    user=session.user,
                    deck=target_deck,
                    card_type=infer_card_type(card_data['front_md'], card_data['back_md']),
                    front_md=card_data['front_md'],
                    back_md=card_data['back_md'],
                    tags=card_data.get('tags', []),
                    media=card_data.get('media', []),
                    source_path=card_data.get('source_path'),
                    source_anchor=card_data.get('source_anchor'),
                )
                ExternalId.objects.create(card=card, system='logseq', external_key=card_data['external_key'])
                summary['created'] += 1
                continue

            try:
                existing_card = Card.objects.get(id=existing_payload['card_id'], user=session.user)
            except (KeyError, Card.DoesNotExist):
                # Card disappeared; treat as new card.
                if decision == 'existing':
                    summary['skipped'] += 1
                    continue
                card = Card.objects.create(
                    user=session.user,
                    deck=target_deck,
                    card_type=infer_card_type(card_data['front_md'], card_data['back_md']),
                    front_md=card_data['front_md'],
                    back_md=card_data['back_md'],
                    tags=card_data.get('tags', []),
                    media=card_data.get('media', []),
                    source_path=card_data.get('source_path'),
                    source_anchor=card_data.get('source_anchor'),
                )
                ExternalId.objects.get_or_create(card=card, system='logseq', external_key=card_data['external_key'])
                summary['created'] += 1
                continue

            if decision == 'existing':
                summary['skipped'] += 1
                continue

            basic_types = {'basic', 'basic_image_front', 'basic_image_back'}
            if (existing_card.card_type or 'basic') in basic_types:
                existing_card.card_type = infer_card_type(
                    card_data['front_md'], card_data['back_md'], default=existing_card.card_type or 'basic'
                )
            existing_card.front_md = card_data['front_md']
            existing_card.back_md = card_data['back_md']
            existing_card.tags = card_data.get('tags', [])
            existing_card.media = card_data.get('media', [])
            existing_card.source_path = card_data.get('source_path')
            existing_card.source_anchor = card_data.get('source_anchor')
            existing_card.deck = target_deck
            existing_card.save(
                update_fields=[
                    'front_md',
                    'back_md',
                    'tags',
                    'media',
                    'source_path',
                    'source_anchor',
                    'deck',
                    'card_type',
                    'updated_at',
                ]
            )
            summary['updated'] += 1

        import_record = Import.objects.create(
            user=session.user,
            kind='markdown',
            status='ok',
            summary=summary,
            created_at=timezone.now(),
        )
        payload['result'] = summary
        session.status = 'applied'
        session.import_record = import_record
        session.payload = payload
        session.processed = session.total
        session.save(update_fields=['status', 'import_record', 'payload', 'processed', 'updated_at'])
        return import_record


def cancel_markdown_session(session: ImportSession) -> None:
    if session.status != 'ready':
        return
    session.status = 'cancelled'
    session.save(update_fields=['status', 'updated_at'])


@transaction.atomic
def process_markdown_archive(*, user, deck: Deck, uploaded_file) -> dict:
    session = prepare_markdown_session(user=user, deck=deck, uploaded_file=uploaded_file)
    import_record = apply_markdown_session(session)
    return import_record
