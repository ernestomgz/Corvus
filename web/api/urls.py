from django.urls import path

from . import views

app_name = 'api'

urlpatterns = [
    path('analytics/heatmap/', views.analytics_heatmap_summary, name='analytics-heatmap'),
    path('analytics/heatmap/<str:date_str>/', views.analytics_heatmap_day, name='analytics-heatmap-day'),
    path('auth/register', views.auth_register, name='auth-register'),
    path('auth/login', views.auth_login, name='auth-login'),
    path('auth/logout', views.auth_logout, name='auth-logout'),
    path('decks/', views.decks_collection, name='decks-collection'),
    path('decks/<int:deck_id>', views.deck_detail, name='deck-detail'),
    path('cards/', views.cards_collection, name='cards-collection'),
    path('cards/<uuid:card_id>', views.card_detail, name='card-detail'),
    path('review/today', views.review_today, name='review-today'),
    path('review/next', views.review_next, name='review-next'),
    path('review/reveal', views.review_reveal, name='review-reveal'),
    path('review/grade', views.review_grade, name='review-grade'),
    path('imports/markdown', views.import_markdown, name='import-markdown'),
    path('imports/anki', views.import_anki, name='import-anki'),
    path('imports/<int:import_id>', views.import_status, name='import-status'),
]
