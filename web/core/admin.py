from django.contrib import admin
from .models import Deck, Card, SchedulingState, Review, ExternalId, Import

@admin.register(Deck)
class DeckAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'name', 'created_at')
    search_fields = ('name',)
    list_filter = ('user',)

@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'deck', 'card_type', 'created_at', 'updated_at')
    search_fields = ('front_md', 'back_md')
    list_filter = ('user', 'deck', 'card_type')

@admin.register(SchedulingState)
class SchedulingStateAdmin(admin.ModelAdmin):
    list_display = ('card', 'ease', 'interval_days', 'reps', 'lapses', 'due_at', 'queue_status', 'learning_step_index', 'last_rating')
    list_filter = ('queue_status',)

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'card', 'user', 'reviewed_at', 'rating')
    list_filter = ('user', 'rating')

@admin.register(ExternalId)
class ExternalIdAdmin(admin.ModelAdmin):
    list_display = ('id', 'card', 'system', 'external_key')
    search_fields = ('external_key',)
    list_filter = ('system',)

@admin.register(Import)
class ImportAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'kind', 'status', 'created_at')
    list_filter = ('kind', 'status', 'user')
