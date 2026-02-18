# Knowledge Maps

Corvus now understands *knowledge maps*: tree-shaped frameworks that describe how you organise a subject. Maps are stored separately from cards so you can design a taxonomy first, then attach cards to the correct branch using tags.

## Concept

- **Knowledge Map** – definition of a framework. Each map belongs to a user, has a human name, machine slug, description, and optional metadata.
- **Knowledge Nodes** – individual cards inside the tree. Nodes carry a stable key, readable title, plain-text definition, optional guidance, source citations, and arbitrary metadata for tooling.
- **Canonical Tag Format** – every node automatically exposes a tag: `km:<map-slug>:<node-key>`. When you assign that tag to a card, Corvus (and future AI helpers) can see exactly where the card sits inside the framework.

## JSON Format

Use JSON to import knowledge maps. Only framework data is required—no cards.

```json
{
  "map": {
    "slug": "learning-grid",
    "name": "Learning Grid",
    "description": "Personal taxonomy for tracking language depth",
    "metadata": {
      "version": 1,
      "owner": "demo"
    }
  },
  "nodes": [
    {
      "key": "foundations",
      "title": "Foundations",
      "definition": "Baseline material.",
      "guidance": "Use for the first exposure to an idea.",
      "sources": [
        { "label": "Notebook", "url": "https://example.org/notes" },
        "Internal Brief"
      ],
      "metadata": {
        "color": "#c1e1c1"
      },
      "children": [
        { "key": "foundations.scope", "title": "Scope", "definition": "What is covered?" },
        { "key": "foundations.vocab", "title": "Vocabulary", "definition": "Key expressions" }
      ]
    }
  ]
}
```

Rules:

- `map.slug` – optional. If omitted the slug is derived from `map.name`. Must be lowercase letters/numbers plus `-` or `_`.
- `nodes` – required list. Each entry must include a unique `key` (`[a-z0-9._-]`), a `title`, optional `definition`, optional `guidance`, optional `sources`, optional `metadata`, and optional `children`.
- `sources` – strings or objects with string fields (`label`, `url`, etc.).
- `children` – nested nodes. Keys must stay unique across the entire map.

See `samples/knowledge_map.json` for a ready-to-import example.

## Import Workflow

You can manage everything from the web UI at `/knowledge-maps/`, which lets you upload/paste JSON and browse the resulting tree. For API or scripted workflows:

1. Produce a JSON file that follows the format above (you can have an AI generate it).
2. Call the API:

   ```bash
   curl -X POST \
     -H "Content-Type: application/json" \
     -H "X-CSRFToken: ..." \
     --cookie "sessionid=..." \
     http://localhost:8000/api/knowledge-maps/import \
     -d @samples/knowledge_map.json
   ```

   The response includes the slug, node counts, and whether the map was newly created or replaced.

3. Retrieve your map (tree + node tags) via `GET /api/knowledge-maps/<slug>`.

4. Apply node tags to cards (see below) so reviews and analytics know where each card sits.

Importing with an existing slug replaces the stored nodes, letting you version-control your frameworks externally.

## Tagging Cards

- Every node exposes an immutable tag string with format `km:<map-slug>:<node-key>`.
- Add that exact tag to any card (manually or via import rules) to link it with the node.
- Because the format is predictable and unique, automated tooling can parse tags and compute coverage (for example, average mastery of all cards tagged with `km:learning-grid:foundations.vocab`).

Example: A card covering “Scope of Safety Assessments” under the `learning-grid` map would receive the tag `km:learning-grid:foundations.scope`.

## API Reference

| Endpoint | Method(s) | Purpose |
| --- | --- | --- |
| `/api/knowledge-maps/` | `GET` | List all maps for the authenticated user (metadata + tag prefix). |
| `/api/knowledge-maps/import` | `POST` | Import or replace a map using the JSON payload above. |
| `/api/knowledge-maps/<slug>` | `GET` | Retrieve a map plus its tree of nodes and canonical tags. |

These endpoints reuse existing authentication/session handling, so they integrate seamlessly with the rest of the Corvus API and UI workflows.
