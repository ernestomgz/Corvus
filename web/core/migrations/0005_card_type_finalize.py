from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_card_type_seed'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='card',
            name='card_type',
        ),
        migrations.RenameField(
            model_name='card',
            old_name='card_type_temp',
            new_name='card_type',
        ),
        migrations.AlterField(
            model_name='card',
            name='card_type',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='cards',
                to='core.cardtype',
            ),
        ),
    ]
