"""Validate the configuration contract for project-scoped Codex agents.

This is a static configuration test. It does not prove actual subagent spawning.
"""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROLES = {"scout", "atlas", "trace", "forge", "pixel", "echo", "shield"}


class AgentConfigurationTests(unittest.TestCase):
    def test_all_seven_roles_have_valid_toml_and_instructions(self):
        role_dir = ROOT / ".codex" / "agents"
        paths = list(role_dir.glob("*.toml"))
        self.assertEqual({p.stem for p in paths}, ROLES)
        for path in paths:
            with self.subTest(role=path.stem):
                data = tomllib.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(data["name"], path.stem)
                self.assertTrue(data["description"].strip())
                self.assertGreater(len(data["developer_instructions"].strip()), 80)
                self.assertEqual(data["model_reasoning_effort"], "high")
                self.assertNotIn("model", data, "Do not pin unsupported account-specific models")

    def test_concurrency_bound_and_persistent_contract(self):
        config = tomllib.loads((ROOT / ".codex" / "config.toml").read_text(encoding="utf-8"))
        agents = config["agents"]
        self.assertTrue(agents["enabled"])
        self.assertEqual(agents["max_concurrent_threads_per_session"], 3)
        self.assertEqual(agents["default_subagent_reasoning_effort"], "high")
        self.assertTrue((ROOT / "docs" / "AI_AGENT_TEAM.md").is_file())
        instructions = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        for role in ROLES:
            self.assertIn("`" + role + "`", instructions)
        self.assertIn("never invent", instructions.lower())


if __name__ == "__main__":
    unittest.main()
