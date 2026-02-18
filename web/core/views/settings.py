from __future__ import annotations

import io
import yaml

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from ..forms import UserSettingsForm
from ..models import UserSettings


def _load_settings_for_user(user):
    settings_obj, _ = UserSettings.objects.get_or_create(user=user)
    return settings_obj


@login_required
def settings_detail(request: HttpRequest) -> HttpResponse:
    settings_obj = _load_settings_for_user(request.user)
    form = UserSettingsForm(request.POST or None, instance=settings_obj, user=request.user)
    if request.method == 'POST':
        if form.is_valid():
            # Preserve existing secrets when fields left blank.
            original = _load_settings_for_user(request.user)
            settings_obj = form.save(commit=False)
            if not form.cleaned_data.get('plugin_github_token'):
                settings_obj.plugin_github_token = original.plugin_github_token
            if not form.cleaned_data.get('plugin_ai_api_key'):
                settings_obj.plugin_ai_api_key = original.plugin_ai_api_key
            settings_obj.save()
            messages.success(request, 'Settings saved.')
            return redirect('settings:detail')
    export_url = redirect('settings:export').url
    return render(
        request,
        'core/settings.html',
        {
            'form': form,
            'export_url': export_url,
            'settings_obj': settings_obj,
        },
    )


@login_required
def settings_export(request: HttpRequest) -> HttpResponse:
    settings_obj = _load_settings_for_user(request.user)
    payload = settings_obj.to_export_payload()
    buffer = io.StringIO()
    yaml.safe_dump(payload, buffer, sort_keys=False)
    response = HttpResponse(buffer.getvalue(), content_type='text/yaml')
    response['Content-Disposition'] = 'attachment; filename=\"corvus-settings.yaml\"'
    return response
