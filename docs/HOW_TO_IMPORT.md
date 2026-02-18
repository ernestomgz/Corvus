# Corvus Markdown Import System

This document explains how Corvus imports Markdown/Logseq-style notes into spaced-repetition cards. The system borrows the Anki idea of *note types*, but extends it with Markdown-aware templates, hierarchy-aware fronts, and an import-preview pipeline.

---

## 1. Building Blocks

### 1.1 Card Types
* Every card belongs to a **card type** (`core.models.CardType`). A type defines:
  - `field_schema`: named fields such as `front`, `back`, `hierarchy`, `title`, or custom inputs.
  - `front_template` / `back_template`: how the field values are rendered when the card is shown.
* Card types can be global (built-in) or user-defined. The importer always resolves the type via its slug, so you can extend the library without touching code.

### 1.2 Import Formats
* Each card type can expose one or more **import formats** (`core.models.CardImportFormat`). A format describes how to detect a card inside Markdown:
  - `options.marker`: token that marks a heading as a card (for example `#card` or `#photo-card`).
  - `options.allow_reverse`: optionally emit a reversed card when the marker is written as `#card/reverse` or `#card-reverse` (defaults to `true`).
  - `options.default_tags`: tags automatically added when a note uses the format.
  - `options.external_id_field`, `options.tags_field`, `options.anchor_field`: indicate which placeholder should be filled when writing the template back out.
* During import the system loads all accessible formats, builds a regex resolver, and only the declared markers are accepted. This keeps the importer fully data-driven.

### 1.3 Hierarchical Fronts
* The parser records Markdown heading hierarchy while scanning each note.
* For card headings (typically `### Title #card`), the front is composed as:
  1. First line: `<H1 Title> > <H2 Title>` (if they exist).
  2. Second line: `<Card heading>` itself.
* Template fields `hierarchy` and `title` are available so every card type can reference them. Built-in Basic formats already place `{{hierarchy}}` above `{{title}}`.

---

## 2. Preparing Markdown Archives

### 2.1 Folder → Deck Mapping
* Zip files may contain nested folders. Each top-level folder becomes (or reuses) a deck; each subfolder becomes a child deck.
* If you select a destination deck during import, Corvus strips that deck’s path from the archive folders, so you can safely export and re-import the same tree.
* **Rule**: When no destination deck is chosen, every Markdown file must live inside at least one folder. Plain files at the archive root fail validation (the preview will highlight them).

Example tree (zip root shown as `.`):

```text
.
├── Mathematics
│   ├── Equations
│   │   └── differentials.md
│   └── attachments
│       └── Parabola.png
└── Physics
    └── Thermodynamics.md
```

### 2.2 Note Anatomy
Within each Markdown file:

1. Use headings to create context:
   ```md
   # Combinatorial numbers
   ## Newton binomial
   ### Formula #card
   $$(a+b)^n = \sum_{j=0}^n \binom{n}{j} a^{n-j} b^j$$
   ```
   This produces a front with:
   ```
   Combinatorial numbers > Newton binomial
   Formula
   ```

2. Optional metadata lines immediately after the marker heading:
   ```md
   id:: example-guid
   tags:: math, binomial, spaced
   ```
   * `id::` links future imports to the existing card (stored as an external ID).
   * `tags::` accepts comma or semicolon separators.

3. Body content continues until the next blank line followed by another marker.

4. To create a reversed card, append `/reverse` or `-reverse` to the marker:
   ```md
   ### Capital of Spain #card/reverse
   Madrid
   ```
   The import session will show two entries: straight and reversed.

### 2.3 Media & Attachments
* Image/file references support both Markdown `![](path/file.png)` and Obsidian `![[file.png]]` syntax.
* Corvus searches the note’s folder and an `attachments/` subfolder for the asset. Missing files show up as preview errors and block the import.
* Imported media is copied into the user’s media storage and the Markdown is rewritten with the new URLs.

---

## 3. Import Workflow

1. **Upload** a `.zip` (or a single `.md` file) from *Import → Markdown / Logseq*.
2. The system parses every Markdown file using the card-type resolver. Cards with unknown markers are ignored; cards with invalid structure surface errors.
3. **Preview session** displays:
   - New cards and updates, grouped separately.
   - Hierarchy-aware fronts rendered via the same Markdown renderer used in-study.
   - Validation errors (missing folders, missing attachments, etc.). Apply is disabled until all errors disappear.
4. **Decide per card** whether to import or skip. When applying:
   - Deck paths are auto-created based on folders if needed.
   - External IDs keep track of re-imports.
   - **Tags are merged**: existing manual tags stay, and new tags from Markdown are appended (de-duplicated). Removing a tag from Markdown will not delete a tag you added in the UI.
   - Media references stay in sync with the copied files.
5. The resulting `Import` record captures created/updated/skipped counts, decks created, and media copies for auditing.

---

## 4. Extending the System

1. Navigate to **Card Types** in the app.
2. Duplicate a built-in type or create a new one:
   - Define the field schema (add custom fields if your format needs them).
   - Write the front/back templates using `{{field}}` placeholders; `{{hierarchy}}`, `{{title}}`, and `{{context}}` are always populated.
3. Add **Import Formats** for that type:
   - Choose `Markdown` as the format kind.
   - Specify a template that illustrates how the note should be written.
   - In the `options` JSON, set at least the marker (`{"marker": "#my-card"}`) and any other behaviour flags (`allow_reverse`, `default_tags`, etc.).
4. After saving, the Markdown importer immediately understands the new marker—no code deploy needed.

---

## 5. Practical Examples

### 5.1 Basic fact card
```md
# Biology
## Cell components
### Mitochondria #card
id:: bio_cell_001
tags:: biology, cell

Powerhouse of the cell.
```

### 5.2 Cloze-style template (custom type)
```md
# Languages
## Spanish
### Verb conjugation #cloze-card
tags:: spanish, cloze

`{{c1::ser}}` means `{{c2::to be}}`.
```

### 5.3 Photo card
```md
## Identify plant #photo-card
![[attachments/leaf.png]]

Look for serrated edges.
```
*(Make sure the corresponding `attachments/leaf.png` exists inside the same folder in the zip.)*

---

By keeping import behaviour in your card types and formats, Corvus matches Anki’s flexibility while embracing Markdown-native workflows. Use this document as a checklist before exporting notes from Logseq/Obsidian or any other markdown-based knowledge base. If an import looks wrong in the preview, adjust the Markdown (or the card type configuration) and try again—no code changes required.
