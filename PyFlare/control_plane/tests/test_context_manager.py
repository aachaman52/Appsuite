"""Acceptance tests for PyFlare Beta Project Context Manager (Section 4)."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pyflare_control.context import (
    ProjectContextManager,
    ProjectNotFoundError,
)


class ProjectContextManagerAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = TemporaryDirectory()
        self.base_path = Path(self.tmp_dir.name)
        self.db_path = self.base_path / "context.sqlite3"
        self.manager = ProjectContextManager(self.db_path)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def _create_sample_unity_project(self, root: Path) -> None:
        """Helper to create a representative Unity project layout."""
        # 1. ProjectSettings
        settings = root / "ProjectSettings"
        settings.mkdir(parents=True)
        (settings / "ProjectVersion.txt").write_text(
            "m_EditorVersion: 6000.0.23f1\nm_StandardAssetsVersion: 0\n",
            encoding="utf-8",
        )

        # 2. Assets/Scripts
        scripts = root / "Assets" / "Scripts"
        scripts.mkdir(parents=True)
        (scripts / "PlayerController.cs").write_text(
            """using UnityEngine;

namespace PyFlare.Game
{
    public class PlayerController : MonoBehaviour
    {
        public float moveSpeed = 5.0f;
        public float jumpForce = 8.0f;

        void Update()
        {
            float horizontal = Input.GetAxis("Horizontal");
            transform.Translate(Vector3.right * horizontal * moveSpeed * Time.deltaTime);
        }

        public void Jump()
        {
            GetComponent<Rigidbody2D>().AddForce(Vector2.up * jumpForce, ForceMode2D.Impulse);
        }
    }
}
""",
            encoding="utf-8",
        )

        (scripts / "GameManager.cs").write_text(
            """using UnityEngine;

namespace PyFlare.Game
{
    public class GameManager : MonoBehaviour
    {
        public static GameManager Instance { get; private set; }
        public int currentScore = 0;

        void Awake()
        {
            Instance = this;
        }

        public void AddScore(int amount)
        {
            currentScore += amount;
            Debug.Log($"Score updated to: {currentScore}");
        }
    }
}
""",
            encoding="utf-8",
        )

        # 3. Assembly definition
        (scripts / "GameAssembly.asmdef").write_text(
            """{
    "name": "GameAssembly",
    "rootNamespace": "PyFlare.Game",
    "references": [],
    "includePlatforms": [],
    "excludePlatforms": [],
    "allowUnsafeCode": false,
    "overrideReferences": false,
    "precompiledReferences": [],
    "autoReferenced": true,
    "defineConstraints": [],
    "versionDefines": [],
    "noEngineReferences": false
}""",
            encoding="utf-8",
        )

        # 4. Assets/Scenes
        scenes = root / "Assets" / "Scenes"
        scenes.mkdir(parents=True)
        (scenes / "MainScene.unity").write_text("%YAML 1.1\n%TAG !u! tag:unity3d.com,2011:\n", encoding="utf-8")

        # 5. Sensitive credentials / temporary folders that must be excluded
        (root / ".env").write_text("API_SECRET_KEY=super_secret_production_key_12345\n", encoding="utf-8")
        (root / "api_credentials.json").write_text('{"secret": "do_not_leak"}', encoding="utf-8")
        (scripts / "id_rsa_backup.key").write_text("RSA_SECRET_987654_DO_NOT_EXPOSE", encoding="utf-8")

        library = root / "Library"
        library.mkdir(parents=True)
        (library / "artifact.cache").write_text("SUPER_EXCLUSIVE_LIBRARY_CACHE_STRING", encoding="utf-8")

        temp_dir = root / "Temp"
        temp_dir.mkdir(parents=True)
        (temp_dir / "editor.log").write_text("temporary log", encoding="utf-8")

    def test_acceptance_1_index_representative_unity_project(self) -> None:
        """Acceptance Test 1: Index a representative Unity project."""
        project_dir = self.base_path / "UnityProject"
        self._create_sample_unity_project(project_dir)

        info = self.manager.register_project("unity-proj-1", project_dir)
        self.assertEqual(info.project_id, "unity-proj-1")
        self.assertEqual(info.project_type, "unity")
        self.assertEqual(info.metadata.get("unity_version"), "6000.0.23f1")
        self.assertIn("Assets/Scenes/MainScene.unity", info.metadata.get("scenes", []))
        self.assertIn("Assets/Scripts/GameAssembly.asmdef", info.metadata.get("asmdefs", []))

        report = self.manager.index_project("unity-proj-1")
        self.assertGreaterEqual(report.indexed_files, 3)  # PlayerController.cs, GameManager.cs, GameAssembly.asmdef
        self.assertGreaterEqual(report.total_chunks, 3)
        self.assertEqual(report.removed_files, 0)

    def test_acceptance_2_and_3_ask_question_and_retrieve_relevant_source(self) -> None:
        """Acceptance Tests 2 & 3: Ask a question and retrieve correct relevant source with reason."""
        project_dir = self.base_path / "UnityProject"
        self._create_sample_unity_project(project_dir)
        self.manager.register_project("unity-proj-1", project_dir)
        self.manager.index_project("unity-proj-1")

        context = self.manager.retrieve_context(
            "unity-proj-1",
            "How does PlayerController move horizontally and handle jump?",
            max_tokens=2000,
        )

        self.assertGreater(len(context.sources), 0)
        top_source = context.sources[0]
        self.assertEqual(top_source.rel_path, "Assets/Scripts/PlayerController.cs")
        self.assertGreater(top_source.score, 0.0)
        self.assertTrue(any(term in top_source.reason for term in ["playercontroller", "jump", "move"]))
        self.assertIn("transform.Translate", top_source.content)
        self.assertIn("AddForce", top_source.content)

        # Check that retrieved sources format clearly into bounded task context
        self.assertIn("### File: Assets/Scripts/PlayerController.cs", context.formatted_context)
        self.assertIn("Retrieval Reason:", context.formatted_context)
        self.assertLessEqual(context.estimated_tokens, 2000)

    def test_acceptance_4_file_change_reflected_in_refreshed_context(self) -> None:
        """Acceptance Test 4: Change the file and verify refreshed context reflects the change."""
        project_dir = self.base_path / "UnityProject"
        self._create_sample_unity_project(project_dir)
        self.manager.register_project("unity-proj-1", project_dir)
        self.manager.index_project("unity-proj-1")

        # Initial state has moveSpeed = 5.0f
        initial_context = self.manager.retrieve_context("unity-proj-1", "moveSpeed")
        self.assertIn("moveSpeed = 5.0f", initial_context.sources[0].content)

        # Verify not stale yet
        self.assertFalse(self.manager.is_stale("unity-proj-1"))

        # Modify file on disk
        player_file = project_dir / "Assets" / "Scripts" / "PlayerController.cs"
        updated_content = player_file.read_text(encoding="utf-8").replace("5.0f", "14.5f")
        player_file.write_text(updated_content, encoding="utf-8")

        # Now is_stale must detect change
        self.assertTrue(self.manager.is_stale("unity-proj-1"))

        # Re-index
        refresh_report = self.manager.index_project("unity-proj-1")
        self.assertEqual(refresh_report.indexed_files, 1)  # Only modified file re-indexed

        # Query again: refreshed context must reflect the updated code
        refreshed_context = self.manager.retrieve_context("unity-proj-1", "moveSpeed")
        self.assertIn("moveSpeed = 14.5f", refreshed_context.sources[0].content)
        self.assertNotIn("5.0f", refreshed_context.sources[0].content)

    def test_acceptance_5_project_isolation(self) -> None:
        """Acceptance Test 5: Verify project A cannot retrieve private context from project B."""
        # Setup Project A
        proj_a = self.base_path / "ProjectA"
        proj_a.mkdir()
        (proj_a / "SecretLogicA.cs").write_text("public class SecretLogicA { int a = 42; }", encoding="utf-8")
        self.manager.register_project("proj-a", proj_a)
        self.manager.index_project("proj-a")

        # Setup Project B
        proj_b = self.base_path / "ProjectB"
        proj_b.mkdir()
        (proj_b / "SecretLogicB.cs").write_text("public class SecretLogicB { int b = 99; }", encoding="utf-8")
        self.manager.register_project("proj-b", proj_b)
        self.manager.index_project("proj-b")

        # Query Project A for SecretLogicB
        context_a = self.manager.retrieve_context("proj-a", "SecretLogicB")
        for src in context_a.sources:
            self.assertNotEqual(src.rel_path, "SecretLogicB.cs")
            self.assertNotIn("SecretLogicB", src.content)

        # Query Project B for SecretLogicA
        context_b = self.manager.retrieve_context("proj-b", "SecretLogicA")
        for src in context_b.sources:
            self.assertNotEqual(src.rel_path, "SecretLogicA.cs")
            self.assertNotIn("SecretLogicA", src.content)

        # Non-existent project raises ProjectNotFoundError
        with self.assertRaises(ProjectNotFoundError):
            self.manager.retrieve_context("unknown-project-x", "SecretLogicA")

    def test_acceptance_6_excluded_secrets_never_included(self) -> None:
        """Acceptance Test 6: Verify excluded secrets, tokens and keys are NEVER indexed or retrieved."""
        project_dir = self.base_path / "UnityProject"
        self._create_sample_unity_project(project_dir)
        self.manager.register_project("unity-proj-1", project_dir)
        self.manager.index_project("unity-proj-1")

        # Search for secret terms that exist in .env and api_credentials.json
        context = self.manager.retrieve_context("unity-proj-1", "API_SECRET_KEY super_secret_production_key_12345")
        self.assertEqual(len(context.sources), 0)
        self.assertNotIn("super_secret_production_key_12345", context.formatted_context)

        # Search for private key backup
        key_context = self.manager.retrieve_context("unity-proj-1", "RSA_SECRET_987654_DO_NOT_EXPOSE")
        self.assertEqual(len(key_context.sources), 0)
        self.assertNotIn("RSA_SECRET_987654_DO_NOT_EXPOSE", key_context.formatted_context)
        self.assertNotIn("id_rsa_backup.key", [s.rel_path for s in key_context.sources])

        # Search for Library cache
        lib_context = self.manager.retrieve_context("unity-proj-1", "SUPER_EXCLUSIVE_LIBRARY_CACHE_STRING")
        self.assertEqual(len(lib_context.sources), 0)
        self.assertNotIn("artifact.cache", [s.rel_path for s in lib_context.sources])

    def test_acceptance_7_predictable_behavior_when_stale_or_empty(self) -> None:
        """Acceptance Test 7: Predictable behavior when index is missing, empty or deleted."""
        empty_dir = self.base_path / "EmptyProject"
        empty_dir.mkdir()
        self.manager.register_project("empty-proj", empty_dir)

        # Retrieve on empty project before indexing returns clean empty context, no crash
        context = self.manager.retrieve_context("empty-proj", "PlayerController")
        self.assertEqual(len(context.sources), 0)
        self.assertEqual(context.formatted_context, "")

        # Index empty project
        report = self.manager.index_project("empty-proj")
        self.assertEqual(report.indexed_files, 0)
        self.assertEqual(report.total_chunks, 0)

        # Add a file, verify is_stale detects it
        (empty_dir / "NewScript.cs").write_text("class NewScript {}", encoding="utf-8")
        self.assertTrue(self.manager.is_stale("empty-proj"))


if __name__ == "__main__":
    unittest.main()
