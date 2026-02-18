from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from core.models import Import
from import_md.forms import MarkdownImportForm

from .forms import AnkiImportForm
from .services import AnkiImportError, process_apkg_archive


@login_required
def upload_anki(request: HttpRequest) -> HttpResponse:
    if request.method != 'POST':
        return redirect('imports:dashboard')
    form = AnkiImportForm(request.POST, request.FILES, user=request.user)
    if form.is_valid():
        package = form.cleaned_data['package']
        deck = form.cleaned_data['deck']
        try:
            import_record = process_apkg_archive(user=request.user, deck=deck, uploaded_file=package)
            summary = import_record.summary
            messages.success(
                request,
                f"Anki import complete. Created {summary['created']} and updated {summary['updated']} cards.",
            )
        except AnkiImportError as exc:
            messages.error(request, f"Import failed: {exc}")
        return redirect('imports:dashboard')
    markdown_form = MarkdownImportForm(user=request.user)
    recent_imports = Import.objects.filter(user=request.user).order_by('-created_at')[:10]
    return render(
        request,
        'imports/dashboard.html',
        {
            'anki_form': form,
            'markdown_form': markdown_form,
            'imports': recent_imports,
        },
    )
