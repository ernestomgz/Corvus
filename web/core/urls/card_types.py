from django.urls import path

from core.views import card_types as views

app_name = 'card_types'

urlpatterns = [
    path('', views.list_card_types, name='list'),
    path('create/', views.create_card_type, name='create'),
    path('<int:pk>/', views.view_card_type, name='detail'),
    path('<int:pk>/edit/', views.edit_card_type, name='edit'),
    path('<int:pk>/delete/', views.delete_card_type, name='delete'),
]
