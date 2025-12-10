from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_deck_hierarchy_and_import_session'),
    ]

    operations = [
        migrations.CreateModel(
            name='CardType',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('slug', models.SlugField(max_length=64)),
                ('description', models.TextField(blank=True)),
                ('field_schema', models.JSONField(default=list)),
                ('front_template', models.TextField()),
                ('back_template', models.TextField()),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'user',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='card_types',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.AddConstraint(
            model_name='cardtype',
            constraint=models.UniqueConstraint(fields=['user', 'slug'], name='unique_card_type_per_user'),
        ),
        migrations.AddConstraint(
            model_name='cardtype',
            constraint=models.UniqueConstraint(
                condition=models.Q(user__isnull=True),
                fields=['slug'],
                name='unique_global_card_type_slug',
            ),
        ),
        migrations.CreateModel(
            name='CardImportFormat',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('format_kind', models.CharField(choices=[('markdown', 'Markdown')], max_length=32)),
                ('template', models.TextField()),
                ('options', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'card_type',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='import_formats',
                        to='core.cardtype',
                    ),
                ),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='card',
            name='field_values',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='card',
            name='card_type_temp',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='+',
                to='core.cardtype',
            ),
        ),
    ]
