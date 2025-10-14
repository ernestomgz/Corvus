from django.urls import path

from ..views import review

app_name = 'review'

urlpatterns = [
    path('today/', review.review_today, name='today'),
    path('next/', review.review_next, name='next'),
    path('reveal/', review.review_reveal, name='reveal'),
    path('grade/', review.review_grade, name='grade'),
]
