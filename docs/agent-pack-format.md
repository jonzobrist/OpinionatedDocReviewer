# Agent Pack Format (`v1`)

Agent packs are structured JSON bundles for sharing reviewer personas across environments.

## Top-level shape

```json
{
  "schema_version": "v1",
  "exported_at": "2026-02-17T18:20:00Z",
  "personas": []
}
```

## Persona entry

```json
{
  "name": "Risk & Compliance",
  "description": "Flags risk and compliance gaps.",
  "system_prompt": "Identify risk, compliance, privacy, and security concerns.",
  "focus_areas": ["security", "privacy", "compliance", "risk"],
  "tone": "cautious, precise",
  "reference_notes": "Prioritize concrete mitigation actions.",
  "output_requirements": {
    "format": "bullet_list",
    "max_bullets": 4,
    "require_quote_excerpt": true,
    "require_actionable": true,
    "include_severity": true
  },
  "examples": [],
  "sort_order": 20,
  "color_theme": "#b7482f",
  "is_active": true,
  "group_name": "Default Review"
}
```

## Import behavior

- Endpoint: `POST /api/personas/bundle/import`
- Required fields:
  - `schema_version`: currently only `v1`
  - `conflict_policy`: `skip` | `overwrite` | `rename`
  - `dry_run`: boolean
  - `personas`: array
- Group mapping:
  - `group_name` maps to tenant-local persona groups
  - Missing groups are auto-created during import

## Conflict policy semantics

- `skip`: keep existing persona, do not import conflicting name
- `overwrite`: update existing persona with imported values
- `rename`: create a new persona with suffix `(<n>)`

## Security guidance

- Treat imported prompts/reference data as untrusted input.
- Review `system_prompt` and `reference_notes` before applying to production tenants.
- Prefer `dry_run=true` first, then apply.

## Compatibility

- Future versions should increment `schema_version`.
- Importers must reject unknown schema versions with clear errors.
