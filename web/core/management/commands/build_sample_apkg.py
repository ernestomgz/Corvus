import json
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Generate a minimal sample.apkg for manual import testing.'

    def handle(self, *args, **options):
        output_path = Path(__file__).resolve().parents[4] / 'samples' / 'sample.apkg'
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            db_path = tmp_path / 'collection.anki2'
            conn = sqlite3.connect(db_path)
            conn.execute(
                'CREATE TABLE notes (id INTEGER PRIMARY KEY, guid TEXT, mid INTEGER, mod INTEGER, usn INTEGER, tags TEXT, flds TEXT, sfld INTEGER, csum INTEGER, flags INTEGER, data TEXT)'
            )
            conn.execute(
                'CREATE TABLE cards (id INTEGER PRIMARY KEY, nid INTEGER, did INTEGER, ord INTEGER, mod INTEGER, usn INTEGER, type INTEGER, queue INTEGER, due INTEGER, ivl INTEGER, factor INTEGER, reps INTEGER, lapses INTEGER, left INTEGER, odue INTEGER, odid INTEGER, flags INTEGER, data TEXT)'
            )
            conn.execute(
                'INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (1, 'sample-guid', 1, 0, 0, '', 'Front side\x1fBack side', 0, 0, 0, ''),
            )
            conn.execute(
                'INSERT INTO cards (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (1, 1, 1, 0, 0, 0, 0, 2, 2, 5, 2600, 3, 1, 0, 0, 0, 0, ''),
            )
            conn.commit()
            conn.close()

            media_map = {'0': 'sample.png'}
            (tmp_path / '0').write_bytes(b'sample-media')
            (tmp_path / 'media').write_text(json.dumps(media_map))

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(output_path, 'w') as zf:
                zf.write(db_path, arcname='collection.anki2')
                zf.write(tmp_path / 'media', arcname='media')
                zf.write(tmp_path / '0', arcname='0')
        self.stdout.write(self.style.SUCCESS(f'Wrote {output_path}'))
