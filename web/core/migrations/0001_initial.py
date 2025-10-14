from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid
from django.contrib.postgres.fields import ArrayField


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL("CREATE EXTENSION IF NOT EXISTS pgcrypto"),
        migrations.CreateModel(
            name='Deck',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='decks', to='accounts.user')),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Card',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('card_type', models.CharField(choices=[('basic', 'Basic'), ('cloze', 'Cloze'), ('problem', 'Problem'), ('ai', 'AI')], max_length=10)),
                ('front_md', models.TextField()),
                ('back_md', models.TextField()),
                ('tags', ArrayField(base_field=models.TextField(), blank=True, default=list, size=None)),
                ('source_path', models.TextField(blank=True, null=True)),
                ('source_anchor', models.TextField(blank=True, null=True)),
                ('media', models.JSONField(default=list)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deck', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cards', to='core.deck')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cards', to='accounts.user')),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='SchedulingState',
            fields=[
                ('card', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name='scheduling_state', serialize=False, to='core.card')),
                ('ease', models.FloatField(default=2.5)),
                ('interval_days', models.IntegerField(default=0)),
                ('reps', models.IntegerField(default=0)),
                ('lapses', models.IntegerField(default=0)),
                ('due_at', models.DateTimeField(blank=True, null=True)),
                ('queue_status', models.CharField(choices=[('new', 'New'), ('learn', 'Learn'), ('review', 'Review'), ('relearn', 'Relearn')], default='new', max_length=10)),
                ('learning_step_index', models.SmallIntegerField(default=0)),
                ('last_rating', models.SmallIntegerField(blank=True, null=True)),
            ],
            options={
                'ordering': ['due_at'],
            },
        ),
        migrations.CreateModel(
            name='Review',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('reviewed_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('rating', models.SmallIntegerField()),
                ('elapsed_days', models.IntegerField()),
                ('interval_before', models.IntegerField()),
                ('interval_after', models.IntegerField()),
                ('ease_before', models.FloatField()),
                ('ease_after', models.FloatField()),
                ('card', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to='core.card')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to='accounts.user')),
            ],
            options={
                'ordering': ['-reviewed_at'],
            },
        ),
        migrations.CreateModel(
            name='Import',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('kind', models.CharField(choices=[('markdown', 'Markdown'), ('anki', 'Anki')], max_length=10)),
                ('status', models.CharField(choices=[('ok', 'OK'), ('error', 'Error'), ('partial', 'Partial')], max_length=10)),
                ('summary', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='imports', to='accounts.user')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ExternalId',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('system', models.CharField(choices=[('logseq', 'Logseq'), ('anki', 'Anki'), ('manual', 'Manual')], max_length=10)),
                ('external_key', models.TextField(unique=True)),
                ('extra', models.JSONField(default=dict)),
                ('card', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='external_ids', to='core.card')),
            ],
        ),
        migrations.AddConstraint(
            model_name='deck',
            constraint=models.UniqueConstraint(fields=('user', 'name'), name='unique_deck_per_user'),
        ),
        migrations.AddIndex(
            model_name='deck',
            index=models.Index(fields=['user', 'name'], name='core_deck_user__b72397_idx'),
        ),
        migrations.AddIndex(
            model_name='deck',
            index=models.Index(fields=['user', 'id'], name='core_deck_user__cd49e9_idx'),
        ),
        migrations.AddIndex(
            model_name='card',
            index=models.Index(fields=['user', 'deck'], name='core_card_user__01a54c_idx'),
        ),
        migrations.AddIndex(
            model_name='card',
            index=models.Index(fields=['updated_at'], name='core_card_updated__ba3f04_idx'),
        ),
        migrations.AddIndex(
            model_name='review',
            index=models.Index(fields=['user', 'reviewed_at'], name='core_review_user__1ba91a_idx'),
        ),
        migrations.AddIndex(
            model_name='review',
            index=models.Index(fields=['card', 'reviewed_at'], name='core_review_card_r_3ab683_idx'),
        ),
        migrations.AddIndex(
            model_name='externalid',
            index=models.Index(fields=['system'], name='core_externa_system_71e059_idx'),
        ),
        migrations.AddIndex(
            model_name='import',
            index=models.Index(fields=['user', 'created_at'], name='core_import_user__fca2f7_idx'),
        ),
    ]
