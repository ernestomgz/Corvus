from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0007_knowledge_maps'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('new_card_daily_limit', models.IntegerField(default=20)),
                ('notifications_enabled', models.BooleanField(default=False)),
                ('theme', models.CharField(default='system', max_length=20)),
                ('plugin_github_enabled', models.BooleanField(default=False)),
                ('plugin_github_repo', models.CharField(blank=True, max_length=255)),
                ('plugin_github_branch', models.CharField(default='update-cards-bot', max_length=255)),
                ('plugin_github_token', models.TextField(blank=True)),
                ('plugin_ai_enabled', models.BooleanField(default=False)),
                ('plugin_ai_provider', models.CharField(blank=True, max_length=50)),
                ('plugin_ai_api_key', models.TextField(blank=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('scheduled_pull_interval', models.CharField(choices=[('off', 'Off'), ('hourly', 'Hourly'), ('daily', 'Daily')], default='off', max_length=20)),
                ('max_delete_threshold', models.IntegerField(default=50)),
                ('require_recent_pull_before_push', models.BooleanField(default=True)),
                ('push_preview_required', models.BooleanField(default=True)),
                ('last_pull_at', models.DateTimeField(blank=True, null=True)),
                ('last_push_at', models.DateTimeField(blank=True, null=True)),
                ('last_sync_status', models.CharField(blank=True, max_length=32)),
                ('last_sync_error', models.TextField(blank=True)),
                ('last_sync_summary', models.JSONField(blank=True, default=dict)),
                ('default_deck', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='default_for_users', to='core.deck')),
                ('default_study_set', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='default_for_users', to='core.studyset')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='settings', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['user_id'],
            },
        ),
    ]
