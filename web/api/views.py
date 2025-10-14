from __future__ import annotations

import json
from typing import Any, Dict

from django.contrib.auth import authenticate, login, logout
from django.db.models import Q
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from accounts.models import User
from core.models import Card, Deck, Import
from core.scheduling import ensure_state
from core.services.review import get_next_card, get_today_summary, grade_card_for_user
from import_anki.services import AnkiImportError, process_apkg_archive
from import_md.services import MarkdownImportError, process_markdown_archive


def _json_error(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({'error': message}, status=status)


def _parse_json(request: HttpRequest) -> Dict[str, Any]:
    try:
        if not request.body:
            return {}
        return json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError as exc:  # pragma: no cover - error path exercised in tests
        raise ValueError(f'Invalid JSON payload: {exc}')


def _require_user(request: HttpRequest) -> User:
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        raise PermissionError('authentication required')
    return user  # type: ignore[return-value]


def _deck_to_dict(deck: Deck) -> dict:
    return {
        'id': deck.id,
        'name': deck.name,
        'description': deck.description,
        'created_at': deck.created_at.isoformat(),
    }


def _card_to_dict(card: Card) -> dict:
    state = getattr(card, 'scheduling_state', None) or ensure_state(card)
    return {
        'id': str(card.id),
        'deck_id': card.deck_id,
        'card_type': card.card_type,
        'front_md': card.front_md,
        'back_md': card.back_md,
        'tags': card.tags,
        'media': card.media,
        'source_path': card.source_path,
        'source_anchor': card.source_anchor,
        'created_at': card.created_at.isoformat(),
        'updated_at': card.updated_at.isoformat(),
        'scheduling': {
            'queue_status': state.queue_status,
            'due_at': state.due_at.isoformat() if state.due_at else None,
            'ease': state.ease,
            'interval_days': state.interval_days,
            'reps': state.reps,
            'lapses': state.lapses,
            'last_rating': state.last_rating,
        },
    }


@csrf_exempt
@require_http_methods(['POST'])
def auth_register(request: HttpRequest) -> JsonResponse:
    try:
        payload = _parse_json(request)
    except ValueError as exc:
        return _json_error(str(exc))
    email = payload.get('email')
    password = payload.get('password')
    if not email or not password:
        return _json_error('email and password required')
    if User.objects.filter(email=email).exists():
        return _json_error('email already registered')
    user = User.objects.create_user(email=email, password=password)
    login(request, user)
    return JsonResponse({'id': user.id, 'email': user.email}, status=201)


@csrf_exempt
@require_http_methods(['POST'])
def auth_login(request: HttpRequest) -> JsonResponse:
    try:
        payload = _parse_json(request)
    except ValueError as exc:
        return _json_error(str(exc))
    email = payload.get('email')
    password = payload.get('password')
    if not email or not password:
        return _json_error('email and password required')
    user = authenticate(request, email=email, password=password)
    if user is None:
        return _json_error('invalid credentials', status=401)
    login(request, user)
    return JsonResponse({'id': user.id, 'email': user.email})


@csrf_exempt
@require_http_methods(['POST'])
def auth_logout(request: HttpRequest) -> JsonResponse:
    logout(request)
    return JsonResponse({'success': True})


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def decks_collection(request: HttpRequest) -> JsonResponse:
    try:
        user = _require_user(request)
    except PermissionError as exc:
        return _json_error(str(exc), status=401)

    if request.method == 'GET':
        decks = Deck.objects.for_user(user).order_by('name')
        return JsonResponse([_deck_to_dict(deck) for deck in decks], safe=False)

    try:
        payload = _parse_json(request)
    except ValueError as exc:
        return _json_error(str(exc))
    name = payload.get('name')
    if not name:
        return _json_error('name required')
    description = payload.get('description', '')
    deck = Deck.objects.create(user=user, name=name, description=description)
    return JsonResponse(_deck_to_dict(deck), status=201)


@csrf_exempt
@require_http_methods(['GET', 'PATCH', 'DELETE'])
def deck_detail(request: HttpRequest, deck_id: int) -> JsonResponse:
    try:
        user = _require_user(request)
    except PermissionError as exc:
        return _json_error(str(exc), status=401)
    try:
        deck = Deck.objects.get(id=deck_id, user=user)
    except Deck.DoesNotExist:
        return _json_error('deck not found', status=404)

    if request.method == 'GET':
        return JsonResponse(_deck_to_dict(deck))

    if request.method == 'PATCH':
        try:
            payload = _parse_json(request)
        except ValueError as exc:
            return _json_error(str(exc))
        if 'name' in payload:
            deck.name = payload['name']
        if 'description' in payload:
            deck.description = payload['description']
        deck.save(update_fields=['name', 'description'])
        return JsonResponse(_deck_to_dict(deck))

    deck.delete()
    return JsonResponse({'success': True})


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def cards_collection(request: HttpRequest) -> JsonResponse:
    try:
        user = _require_user(request)
    except PermissionError as exc:
        return _json_error(str(exc), status=401)

    if request.method == 'GET':
        deck_id = request.GET.get('deck_id')
        search = request.GET.get('q')
        tag = request.GET.get('tag')
        cards = Card.objects.for_user(user).select_related('deck', 'scheduling_state')
        if deck_id:
            cards = cards.filter(deck_id=deck_id)
        if tag:
            cards = cards.filter(tags__contains=[tag.strip()])
        if search:
            cards = cards.filter(Q(front_md__icontains=search) | Q(back_md__icontains=search))
        cards = cards.order_by('-updated_at')
        return JsonResponse([_card_to_dict(card) for card in cards], safe=False)

    try:
        payload = _parse_json(request)
    except ValueError as exc:
        return _json_error(str(exc))
    deck_id = payload.get('deck_id')
    if not deck_id:
        return _json_error('deck_id required')
    try:
        deck = Deck.objects.get(id=deck_id, user=user)
    except Deck.DoesNotExist:
        return _json_error('deck not found', status=404)
    card_type = payload.get('card_type', 'basic')
    if card_type not in {'basic', 'cloze', 'problem', 'ai'}:
        return _json_error('invalid card_type')
    tags = payload.get('tags', [])
    if not isinstance(tags, list):
        return _json_error('tags must be a list')
    card = Card.objects.create(
        user=user,
        deck=deck,
        card_type=card_type,
        front_md=payload.get('front_md', ''),
        back_md=payload.get('back_md', ''),
        tags=[str(tag) for tag in tags],
    )
    ensure_state(card)
    return JsonResponse(_card_to_dict(card), status=201)


@csrf_exempt
@require_http_methods(['GET', 'PATCH', 'DELETE'])
def card_detail(request: HttpRequest, card_id: str) -> JsonResponse:
    try:
        user = _require_user(request)
    except PermissionError as exc:
        return _json_error(str(exc), status=401)
    try:
        card = Card.objects.select_related('deck', 'scheduling_state').get(id=card_id, user=user)
    except Card.DoesNotExist:
        return _json_error('card not found', status=404)

    if request.method == 'GET':
        return JsonResponse(_card_to_dict(card))

    if request.method == 'PATCH':
        try:
            payload = _parse_json(request)
        except ValueError as exc:
            return _json_error(str(exc))
        if 'deck_id' in payload:
            try:
                deck = Deck.objects.get(id=payload['deck_id'], user=user)
            except Deck.DoesNotExist:
                return _json_error('deck not found', status=404)
            card.deck = deck
        if 'card_type' in payload:
            card_type = payload['card_type']
            if card_type not in {'basic', 'cloze', 'problem', 'ai'}:
                return _json_error('invalid card_type')
            card.card_type = card_type
        if 'front_md' in payload:
            card.front_md = payload['front_md']
        if 'back_md' in payload:
            card.back_md = payload['back_md']
        if 'tags' in payload:
            tags = payload['tags']
            if not isinstance(tags, list):
                return _json_error('tags must be a list')
            card.tags = [str(tag) for tag in tags]
        card.save()
        return JsonResponse(_card_to_dict(card))

    card.delete()
    return JsonResponse({'success': True})


@csrf_exempt
@require_http_methods(['GET'])
def review_today(request: HttpRequest) -> JsonResponse:
    try:
        user = _require_user(request)
    except PermissionError as exc:
        return _json_error(str(exc), status=401)
    deck = None
    deck_id = request.GET.get('deck_id')
    if deck_id:
        try:
            deck = Deck.objects.get(id=deck_id, user=user)
        except Deck.DoesNotExist:
            return _json_error('deck not found', status=404)
    summary = get_today_summary(user, deck)
    return JsonResponse({
        'new_count': summary.new_count,
        'review_count': summary.review_count,
        'due_count': summary.due_count,
    })


@csrf_exempt
@require_http_methods(['POST'])
def review_next(request: HttpRequest) -> JsonResponse:
    try:
        user = _require_user(request)
    except PermissionError as exc:
        return _json_error(str(exc), status=401)
    try:
        payload = _parse_json(request)
    except ValueError as exc:
        return _json_error(str(exc))
    deck = None
    deck_id = payload.get('deck_id')
    if deck_id:
        try:
            deck = Deck.objects.get(id=deck_id, user=user)
        except Deck.DoesNotExist:
            return _json_error('deck not found', status=404)
    card = get_next_card(user, deck)
    if not card:
        return JsonResponse({'card_id': None})
    ensure_state(card)
    return JsonResponse({'card_id': str(card.id), 'card_type': card.card_type, 'front_md': card.front_md})


@csrf_exempt
@require_http_methods(['POST'])
def review_reveal(request: HttpRequest) -> JsonResponse:
    try:
        user = _require_user(request)
    except PermissionError as exc:
        return _json_error(str(exc), status=401)
    try:
        payload = _parse_json(request)
    except ValueError as exc:
        return _json_error(str(exc))
    card_id = payload.get('card_id')
    if not card_id:
        return _json_error('card_id required')
    try:
        card = Card.objects.get(id=card_id, user=user)
    except Card.DoesNotExist:
        return _json_error('card not found', status=404)
    ensure_state(card)
    return JsonResponse({'card_id': str(card.id), 'back_md': card.back_md})


@csrf_exempt
@require_http_methods(['POST'])
def review_grade(request: HttpRequest) -> JsonResponse:
    try:
        user = _require_user(request)
    except PermissionError as exc:
        return _json_error(str(exc), status=401)
    try:
        payload = _parse_json(request)
    except ValueError as exc:
        return _json_error(str(exc))
    card_id = payload.get('card_id')
    rating = payload.get('rating')
    deck_id = payload.get('deck_id')
    if card_id is None or rating is None:
        return _json_error('card_id and rating required')
    try:
        rating_int = int(rating)
    except (TypeError, ValueError):
        return _json_error('rating must be an integer between 0 and 3')
    if rating_int not in {0, 1, 2, 3}:
        return _json_error('rating must be between 0 and 3')
    deck = None
    if deck_id:
        try:
            deck = Deck.objects.get(id=deck_id, user=user)
        except Deck.DoesNotExist:
            return _json_error('deck not found', status=404)
    if not Card.objects.filter(id=card_id, user=user).exists():
        return _json_error('card not found', status=404)
    grade_card_for_user(user=user, card_id=card_id, rating=rating_int)
    next_card = get_next_card(user, deck)
    return JsonResponse({'next_available': next_card is not None})


@csrf_exempt
@require_http_methods(['POST'])
def import_markdown(request: HttpRequest) -> JsonResponse:
    try:
        user = _require_user(request)
    except PermissionError as exc:
        return _json_error(str(exc), status=401)
    deck_id = request.POST.get('deck_id')
    archive = request.FILES.get('archive')
    if not deck_id or archive is None:
        return _json_error('deck_id and archive required')
    try:
        deck = Deck.objects.get(id=deck_id, user=user)
    except Deck.DoesNotExist:
        return _json_error('deck not found', status=404)
    try:
        import_record = process_markdown_archive(user=user, deck=deck, uploaded_file=archive)
    except MarkdownImportError as exc:
        return _json_error(str(exc), status=400)
    return JsonResponse({'import_id': import_record.id, 'summary': import_record.summary})


@csrf_exempt
@require_http_methods(['POST'])
def import_anki(request: HttpRequest) -> JsonResponse:
    try:
        user = _require_user(request)
    except PermissionError as exc:
        return _json_error(str(exc), status=401)
    deck_id = request.POST.get('deck_id')
    package = request.FILES.get('package')
    if not deck_id or package is None:
        return _json_error('deck_id and package required')
    try:
        deck = Deck.objects.get(id=deck_id, user=user)
    except Deck.DoesNotExist:
        return _json_error('deck not found', status=404)
    try:
        import_record = process_apkg_archive(user=user, deck=deck, uploaded_file=package)
    except AnkiImportError as exc:
        return _json_error(str(exc), status=400)
    return JsonResponse({'import_id': import_record.id, 'summary': import_record.summary})


@csrf_exempt
@require_http_methods(['GET'])
def import_status(request: HttpRequest, import_id: int) -> JsonResponse:
    try:
        user = _require_user(request)
    except PermissionError as exc:
        return _json_error(str(exc), status=401)
    try:
        import_record = Import.objects.get(id=import_id, user=user)
    except Import.DoesNotExist:
        return _json_error('import not found', status=404)
    return JsonResponse(
        {
            'id': import_record.id,
            'kind': import_record.kind,
            'status': import_record.status,
            'summary': import_record.summary,
        }
    )
