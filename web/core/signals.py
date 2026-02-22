from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Card, SchedulingState
from .scheduling import ensure_state


@receiver(post_save, sender=Card)
def create_scheduling_state(sender, instance: Card, created: bool, **kwargs):
    if created:
        ensure_state(instance)
