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


class CardType(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='card_types',
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=64)
    description = models.TextField(blank=True)
    field_schema = models.JSONField(default=list, blank=True)
    front_template = models.TextField()
    back_template = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserScopedQuerySet.as_manager()

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['user', 'slug'], name='unique_card_type_per_user'),
            models.UniqueConstraint(
                fields=['slug'],
                condition=models.Q(user__isnull=True),
                name='unique_global_card_type_slug',
            ),
        ]

    def __str__(self) -> str:
        owner = getattr(self.user, 'email', None) or 'global'
        return f"{self.name} ({owner})"


class CardImportFormat(models.Model):
    FORMAT_CHOICES = [
        ('markdown', 'Markdown'),
    ]

    id = models.BigAutoField(primary_key=True)
    card_type = models.ForeignKey(CardType, on_delete=models.CASCADE, related_name='import_formats')
    name = models.CharField(max_length=255)
    format_kind = models.CharField(max_length=32, choices=FORMAT_CHOICES)
    template = models.TextField()
    options = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return f"{self.card_type.name}: {self.name}"


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


class StudySet(models.Model):
    KIND_DECK = 'deck'
    KIND_TAG = 'tag'
    KIND_CHOICES = [
        (KIND_DECK, 'Deck'),
        (KIND_TAG, 'Tag'),
    ]

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='study_sets')
    name = models.CharField(max_length=255)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    deck = models.ForeignKey(Deck, null=True, blank=True, on_delete=models.CASCADE, related_name='study_sets')
    tag = models.CharField(max_length=255, blank=True)
    is_favorite = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserScopedQuerySet.as_manager()

    class Meta:
        ordering = ['-is_favorite', 'name']
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(kind='deck', deck__isnull=False)
                    | models.Q(kind='tag', deck__isnull=True)
                ),
                name='study_set_requires_matching_deck_state',
            ),
            models.CheckConstraint(
                check=(
                    models.Q(kind='tag', tag__gt='')
                    | models.Q(kind='deck')
                ),
                name='study_set_requires_tag_for_tag_kind',
            ),
            models.UniqueConstraint(
                fields=['user', 'deck'],
                condition=models.Q(kind='deck'),
                name='study_set_unique_deck',
            ),
            models.UniqueConstraint(
                fields=['user', 'tag'],
                condition=models.Q(kind='tag'),
                name='study_set_unique_tag',
            ),
        ]

    def __str__(self) -> str:
        if self.kind == self.KIND_TAG:
            return f"{self.name} (Tag: {self.tag})"
        if self.deck:
            return f"{self.name} (Deck: {self.deck.full_path()})"
        return self.name


class Card(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cards')
    deck = models.ForeignKey(Deck, on_delete=models.CASCADE, related_name='cards')
    card_type = models.ForeignKey(CardType, on_delete=models.PROTECT, related_name='cards')
    front_md = models.TextField()
    back_md = models.TextField()
    tags = ArrayField(models.TextField(), blank=True, default=list)
    field_values = models.JSONField(default=dict, blank=True)
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
        type_name = getattr(self.card_type, 'name', '')
        return f"{type_name}: {self.front_md[:40]}"

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
