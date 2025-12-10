from __future__ import annotations

from django import template

register = template.Library()


@register.filter
def study_summary(summary_map, study_set):
    """Return the TodaySummary for the given study set id."""
    if summary_map is None or study_set is None:
        return None
    key = getattr(study_set, 'id', study_set)
    return summary_map.get(key)


@register.filter
def dict_get(mapping, key):
    if mapping is None:
        return None
    return mapping.get(key)
