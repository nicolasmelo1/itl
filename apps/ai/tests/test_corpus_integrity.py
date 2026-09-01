"""One corpus, one path, and a real session ID on every judgment.

Session hold-out is the primary benchmark of Plan 07, and it is only as good as
the identifier. These are the two ways the corpus silently stopped being one:
a relative store path that resolved against the caller's shell, and a client
that hardcoded `local` for every judgment it ever recorded.
"""

import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from itl_ai.config.paths import APPLICATION_ROOT, resolve_application_path
from itl_ai.config.settings import load_settings
from itl_ai.memory.repository import PreferenceRepository
from itl_ai.refine.models import (
    AtomicScope,
    DesignContext,
    PreferenceEventRequest,
    PreferenceEvidence,
    ProjectContext,
)
from itl_ai.refine.service import RefineService

SCOPE = AtomicScope(level="atom", id="hero-continue-button", semanticRole="primary-action")
PROJECT = ProjectContext(productKind="saas", visualTone=["serious"], platform="web")


def button_spec(radius: str = "soft") -> dict[str, object]:
    return {
        "version": "itl.ui/v1",
        "root": "continue-button",
        "elements": {
            "continue-button": {
                "type": "Button",
                "props": {
                    "content": {"label": "Continue"},
                    "semantic": {"role": "primary-action", "state": "default"},
                    "appearance": {
                        "recipe": "primary",
                        "size": "regular",
                        "radius": radius,
                        "density": "comfortable",
                        "fontWeight": "semibold",
                    },
                },
                "children": [],
            }
        },
    }


def context() -> DesignContext:
    return DesignContext(role="primary-action", surface="hero", density="comfortable")


def judgment(session_id: str, project: ProjectContext | None = PROJECT) -> PreferenceEventRequest:
    return PreferenceEventRequest(
        sessionId=session_id,
        componentType="Button",
        scope=SCOPE,
        context=context(),
        projectContext=project,
        targetElementId="continue-button",
        action="candidate_acceptance",
        source="candidate_acceptance",
        beforeSpec=button_spec("square"),
        candidateId="accepted-square",
        evidence=PreferenceEvidence(strength="moderate"),
    )


def test_the_store_resolves_to_one_path_whatever_the_working_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("PREFERENCE_DATABASE_PATH", raising=False)

    monkeypatch.chdir(tmp_path)
    from_elsewhere = load_settings().preference_database_path
    monkeypatch.chdir(APPLICATION_ROOT)
    from_the_service = load_settings().preference_database_path

    assert from_elsewhere.is_absolute()
    assert from_elsewhere == from_the_service == APPLICATION_ROOT / "data/preferences.db"


def test_a_configured_relative_path_anchors_to_the_service_and_an_absolute_one_is_kept(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    assert resolve_application_path("data/other.db") == APPLICATION_ROOT / "data/other.db"

    absolute = tmp_path / "explicit.db"
    monkeypatch.setenv("PREFERENCE_DATABASE_PATH", str(absolute))
    assert load_settings().preference_database_path == absolute


def test_a_judgment_without_a_real_session_id_is_refused() -> None:
    for placeholder in ("local", "LOCAL", "default", "short"):
        with pytest.raises(ValidationError):
            judgment(placeholder)


def test_a_judgment_carries_its_session_id_into_the_corpus(tmp_path: Path) -> None:
    repository = PreferenceRepository(tmp_path / "preferences.sqlite")
    recorded = RefineService(repository).record_preference_event(judgment("bench-2026-08-31-a"))

    with sqlite3.connect(tmp_path / "preferences.sqlite") as connection:
        stored = connection.execute(
            "SELECT session_id FROM preference_events WHERE id = ?", (recorded.id,)
        ).fetchone()
    assert stored[0] == "bench-2026-08-31-a"


def test_rows_recorded_before_the_contract_are_marked_legacy_and_never_rewritten(tmp_path: Path) -> None:
    """The 95 existing judgments stay usable, readable and clearly separate."""
    database = tmp_path / "preferences.sqlite"
    repository = PreferenceRepository(database)
    current = RefineService(repository).record_preference_event(judgment("bench-2026-08-31-a"))
    legacy_id = _insert_pre_contract_row(database)

    retrieved = repository.retrieve("Button", context(), PreferenceEvidence(), SCOPE, PROJECT)
    strata = {item.id: item.stratum for item in retrieved}

    assert strata[current.id] == "primary"
    assert strata[legacy_id] == "legacy"
    # A legacy row informs retrieval but can never outrank one recorded under
    # the current contract.
    assert [item.id for item in retrieved] == [current.id, legacy_id]

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT session_id, scope_json, outcome, project_context_json FROM preference_events WHERE id = ?",
            (legacy_id,),
        ).fetchone()
    assert tuple(row) == ("local", None, None, None)


def _insert_pre_contract_row(database: Path) -> int:
    """Write a row exactly as the client wrote them before this phase."""
    with sqlite3.connect(database) as connection:
        snapshot = connection.execute("SELECT id FROM spec_snapshots LIMIT 1").fetchone()[0]
        cursor = connection.execute(
            """
            INSERT INTO preference_events (
                session_id, component_type, target_element_id, action, source,
                before_snapshot_id, created_at
            ) VALUES ('local', 'Button', 'continue-button', 'absolute_feedback', 'absolute_feedback', ?, ?)
            """,
            (snapshot, "2026-08-28T10:00:00+00:00"),
        )
        return int(cursor.lastrowid or 0)
