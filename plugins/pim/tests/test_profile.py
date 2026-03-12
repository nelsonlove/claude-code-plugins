"""Tests for the profile and onboarding system."""

import json

from src.profile import Profile, OnboardingFlow, INTERVIEW_PHASES


# --- Profile ---

class TestProfileInit:
    def test_default_profile(self, tmp_path):
        profile = Profile(tmp_path)
        assert not profile.exists
        assert not profile.is_configured
        assert profile.data["version"] == 1
        assert profile.data["tools"] == {}

    def test_load_existing(self, tmp_path):
        data = {"version": 1, "tools": {"omnifocus": {"types": ["task"]}},
                "topic_hierarchy": {}, "conventions": {}, "workflow_patterns": []}
        (tmp_path / "profile.json").write_text(json.dumps(data))

        profile = Profile(tmp_path)
        assert profile.exists
        assert profile.is_configured
        assert "omnifocus" in profile.get_tools()

    def test_load_missing_keys_filled(self, tmp_path):
        """Profile with missing keys gets defaults filled in."""
        data = {"version": 1, "tools": {"x": {}}}
        (tmp_path / "profile.json").write_text(json.dumps(data))

        profile = Profile(tmp_path)
        assert "conventions" in profile.data
        assert "workflow_patterns" in profile.data

    def test_load_corrupt_json(self, tmp_path):
        (tmp_path / "profile.json").write_text("not json{{{")
        profile = Profile(tmp_path)
        assert not profile.is_configured

    def test_load_creates_dir(self, tmp_path):
        nested = tmp_path / "deep" / "nested"
        profile = Profile(nested)
        profile.set_tool("test", {"types": ["note"]})
        assert (nested / "profile.json").exists()


class TestProfileTools:
    def test_set_and_get_tool(self, tmp_path):
        profile = Profile(tmp_path)
        config = {"types": ["task", "topic"], "registers": {"scratch": "inbox"}}
        profile.set_tool("omnifocus", config)

        assert profile.get_tool("omnifocus") == config
        assert profile.is_configured

    def test_get_nonexistent_tool(self, tmp_path):
        profile = Profile(tmp_path)
        assert profile.get_tool("missing") is None

    def test_update_tool(self, tmp_path):
        profile = Profile(tmp_path)
        profile.set_tool("omnifocus", {"types": ["task"]})
        profile.set_tool("omnifocus", {"types": ["task", "topic"]})
        assert profile.get_tool("omnifocus")["types"] == ["task", "topic"]

    def test_remove_tool(self, tmp_path):
        profile = Profile(tmp_path)
        profile.set_tool("omnifocus", {"types": ["task"]})
        assert profile.remove_tool("omnifocus") is True
        assert profile.get_tool("omnifocus") is None

    def test_remove_nonexistent_tool(self, tmp_path):
        profile = Profile(tmp_path)
        assert profile.remove_tool("missing") is False

    def test_persists_across_instances(self, tmp_path):
        p1 = Profile(tmp_path)
        p1.set_tool("omnifocus", {"types": ["task"]})

        p2 = Profile(tmp_path)
        assert p2.get_tool("omnifocus") is not None


class TestProfileTopicHierarchy:
    def test_set_and_get(self, tmp_path):
        profile = Profile(tmp_path)
        hierarchy = {"system": "johnny_decimal", "areas": [{"range": "10-19", "name": "Work"}]}
        profile.set_topic_hierarchy(hierarchy)
        assert profile.get_topic_hierarchy() == hierarchy

    def test_default_empty(self, tmp_path):
        profile = Profile(tmp_path)
        assert profile.get_topic_hierarchy() == {}


class TestProfileConventions:
    def test_set_and_get(self, tmp_path):
        profile = Profile(tmp_path)
        profile.set_convention("task_contexts", ["@computer", "@phone"])
        assert profile.get_conventions()["task_contexts"] == ["@computer", "@phone"]

    def test_remove(self, tmp_path):
        profile = Profile(tmp_path)
        profile.set_convention("key", "value")
        assert profile.remove_convention("key") is True
        assert "key" not in profile.get_conventions()

    def test_remove_nonexistent(self, tmp_path):
        profile = Profile(tmp_path)
        assert profile.remove_convention("missing") is False


class TestProfileWorkflowPatterns:
    def test_add_pattern(self, tmp_path):
        profile = Profile(tmp_path)
        profile.add_workflow_pattern("Email → extract tasks into OmniFocus")
        assert "Email → extract tasks into OmniFocus" in profile.get_workflow_patterns()

    def test_no_duplicates(self, tmp_path):
        profile = Profile(tmp_path)
        profile.add_workflow_pattern("pattern A")
        profile.add_workflow_pattern("pattern A")
        assert profile.get_workflow_patterns().count("pattern A") == 1

    def test_remove_pattern(self, tmp_path):
        profile = Profile(tmp_path)
        profile.add_workflow_pattern("pattern A")
        assert profile.remove_workflow_pattern("pattern A") is True
        assert "pattern A" not in profile.get_workflow_patterns()

    def test_remove_nonexistent(self, tmp_path):
        profile = Profile(tmp_path)
        assert profile.remove_workflow_pattern("missing") is False


class TestProfileBulkUpdate:
    def test_update_tools(self, tmp_path):
        profile = Profile(tmp_path)
        profile.update({"tools": {"omnifocus": {"types": ["task"]}}})
        assert profile.get_tool("omnifocus") is not None

    def test_update_merges_tools(self, tmp_path):
        profile = Profile(tmp_path)
        profile.set_tool("omnifocus", {"types": ["task"]})
        profile.update({"tools": {"dayone": {"types": ["entry"]}}})
        assert profile.get_tool("omnifocus") is not None
        assert profile.get_tool("dayone") is not None

    def test_update_replaces_hierarchy(self, tmp_path):
        profile = Profile(tmp_path)
        profile.set_topic_hierarchy({"system": "flat"})
        profile.update({"topic_hierarchy": {"system": "jd"}})
        assert profile.get_topic_hierarchy()["system"] == "jd"

    def test_update_merges_conventions(self, tmp_path):
        profile = Profile(tmp_path)
        profile.set_convention("a", "1")
        profile.update({"conventions": {"b": "2"}})
        assert profile.get_conventions()["a"] == "1"
        assert profile.get_conventions()["b"] == "2"

    def test_update_appends_patterns(self, tmp_path):
        profile = Profile(tmp_path)
        profile.add_workflow_pattern("existing")
        profile.update({"workflow_patterns": ["new"]})
        assert "existing" in profile.get_workflow_patterns()
        assert "new" in profile.get_workflow_patterns()

    def test_update_no_duplicate_patterns(self, tmp_path):
        profile = Profile(tmp_path)
        profile.add_workflow_pattern("existing")
        profile.update({"workflow_patterns": ["existing"]})
        assert profile.get_workflow_patterns().count("existing") == 1


class TestProfileReset:
    def test_reset(self, tmp_path):
        profile = Profile(tmp_path)
        profile.set_tool("omnifocus", {"types": ["task"]})
        profile.reset()
        assert not profile.is_configured
        assert not profile.exists


class TestProfileExport:
    def test_export(self, tmp_path):
        profile = Profile(tmp_path)
        profile.set_tool("omnifocus", {"types": ["task"]})
        profile.set_convention("key", "value")
        profile.add_workflow_pattern("pattern")

        exported = profile.export()
        assert exported["version"] == 1
        assert "omnifocus" in exported["tools"]
        assert exported["conventions"]["key"] == "value"
        assert "pattern" in exported["workflow_patterns"]
        assert exported["is_configured"] is True


# --- OnboardingFlow ---

class TestOnboardingInit:
    def test_initial_state(self, tmp_path):
        profile = Profile(tmp_path)
        flow = OnboardingFlow(profile)
        assert not flow.is_complete
        assert flow.current_phase is not None
        assert flow.current_phase["phase"] == "tool_inventory"
        assert flow.current_question is not None

    def test_phases_available(self, tmp_path):
        profile = Profile(tmp_path)
        flow = OnboardingFlow(profile)
        assert len(flow.phases) == 4


class TestOnboardingProgress:
    def test_progress_initial(self, tmp_path):
        profile = Profile(tmp_path)
        flow = OnboardingFlow(profile)
        progress = flow.progress
        assert progress["phase"] == 0
        assert progress["question"] == 0
        assert progress["answered"] == 0
        assert progress["is_complete"] is False
        assert progress["current_phase_name"] == "Tool Inventory"

    def test_record_response_advances(self, tmp_path):
        profile = Profile(tmp_path)
        flow = OnboardingFlow(profile)
        q = flow.current_question
        flow.record_response(q, "I use Apple Notes")
        assert flow.progress["answered"] == 1
        assert flow.progress["question"] == 1

    def test_phase_advances_after_all_questions(self, tmp_path):
        profile = Profile(tmp_path)
        flow = OnboardingFlow(profile)

        # Answer all questions in phase 0 (tool_inventory)
        phase = INTERVIEW_PHASES[0]
        for q in phase["questions"]:
            flow.record_response(q, "answer")

        assert flow.progress["phase"] == 1
        assert flow.current_phase["phase"] == "workflow_discovery"

    def test_complete_after_all_phases(self, tmp_path):
        profile = Profile(tmp_path)
        flow = OnboardingFlow(profile)

        for phase in INTERVIEW_PHASES:
            for q in phase["questions"]:
                flow.record_response(q, "answer")

        assert flow.is_complete
        assert flow.current_phase is None
        assert flow.current_question is None


class TestOnboardingResponses:
    def test_get_all_responses(self, tmp_path):
        profile = Profile(tmp_path)
        flow = OnboardingFlow(profile)
        q = flow.current_question
        flow.record_response(q, "Apple Notes")
        responses = flow.get_responses()
        assert "tool_inventory" in responses
        assert len(responses["tool_inventory"]) == 1

    def test_get_phase_responses(self, tmp_path):
        profile = Profile(tmp_path)
        flow = OnboardingFlow(profile)
        q = flow.current_question
        flow.record_response(q, "Apple Notes")
        responses = flow.get_responses("tool_inventory")
        assert len(responses["tool_inventory"]) == 1

    def test_get_empty_phase(self, tmp_path):
        profile = Profile(tmp_path)
        flow = OnboardingFlow(profile)
        responses = flow.get_responses("workflow_discovery")
        assert responses["workflow_discovery"] == []

    def test_record_on_complete_is_noop(self, tmp_path):
        profile = Profile(tmp_path)
        flow = OnboardingFlow(profile)
        for phase in INTERVIEW_PHASES:
            for q in phase["questions"]:
                flow.record_response(q, "answer")

        flow.record_response("extra", "ignored")
        total = sum(len(qs) for qs in flow.get_responses().values())
        total_expected = sum(len(p["questions"]) for p in INTERVIEW_PHASES)
        assert total == total_expected


class TestOnboardingApply:
    def test_apply_tools(self, tmp_path):
        profile = Profile(tmp_path)
        flow = OnboardingFlow(profile)
        flow.apply_to_profile(
            tool_configs={"omnifocus": {"types": ["task"]}},
        )
        assert profile.get_tool("omnifocus") is not None

    def test_apply_full(self, tmp_path):
        profile = Profile(tmp_path)
        flow = OnboardingFlow(profile)
        flow.apply_to_profile(
            tool_configs={"omnifocus": {"types": ["task"]}},
            topic_hierarchy={"system": "jd"},
            conventions={"capture_default": "OmniFocus inbox"},
            workflow_patterns=["Email → tasks"],
        )
        assert profile.is_configured
        assert profile.get_topic_hierarchy()["system"] == "jd"
        assert "capture_default" in profile.get_conventions()
        assert "Email → tasks" in profile.get_workflow_patterns()

    def test_apply_empty_is_noop(self, tmp_path):
        profile = Profile(tmp_path)
        flow = OnboardingFlow(profile)
        flow.apply_to_profile()
        assert not profile.is_configured


class TestOnboardingNavigation:
    def test_skip_to_phase(self, tmp_path):
        profile = Profile(tmp_path)
        flow = OnboardingFlow(profile)
        flow.skip_to_phase(2)
        assert flow.current_phase["phase"] == "organizational_structure"
        assert flow.progress["question"] == 0

    def test_skip_to_end(self, tmp_path):
        profile = Profile(tmp_path)
        flow = OnboardingFlow(profile)
        flow.skip_to_phase(len(INTERVIEW_PHASES))
        assert flow.is_complete

    def test_skip_question(self, tmp_path):
        profile = Profile(tmp_path)
        flow = OnboardingFlow(profile)
        first_q = flow.current_question
        flow.skip_question()
        assert flow.current_question != first_q
        assert flow.progress["question"] == 1

    def test_skip_last_question_advances_phase(self, tmp_path):
        profile = Profile(tmp_path)
        flow = OnboardingFlow(profile)
        phase = INTERVIEW_PHASES[0]
        for _ in range(len(phase["questions"])):
            flow.skip_question()
        assert flow.current_phase["phase"] == "workflow_discovery"

    def test_skip_on_complete_is_noop(self, tmp_path):
        profile = Profile(tmp_path)
        flow = OnboardingFlow(profile)
        flow.skip_to_phase(len(INTERVIEW_PHASES))
        flow.skip_question()  # should not crash
        assert flow.is_complete
