from django.urls import path

from ..views import decks

app_name = 'decks'

urlpatterns = [
    path('', decks.deck_list, name='list'),
    path('create/', decks.deck_list, name='create'),
    path('<int:pk>/edit/', decks.deck_update, name='edit'),
    path('<int:pk>/delete/', decks.deck_delete, name='delete'),
]
