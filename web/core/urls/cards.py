from django.urls import path

from ..views import cards

app_name = 'cards'

urlpatterns = [
    path('', cards.card_list, name='list'),
    path('create/', cards.card_create, name='create'),
    path('<uuid:pk>/', cards.card_detail, name='detail'),
    path('<uuid:pk>/edit/', cards.card_edit, name='edit'),
    path('<uuid:pk>/delete/', cards.card_delete, name='delete'),
]
