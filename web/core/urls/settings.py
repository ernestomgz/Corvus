from django.urls import path

from ..views import settings as settings_views

app_name = 'settings'

urlpatterns = [
    path('', settings_views.settings_detail, name='detail'),
    path('export/', settings_views.settings_export, name='export'),
]
