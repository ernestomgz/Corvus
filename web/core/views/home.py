from __future__ import annotations

from django.contrib.auth import get_user_model
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect


def landing(request: HttpRequest) -> HttpResponse:
    """Redirect visitors to the appropriate homepage."""
    if request.user.is_authenticated:
        return redirect('review:dashboard')
    return redirect('accounts:login')
