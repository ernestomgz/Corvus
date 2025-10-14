from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from core.models import Import
from import_anki.forms import AnkiImportForm

from .forms import MarkdownImportForm
from .services import MarkdownImportError, process_markdown_archive


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    markdown_form = MarkdownImportForm(user=request.user)
    anki_form = AnkiImportForm(user=request.user)
    recent_imports = Import.objects.filter(user=request.user).order_by('-created_at')[:10]
    return render(
        request,
        'imports/dashboard.html',
        {
            'markdown_form': markdown_form,
            'anki_form': anki_form,
            'imports': recent_imports,
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
            import_record = process_markdown_archive(user=request.user, deck=deck, uploaded_file=archive)
            summary = import_record.summary
            messages.success(
                request,
                f"Markdown import complete. Created {summary['created']} and updated {summary['updated']} cards.",
            )
        except MarkdownImportError as exc:
            messages.error(request, f"Import failed: {exc}")
        return redirect('imports:dashboard')
    anki_form = AnkiImportForm(user=request.user)
    recent_imports = Import.objects.filter(user=request.user).order_by('-created_at')[:10]
    return render(
        request,
        'imports/dashboard.html',
        {
            'markdown_form': form,
            'anki_form': anki_form,
            'imports': recent_imports,
        },
    )
