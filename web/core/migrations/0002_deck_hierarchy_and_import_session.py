from __future__ import annotations

import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='deck',
            name='parent',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='core.deck'),
        ),
        migrations.RemoveConstraint(
            model_name='deck',
            name='unique_deck_per_user',
        ),
        migrations.AddConstraint(
            model_name='deck',
            constraint=models.UniqueConstraint(fields=('user', 'parent', 'name'), name='unique_deck_per_parent'),
        ),
        migrations.AddIndex(
            model_name='deck',
            index=models.Index(fields=('user', 'parent'), name='core_deck_user_parent_idx'),
        ),
        migrations.AlterField(
            model_name='card',
            name='card_type',
            field=models.CharField(
                choices=[
                    ('basic', 'Basic'),
                    ('basic_image_front', 'Basic (Image on Front)'),
                    ('basic_image_back', 'Basic (Image on Back)'),
                    ('cloze', 'Cloze'),
                    ('problem', 'Problem'),
                    ('ai', 'AI'),
                ],
                max_length=32,
            ),
        ),
        migrations.CreateModel(
            name='ImportSession',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('ready', 'Ready'), ('applied', 'Applied'), ('cancelled', 'Cancelled'), ('error', 'Error')], default='pending', max_length=20)),
                ('source_name', models.CharField(blank=True, max_length=255)),
                ('total', models.IntegerField(default=0)),
                ('processed', models.IntegerField(default=0)),
                ('payload', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('import_record', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='session', to='core.import')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='import_sessions', to=settings.AUTH_USER_MODEL)),
                ('kind', models.CharField(choices=[('markdown', 'Markdown'), ('anki', 'Anki')], max_length=10)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddIndex(
            model_name='importsession',
            index=models.Index(fields=('user', 'status'), name='core_importsession_user_status_idx'),
        ),
        migrations.AddIndex(
            model_name='importsession',
            index=models.Index(fields=('created_at',), name='core_importsession_created_idx'),
        ),
    ]
