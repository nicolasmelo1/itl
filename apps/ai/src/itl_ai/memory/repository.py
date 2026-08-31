"""SQLite boundary for append-only, contextual Button preference evidence."""

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TypeAlias, cast

from pydantic import TypeAdapter, ValidationError

from itl_ai.refine.models import (
    DEFAULT_BUTTON_SCOPE,
    AtomicScope,
    AttributeDirective,
    ButtonAppearance,
    DesignContext,
    Interpretation,
    PreferenceEventRequest,
    PreferenceEvidence,
    RetrievedEvidence,
    SpecDiff,
)

SOURCE_CONFIDENCE = {
    "manual_edit": 60,
    "confirmed_critique": 50,
    "explicit_attribute_feedback": 40,
    "absolute_feedback": 30,
    "pairwise_choice": 20,
    "candidate_acceptance": 25,
    "model_inference": 10,
}
STRENGTH_SCORE = {"weak": 10, "moderate": 30, "strong": 50}
DIRECTIVES_ADAPTER = TypeAdapter(list[AttributeDirective])
TasteOutcome: TypeAlias = Literal["accepted", "almost", "rejected", "indifferent", "manual_edit"]
OUTCOMES: dict[str, TasteOutcome] = {
    "candidate_acceptance": "accepted",
    "almost": "almost",
    "rejection": "rejected",
    "indifference": "indifferent",
    "manual_edit": "manual_edit",
}


class PreferenceRepository:
    """Only this class issues SQL for preference events and their audit records."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self._migrate()

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _migrate(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS spec_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    spec_json TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS preference_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    component_type TEXT NOT NULL,
                    context TEXT,
                    target_element_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    source TEXT NOT NULL,
                    before_snapshot_id INTEGER NOT NULL REFERENCES spec_snapshots(id),
                    after_snapshot_id INTEGER REFERENCES spec_snapshots(id),
                    selected_element_id TEXT,
                    candidate_id TEXT,
                    liked_paths_json TEXT NOT NULL DEFAULT '[]',
                    disliked_paths_json TEXT NOT NULL DEFAULT '[]',
                    locked_paths_json TEXT NOT NULL DEFAULT '[]',
                    critique TEXT,
                    parser_interpretation_json TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS generation_audits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    output_id TEXT NOT NULL UNIQUE,
                    session_id TEXT NOT NULL,
                    output_kind TEXT NOT NULL,
                    policy TEXT,
                    evidence_ids_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(preference_events)")}
            migrations = {
                "context_json": "ALTER TABLE preference_events ADD COLUMN context_json TEXT",
                "evidence_json": "ALTER TABLE preference_events ADD COLUMN evidence_json TEXT",
                "directives_json": "ALTER TABLE preference_events ADD COLUMN directives_json TEXT",
                "spec_diff_json": "ALTER TABLE preference_events ADD COLUMN spec_diff_json TEXT",
                "atomic_level": "ALTER TABLE preference_events ADD COLUMN atomic_level TEXT",
                "scope_json": "ALTER TABLE preference_events ADD COLUMN scope_json TEXT",
            }
            for column, statement in migrations.items():
                if column not in columns:
                    connection.execute(statement)
            audit_columns = {row["name"] for row in connection.execute("PRAGMA table_info(generation_audits)")}
            if "brief_version" not in audit_columns:
                connection.execute("ALTER TABLE generation_audits ADD COLUMN brief_version TEXT")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS preference_events_retrieval_context "
                "ON preference_events(component_type, created_at DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS generation_audits_session ON generation_audits(session_id, created_at DESC)"
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (4, CURRENT_TIMESTAMP)"
            )

    def add_event(self, event: PreferenceEventRequest) -> tuple[int, datetime]:
        created_at = datetime.now(UTC)
        with self._connection() as connection:
            before_id = self._snapshot_id(connection, event.beforeSpec, created_at)
            after_id = self._snapshot_id(connection, event.afterSpec, created_at) if event.afterSpec else None
            diff = _spec_diff(event.beforeSpec, event.afterSpec)
            cursor = connection.execute(
                """
                INSERT INTO preference_events (
                    session_id, component_type, atomic_level, scope_json, context, context_json,
                    target_element_id, action, source,
                    before_snapshot_id, after_snapshot_id, selected_element_id, candidate_id,
                    liked_paths_json, disliked_paths_json, locked_paths_json, evidence_json, directives_json,
                    spec_diff_json, critique, parser_interpretation_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.sessionId,
                    event.componentType,
                    event.scope.level,
                    _json(event.scope.model_dump()),
                    event.context.surface,
                    _json(event.context.model_dump()),
                    event.targetElementId,
                    event.action,
                    event.source,
                    before_id,
                    after_id,
                    event.selectedElementId,
                    event.candidateId,
                    _json(event.evidence.likedPaths),
                    _json(event.evidence.dislikedPaths),
                    _json(event.evidence.lockedPaths),
                    _json(event.evidence.model_dump()),
                    _json([directive.model_dump() for directive in event.directives]),
                    _json([change.model_dump() for change in diff]),
                    event.critique,
                    _json(event.parserInterpretation.model_dump()) if event.parserInterpretation else None,
                    created_at.isoformat(),
                ),
            )
        if cursor.lastrowid is None:
            raise RuntimeError("SQLite did not return an ID for the preference event.")
        return cursor.lastrowid, created_at

    def retrieve(
        self,
        component_type: str,
        context: DesignContext,
        query_evidence: PreferenceEvidence,
        scope: AtomicScope = DEFAULT_BUTTON_SCOPE,
        limit: int = 6,
    ) -> list[RetrievedEvidence]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT preference_events.id, preference_events.atomic_level, preference_events.scope_json,
                       preference_events.context_json, preference_events.context,
                       preference_events.source, preference_events.action, preference_events.evidence_json,
                       preference_events.liked_paths_json, preference_events.disliked_paths_json,
                       preference_events.locked_paths_json, preference_events.critique,
                       preference_events.candidate_id, preference_events.directives_json,
                       preference_events.spec_diff_json, preference_events.parser_interpretation_json,
                       preference_events.target_element_id, after_snapshot.spec_json AS after_snapshot_json
                FROM preference_events
                LEFT JOIN spec_snapshots AS after_snapshot
                  ON after_snapshot.id = preference_events.after_snapshot_id
                WHERE preference_events.component_type = ?
                ORDER BY preference_events.id DESC
                """,
                (component_type,),
            ).fetchall()

        scored = [_retrieval_row(row, context, query_evidence, scope) for row in rows]
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        selected = scored[:limit]
        mismatch = next((item for item in scored if item[2].contextRelation == "mismatch"), None)
        if mismatch and mismatch not in selected:
            selected = selected[: max(0, limit - 1)] + [mismatch]
        return [item[2] for item in selected]

    def record_generation(
        self,
        output_id: str,
        session_id: str,
        output_kind: str,
        evidence_ids: list[int],
        policy: str | None,
        brief_version: str | None = None,
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO generation_audits(
                       output_id, session_id, output_kind, policy, evidence_ids_json, brief_version, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    output_id,
                    session_id,
                    output_kind,
                    policy,
                    _json(evidence_ids),
                    brief_version,
                    datetime.now(UTC).isoformat(),
                ),
            )

    def policy_counts(self, session_id: str) -> dict[str, int]:
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT policy, COUNT(*) AS count FROM generation_audits
                   WHERE session_id = ? AND policy IS NOT NULL GROUP BY policy""",
                (session_id,),
            ).fetchall()
        return {str(row["policy"]): int(row["count"]) for row in rows}

    def evidence_for_output(self, output_id: str) -> list[int]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT evidence_ids_json FROM generation_audits WHERE output_id = ?", (output_id,)
            ).fetchone()
        if row is None:
            return []
        decoded = json.loads(str(row["evidence_ids_json"]))
        return [item for item in decoded if isinstance(item, int)]

    def brief_version_for_output(self, output_id: str) -> str | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT brief_version FROM generation_audits WHERE output_id = ?", (output_id,)
            ).fetchone()
        return str(row["brief_version"]) if row and row["brief_version"] is not None else None

    @staticmethod
    def _snapshot_id(connection: sqlite3.Connection, spec: dict[str, object], created_at: datetime) -> int:
        encoded = _json(spec)
        connection.execute(
            "INSERT OR IGNORE INTO spec_snapshots(spec_json, created_at) VALUES (?, ?)",
            (encoded, created_at.isoformat()),
        )
        row = connection.execute("SELECT id FROM spec_snapshots WHERE spec_json = ?", (encoded,)).fetchone()
        if row is None:
            raise RuntimeError("SQLite did not return the snapshot it just stored.")
        return int(row["id"])


def _retrieval_row(
    row: sqlite3.Row, context: DesignContext, query_evidence: PreferenceEvidence, requested_scope: AtomicScope
) -> tuple[int, int, RetrievedEvidence]:
    stored_context = _decode_context(row["context_json"])
    stored_scope = _decode_scope(row["scope_json"], row["atomic_level"])
    stored_evidence = _decode_evidence(row)
    context_relation = _context_relation(context, stored_context)
    preference_relation = _preference_relation(query_evidence, stored_evidence)
    score = (
        SOURCE_CONFIDENCE[str(row["source"])]
        + STRENGTH_SCORE[stored_evidence.strength]
        + {"exact": 120, "compatible": 70, "global": 25, "mismatch": 0}[context_relation]
        + {"supporting": 30, "unknown": 0, "conflicting": -20}[preference_relation]
        + _scope_score(requested_scope, stored_scope)
    )
    evidence = RetrievedEvidence(
        id=row["id"],
        contextRelation=context_relation,
        preferenceRelation=preference_relation,
        source=row["source"],
        scope=stored_scope,
        context=stored_context,
        evidence=stored_evidence,
        critique=row["critique"],
        outcome=_outcome(row["action"]),
        observedAppearance=_decode_observed_appearance(row["after_snapshot_json"], row["target_element_id"]),
        diff=_decode_diff(row["spec_diff_json"]),
        candidateId=row["candidate_id"],
        directives=_decode_directives(row["directives_json"]),
        parserInterpretation=_decode_interpretation(row["parser_interpretation_json"]),
    )
    return score, int(row["id"]), evidence


def _decode_context(value: str | None) -> DesignContext | None:
    if not value:
        return None
    try:
        return DesignContext.model_validate_json(value)
    except ValueError:
        return None


def _decode_scope(value: str | None, atomic_level: str | None) -> AtomicScope | None:
    if value:
        try:
            return AtomicScope.model_validate_json(value)
        except ValueError:
            return None
    if atomic_level == "atom":
        return DEFAULT_BUTTON_SCOPE
    return None


def _scope_score(requested: AtomicScope, stored: AtomicScope | None) -> int:
    if stored is None:
        return 0
    if stored == requested:
        return 80
    if stored.level == requested.level:
        return 25
    return -15


def _decode_evidence(row: sqlite3.Row) -> PreferenceEvidence:
    if row["evidence_json"]:
        return PreferenceEvidence.model_validate_json(row["evidence_json"])
    return PreferenceEvidence(
        likedPaths=_decode_paths(row["liked_paths_json"]),
        dislikedPaths=_decode_paths(row["disliked_paths_json"]),
        lockedPaths=_decode_paths(row["locked_paths_json"]),
        strength="weak",
    )


def _outcome(action: str) -> TasteOutcome | None:
    return OUTCOMES.get(action)


def _decode_observed_appearance(snapshot: str | None, target_element_id: str) -> ButtonAppearance | None:
    if not snapshot:
        return None
    try:
        decoded = json.loads(snapshot)
        appearance = decoded["elements"][target_element_id]["props"]["appearance"]
        return ButtonAppearance.model_validate(appearance)
    except (KeyError, TypeError, ValueError):
        return None


def _decode_diff(value: str | None) -> list[SpecDiff]:
    if not value:
        return []
    try:
        return [SpecDiff.model_validate(item) for item in json.loads(value)]
    except (TypeError, ValueError):
        return []


def _decode_directives(value: str | None) -> list[AttributeDirective]:
    if not value:
        return []
    try:
        return DIRECTIVES_ADAPTER.validate_json(value)
    except ValidationError:
        return []


def _decode_interpretation(value: str | None) -> Interpretation | None:
    if not value:
        return None
    try:
        return Interpretation.model_validate_json(value)
    except ValueError:
        return None


def _decode_paths(
    value: str,
) -> list[
    Literal[
        "/appearance/recipe", "/appearance/size", "/appearance/radius", "/appearance/density", "/appearance/fontWeight"
    ]
]:
    decoded = json.loads(value)
    return [
        item
        for item in decoded
        if item
        in {
            "/appearance/recipe",
            "/appearance/size",
            "/appearance/radius",
            "/appearance/density",
            "/appearance/fontWeight",
        }
    ]


def _context_relation(
    requested: DesignContext, stored: DesignContext | None
) -> Literal["exact", "compatible", "global", "mismatch"]:
    if stored is None:
        return "global"
    if stored == requested:
        return "exact"
    if stored.role == requested.role and stored.surface == requested.surface:
        return "compatible"
    return "mismatch"


def _preference_relation(
    query: PreferenceEvidence, stored: PreferenceEvidence
) -> Literal["supporting", "conflicting", "unknown"]:
    requested_positive = set(query.likedPaths + query.lockedPaths)
    stored_positive = set(stored.likedPaths + stored.lockedPaths)
    requested_negative = set(query.dislikedPaths)
    stored_negative = set(stored.dislikedPaths)
    if requested_positive.intersection(stored_negative) or requested_negative.intersection(stored_positive):
        return "conflicting"
    if requested_positive.intersection(stored_positive) or requested_negative.intersection(stored_negative):
        return "supporting"
    return "unknown"


def _spec_diff(before: dict[str, object], after: dict[str, object] | None) -> list[SpecDiff]:
    if after is None:
        return []
    return _diff_value(before, after, "")


def _diff_value(before: object, after: object, path: str) -> list[SpecDiff]:
    if isinstance(before, dict) and isinstance(after, dict):
        before_values = cast(dict[str, object], before)
        after_values = cast(dict[str, object], after)
        changes: list[SpecDiff] = []
        for key in sorted(set(before_values) | set(after_values)):
            changes.extend(_diff_value(before_values.get(key), after_values.get(key), f"{path}/{key}"))
        return changes
    if before != after:
        before_value: object = dict(cast(dict[str, object], before)) if isinstance(before, dict) else before
        after_value: object = dict(cast(dict[str, object], after)) if isinstance(after, dict) else after
        return [SpecDiff(path=path or "/", before=before_value, after=after_value)]
    return []


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
