"""User profile and onboarding system.

The profile captures the user's tool landscape, workflow patterns,
organizational conventions, and adapter configuration. It is produced
by the onboarding interview and evolves as the user's setup changes.

Stored at: <data_dir>/profile.json
"""

import json
from pathlib import Path
from typing import Any


# Default empty profile structure
DEFAULT_PROFILE: dict[str, Any] = {
    "version": 1,
    "tools": {},
    "topic_hierarchy": {},
    "conventions": {},
    "workflow_patterns": [],
}

# Onboarding interview phases with questions
INTERVIEW_PHASES: list[dict[str, Any]] = [
    {
        "phase": "tool_inventory",
        "title": "Tool Inventory",
        "description": "What apps and tools does the user use day to day?",
        "questions": [
            "What do you use for notes?",
            "What do you use for tasks and to-dos?",
            "What do you use for email?",
            "What do you use for calendar and events?",
            "Do you have a journaling app or habit?",
            "Where do you save articles, bookmarks, or files you want to keep?",
            "How do you keep track of contacts?",
        ],
    },
    {
        "phase": "workflow_discovery",
        "title": "Workflow Discovery",
        "description": "How does information flow through the user's day?",
        "questions": [
            "When you jot something down quickly, where does it go?",
            "When you sit down to do focused work, where does that happen?",
            "Do you have a place for things you look up but don't change much?",
            "When you finish something, what happens to it?",
        ],
    },
    {
        "phase": "organizational_structure",
        "title": "Organizational Structure",
        "description": "How does the user organize their world?",
        "questions": [
            "How do you organize your projects? Folders, tags, categories?",
            "Do you have areas of responsibility (work, personal, household)?",
            "Do you use a numbering system like Johnny Decimal?",
            "Are there naming conventions you follow?",
        ],
    },
    {
        "phase": "relationship_patterns",
        "title": "Relationship Patterns",
        "description": "How are things connected in the user's mind?",
        "questions": [
            "When you get an email that requires action, what do you do?",
            "When you have a meeting, do you take notes? Where?",
            "Do you track who gave you a task or who you're waiting on?",
        ],
    },
]


class Profile:
    """Manages the user's PIM profile.

    The profile is a JSON file that captures tool inventory, workflow
    patterns, organizational structure, and conventions. It is the
    output of the onboarding interview and evolves over time.
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.profile_path = data_dir / "profile.json"
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        """Load profile from disk, or return default."""
        if self.profile_path.exists():
            try:
                with open(self.profile_path) as f:
                    data = json.load(f)
                # Ensure all expected keys exist
                for key, default in DEFAULT_PROFILE.items():
                    if key not in data:
                        data[key] = default if not isinstance(default, (dict, list)) else type(default)(default)
                return data
            except (json.JSONDecodeError, OSError):
                return json.loads(json.dumps(DEFAULT_PROFILE))
        return json.loads(json.dumps(DEFAULT_PROFILE))

    def _save(self) -> None:
        """Persist profile to disk."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with open(self.profile_path, "w") as f:
            json.dump(self._data, f, indent=2)

    @property
    def exists(self) -> bool:
        """Whether a profile has been saved before."""
        return self.profile_path.exists()

    @property
    def is_configured(self) -> bool:
        """Whether the profile has at least one tool configured."""
        return bool(self._data.get("tools"))

    @property
    def data(self) -> dict[str, Any]:
        """Full profile data (read-only copy)."""
        return dict(self._data)

    # --- Tool management ---

    def get_tools(self) -> dict[str, Any]:
        """Return all configured tools."""
        return dict(self._data.get("tools", {}))

    def get_tool(self, tool_id: str) -> dict[str, Any] | None:
        """Return config for a specific tool."""
        return self._data.get("tools", {}).get(tool_id)

    def set_tool(self, tool_id: str, config: dict[str, Any]) -> None:
        """Add or update a tool configuration."""
        self._data.setdefault("tools", {})[tool_id] = config
        self._save()

    def remove_tool(self, tool_id: str) -> bool:
        """Remove a tool. Returns True if it existed."""
        tools = self._data.get("tools", {})
        if tool_id in tools:
            del tools[tool_id]
            self._save()
            return True
        return False

    # --- Topic hierarchy ---

    def get_topic_hierarchy(self) -> dict[str, Any]:
        """Return topic hierarchy config."""
        return dict(self._data.get("topic_hierarchy", {}))

    def set_topic_hierarchy(self, hierarchy: dict[str, Any]) -> None:
        """Set the topic hierarchy."""
        self._data["topic_hierarchy"] = hierarchy
        self._save()

    # --- Conventions ---

    def get_conventions(self) -> dict[str, Any]:
        """Return user conventions."""
        return dict(self._data.get("conventions", {}))

    def set_convention(self, key: str, value: Any) -> None:
        """Set a single convention."""
        self._data.setdefault("conventions", {})[key] = value
        self._save()

    def remove_convention(self, key: str) -> bool:
        """Remove a convention. Returns True if it existed."""
        conventions = self._data.get("conventions", {})
        if key in conventions:
            del conventions[key]
            self._save()
            return True
        return False

    # --- Workflow patterns ---

    def get_workflow_patterns(self) -> list[str]:
        """Return workflow pattern list."""
        return list(self._data.get("workflow_patterns", []))

    def add_workflow_pattern(self, pattern: str) -> None:
        """Add a workflow pattern (no duplicates)."""
        patterns = self._data.setdefault("workflow_patterns", [])
        if pattern not in patterns:
            patterns.append(pattern)
            self._save()

    def remove_workflow_pattern(self, pattern: str) -> bool:
        """Remove a workflow pattern. Returns True if it existed."""
        patterns = self._data.get("workflow_patterns", [])
        if pattern in patterns:
            patterns.remove(pattern)
            self._save()
            return True
        return False

    # --- Bulk operations ---

    def update(self, changes: dict[str, Any]) -> None:
        """Merge changes into the profile.

        Supports top-level keys: tools, topic_hierarchy, conventions,
        workflow_patterns. For tools, merges individual tool configs.
        """
        if "tools" in changes:
            self._data.setdefault("tools", {}).update(changes["tools"])
        if "topic_hierarchy" in changes:
            self._data["topic_hierarchy"] = changes["topic_hierarchy"]
        if "conventions" in changes:
            self._data.setdefault("conventions", {}).update(changes["conventions"])
        if "workflow_patterns" in changes:
            for p in changes["workflow_patterns"]:
                patterns = self._data.setdefault("workflow_patterns", [])
                if p not in patterns:
                    patterns.append(p)
        self._save()

    def reset(self) -> None:
        """Reset profile to defaults."""
        self._data = json.loads(json.dumps(DEFAULT_PROFILE))
        if self.profile_path.exists():
            self.profile_path.unlink()

    def export(self) -> dict[str, Any]:
        """Export full profile for display or injection into prompts."""
        return {
            "version": self._data.get("version", 1),
            "tools": self.get_tools(),
            "topic_hierarchy": self.get_topic_hierarchy(),
            "conventions": self.get_conventions(),
            "workflow_patterns": self.get_workflow_patterns(),
            "is_configured": self.is_configured,
        }


class OnboardingFlow:
    """Manages the onboarding interview process.

    Tracks which phases/questions have been answered and collects
    responses to build the profile. In Tier 1, this provides the
    data structure and tracking — the actual conversational interview
    is driven by the config agent with LLM access.
    """

    def __init__(self, profile: Profile):
        self.profile = profile
        self._responses: dict[str, list[dict[str, str]]] = {}
        self._current_phase: int = 0
        self._current_question: int = 0

    @property
    def phases(self) -> list[dict[str, Any]]:
        """All interview phases."""
        return INTERVIEW_PHASES

    @property
    def current_phase(self) -> dict[str, Any] | None:
        """Current phase, or None if complete."""
        if self._current_phase >= len(INTERVIEW_PHASES):
            return None
        return INTERVIEW_PHASES[self._current_phase]

    @property
    def current_question(self) -> str | None:
        """Current question, or None if phase/interview complete."""
        phase = self.current_phase
        if phase is None:
            return None
        questions = phase["questions"]
        if self._current_question >= len(questions):
            return None
        return questions[self._current_question]

    @property
    def is_complete(self) -> bool:
        """Whether all phases have been completed."""
        return self._current_phase >= len(INTERVIEW_PHASES)

    @property
    def progress(self) -> dict[str, Any]:
        """Current progress through the interview."""
        total_questions = sum(len(p["questions"]) for p in INTERVIEW_PHASES)
        answered = sum(len(qs) for qs in self._responses.values())
        return {
            "phase": self._current_phase,
            "total_phases": len(INTERVIEW_PHASES),
            "question": self._current_question,
            "total_questions": total_questions,
            "answered": answered,
            "is_complete": self.is_complete,
            "current_phase_name": self.current_phase["title"] if self.current_phase else None,
        }

    def record_response(self, question: str, answer: str) -> None:
        """Record a response to a question and advance."""
        phase = self.current_phase
        if phase is None:
            return

        phase_key = phase["phase"]
        self._responses.setdefault(phase_key, []).append({
            "question": question,
            "answer": answer,
        })

        # Advance to next question
        self._current_question += 1
        if self._current_question >= len(phase["questions"]):
            # Advance to next phase
            self._current_phase += 1
            self._current_question = 0

    def get_responses(self, phase: str | None = None) -> dict[str, list[dict[str, str]]]:
        """Get recorded responses, optionally filtered by phase."""
        if phase:
            return {phase: self._responses.get(phase, [])}
        return dict(self._responses)

    def apply_to_profile(self, tool_configs: dict[str, Any] | None = None,
                         topic_hierarchy: dict[str, Any] | None = None,
                         conventions: dict[str, Any] | None = None,
                         workflow_patterns: list[str] | None = None) -> None:
        """Apply interview results to the profile.

        In Tier 1, the caller (config agent) interprets responses
        and passes structured data. Later tiers will have LLM-driven
        interpretation.
        """
        changes: dict[str, Any] = {}
        if tool_configs:
            changes["tools"] = tool_configs
        if topic_hierarchy:
            changes["topic_hierarchy"] = topic_hierarchy
        if conventions:
            changes["conventions"] = conventions
        if workflow_patterns:
            changes["workflow_patterns"] = workflow_patterns

        if changes:
            self.profile.update(changes)

    def skip_to_phase(self, phase_index: int) -> None:
        """Skip to a specific phase (0-indexed)."""
        if 0 <= phase_index <= len(INTERVIEW_PHASES):
            self._current_phase = phase_index
            self._current_question = 0

    def skip_question(self) -> None:
        """Skip the current question."""
        phase = self.current_phase
        if phase is None:
            return
        self._current_question += 1
        if self._current_question >= len(phase["questions"]):
            self._current_phase += 1
            self._current_question = 0
