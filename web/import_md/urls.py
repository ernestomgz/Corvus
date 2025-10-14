from django.urls import path

from import_anki import views as anki_views

from . import views

app_name = 'imports'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('markdown/', views.upload_markdown, name='markdown'),
    path('anki/', anki_views.upload_anki, name='anki'),
]
