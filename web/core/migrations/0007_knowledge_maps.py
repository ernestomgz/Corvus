from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_study_sets'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='KnowledgeMap',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(max_length=64)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='knowledge_maps', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='KnowledgeNode',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('identifier', models.CharField(max_length=96)),
                ('title', models.CharField(max_length=255)),
                ('definition', models.TextField(blank=True)),
                ('guidance', models.TextField(blank=True)),
                ('sources', models.JSONField(blank=True, default=list)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('display_order', models.IntegerField(default=0)),
                ('tag_value', models.CharField(max_length=255, unique=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('knowledge_map', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='nodes', to='core.knowledgemap')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='core.knowledgenode')),
            ],
            options={
                'ordering': ['knowledge_map', 'display_order', 'title'],
            },
        ),
        migrations.AddConstraint(
            model_name='knowledgemap',
            constraint=models.UniqueConstraint(fields=('user', 'slug'), name='unique_knowledge_map_slug_per_user'),
        ),
        migrations.AddIndex(
            model_name='knowledgenode',
            index=models.Index(fields=['knowledge_map', 'parent'], name='core_knowle_knowledg_831e76_idx'),
        ),
        migrations.AddIndex(
            model_name='knowledgenode',
            index=models.Index(fields=['knowledge_map', 'identifier'], name='core_knowle_knowledg_eb5e57_idx'),
        ),
        migrations.AddConstraint(
            model_name='knowledgenode',
            constraint=models.UniqueConstraint(fields=('knowledge_map', 'identifier'), name='unique_knowledge_node_identifier_per_map'),
        ),
    ]
