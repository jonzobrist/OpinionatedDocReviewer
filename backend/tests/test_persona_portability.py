import difflib
import itertools
import json
from difflib import SequenceMatcher
from pathlib import Path

MAX_NEAR_DUPLICATE_PERSONA_RATIO = 0.9

GOLDEN_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "persona_golden"
GOLDEN_FIXTURE_PATH = GOLDEN_FIXTURE_DIR / "persona_bundle_v1.json"


def _load_golden_bundle() -> dict:
    return json.loads(GOLDEN_FIXTURE_PATH.read_text(encoding="utf-8"))


def _persona_signature(persona: dict) -> str:
    lines = [
        f"name={persona.get('name', '')}",
        f"description={persona.get('description', '')}",
        f"system_prompt={persona.get('system_prompt', '')}",
        f"focus_areas={','.join(persona.get('focus_areas', []))}",
        f"tone={persona.get('tone', '')}",
        f"reference_notes={persona.get('reference_notes', '')}",
        f"output_requirements={json.dumps(persona.get('output_requirements', {}), sort_keys=True)}",
        f"examples={json.dumps(persona.get('examples', []), sort_keys=True)}",
    ]
    return "\n".join(lines)


def _assert_personas_are_differentiated(personas: list[dict]) -> None:
    for left, right in itertools.combinations(personas, 2):
        left_sig = _persona_signature(left)
        right_sig = _persona_signature(right)
        similarity = SequenceMatcher(None, left_sig, right_sig).ratio()
        if similarity < MAX_NEAR_DUPLICATE_PERSONA_RATIO:
            continue

        diff = "".join(
            difflib.unified_diff(
                left_sig.splitlines(keepends=True),
                right_sig.splitlines(keepends=True),
                fromfile=f"persona/{left.get('name')}",
                tofile=f"persona/{right.get('name')}",
                n=2,
            )
        )
        raise AssertionError(
            "Persona fixture differentiation regression detected: "
            f"{left.get('name')} vs {right.get('name')} similarity={similarity:.3f} "
            f">= {MAX_NEAR_DUPLICATE_PERSONA_RATIO}.\nDiff:\n{diff}"
        )


def test_persona_export_and_import_roundtrip(client) -> None:
    headers = {"X-Tenant-Id": "tenant-portable"}
    create_resp = client.post(
        "/api/personas",
        json={
            "name": "Portable Agent",
            "description": "portable",
            "system_prompt": "portable prompt",
            "focus_areas": ["clarity"],
            "tone": "direct",
            "is_active": True,
            "group_id": None,
        },
        headers=headers,
    )
    assert create_resp.status_code == 201

    export_resp = client.get("/api/personas/bundle/export", headers=headers)
    assert export_resp.status_code == 200
    bundle = export_resp.json()
    assert bundle["schema_version"] == "v1"
    assert len(bundle["personas"]) >= 1

    import_resp = client.post(
        "/api/personas/bundle/import",
        json={
            "schema_version": "v1",
            "conflict_policy": "rename",
            "dry_run": False,
            "personas": bundle["personas"],
        },
        headers=headers,
    )
    assert import_resp.status_code == 200
    body = import_resp.json()
    assert body["renamed"] >= 1


def test_persona_import_dry_run(client) -> None:
    headers = {"X-Tenant-Id": "tenant-portable-dryrun"}
    payload = {
        "schema_version": "v1",
        "conflict_policy": "skip",
        "dry_run": True,
        "personas": [
            {
                "name": "Dry Run Agent",
                "description": None,
                "system_prompt": "prompt",
                "focus_areas": [],
                "tone": None,
                "reference_notes": None,
                "output_requirements": {
                    "format": "bullet_list",
                    "max_bullets": 4,
                    "require_quote_excerpt": True,
                    "require_actionable": True,
                    "include_severity": False,
                },
                "examples": [],
                "sort_order": 100,
                "color_theme": None,
                "is_active": True,
                "group_name": None,
            }
        ],
    }
    dry = client.post("/api/personas/bundle/import", json=payload, headers=headers)
    assert dry.status_code == 200
    assert dry.json()["created"] == 1
    all_resp = client.get("/api/personas", headers=headers)
    assert all_resp.status_code == 200
    assert len(all_resp.json()) == 0


def test_golden_persona_fixture_import_export_differentiation(client) -> None:
    headers = {"X-Tenant-Id": "tenant-portable-golden"}
    fixture_bundle = _load_golden_bundle()
    fixture_personas = fixture_bundle["personas"]

    import_resp = client.post(
        "/api/personas/bundle/import",
        json={
            "schema_version": fixture_bundle["schema_version"],
            "conflict_policy": "skip",
            "dry_run": False,
            "personas": fixture_personas,
        },
        headers=headers,
    )
    assert import_resp.status_code == 200
    import_body = import_resp.json()
    assert import_body["created"] == 4

    export_resp = client.get("/api/personas/bundle/export", headers=headers)
    assert export_resp.status_code == 200
    exported = export_resp.json()
    exported_personas = exported["personas"]

    exported_by_name = {item["name"]: item for item in exported_personas}
    expected_names = [item["name"] for item in fixture_personas]
    assert set(expected_names).issubset(set(exported_by_name.keys()))

    golden_exported = [exported_by_name[name] for name in expected_names]
    _assert_personas_are_differentiated(golden_exported)
