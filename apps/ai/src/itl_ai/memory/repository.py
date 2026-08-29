"""SQLite repository boundary for local, append-only preference evidence."""

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from itl_ai.refine.models import PreferenceEventRequest, RetrievedEvidence

SOURCE_CONFIDENCE = {
    "manual_edit": 60,
    "confirmed_critique": 50,
    "explicit_attribute_feedback": 40,
    "absolute_feedback": 30,
    "pairwise_choice": 20,
    "model_inference": 10,
}


class PreferenceRepository:
    """Only this class issues SQL for preference events and audit records."""

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
                    liked_paths_json TEXT NOT NULL,
                    disliked_paths_json TEXT NOT NULL,
                    locked_paths_json TEXT NOT NULL,
                    critique TEXT,
                    parser_interpretation_json TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS preference_events_retrieval
                    ON preference_events(component_type, context, created_at DESC);
                CREATE TABLE IF NOT EXISTS generation_audits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    output_id TEXT NOT NULL UNIQUE,
                    session_id TEXT NOT NULL,
                    output_kind TEXT NOT NULL,
                    policy TEXT,
                    evidence_ids_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS generation_audits_session
                    ON generation_audits(session_id, created_at DESC);
                INSERT OR IGNORE INTO schema_migrations(version, applied_at)
                    VALUES (1, CURRENT_TIMESTAMP);
                """
            )

    def add_event(self, event: PreferenceEventRequest) -> tuple[int, datetime]:
        created_at = datetime.now(UTC)
        with self._connection() as connection:
            before_id = self._snapshot_id(connection, event.beforeSpec, created_at)
            after_id = self._snapshot_id(connection, event.afterSpec, created_at) if event.afterSpec else None
            cursor = connection.execute(
                """
                INSERT INTO preference_events (
                    session_id, component_type, context, target_element_id, action, source,
                    before_snapshot_id, after_snapshot_id, selected_element_id,
                    liked_paths_json, disliked_paths_json, locked_paths_json, critique,
                    parser_interpretation_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.sessionId,
                    event.componentType,
                    event.context,
                    event.targetElementId,
                    event.action,
                    event.source,
                    before_id,
                    after_id,
                    event.selectedElementId,
                    _json(event.likedPaths),
                    _json(event.dislikedPaths),
                    _json(event.lockedPaths),
                    event.critique,
                    _json(event.parserInterpretation.model_dump()) if event.parserInterpretation else None,
                    created_at.isoformat(),
                ),
            )
        if cursor.lastrowid is None:
            raise RuntimeError("SQLite did not return an ID for the preference event.")
        return cursor.lastrowid, created_at

    def retrieve(
        self, component_type: str, context: str | None, paths: set[str], limit: int = 6
    ) -> list[RetrievedEvidence]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT id, context, source, liked_paths_json, disliked_paths_json,
                       locked_paths_json, critique, created_at
                FROM preference_events
                WHERE component_type = ?
                ORDER BY id DESC
                """,
                (component_type,),
            ).fetchall()

        scored: list[tuple[int, int, RetrievedEvidence]] = []
        for row in rows:
            liked = _decode_list(row["liked_paths_json"])
            disliked = _decode_list(row["disliked_paths_json"])
            locked = _decode_list(row["locked_paths_json"])
            event_paths = set(liked + disliked + locked)
            same_context = _normalise_context(row["context"]) == _normalise_context(context)
            relation = "supporting" if same_context or not row["context"] else "contradictory"
            score = SOURCE_CONFIDENCE[row["source"]] + (100 if same_context else 0) + 15 * len(paths & event_paths)
            evidence = RetrievedEvidence(
                id=row["id"],
                relation=relation,
                source=row["source"],
                context=row["context"],
                likedPaths=liked,
                dislikedPaths=disliked,
                lockedPaths=locked,
                critique=row["critique"],
            )
            scored.append((score, row["id"], evidence))

        # A contextual mismatch remains visible as contradictory evidence; it is never silently discarded.
        supporting = sorted((item for item in scored if item[2].relation == "supporting"), reverse=True)
        contradictory = sorted((item for item in scored if item[2].relation == "contradictory"), reverse=True)
        selected = supporting[: max(1, limit - min(2, len(contradictory)))] + contradictory[:2]
        return [item[2] for item in sorted(selected, reverse=True)[:limit]]

    def record_generation(
        self, output_id: str, session_id: str, output_kind: str, evidence_ids: list[int], policy: str | None
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO generation_audits(
                       output_id, session_id, output_kind, policy, evidence_ids_json, created_at
                   )
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (output_id, session_id, output_kind, policy, _json(evidence_ids), datetime.now(UTC).isoformat()),
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
        """Expose the audit link without leaking SQLite details to callers."""
        with self._connection() as connection:
            row = connection.execute(
                "SELECT evidence_ids_json FROM generation_audits WHERE output_id = ?", (output_id,)
            ).fetchone()
        if row is None:
            return []
        decoded = json.loads(str(row["evidence_ids_json"]))
        return [item for item in decoded if isinstance(item, int)]

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


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _decode_list(value: str) -> list[str]:
    decoded = json.loads(value)
    return [item for item in decoded if isinstance(item, str)]


def _normalise_context(context: str | None) -> str:
    return (context or "").strip().lower()
