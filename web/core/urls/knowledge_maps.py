from django.urls import path

from ..views import knowledge_maps

app_name = 'knowledge_maps'

urlpatterns = [
    path('', knowledge_maps.knowledge_map_list, name='list'),
    path('<slug:slug>/', knowledge_maps.knowledge_map_detail, name='detail'),
]
