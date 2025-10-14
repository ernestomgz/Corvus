from __future__ import annotations

import uuid
from typing import Iterable

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone


class UserScopedQuerySet(models.QuerySet):
    def for_user(self, user: settings.AUTH_USER_MODEL) -> "UserScopedQuerySet":
        return self.filter(user=user)


class Deck(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='decks')
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='children')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    objects = UserScopedQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'parent', 'name'], name='unique_deck_per_parent'),
        ]
        indexes = [
            models.Index(fields=['user', 'parent']),
            models.Index(fields=['user', 'name']),
            models.Index(fields=['user', 'id']),
        ]
        ordering = ['name']

    def full_path(self) -> str:
        parts = [self.name]
        current = self.parent
        while current is not None:
            parts.append(current.name)
            current = current.parent
        return '/'.join(reversed(parts))

    def __str__(self) -> str:
        return self.full_path()

    def descendant_ids(self, include_self: bool = True) -> list[int]:
        from collections import defaultdict

        rows = Deck.objects.filter(user=self.user).values('id', 'parent_id')
        children: dict[int | None, list[int]] = defaultdict(list)
        for row in rows:
            children[row['parent_id']].append(row['id'])
        stack = [self.id]
        visited: list[int] = []
        while stack:
            current_id = stack.pop()
            visited.append(current_id)
            stack.extend(children.get(current_id, []))
        if not include_self and self.id in visited:
            visited.remove(self.id)
        return visited


class Card(models.Model):
    CARD_TYPE_CHOICES = [
        ('basic', 'Basic'),
        ('basic_image_front', 'Basic (Image on Front)'),
        ('basic_image_back', 'Basic (Image on Back)'),
        ('cloze', 'Cloze'),
        ('problem', 'Problem'),
        ('ai', 'AI'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cards')
    deck = models.ForeignKey(Deck, on_delete=models.CASCADE, related_name='cards')
    card_type = models.CharField(max_length=32, choices=CARD_TYPE_CHOICES)
    front_md = models.TextField()
    back_md = models.TextField()
    tags = ArrayField(models.TextField(), blank=True, default=list)
    source_path = models.TextField(null=True, blank=True)
    source_anchor = models.TextField(null=True, blank=True)
    media = models.JSONField(default=list)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserScopedQuerySet.as_manager()

    class Meta:
        indexes = [
            models.Index(fields=['user', 'deck']),
            models.Index(fields=['updated_at']),
        ]
        ordering = ['-updated_at']

    def __str__(self) -> str:
        return f"{self.card_type}: {self.front_md[:40]}"

    def add_tag(self, tag: str) -> None:
        normalised = tag.strip()
        if not normalised:
            return
        if normalised not in self.tags:
            self.tags.append(normalised)
            self.save(update_fields=['tags'])

    def remove_tag(self, tag: str) -> None:
        normalised = tag.strip()
        if normalised in self.tags:
            updated = [t for t in self.tags if t != normalised]
            self.tags = updated
            self.save(update_fields=['tags'])


class SchedulingState(models.Model):
    QUEUE_STATUS_CHOICES = [
        ('new', 'New'),
        ('learn', 'Learn'),
        ('review', 'Review'),
        ('relearn', 'Relearn'),
    ]

    card = models.OneToOneField(Card, on_delete=models.CASCADE, primary_key=True, related_name='scheduling_state')
    ease = models.FloatField(default=2.5)
    interval_days = models.IntegerField(default=0)
    reps = models.IntegerField(default=0)
    lapses = models.IntegerField(default=0)
    due_at = models.DateTimeField(null=True, blank=True)
    queue_status = models.CharField(max_length=10, choices=QUEUE_STATUS_CHOICES, default='new')
    learning_step_index = models.SmallIntegerField(default=0)
    last_rating = models.SmallIntegerField(null=True, blank=True)

    objects = models.Manager()

    class Meta:
        ordering = ['due_at']


class Review(models.Model):
    id = models.BigAutoField(primary_key=True)
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    reviewed_at = models.DateTimeField(default=timezone.now)
    rating = models.SmallIntegerField()
    elapsed_days = models.IntegerField()
    interval_before = models.IntegerField()
    interval_after = models.IntegerField()
    ease_before = models.FloatField()
    ease_after = models.FloatField()

    class Meta:
        indexes = [
            models.Index(fields=['user', 'reviewed_at']),
            models.Index(fields=['card', 'reviewed_at']),
        ]
        ordering = ['-reviewed_at']


class ExternalId(models.Model):
    SYSTEM_CHOICES = [
        ('logseq', 'Logseq'),
        ('anki', 'Anki'),
        ('manual', 'Manual'),
    ]

    id = models.BigAutoField(primary_key=True)
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='external_ids')
    system = models.CharField(max_length=10, choices=SYSTEM_CHOICES)
    external_key = models.TextField(unique=True)
    extra = models.JSONField(default=dict)

    class Meta:
        indexes = [
            models.Index(fields=['system']),
        ]

    def __str__(self) -> str:
        return f"{self.system}:{self.external_key}"


class Import(models.Model):
    KIND_CHOICES = [
        ('markdown', 'Markdown'),
        ('anki', 'Anki'),
    ]
    STATUS_CHOICES = [
        ('ok', 'OK'),
        ('error', 'Error'),
        ('partial', 'Partial'),
    ]

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='imports')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    summary = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'created_at']),
        ]
        ordering = ['-created_at']


class ImportSession(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('ready', 'Ready'),
        ('applied', 'Applied'),
        ('cancelled', 'Cancelled'),
        ('error', 'Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='import_sessions')
    kind = models.CharField(max_length=10, choices=Import.KIND_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    source_name = models.CharField(max_length=255, blank=True)
    total = models.IntegerField(default=0)
    processed = models.IntegerField(default=0)
    payload = models.JSONField(default=dict)
    import_record = models.OneToOneField('Import', null=True, blank=True, on_delete=models.SET_NULL, related_name='session')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']



def bulk_upsert_external_ids(external_id_tuples: Iterable[tuple[str, str, Card]]) -> None:
    """Utility to bulk-create external ids without clobbering existing rows."""
    objects = [
        ExternalId(system=system, external_key=external_key, card=card)
        for system, external_key, card in external_id_tuples
    ]
    if objects:
        ExternalId.objects.bulk_create(objects, ignore_conflicts=True)
