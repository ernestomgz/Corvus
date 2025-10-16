from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from core.models import Import, ImportSession
from import_anki.forms import AnkiImportForm

from .forms import MarkdownImportForm
from .services import (
    MarkdownImportError,
    apply_markdown_session,
    cancel_markdown_session,
    prepare_markdown_session,
)


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    markdown_form = MarkdownImportForm(user=request.user)
    anki_form = AnkiImportForm(user=request.user)
    recent_imports = Import.objects.filter(user=request.user).order_by('-created_at')[:10]
    pending_sessions = ImportSession.objects.filter(
        user=request.user, kind='markdown', status='ready'
    ).order_by('-created_at')
    return render(
        request,
        'imports/dashboard.html',
        {
            'markdown_form': markdown_form,
            'anki_form': anki_form,
            'imports': recent_imports,
            'sessions': pending_sessions,
        },
    )


@login_required
def upload_markdown(request: HttpRequest) -> HttpResponse:
    if request.method != 'POST':
        return redirect('imports:dashboard')
    form = MarkdownImportForm(request.POST, request.FILES, user=request.user)
    if form.is_valid():
        archive = form.cleaned_data['archive']
        deck = form.cleaned_data['deck']
        try:
            session = prepare_markdown_session(user=request.user, deck=deck, uploaded_file=archive)
        except MarkdownImportError as exc:
            messages.error(request, f"Import failed: {exc}")
            return redirect('imports:dashboard')
        payload = session.payload or {}
        summary = payload.get('summary', {})
        if summary.get('updates', 0) == 0 and summary.get('conflicts', 0) == 0:
            import_record = apply_markdown_session(session)
            applied = import_record.summary
            messages.success(
                request,
                f"Markdown import complete. Created {applied['created']} and updated {applied['updated']} cards.",
            )
            return redirect('imports:dashboard')
        return redirect('imports:markdown-preview', session_id=session.id)
    anki_form = AnkiImportForm(user=request.user)
    recent_imports = Import.objects.filter(user=request.user).order_by('-created_at')[:10]
    pending_sessions = ImportSession.objects.filter(
        user=request.user, kind='markdown', status='ready'
    ).order_by('-created_at')
    return render(
        request,
        'imports/dashboard.html',
        {
            'markdown_form': form,
            'anki_form': anki_form,
            'imports': recent_imports,
            'sessions': pending_sessions,
        },
    )


@login_required
def preview_markdown(request: HttpRequest, session_id: str) -> HttpResponse:
    session = get_object_or_404(
        ImportSession,
        id=session_id,
        user=request.user,
        kind='markdown',
    )
    if session.status != 'ready':
        messages.error(request, 'This import session has already been processed.')
        return redirect('imports:dashboard')

    payload = session.payload or {}
    cards = payload.get('cards', [])
    summary = payload.get('summary', {})
    total = session.total or len(cards)
    processed = session.processed or len(cards)
    progress = 0
    if total:
        progress = min(100, int((processed / total) * 100))

    if request.method == 'POST':
        action = request.POST.get('action', 'apply')
        if action == 'cancel':
            cancel_markdown_session(session)
            messages.info(request, 'Import session cancelled.')
            return redirect('imports:dashboard')
        decisions: dict[int, str] = {}
        for card in cards:
            index = card.get('index')
            if index is None:
                continue
            decision_key = f'card-{index}-decision'
            decision_value = request.POST.get(decision_key, 'imported')
            decisions[int(index)] = decision_value
        try:
            import_record = apply_markdown_session(session, decisions=decisions)
        except MarkdownImportError as exc:
            messages.error(request, f'Unable to apply import: {exc}')
            return redirect('imports:dashboard')
        summary = import_record.summary
        messages.success(
            request,
            f"Markdown import applied. Created {summary['created']}, updated {summary['updated']}, skipped {summary['skipped']}.",
        )
        return redirect('imports:dashboard')

    new_cards = [card for card in cards if not card.get('existing')]
    update_cards = [card for card in cards if card.get('existing')]
    return render(
        request,
        'imports/preview.html',
        {
            'session': session,
            'cards': cards,
            'new_cards': new_cards,
            'update_cards': update_cards,
            'summary': summary,
            'progress': progress,
        },
    )


@login_required
def cancel_markdown(request: HttpRequest, session_id: str) -> HttpResponse:
    if request.method != 'POST':
        raise Http404
    session = get_object_or_404(
        ImportSession,
        id=session_id,
        user=request.user,
        kind='markdown',
    )
    cancel_markdown_session(session)
    messages.info(request, 'Import session cancelled.')
    return redirect('imports:dashboard')
