"""SQLite boundary for append-only, contextual preference evidence.

Evidence is partitioned by `AtomicScope`: one editable subject never reads
another's decisions unless a reviewed rule says it may. The dimension altitude
is the one deliberate exception, and it only carries readings on dimensions two
components both declare.
"""

import json
import re
import sqlite3
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

from pydantic import TypeAdapter, ValidationError

from itl_ai.memory.compiler import ObservationRow, compile_dimension_evidence
from itl_ai.refine.base import ContextRelation, TasteOutcome
from itl_ai.refine.dimensions import dimensions_for, stimulus_coordinates
from itl_ai.refine.models import (
    DEFAULT_BUTTON_SCOPE,
    DEFAULT_EVENT_OUTCOMES,
    EDITABLE_COMPONENTS,
    RESERVED_SESSION_IDS,
    AtomicScope,
    AttributeDirective,
    ContextRelations,
    CorpusStratum,
    DesignContext,
    DimensionEvidence,
    Interpretation,
    ObservedAppearance,
    PreferenceEventRequest,
    PreferenceEvidence,
    ProjectContext,
    RetrievedEvidence,
    SpecDiff,
    UsageContext,
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
# A judgment made somewhere else still says something, but far less. A legacy
# row that names no project context can never outrank one that does.
USAGE_SCORE: dict[ContextRelation, int] = {"exact": 120, "compatible": 70, "global": 25, "mismatch": 0}
PROJECT_SCORE: dict[ContextRelation, int] = {"exact": 40, "compatible": 20, "global": 0, "mismatch": -30}
LEGACY_STRATUM_PENALTY = 40
STRENGTH_WEIGHT = {"weak": 0.5, "moderate": 1.0, "strong": 1.5}
USAGE_WEIGHT: dict[ContextRelation, float] = {"exact": 1.0, "compatible": 0.6, "global": 0.3, "mismatch": 0.15}
PROJECT_WEIGHT: dict[ContextRelation, float] = {"exact": 1.0, "compatible": 0.8, "global": 0.5, "mismatch": 0.2}
DIRECTIVES_ADAPTER = TypeAdapter(list[AttributeDirective])
VISUAL_PATH_PATTERN = re.compile(r"^/appearance/[a-z][a-zA-Z0-9]*$")
OUTCOMES = DEFAULT_EVENT_OUTCOMES


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
                -- A derived, rebuildable projection of the event log onto the
                -- shared dimension space. The events remain canonical.
                CREATE TABLE IF NOT EXISTS dimension_observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL REFERENCES preference_events(id),
                    dimension TEXT NOT NULL,
                    component_type TEXT NOT NULL,
                    token TEXT NOT NULL,
                    value TEXT NOT NULL,
                    coordinate REAL NOT NULL,
                    polarity REAL NOT NULL,
                    strength TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(event_id, dimension, value)
                );
                CREATE INDEX IF NOT EXISTS dimension_observations_dimension
                    ON dimension_observations(dimension);
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
                "outcome": "ALTER TABLE preference_events ADD COLUMN outcome TEXT",
                "project_context_json": "ALTER TABLE preference_events ADD COLUMN project_context_json TEXT",
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
            self._project_existing_events_onto_the_dimension_space(connection)
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (6, CURRENT_TIMESTAMP)"
            )

    @staticmethod
    def _project_existing_events_onto_the_dimension_space(connection: sqlite3.Connection) -> None:
        """Rebuild the derived altitude for rows recorded before it existed.

        The events themselves are never rewritten; only the projection is.
        """
        applied = connection.execute("SELECT 1 FROM schema_migrations WHERE version = 6").fetchone()
        if applied is not None:
            return
        rows = connection.execute(
            """
            SELECT preference_events.id, preference_events.component_type, preference_events.action,
                   preference_events.outcome, preference_events.evidence_json,
                   preference_events.target_element_id, preference_events.created_at,
                   before_snapshot.spec_json AS before_snapshot_json,
                   after_snapshot.spec_json AS after_snapshot_json
            FROM preference_events
            JOIN spec_snapshots AS before_snapshot
              ON before_snapshot.id = preference_events.before_snapshot_id
            LEFT JOIN spec_snapshots AS after_snapshot
              ON after_snapshot.id = preference_events.after_snapshot_id
            """
        ).fetchall()
        for row in rows:
            _record_dimension_observations(
                connection,
                event_id=int(row["id"]),
                component_type=str(row["component_type"]),
                before=_decode_observed_appearance(row["before_snapshot_json"], row["target_element_id"]),
                after=_decode_observed_appearance(row["after_snapshot_json"], row["target_element_id"]),
                outcome=_outcome(str(row["action"]), row["outcome"]),
                strength=_strength_from(row["evidence_json"]),
                created_at=str(row["created_at"]),
            )

    def add_event(self, event: PreferenceEventRequest) -> tuple[int, datetime]:
        """Append one judgment, and project it onto the shared dimension space.

        One observation therefore teaches at two altitudes at once: the shared
        dimensions the component exposes, and a residual scoped to it.
        """
        created_at = datetime.now(UTC)
        with self._connection() as connection:
            before_id = self._snapshot_id(connection, event.beforeSpec, created_at)
            after_id = self._snapshot_id(connection, event.afterSpec, created_at) if event.afterSpec else None
            diff = _spec_diff(event.beforeSpec, event.afterSpec)
            cursor = connection.execute(
                """
                INSERT INTO preference_events (
                    session_id, component_type, atomic_level, scope_json, context, context_json,
                    target_element_id, action, outcome, source,
                    before_snapshot_id, after_snapshot_id, selected_element_id, candidate_id,
                    liked_paths_json, disliked_paths_json, locked_paths_json, evidence_json, directives_json,
                    spec_diff_json, critique, parser_interpretation_json, project_context_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    event.outcome,
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
                    _json(event.projectContext.model_dump()) if event.projectContext else None,
                    created_at.isoformat(),
                ),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("SQLite did not return an ID for the preference event.")
            event_id = cursor.lastrowid
            _record_dimension_observations(
                connection,
                event_id=event_id,
                component_type=event.componentType,
                before=_appearance_in(event.beforeSpec, event.targetElementId),
                after=_appearance_in(event.afterSpec, event.targetElementId),
                outcome=event.outcome or DEFAULT_EVENT_OUTCOMES[event.action],
                strength=event.evidence.strength,
                created_at=created_at.isoformat(),
            )
        return event_id, created_at

    def retrieve(
        self,
        component_type: str,
        context: DesignContext,
        query_evidence: PreferenceEvidence,
        scope: AtomicScope = DEFAULT_BUTTON_SCOPE,
        project_context: ProjectContext | None = None,
        limit: int = 6,
    ) -> list[RetrievedEvidence]:
        """Return evidence for one editable subject only, ranked by relevance.

        The component type is a hard partition: an atom decision is never
        retrieved for a molecule. The scope then ranks subjects inside it.
        """
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT preference_events.id, preference_events.atomic_level, preference_events.scope_json,
                       preference_events.context_json, preference_events.context,
                       preference_events.project_context_json, preference_events.session_id,
                       preference_events.source, preference_events.action, preference_events.outcome,
                       preference_events.evidence_json,
                       preference_events.liked_paths_json, preference_events.disliked_paths_json,
                       preference_events.locked_paths_json, preference_events.critique,
                       preference_events.candidate_id, preference_events.directives_json,
                       preference_events.spec_diff_json, preference_events.parser_interpretation_json,
                       preference_events.target_element_id, before_snapshot.spec_json AS before_snapshot_json,
                       after_snapshot.spec_json AS after_snapshot_json
                FROM preference_events
                JOIN spec_snapshots AS before_snapshot
                  ON before_snapshot.id = preference_events.before_snapshot_id
                LEFT JOIN spec_snapshots AS after_snapshot
                  ON after_snapshot.id = preference_events.after_snapshot_id
                WHERE preference_events.component_type = ?
                ORDER BY preference_events.id DESC
                """,
                (component_type,),
            ).fetchall()

        scored = [_retrieval_row(row, context, query_evidence, scope, project_context) for row in rows]
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        selected = scored[:limit]
        mismatch = next((item for item in scored if item[2].contextRelation == "mismatch"), None)
        if mismatch and mismatch not in selected:
            selected = selected[: max(0, limit - 1)] + [mismatch]
        return [item[2] for item in selected]

    def retrieve_dimensions(
        self,
        component_type: str,
        context: DesignContext,
        project_context: ProjectContext | None = None,
    ) -> list[DimensionEvidence]:
        """Read the shared taste space through the queried component's tokens.

        This is the altitude at which a judgment about a Button is legible to a
        Field: the query only ever loads dimensions the queried component
        declares, so evidence transfers along a shared dimension and nowhere
        else.
        """
        exposed = sorted(dimensions_for(component_type))
        if not exposed:
            return []
        placeholders = ",".join("?" for _ in exposed)
        with self._connection() as connection:
            rows = connection.execute(
                f"""
                SELECT dimension_observations.event_id, dimension_observations.dimension,
                       dimension_observations.component_type, dimension_observations.value,
                       dimension_observations.coordinate, dimension_observations.polarity,
                       dimension_observations.strength, preference_events.context_json,
                       preference_events.project_context_json
                FROM dimension_observations
                JOIN preference_events ON preference_events.id = dimension_observations.event_id
                WHERE dimension_observations.dimension IN ({placeholders})
                """,
                exposed,
            ).fetchall()
        return compile_dimension_evidence(component_type, _weighted_observations(rows, context, project_context))

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
    row: sqlite3.Row,
    context: DesignContext,
    query_evidence: PreferenceEvidence,
    requested_scope: AtomicScope,
    requested_project: ProjectContext | None = None,
) -> tuple[int, int, RetrievedEvidence]:
    stored_context = _decode_context(row["context_json"])
    stored_project = _decode_project_context(row["project_context_json"])
    stored_scope = _decode_scope(row["scope_json"], row["atomic_level"])
    stored_evidence = _decode_evidence(row)
    relations = _relations(context.usage(), requested_project, stored_context, stored_project)
    stratum = _stratum(row["session_id"], row["scope_json"], row["outcome"], row["project_context_json"])
    preference_relation = _preference_relation(query_evidence, stored_evidence)
    score = (
        SOURCE_CONFIDENCE[str(row["source"])]
        + STRENGTH_SCORE[stored_evidence.strength]
        + USAGE_SCORE[relations.usage]
        + PROJECT_SCORE[relations.project]
        + _scope_score(requested_scope, stored_scope)
        - (LEGACY_STRATUM_PENALTY if stratum == "legacy" else 0)
    )
    evidence = RetrievedEvidence(
        id=row["id"],
        contextRelation=relations.overall,
        relations=relations,
        stratum=stratum,
        preferenceRelation=preference_relation,
        source=row["source"],
        scope=stored_scope,
        context=stored_context,
        projectContext=stored_project,
        evidence=stored_evidence,
        critique=row["critique"],
        outcome=_outcome(row["action"], row["outcome"]),
        observedAppearance=_decode_observed_appearance(
            row["after_snapshot_json"] or row["before_snapshot_json"], row["target_element_id"]
        ),
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


def _outcome(action: str, stored: str | None) -> TasteOutcome:
    if stored in OUTCOMES.values():
        return cast(TasteOutcome, stored)
    return OUTCOMES.get(action, "indifferent")


def _decode_observed_appearance(snapshot: str | None, target_element_id: str) -> ObservedAppearance | None:
    """Recover what was on screen, validated against the subject's vocabulary."""
    if not snapshot:
        return None
    try:
        element = json.loads(snapshot)["elements"][target_element_id]
        entry = EDITABLE_COMPONENTS.get(element["type"])
        if entry is None or entry.appearance is None:
            return None
        appearance = entry.appearance.model_validate(element["props"]["appearance"]).model_dump()
        return ObservedAppearance(componentType=element["type"], appearance=appearance)
    except (KeyError, TypeError, ValueError):
        return None


def _appearance_in(spec: dict[str, object] | None, target_element_id: str) -> ObservedAppearance | None:
    """The treatment a person looked at, read straight off a request's spec."""
    return _decode_observed_appearance(_json(spec), target_element_id) if spec is not None else None


def _strength_from(evidence_json: object) -> str:
    if not isinstance(evidence_json, str) or not evidence_json:
        return "weak"
    try:
        return PreferenceEvidence.model_validate_json(evidence_json).strength
    except ValueError:
        return "weak"


def _record_dimension_observations(
    connection: sqlite3.Connection,
    *,
    event_id: int,
    component_type: str,
    before: ObservedAppearance | None,
    after: ObservedAppearance | None,
    outcome: TasteOutcome,
    strength: str,
    created_at: str,
) -> None:
    """Write the derived altitude for one judgment. The event stays canonical."""
    if before is None:
        return
    readings = stimulus_coordinates(
        component_type, before.appearance, after.appearance if after is not None else None, outcome
    )
    for reading in readings:
        connection.execute(
            """INSERT OR IGNORE INTO dimension_observations(
                   event_id, dimension, component_type, token, value, coordinate, polarity, strength, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event_id,
                reading.dimension,
                component_type,
                reading.token,
                reading.value,
                reading.coordinate,
                reading.polarity,
                strength,
                created_at,
            ),
        )


def _weighted_observations(
    rows: Sequence[sqlite3.Row], context: DesignContext, project_context: ProjectContext | None
) -> list[ObservationRow]:
    """Discount each reading by how far its context sits from the query's."""
    requested_usage = context.usage()
    observations: list[ObservationRow] = []
    for row in rows:
        relations = _relations(
            requested_usage,
            project_context,
            _decode_context(row["context_json"]),
            _decode_project_context(row["project_context_json"]),
        )
        weight = (
            float(row["polarity"])
            * STRENGTH_WEIGHT.get(str(row["strength"]), 1.0)
            * USAGE_WEIGHT[relations.usage]
            * PROJECT_WEIGHT[relations.project]
        )
        observations.append(
            ObservationRow(
                event_id=int(row["event_id"]),
                dimension=str(row["dimension"]),
                component_type=str(row["component_type"]),
                value=str(row["value"]),
                coordinate=float(row["coordinate"]),
                weight=round(weight, 6),
            )
        )
    return observations


def _decode_project_context(value: object) -> ProjectContext | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return ProjectContext.model_validate_json(value)
    except ValueError:
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


def _decode_paths(value: str) -> list[str]:
    decoded = json.loads(value)
    return [item for item in decoded if isinstance(item, str) and VISUAL_PATH_PATTERN.match(item)]


def _usage_relation(requested: UsageContext, stored: UsageContext | None) -> ContextRelation:
    if stored is None:
        return "global"
    if stored == requested:
        return "exact"
    if stored.semanticRole == requested.semanticRole and stored.surface == requested.surface:
        return "compatible"
    return "mismatch"


def _project_relation(requested: ProjectContext | None, stored: ProjectContext | None) -> ContextRelation:
    """A row that names no product tone is unspecified, never contradictory."""
    if requested is None or stored is None:
        return "global"
    if stored == requested:
        return "exact"
    shares_tone = bool(set(stored.visualTone).intersection(requested.visualTone))
    if stored.productKind == requested.productKind and stored.platform == requested.platform and shares_tone:
        return "compatible"
    return "mismatch"


def _relations(
    requested_usage: UsageContext,
    requested_project: ProjectContext | None,
    stored_context: DesignContext | None,
    stored_project: ProjectContext | None,
) -> ContextRelations:
    """Report each axis, then summarize — never collapse them before comparing.

    The same usage under two product tones differs on an axis the system has, so
    it summarizes as `compatible`. Collapsing the axes first is what made that
    case look like the person contradicting themselves.
    """
    usage = _usage_relation(requested_usage, stored_context.usage() if stored_context else None)
    project = _project_relation(requested_project, stored_project)
    return ContextRelations(usage=usage, project=project, overall=_overall_relation(usage, project))


def _overall_relation(usage: ContextRelation, project: ContextRelation) -> ContextRelation:
    if usage == "mismatch":
        return "mismatch"
    if usage == "global":
        return "global"
    if project == "mismatch":
        return "compatible"
    return "exact" if usage == "exact" and project in {"exact", "global"} else "compatible"


def _stratum(
    session_id: object, scope_json: object, outcome: object, project_context_json: object
) -> CorpusStratum:
    """Which acquisition contract a row was recorded under.

    Rows that predate a real session ID, a scope, an outcome or a product tone
    are read as they were written and reported separately, never rewritten and
    never silently pooled with rows that carry all four.
    """
    named_session = isinstance(session_id, str) and session_id.lower() not in RESERVED_SESSION_IDS
    complete = named_session and all(bool(field) for field in (scope_json, outcome, project_context_json))
    return "primary" if complete else "legacy"


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
