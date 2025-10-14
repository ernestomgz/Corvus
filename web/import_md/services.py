from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.models import Card, Deck, ExternalId, Import


CARD_PATTERN = re.compile(r'^\s*#card\b', re.IGNORECASE)
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
    normalized_asset = asset_path.lstrip('./')
    try:
        data = zip_file.read(normalized_asset)
    except KeyError:
        return None
    digest = hashlib.sha1(data).hexdigest()
    suffix = Path(normalized_asset).suffix or ''
    filename = f"{digest}{suffix}"
    destination_dir = _ensure_media_directory(user_id)
    destination_path = destination_dir / filename
    if not destination_path.exists():
        destination_path.write_bytes(data)
    url = f"{settings.MEDIA_URL}{user_id}/{filename}".replace('//', '/')
    return url, {'name': Path(normalized_asset).name, 'url': url, 'hash': digest}


def _rewrite_media_links(text: str, *, user_id: int, zip_file: zipfile.ZipFile, summary: dict) -> Tuple[str, list[dict]]:
    media_items: list[dict] = []

    def replacer(match: re.Match) -> str:
        original_path = match.group(1)
        asset_path = str(Path(original_path).as_posix())
        result = _copy_media(user_id, zip_file, asset_path)
        if result is None:
            return match.group(0)
        url, media_meta = result
        media_items.append(media_meta)
        summary['media_copied'] += 1
        return match.group(0).replace(original_path, url)

    rewritten = MEDIA_PATTERN.sub(replacer, text)
    return rewritten, media_items


def _parse_markdown_cards(content: str, source_path: str, *, user_id: int, zip_file: zipfile.ZipFile, summary: dict) -> List[ParsedCard]:
    lines = content.splitlines()
    parsed_cards: list[ParsedCard] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not CARD_PATTERN.match(line):
            i += 1
            continue

        line_no = i + 1
        front_content = line.split('#card', 1)[1].strip() if '#card' in line.lower() else ''
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
            )
        )
    return parsed_cards


@transaction.atomic
def process_markdown_archive(*, user, deck: Deck, uploaded_file) -> dict:
    summary = {'created': 0, 'updated': 0, 'skipped': 0, 'media_copied': 0}
    import_record = Import.objects.create(
        user=user,
        kind='markdown',
        status='partial',
        summary=summary,
        created_at=timezone.now(),
    )

    try:
        data = uploaded_file.read()
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            parsed_cards: list[ParsedCard] = []
            for info in zf.infolist():
                if info.is_dir() or not info.filename.lower().endswith('.md'):
                    continue
                try:
                    raw = zf.read(info).decode('utf-8')
                except UnicodeDecodeError:
                    raw = zf.read(info).decode('utf-8', 'ignore')
                parsed_cards.extend(
                    _parse_markdown_cards(raw, info.filename, user_id=user.id, zip_file=zf, summary=summary)
                )

            for parsed in parsed_cards:
                try:
                    external = ExternalId.objects.select_related('card').get(
                        system='logseq', external_key=parsed.external_key
                    )
                except ExternalId.DoesNotExist:
                    card = Card.objects.create(
                        user=user,
                        deck=deck,
                        card_type='basic',
                        front_md=parsed.front_md,
                        back_md=parsed.back_md,
                        tags=parsed.tags,
                        media=parsed.media,
                        source_path=parsed.source_path,
                        source_anchor=parsed.source_anchor,
                    )
                    ExternalId.objects.create(card=card, system='logseq', external_key=parsed.external_key)
                    summary['created'] += 1
                    continue

                card = external.card
                if card.user != user:
                    summary['skipped'] += 1
                    continue
                card.front_md = parsed.front_md
                card.back_md = parsed.back_md
                card.tags = parsed.tags
                card.media = parsed.media
                card.source_path = parsed.source_path
                card.source_anchor = parsed.source_anchor
                card.deck = deck
                card.save()
                summary['updated'] += 1

        import_record.status = 'ok'
        import_record.summary = summary
        import_record.save(update_fields=['status', 'summary'])
        return import_record
    except zipfile.BadZipFile as exc:  # pragma: no cover
        import_record.status = 'error'
        import_record.summary = {'error': str(exc)}
        import_record.save(update_fields=['status', 'summary'])
        raise MarkdownImportError('Invalid ZIP archive') from exc
    except Exception as exc:  # pragma: no cover
        import_record.status = 'error'
        import_record.summary = {'error': str(exc)}
        import_record.save(update_fields=['status', 'summary'])
        raise
