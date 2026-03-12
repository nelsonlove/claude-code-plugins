"""Tests for skills and commands — structure validation."""

import re
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).parent.parent

EXPECTED_SKILLS = [
    "search", "triage", "capture", "daily-review",
    "filing", "linking", "contact-lookup",
]

EXPECTED_COMMANDS = [
    "search", "triage", "capture", "review", "onboard", "status",
]


# --- Skill files ---

class TestSkills:
    def test_skill_dirs_exist(self):
        for skill in EXPECTED_SKILLS:
            skill_dir = PLUGIN_ROOT / "skills" / skill
            assert skill_dir.is_dir(), f"Missing skill directory: {skill}"

    def test_skill_files_exist(self):
        for skill in EXPECTED_SKILLS:
            skill_file = PLUGIN_ROOT / "skills" / skill / "SKILL.md"
            assert skill_file.is_file(), f"Missing SKILL.md for: {skill}"

    @pytest.mark.parametrize("skill", EXPECTED_SKILLS)
    def test_skill_has_frontmatter(self, skill):
        content = (PLUGIN_ROOT / "skills" / skill / "SKILL.md").read_text()
        assert content.startswith("---"), f"Skill {skill} missing frontmatter"
        parts = content.split("---", 2)
        assert len(parts) >= 3, f"Skill {skill} has malformed frontmatter"
        fm = parts[1]
        assert "name:" in fm, f"Skill {skill} missing name field"
        assert "description:" in fm, f"Skill {skill} missing description field"

    @pytest.mark.parametrize("skill", EXPECTED_SKILLS)
    def test_skill_name_matches_dir(self, skill):
        content = (PLUGIN_ROOT / "skills" / skill / "SKILL.md").read_text()
        fm = content.split("---", 2)[1]
        match = re.search(r'name:\s*(.+)', fm)
        assert match is not None
        assert match.group(1).strip() == skill

    @pytest.mark.parametrize("skill", EXPECTED_SKILLS)
    def test_skill_has_body(self, skill):
        content = (PLUGIN_ROOT / "skills" / skill / "SKILL.md").read_text()
        body = content.split("---", 2)[2]
        assert len(body.strip()) > 50, f"Skill {skill} body too short"

    @pytest.mark.parametrize("skill", EXPECTED_SKILLS)
    def test_skill_description_is_actionable(self, skill):
        """Description should explain when to trigger the skill."""
        content = (PLUGIN_ROOT / "skills" / skill / "SKILL.md").read_text()
        fm = content.split("---", 2)[1]
        match = re.search(r'description:\s*"(.+)"', fm)
        assert match is not None, f"Skill {skill} description not quoted"
        desc = match.group(1)
        assert len(desc) > 30, f"Skill {skill} description too short"


# --- Command files ---

class TestCommands:
    def test_command_files_exist(self):
        for cmd in EXPECTED_COMMANDS:
            cmd_file = PLUGIN_ROOT / "commands" / f"{cmd}.md"
            assert cmd_file.is_file(), f"Missing command: {cmd}"

    @pytest.mark.parametrize("cmd", EXPECTED_COMMANDS)
    def test_command_has_frontmatter(self, cmd):
        content = (PLUGIN_ROOT / "commands" / f"{cmd}.md").read_text()
        assert content.startswith("---"), f"Command {cmd} missing frontmatter"
        parts = content.split("---", 2)
        assert len(parts) >= 3, f"Command {cmd} has malformed frontmatter"
        fm = parts[1]
        assert "description:" in fm, f"Command {cmd} missing description"
        assert "allowed-tools:" in fm, f"Command {cmd} missing allowed-tools"

    @pytest.mark.parametrize("cmd", EXPECTED_COMMANDS)
    def test_command_has_body(self, cmd):
        content = (PLUGIN_ROOT / "commands" / f"{cmd}.md").read_text()
        body = content.split("---", 2)[2]
        assert len(body.strip()) > 30, f"Command {cmd} body too short"

    @pytest.mark.parametrize("cmd", EXPECTED_COMMANDS)
    def test_command_description_nonempty(self, cmd):
        content = (PLUGIN_ROOT / "commands" / f"{cmd}.md").read_text()
        fm = content.split("---", 2)[1]
        match = re.search(r'description:\s*(.+)', fm)
        assert match is not None
        assert len(match.group(1).strip()) > 5


# --- Plugin manifest ---

class TestPluginManifest:
    def test_plugin_json_exists(self):
        assert (PLUGIN_ROOT / "plugin.json").is_file()

    def test_plugin_json_valid(self):
        import json
        data = json.loads((PLUGIN_ROOT / "plugin.json").read_text())
        assert data["name"] == "pim"
        assert "version" in data
        assert "description" in data
