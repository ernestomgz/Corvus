from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_card_type_finalize'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudySet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('kind', models.CharField(choices=[('deck', 'Deck'), ('tag', 'Tag')], max_length=20)),
                ('tag', models.CharField(blank=True, max_length=255)),
                ('is_favorite', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deck', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='study_sets', to='core.deck')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='study_sets', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-is_favorite', 'name'],
            },
        ),
        migrations.AddConstraint(
            model_name='studyset',
            constraint=models.CheckConstraint(
                check=Q(kind='deck', deck__isnull=False) | Q(kind='tag', deck__isnull=True),
                name='study_set_requires_matching_deck_state',
            ),
        ),
        migrations.AddConstraint(
            model_name='studyset',
            constraint=models.CheckConstraint(
                check=Q(kind='tag', tag__gt='') | Q(kind='deck'),
                name='study_set_requires_tag_for_tag_kind',
            ),
        ),
        migrations.AddConstraint(
            model_name='studyset',
            constraint=models.UniqueConstraint(
                condition=Q(kind='deck'),
                fields=('user', 'deck'),
                name='study_set_unique_deck',
            ),
        ),
        migrations.AddConstraint(
            model_name='studyset',
            constraint=models.UniqueConstraint(
                condition=Q(kind='tag'),
                fields=('user', 'tag'),
                name='study_set_unique_tag',
            ),
        ),
    ]
