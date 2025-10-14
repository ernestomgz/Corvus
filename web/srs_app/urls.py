from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from core.views import home

urlpatterns = [
    path('', home.landing, name='landing'),
    path('admin/', admin.site.urls),
    path('accounts/', include(('accounts.urls', 'accounts'), namespace='accounts')),
    path('decks/', include(('core.urls.decks', 'decks'), namespace='decks')),
    path('cards/', include(('core.urls.cards', 'cards'), namespace='cards')),
    path('review/', include(('core.urls.review', 'review'), namespace='review')),
    path('imports/', include(('import_md.urls', 'imports'), namespace='imports')),
    path('api/v1/', include(('api.urls', 'api'), namespace='api')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
