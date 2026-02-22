from django.urls import path

from ..views import review

app_name = 'review'

urlpatterns = [
    path('today/', review.review_today, name='today'),
    path('dashboard/', review.review_dashboard, name='dashboard'),
    path('study/', review.review_study, name='study'),
    path('next/', review.review_next, name='next'),
    path('reveal/', review.review_reveal, name='reveal'),
    path('grade/', review.review_grade, name='grade'),
    path('undo/', review.review_undo, name='undo'),
    path('defer/', review.review_defer, name='defer'),
    path('delete/', review.review_delete, name='delete'),
]
