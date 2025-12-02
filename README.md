# Corvus SRS — Phase 1

Self-hosted spaced repetition system built with Django 5, HTMX, Tailwind, and PostgreSQL.

## Quickstart

```sh
git clone <repo-url>
cd Corvus
cp .env.example .env
# edit .env for local secrets if needed
docker compose up --build
```

Services:
- Web UI & API: http://localhost:8000
- PostgreSQL: localhost:5432 (`corvus` / `corvus` by default)

First-time setup:
```sh
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_demo  # demo user + sample deck
```

Credentials after seeding: `demo@example.com` / `demo1234`.

Ready-made import bundles live in `samples/`:
- `sample_cards.zip` – Markdown/Logseq-style bundle with multiple decks, tags, LaTeX, and media links.
- `sample.apkg` – Anki package with text/image cards across several decks.
Import them directly via the UI; no generation script is required.

## Tests

Inside the container:
```sh
docker compose exec web pytest
```
The suite covers SM-2 scheduling transitions, importer behaviours, permission boundaries, API review flow, and end-to-end import/re-import scenarios. (Tests were not executed in this workspace because Python is unavailable on the host; please run the command above.)

## Notable Features
- Email/password auth with custom `User` model (PBKDF2 hashes).
- Deck CRUD with HTMX-enhanced inline creation.
- Card browser with filtering, detail view, and editing.
- Review workflow implementing SM-2 defaults (Again/Hard/Good/Easy, leech tagging, learning/relearning queues).
- Markdown/Logseq ZIP importer (external ID detection, media copying, state-preserving upserts).
- Anki `.apkg` importer (SQLite parsing, media remapping, scheduling field mapping on new cards, idempotent re-imports).
- Public REST API (`/api/v1`) for auth, decks, cards, review flow, and imports.
- Tailwind CSS build baked into the Docker image; HTMX included via CDN.

## Useful Commands
- `docker compose exec web python manage.py createsuperuser`
- `docker compose exec web python manage.py seed_demo`
- `docker compose exec web python manage.py collectstatic --noinput`

## Project Structure Highlights
- `web/srs_app/settings.py` – environment-driven configuration.
- `web/core/scheduling.py` – SM-2 scheduler implementation.
- `web/core/services/review.py` – review queue helpers.
- `web/import_md/services.py`, `web/import_anki/services.py` – importer pipelines.
- `web/api/views.py` – session-authenticated JSON endpoints.
- `web/tests/` – pytest suite with factory_boy fixtures.

Enjoy building with Corvus! Contributions for later phases (export, richer analytics, etc.) can plug into the existing app structure.
