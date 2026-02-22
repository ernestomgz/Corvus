import io
import yaml

import pytest
from django.urls import reverse

from core.models import UserSettings

pytestmark = pytest.mark.django_db


def test_settings_create_and_save(client, user_factory, deck_factory):
    user = user_factory()
    deck = deck_factory(user=user)
    assert client.login(email=user.email, password='password123')

    url = reverse('settings:detail')
    response = client.get(url)
    assert response.status_code == 200

    payload = {
        'default_deck': deck.id,
        'new_card_daily_limit': 15,
        'notifications_enabled': 'on',
        'theme': 'dark',
        'plugin_github_enabled': 'on',
        'plugin_github_repo': 'owner/repo',
        'plugin_github_branch': 'update-cards-bot',
        'plugin_github_token': 'ghp_secret',
        'plugin_ai_enabled': 'on',
        'plugin_ai_provider': 'openai',
        'plugin_ai_api_key': 'sk-secret',
        'scheduled_pull_interval': 'hourly',
        'max_delete_threshold': 25,
        'require_recent_pull_before_push': 'on',
        'push_preview_required': 'on',
        'metadata': '{"foo": "bar"}',
    }
    post = client.post(url, payload, follow=True)
    assert post.status_code == 200
    settings_obj = UserSettings.objects.get(user=user)
    assert settings_obj.default_deck_id == deck.id
    assert settings_obj.new_card_daily_limit == 15
    assert settings_obj.notifications_enabled is True
    assert settings_obj.theme == 'dark'
    assert settings_obj.plugin_github_enabled is True
    assert settings_obj.plugin_github_repo == 'owner/repo'
    assert settings_obj.plugin_github_token == 'ghp_secret'
    assert settings_obj.plugin_ai_provider == 'openai'
    assert settings_obj.plugin_ai_api_key == 'sk-secret'
    assert settings_obj.scheduled_pull_interval == 'hourly'
    assert settings_obj.max_delete_threshold == 25
    assert settings_obj.require_recent_pull_before_push is True
    assert settings_obj.push_preview_required is True
    assert settings_obj.metadata.get('foo') == 'bar'


def test_settings_export_excludes_secrets(client, user_factory):
    user = user_factory()
    settings_obj = UserSettings.objects.create(
        user=user,
        plugin_github_enabled=True,
        plugin_github_repo='owner/repo',
        plugin_github_branch='update-cards-bot',
        plugin_github_token='ghp_secret',
        plugin_ai_enabled=True,
        plugin_ai_provider='openai',
        plugin_ai_api_key='sk-secret',
    )
    client.force_login(user)
    response = client.get(reverse('settings:export'))
    assert response.status_code == 200
    assert response['Content-Type'].startswith('text/yaml')
    payload = yaml.safe_load(io.StringIO(response.content.decode('utf-8')))
    assert payload['plugin_github']['enabled'] is True
    assert payload['plugin_github']['repo'] == 'owner/repo'
    assert 'token' not in payload['plugin_github']
    assert payload['plugin_ai']['provider'] == 'openai'
    assert 'api_key' not in payload['plugin_ai']
    assert payload['sync_policy']['max_delete_threshold'] == 50
    assert 'last_sync' in payload
