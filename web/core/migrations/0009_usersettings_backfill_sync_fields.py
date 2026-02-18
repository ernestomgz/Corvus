from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_usersettings'),
    ]

    operations = [
        migrations.RunSQL(
            """
            ALTER TABLE core_usersettings
                ADD COLUMN IF NOT EXISTS scheduled_pull_interval varchar(20) NOT NULL DEFAULT 'off',
                ADD COLUMN IF NOT EXISTS max_delete_threshold integer NOT NULL DEFAULT 50,
                ADD COLUMN IF NOT EXISTS require_recent_pull_before_push boolean NOT NULL DEFAULT TRUE,
                ADD COLUMN IF NOT EXISTS push_preview_required boolean NOT NULL DEFAULT TRUE,
                ADD COLUMN IF NOT EXISTS last_pull_at timestamp with time zone NULL,
                ADD COLUMN IF NOT EXISTS last_push_at timestamp with time zone NULL,
                ADD COLUMN IF NOT EXISTS last_sync_status varchar(32) NULL DEFAULT '',
                ADD COLUMN IF NOT EXISTS last_sync_error text NULL DEFAULT '',
                ADD COLUMN IF NOT EXISTS last_sync_summary jsonb NOT NULL DEFAULT '{}'::jsonb;
            """,
            reverse_sql="SELECT 1;",
        ),
    ]
