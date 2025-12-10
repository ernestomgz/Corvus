from __future__ import annotations

from django.db import migrations


def create_card_types(apps, schema_editor):
    CardType = apps.get_model('core', 'CardType')
    CardImportFormat = apps.get_model('core', 'CardImportFormat')
    Card = apps.get_model('core', 'Card')
    db_alias = schema_editor.connection.alias

    base_schema = [
        {'key': 'front', 'label': 'Front'},
        {'key': 'back', 'label': 'Back'},
        {'key': 'hierarchy', 'label': 'Hierarchy'},
        {'key': 'title', 'label': 'Title'},
        {'key': 'context', 'label': 'Context'},
    ]
    configs = [
        {
            'slug': 'basic',
            'name': 'Basic',
            'description': 'Single front/back Markdown note',
            'field_schema': list(base_schema),
            'front_template': '{{hierarchy}}\n{{title}}',
            'back_template': '{{back}}',
            'formats': [
                {
                    'name': 'Heading marker',
                    'template': '{{hierarchy}}\n## {{title}} #card\n{{back}}',
                    'options': {'marker': '#card'},
                },
                {
                    'name': 'Inline marker',
                    'template': '{{hierarchy}}\n{{title}} #card\n{{back}}',
                    'options': {'marker': '#card'},
                },
                {
                    'name': 'Line marker',
                    'template': '{{hierarchy}}\n{{title}}\n#card\n{{back}}',
                    'options': {'marker': '#card'},
                },
                {
                    'name': 'Marker with metadata',
                    'template': '{{hierarchy}}\n## {{title}} #card\nid:: {{external}}\ntags:: {{tags}}\n\n{{back}}',
                    'options': {
                        'marker': '#card',
                        'external_id_field': 'external',
                        'tags_field': 'tags',
                        'anchor_field': 'external',
                    },
                },
            ],
        },
        {
            'slug': 'basic_image_front',
            'name': 'Basic (Image on Front)',
            'description': 'Front/back card optimized for media on front',
            'field_schema': list(base_schema),
            'front_template': '{{front}}',
            'back_template': '{{back}}',
            'formats': [],
        },
        {
            'slug': 'basic_image_back',
            'name': 'Basic (Image on Back)',
            'description': 'Front/back card optimized for media on back',
            'field_schema': list(base_schema),
            'front_template': '{{front}}',
            'back_template': '{{back}}',
            'formats': [],
        },
        {
            'slug': 'cloze',
            'name': 'Cloze',
            'description': 'Cloze-style deletions',
            'field_schema': list(base_schema),
            'front_template': '{{front}}',
            'back_template': '{{back}}',
            'formats': [],
        },
        {
            'slug': 'problem',
            'name': 'Problem',
            'description': 'Problem/solution layout',
            'field_schema': list(base_schema),
            'front_template': '{{front}}',
            'back_template': '{{back}}',
            'formats': [],
        },
        {
            'slug': 'ai',
            'name': 'AI',
            'description': 'AI generated prompts',
            'field_schema': list(base_schema),
            'front_template': '{{front}}',
            'back_template': '{{back}}',
            'formats': [],
        },
        {
            'slug': 'photo',
            'name': 'Photo Card',
            'description': 'Question/photo/answer cards',
            'field_schema': [
                {'key': 'question', 'label': 'Question'},
                {'key': 'photo', 'label': 'Photo'},
                {'key': 'answer', 'label': 'Answer'},
            ],
            'front_template': '{{note.path}}\n{{question}}\n{{photo}}',
            'back_template': 'The photo meaning is: {{answer}}',
            'formats': [
                {
                    'name': 'Photo question',
                    'template': '## {{question}} #photo-card\n{{photo}}\n\n{{answer}}',
                    'options': {'marker': '#photo-card', 'default_tags': ['photo-card']},
                },
                {
                    'name': 'Photo quick capture',
                    'template': '{{photo}} #photo-card\n\n{{answer}}',
                    'options': {'marker': '#photo-card', 'default_tags': ['photo-card']},
                },
            ],
        },
    ]

    type_map: dict[str, object] = {}
    for config in configs:
        card_type, _ = CardType.objects.using(db_alias).get_or_create(
            user=None,
            slug=config['slug'],
            defaults={
                'name': config['name'],
                'description': config.get('description', ''),
                'field_schema': config['field_schema'],
                'front_template': config['front_template'],
                'back_template': config['back_template'],
            },
        )
        type_map[config['slug']] = card_type
        for fmt in config.get('formats', []):
            CardImportFormat.objects.using(db_alias).get_or_create(
                card_type=card_type,
                name=fmt['name'],
                defaults={
                    'format_kind': 'markdown',
                    'template': fmt['template'],
                    'options': fmt.get('options', {}),
                },
            )

    default_type = type_map.get('basic')
    if default_type is None:
        return
    cards = Card.objects.using(db_alias).all()
    for card in cards:
        slug = (card.card_type or '').strip() or 'basic'
        target = type_map.get(slug, default_type)
        card.card_type_temp_id = target.id
        if not card.field_values:
            card.field_values = {'front': card.front_md, 'back': card.back_md}
        card.save(update_fields=['card_type_temp', 'field_values'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_card_type_models'),
    ]

    operations = [
        migrations.RunPython(create_card_types, migrations.RunPython.noop),
    ]
