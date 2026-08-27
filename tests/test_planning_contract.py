from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLANNING = ROOT / "contracts" / "planning"
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from planning_contract import (  # noqa: E402
    validate_json_schema,
    validate_planning_contract,
    validate_roadmap_parity,
    validate_sequence_semantics,
)


def load_sequence() -> dict[str, Any]:
    return json.loads(
        (PLANNING / "v3-execution-sequence.json").read_text(encoding="utf-8")
    )


def load_roadmap() -> str:
    return (ROOT / "docs" / "v3-hybrid-visual-multiplatform-roadmap.md").read_text(
        encoding="utf-8"
    )


def load_receipt_schema() -> dict[str, Any]:
    return json.loads(
        (PLANNING / "external-readback-receipt.schema.json").read_text(
            encoding="utf-8"
        )
    )


def single_task_sequence(
    evidence: list[str],
    *,
    external_readback_required: bool = False,
    external_readback_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    task: dict[str, Any] = {
        "id": "EXT-001",
        "batch": "B01",
        "title": "External test",
        "status": "complete",
        "depends_on": [],
        "evidence": evidence,
        "external_readback_required": external_readback_required,
    }
    if external_readback_required:
        task["external_readback_contract"] = external_readback_contract or {
            "contract_id": "ext-001-test-v1",
            "kind": "test_readback_v1",
            "minimum_sessions": 1,
            "fixture_required": False,
        }
    elif external_readback_contract is not None:
        task["external_readback_contract"] = external_readback_contract
    return {
        "contract_version": 1,
        "planning_status": "test",
        "updated_at": "2026-08-27",
        "current_frontier": [],
        "batches": [
            {"id": "B01", "title": "Test", "depends_on": [], "tasks": ["EXT-001"]}
        ],
        "tasks": [task],
    }


def valid_external_receipt(
    task_id: str = "EXT-001",
    *,
    contract_id: str = "ext-001-test-v1",
    kind: str = "test_readback_v1",
    session_count: int = 1,
    fixture_identity: str | None = None,
) -> dict[str, Any]:
    return {
        "$schema": "../../external-readback-receipt.schema.json",
        "receipt_type": "external-readback",
        "receipt_version": 1,
        "task_id": task_id,
        "contract_id": contract_id,
        "kind": kind,
        "source": {"commit": "a" * 40, "artifact_sha256": "b" * 64},
        "consumer": {
            "name": "fixture-client",
            "version": "1.0",
            "artifact_sha256": "c" * 64,
            "server_profile": "working",
            "allowlist_sha256": "d" * 64,
        },
        "schema_identity": {"version": "1", "artifact_sha256": "e" * 64},
        "environment": {
            "os": "windows-11",
            "python": "3.11.9",
            "protocol": "mcp-2025-11-25",
        },
        "fixture_identity": fixture_identity or "sha256:" + "f" * 64,
        "readback": {
            "session_count": session_count,
            "lifecycle_sha256": "1" * 64,
            "redaction_manifest_sha256": "4" * 64,
            "result_sha256": "2" * 64,
            "sanitized": True,
            "passed": True,
        },
        "secret_scan": {
            "scanner": "ai-dememory secret-scan",
            "result_sha256": "3" * 64,
            "passed": True,
        },
        "details": [{"name": "task-contract", "artifact_sha256": "5" * 64}],
    }


class PlanningContractTests(unittest.TestCase):
    def test_normative_contract_passes_schema_and_semantic_validation(self) -> None:
        self.assertEqual(validate_planning_contract(ROOT), [])

    def test_execution_sequence_has_one_consistent_public_frontier(self) -> None:
        sequence = load_sequence()
        tasks = {item["id"]: item for item in sequence["tasks"]}
        batches = {item["id"]: item for item in sequence["batches"]}

        self.assertEqual(sequence["contract_version"], 1)
        self.assertEqual(len(tasks), len(sequence["tasks"]))
        self.assertEqual(len(batches), len(sequence["batches"]))
        for task in tasks.values():
            self.assertIn(task["batch"], batches)
            self.assertIn(task["id"], batches[task["batch"]]["tasks"])
            self.assertTrue(set(task["depends_on"]).issubset(tasks))
        for batch in batches.values():
            self.assertTrue(set(batch["depends_on"]).issubset(batches))
            self.assertTrue(set(batch["tasks"]).issubset(tasks))

        frontier = sequence["current_frontier"]
        self.assertEqual(frontier, ["BRG-003"])
        self.assertTrue(all(tasks[item]["status"] == "in_progress" for item in frontier))
        self.assertEqual(tasks["BRG-017"]["status"], "complete")
        self.assertTrue(tasks["BRG-017"]["evidence"])
        self.assertEqual(batches["B04c"]["depends_on"], ["B04b"])
        self.assertEqual(tasks["BRG-019"]["batch"], "B04c")
        self.assertEqual(tasks["BRG-019"]["depends_on"], ["BRG-003", "BRG-017"])
        self.assertEqual(batches["B05a"]["depends_on"], ["B04c"])
        self.assertEqual(batches["B05a"]["tasks"], ["MIG-001"])
        self.assertEqual(batches["B05b"]["depends_on"], ["B05a"])
        self.assertEqual(batches["B05b"]["tasks"], ["RET-001"])
        self.assertEqual(batches["B06"]["depends_on"], ["B05b"])
        self.assertEqual(tasks["MIG-001"]["depends_on"], ["BRG-003", "BRG-017", "BRG-019"])
        self.assertEqual(tasks["RET-001"]["depends_on"], ["MIG-001"])
        self.assertEqual(tasks["GATE-B"]["depends_on"], ["MIG-001", "RET-001"])
        self.assertEqual(tasks["GATE-B"]["status"], "blocked")
        self.assertEqual(tasks["GATE-B"]["evidence"], [])
        self.assertTrue(tasks["GATE-B"]["external_readback_required"])
        self.assertEqual(batches["B06a"]["depends_on"], ["B06"])
        self.assertEqual(batches["B06a"]["tasks"], ["GRF-001"])
        self.assertEqual(batches["B06b"]["depends_on"], ["B06a"])
        self.assertEqual(batches["B06b"]["tasks"], ["RET-002"])
        self.assertEqual(tasks["GRF-001"]["depends_on"], ["GATE-B"])
        self.assertEqual(tasks["RET-002"]["depends_on"], ["GRF-001"])
        self.assertEqual(batches["B07a"]["depends_on"], ["B06"])
        self.assertEqual(batches["B07a"]["tasks"], ["OBS-001"])
        self.assertEqual(batches["B07b"]["depends_on"], ["B07a"])
        self.assertEqual(batches["B07b"]["tasks"], ["OUT-001"])
        self.assertEqual(batches["B08a"]["depends_on"], ["B07b"])
        self.assertEqual(batches["B08a"]["tasks"], ["CON-001"])
        self.assertEqual(batches["B08b"]["depends_on"], ["B08a"])
        self.assertEqual(batches["B08b"]["tasks"], ["MEM-001"])
        self.assertEqual(tasks["OBS-001"]["batch"], "B07a")
        self.assertEqual(tasks["OBS-001"]["depends_on"], ["GATE-B"])
        self.assertEqual(tasks["OUT-001"]["batch"], "B07b")
        self.assertEqual(tasks["OUT-001"]["depends_on"], ["OBS-001"])
        self.assertEqual(tasks["CON-001"]["batch"], "B08a")
        self.assertEqual(tasks["CON-001"]["depends_on"], ["OUT-001"])
        self.assertEqual(tasks["MEM-001"]["batch"], "B08b")
        self.assertEqual(tasks["MEM-001"]["depends_on"], ["CON-001"])
        future_tasks = {
            task_id: task for task_id, task in tasks.items() if task["status"] == "future"
        }
        self.assertTrue(
            {
                "GRF-001",
                "RET-002",
                "OBS-001",
                "OUT-001",
                "CON-001",
                "MEM-001",
            }.issubset(future_tasks)
        )
        self.assertIn("ONB-001", future_tasks)
        self.assertEqual(
            {
                task_id: task["evidence"]
                for task_id, task in future_tasks.items()
                if task["evidence"]
            },
            {},
        )
        self.assertTrue(
            all(
                tasks[item]["status"] == "pending" and tasks[item]["evidence"] == []
                for item in ("BRG-019", "MIG-001", "RET-001")
            )
        )
        self.assertEqual(
            {
                item: tasks[item]["external_readback_required"]
                for item in (
                    "RET-001",
                    "GRF-001",
                    "RET-002",
                    "OBS-001",
                    "OUT-001",
                    "CON-001",
                    "MEM-001",
                )
            },
            {
                "RET-001": False,
                "GRF-001": True,
                "RET-002": True,
                "OBS-001": True,
                "OUT-001": True,
                "CON-001": False,
                "MEM-001": True,
            },
        )
        self.assertEqual(batches["B20"]["depends_on"], ["B06"])
        self.assertEqual(tasks["ONB-001"]["depends_on"], ["GATE-B"])
        self.assertTrue(tasks["ONB-001"]["external_readback_required"])
        for task in tasks.values():
            if task["external_readback_required"]:
                self.assertEqual(
                    set(task["external_readback_contract"]),
                    {
                        "contract_id",
                        "kind",
                        "minimum_sessions",
                        "fixture_required",
                    },
                )
            else:
                self.assertNotIn("external_readback_contract", task)

    def test_normative_roadmap_task_state_table_matches_sequence(self) -> None:
        self.assertEqual(validate_roadmap_parity(load_sequence(), load_roadmap()), [])

    def test_roadmap_parity_accepts_escaped_pipe_in_prose(self) -> None:
        roadmap = load_roadmap().replace(
            "Sole current frontier.", "Sole current \\| frontier."
        )
        self.assertIn("\\|", roadmap)

        self.assertEqual(validate_roadmap_parity(load_sequence(), roadmap), [])

    def test_roadmap_parity_rejects_sequence_state_drift(self) -> None:
        sequence = load_sequence()
        tasks = {item["id"]: item for item in sequence["tasks"]}
        tasks["RET-001"]["status"] = "future"

        errors = validate_roadmap_parity(sequence, load_roadmap())

        self.assertIn(
            "roadmap task RET-001 status mismatch: roadmap 'pending', sequence 'future'",
            errors,
        )

    def test_public_execution_ledger_starts_empty(self) -> None:
        ledger = json.loads(
            (PLANNING / "v3-execution-ledger.json").read_text(encoding="utf-8")
        )

        self.assertEqual(ledger["entries"], [])

    def test_schema_rejects_unknown_task_fields(self) -> None:
        schema = json.loads(
            (PLANNING / "v3-execution-sequence.schema.json").read_text(encoding="utf-8")
        )
        sequence = json.loads(
            (PLANNING / "v3-execution-sequence.json").read_text(encoding="utf-8")
        )
        sequence["tasks"][0]["unreviewed_override"] = True

        errors = validate_json_schema(sequence, schema)

        self.assertTrue(any("unexpected property 'unreviewed_override'" in error for error in errors))

    def test_semantic_guard_rejects_dependency_cycles(self) -> None:
        sequence = load_sequence()
        cyclic = deepcopy(sequence)
        tasks = {item["id"]: item for item in cyclic["tasks"]}
        tasks["BRG-014"]["depends_on"] = ["BRG-019"]

        errors = validate_sequence_semantics(cyclic, ROOT)

        self.assertTrue(any("task dependency cycle" in error for error in errors))

    def test_semantic_guard_rejects_task_dependency_from_unreachable_batch(self) -> None:
        sequence = load_sequence()
        incompatible = deepcopy(sequence)
        tasks = {item["id"]: item for item in incompatible["tasks"]}
        tasks["RET-002"]["depends_on"].append("OBS-001")

        errors = validate_sequence_semantics(incompatible, ROOT)

        self.assertIn(
            "task RET-002 in batch B06b depends on task OBS-001 "
            "in unreachable batch B07a",
            errors,
        )

    def test_semantic_guard_allows_task_dependency_within_same_batch(self) -> None:
        sequence = load_sequence()
        compatible = deepcopy(sequence)
        tasks = {item["id"]: item for item in compatible["tasks"]}
        tasks["BRG-003"]["depends_on"].append("BRG-017")

        self.assertEqual(validate_sequence_semantics(compatible, ROOT), [])

    def test_semantic_guard_rejects_in_progress_task_outside_frontier(self) -> None:
        sequence = load_sequence()
        tasks = {item["id"]: item for item in sequence["tasks"]}
        tasks["BRG-019"]["status"] = "in_progress"

        errors = validate_sequence_semantics(sequence, ROOT)

        self.assertIn(
            "current_frontier must exactly match all in_progress tasks: "
            "missing ['BRG-019'], non-in_progress []",
            errors,
        )

    def test_semantic_guard_rejects_complete_task_without_evidence(self) -> None:
        sequence = load_sequence()
        tasks = {item["id"]: item for item in sequence["tasks"]}
        tasks["BRG-003"]["status"] = "complete"
        tasks["BRG-003"]["evidence"] = []
        sequence["current_frontier"] = []

        errors = validate_sequence_semantics(sequence, ROOT)

        self.assertIn("complete task BRG-003 must have non-empty evidence", errors)

    def test_semantic_guard_rejects_complete_task_with_incomplete_dependency(self) -> None:
        sequence = load_sequence()
        tasks = {item["id"]: item for item in sequence["tasks"]}
        tasks["BRG-019"]["status"] = "complete"
        tasks["BRG-019"]["evidence"] = ["PLAN.md"]

        errors = validate_sequence_semantics(sequence, ROOT)

        self.assertIn(
            "complete task BRG-019 has incomplete dependency BRG-003", errors
        )

    def test_semantic_guard_rejects_future_task_with_evidence(self) -> None:
        sequence = load_sequence()
        tasks = {item["id"]: item for item in sequence["tasks"]}
        tasks["GRF-001"]["evidence"] = ["PLAN.md"]

        errors = validate_sequence_semantics(sequence, ROOT)

        self.assertIn("future task GRF-001 must have empty evidence", errors)

    def test_semantic_guard_rejects_empty_evidence_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            errors = validate_sequence_semantics(
                single_task_sequence([""]), Path(directory)
            )

        self.assertIn(
            "task EXT-001 has empty or whitespace-padded evidence path ''", errors
        )

    def test_semantic_guard_rejects_windows_absolute_and_backslash_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            absolute_errors = validate_sequence_semantics(
                single_task_sequence(["C:/temp/receipt.json"]), Path(directory)
            )
            backslash_errors = validate_sequence_semantics(
                single_task_sequence(["contracts\\planning\\receipt.json"]),
                Path(directory),
            )

        self.assertIn(
            "task EXT-001 has absolute evidence path 'C:/temp/receipt.json'",
            absolute_errors,
        )
        self.assertIn(
            "task EXT-001 evidence path must use forward slashes: "
            "'contracts\\\\planning\\\\receipt.json'",
            backslash_errors,
        )

    def test_semantic_guard_rejects_ntfs_stream_and_git_metadata_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ads_errors = validate_sequence_semantics(
                single_task_sequence(["evidence/receipt:readback.json"]), root
            )
            git_errors = validate_sequence_semantics(
                single_task_sequence([".git/config"]), root
            )
            reserved_errors = validate_sequence_semantics(
                single_task_sequence(["evidence/CON.json"]), root
            )

        self.assertIn(
            "task EXT-001 evidence path must not contain ':' or an alternate stream: "
            "'evidence/receipt:readback.json'",
            ads_errors,
        )
        self.assertIn(
            "task EXT-001 evidence path cannot use .git metadata: '.git/config'",
            git_errors,
        )
        self.assertIn(
            "task EXT-001 evidence path is not portable on Windows: "
            "'evidence/CON.json'",
            reserved_errors,
        )

    def test_semantic_guard_rejects_traversal_and_non_normalized_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "PLAN.md").write_text("fixture", encoding="utf-8")
            traversal_errors = validate_sequence_semantics(
                single_task_sequence(["contracts/../PLAN.md"]), root
            )
            normalized_errors = validate_sequence_semantics(
                single_task_sequence(["./PLAN.md"]), root
            )

        self.assertIn(
            "task EXT-001 has traversal evidence path 'contracts/../PLAN.md'",
            traversal_errors,
        )
        self.assertIn(
            "task EXT-001 has non-normalized evidence path './PLAN.md'",
            normalized_errors,
        )

    def test_semantic_guard_rejects_wrong_case_portably(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "PLAN.md").write_text("fixture", encoding="utf-8")

            errors = validate_sequence_semantics(
                single_task_sequence(["plan.md"]), root
            )

        self.assertIn(
            "task EXT-001 evidence path component 'plan.md' does not match "
            "filesystem spelling 'PLAN.md'",
            errors,
        )

    def test_semantic_guard_rejects_directory_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = "contracts/planning/evidence/EXT-001"
            (root / Path(*PurePosixPath(evidence).parts)).mkdir(parents=True)

            errors = validate_sequence_semantics(
                single_task_sequence([evidence]), root
            )

        self.assertIn(
            "task EXT-001 evidence path is not a regular file: " + evidence,
            errors,
        )

    def test_semantic_guard_rejects_symlink_escape_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            outside_file = Path(outside) / "receipt.json"
            outside_file.write_text("{}", encoding="utf-8")
            evidence = "contracts/planning/evidence/EXT-001/receipt.json"
            link = root / Path(*PurePosixPath(evidence).parts)
            link.parent.mkdir(parents=True)
            try:
                link.symlink_to(outside_file)
            except OSError as exc:
                self.skipTest(f"file symlinks are unavailable: {exc}")

            errors = validate_sequence_semantics(
                single_task_sequence([evidence]), root
            )

        self.assertIn(
            f"task EXT-001 evidence path escapes repository root: {evidence!r}",
            errors,
        )

    def test_external_readback_rejects_arbitrary_file_substitution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "PLAN.md").write_text("not a receipt", encoding="utf-8")

            errors = validate_sequence_semantics(
                single_task_sequence(
                    ["PLAN.md"], external_readback_required=True
                ),
                root,
                receipt_schema=load_receipt_schema(),
            )

        self.assertIn(
            "complete task EXT-001 requires a valid task-bound external-readback "
            "receipt under contracts/planning/evidence/EXT-001/",
            errors,
        )

    def test_external_readback_descriptor_is_required_if_and_only_if_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            missing = single_task_sequence([], external_readback_required=True)
            missing["tasks"][0].pop("external_readback_contract")
            missing_errors = validate_sequence_semantics(missing, root)
            forbidden_errors = validate_sequence_semantics(
                single_task_sequence(
                    ["PLAN.md"],
                    external_readback_contract={
                        "contract_id": "unexpected-v1",
                        "kind": "unexpected_v1",
                        "minimum_sessions": 1,
                        "fixture_required": False,
                    },
                ),
                root,
            )

        self.assertIn(
            "task EXT-001 requires an external_readback_contract descriptor",
            missing_errors,
        )
        self.assertIn(
            "task EXT-001 must not define external_readback_contract when "
            "external_readback_required is false",
            forbidden_errors,
        )

    def test_external_readback_rejects_receipt_for_wrong_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = "contracts/planning/evidence/EXT-001/readback.json"
            receipt_path = root / Path(*PurePosixPath(evidence).parts)
            receipt_path.parent.mkdir(parents=True)
            receipt_path.write_text(
                json.dumps(valid_external_receipt("OTHER-001")), encoding="utf-8"
            )

            errors = validate_sequence_semantics(
                single_task_sequence([evidence], external_readback_required=True),
                root,
                receipt_schema=load_receipt_schema(),
            )

        self.assertIn(
            "task EXT-001 external receipt "
            "contracts/planning/evidence/EXT-001/readback.json: "
            "task_id 'OTHER-001' does not match 'EXT-001'",
            errors,
        )

    def test_external_readback_rejects_contract_or_kind_substitution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = "contracts/planning/evidence/EXT-001/readback.json"
            receipt_path = root / Path(*PurePosixPath(evidence).parts)
            receipt_path.parent.mkdir(parents=True)
            receipt_path.write_text(
                json.dumps(
                    valid_external_receipt(
                        contract_id="other-contract-v1", kind="other_kind_v1"
                    )
                ),
                encoding="utf-8",
            )

            errors = validate_sequence_semantics(
                single_task_sequence([evidence], external_readback_required=True),
                root,
                receipt_schema=load_receipt_schema(),
            )

        prefix = (
            "task EXT-001 external receipt "
            "contracts/planning/evidence/EXT-001/readback.json: "
        )
        self.assertIn(
            prefix + "contract_id 'other-contract-v1' does not match 'ext-001-test-v1'",
            errors,
        )
        self.assertIn(
            prefix + "kind 'other_kind_v1' does not match 'test_readback_v1'",
            errors,
        )

    def test_external_readback_enforces_sessions_and_fixture_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = "contracts/planning/evidence/EXT-001/readback.json"
            receipt_path = root / Path(*PurePosixPath(evidence).parts)
            receipt_path.parent.mkdir(parents=True)
            receipt_path.write_text(
                json.dumps(
                    valid_external_receipt(
                        session_count=1, fixture_identity="not-applicable"
                    )
                ),
                encoding="utf-8",
            )
            contract = {
                "contract_id": "ext-001-test-v1",
                "kind": "test_readback_v1",
                "minimum_sessions": 2,
                "fixture_required": True,
            }

            errors = validate_sequence_semantics(
                single_task_sequence(
                    [evidence],
                    external_readback_required=True,
                    external_readback_contract=contract,
                ),
                root,
                receipt_schema=load_receipt_schema(),
            )

        prefix = (
            "task EXT-001 external receipt "
            "contracts/planning/evidence/EXT-001/readback.json: "
        )
        self.assertIn(prefix + "session_count 1 is below required minimum 2", errors)
        self.assertIn(
            prefix + "fixture_identity must be a SHA-256 digest", errors
        )

    def test_external_readback_accepts_valid_contained_typed_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = "contracts/planning/evidence/EXT-001/readback.json"
            receipt_path = root / Path(*PurePosixPath(evidence).parts)
            receipt_path.parent.mkdir(parents=True)
            receipt_path.write_text(
                json.dumps(valid_external_receipt()), encoding="utf-8"
            )

            errors = validate_sequence_semantics(
                single_task_sequence([evidence], external_readback_required=True),
                root,
                receipt_schema=load_receipt_schema(),
            )

        self.assertEqual(errors, [])

    def test_external_readback_requires_passing_secret_scan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = "contracts/planning/evidence/EXT-001/readback.json"
            receipt_path = root / Path(*PurePosixPath(evidence).parts)
            receipt_path.parent.mkdir(parents=True)
            receipt = valid_external_receipt()
            receipt["secret_scan"]["passed"] = False
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

            errors = validate_sequence_semantics(
                single_task_sequence([evidence], external_readback_required=True),
                root,
                receipt_schema=load_receipt_schema(),
            )

        self.assertIn(
            "task EXT-001 external receipt "
            "contracts/planning/evidence/EXT-001/readback.json: "
            "$.secret_scan.passed: value is not in the allowed enum",
            errors,
        )

    def test_external_readback_rejects_duplicate_json_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = "contracts/planning/evidence/EXT-001/readback.json"
            receipt_path = root / Path(*PurePosixPath(evidence).parts)
            receipt_path.parent.mkdir(parents=True)
            encoded = json.dumps(valid_external_receipt())
            encoded = encoded.replace(
                '"task_id": "EXT-001"',
                '"task_id": "EXT-001", "task_id": "EXT-001"',
                1,
            )
            receipt_path.write_text(encoded, encoding="utf-8")

            errors = validate_sequence_semantics(
                single_task_sequence([evidence], external_readback_required=True),
                root,
                receipt_schema=load_receipt_schema(),
            )

        self.assertIn(
            "task EXT-001 external receipt "
            "contracts/planning/evidence/EXT-001/readback.json: "
            "contracts/planning/evidence/EXT-001/readback.json: "
            "duplicate JSON key 'task_id'",
            errors,
        )

    def test_external_readback_rejects_overlong_integer_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = "contracts/planning/evidence/EXT-001/readback.json"
            receipt_path = root / Path(*PurePosixPath(evidence).parts)
            receipt_path.parent.mkdir(parents=True)
            encoded = json.dumps(valid_external_receipt()).replace(
                '"receipt_version": 1', '"receipt_version": ' + "9" * 5000, 1
            )
            receipt_path.write_text(encoded, encoding="utf-8")

            errors = validate_sequence_semantics(
                single_task_sequence([evidence], external_readback_required=True),
                root,
                receipt_schema=load_receipt_schema(),
            )

        self.assertTrue(
            any(
                "contracts/planning/evidence/EXT-001/readback.json: "
                "invalid JSON value" in error
                for error in errors
            )
        )

    def test_external_readback_rejects_deep_json_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = "contracts/planning/evidence/EXT-001/readback.json"
            receipt_path = root / Path(*PurePosixPath(evidence).parts)
            receipt_path.parent.mkdir(parents=True)
            receipt_path.write_text(
                "[" * 20000 + "0" + "]" * 20000, encoding="utf-8"
            )

            errors = validate_sequence_semantics(
                single_task_sequence([evidence], external_readback_required=True),
                root,
                receipt_schema=load_receipt_schema(),
            )

        self.assertIn(
            "task EXT-001 external receipt "
            "contracts/planning/evidence/EXT-001/readback.json: "
            "contracts/planning/evidence/EXT-001/readback.json: invalid JSON nesting",
            errors,
        )

    def test_external_readback_details_are_identity_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = "contracts/planning/evidence/EXT-001/readback.json"
            receipt_path = root / Path(*PurePosixPath(evidence).parts)
            receipt_path.parent.mkdir(parents=True)
            receipt = valid_external_receipt()
            receipt["details"] = {"raw_transcript": "not allowed"}
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

            errors = validate_sequence_semantics(
                single_task_sequence([evidence], external_readback_required=True),
                root,
                receipt_schema=load_receipt_schema(),
            )

        self.assertIn(
            "task EXT-001 external receipt "
            "contracts/planning/evidence/EXT-001/readback.json: "
            "$.details: expected array",
            errors,
        )

    def test_active_task_requires_all_transitive_predecessor_batches_complete(self) -> None:
        sequence = load_sequence()
        tasks = {item["id"]: item for item in sequence["tasks"]}
        tasks["BRG-019"]["status"] = "in_progress"
        tasks["BRG-019"]["depends_on"] = []
        sequence["current_frontier"] = ["BRG-003", "BRG-019"]

        errors = validate_sequence_semantics(sequence, ROOT)

        self.assertIn(
            "task BRG-019 cannot be in_progress until predecessor batch "
            "B04b task BRG-003 is complete",
            errors,
        )

    def test_malformed_nested_sequence_stops_before_semantic_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            planning = root / "contracts" / "planning"
            planning.mkdir(parents=True)
            for name in (
                "v3-execution-sequence.json",
                "v3-execution-sequence.schema.json",
                "v3-execution-ledger.json",
                "external-readback-receipt.schema.json",
            ):
                shutil.copy2(PLANNING / name, planning / name)
            sequence = json.loads(
                (planning / "v3-execution-sequence.json").read_text(encoding="utf-8")
            )
            sequence["tasks"][0]["depends_on"] = {"malformed": True}
            (planning / "v3-execution-sequence.json").write_text(
                json.dumps(sequence), encoding="utf-8"
            )

            with patch("planning_contract.validate_sequence_semantics") as semantic:
                errors = validate_planning_contract(root)

        semantic.assert_not_called()
        self.assertIn("$.tasks[0].depends_on: expected array", errors)

    def test_sequence_rejects_overlong_integer_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            planning = root / "contracts" / "planning"
            planning.mkdir(parents=True)
            for name in (
                "v3-execution-sequence.json",
                "v3-execution-sequence.schema.json",
                "v3-execution-ledger.json",
                "external-readback-receipt.schema.json",
            ):
                shutil.copy2(PLANNING / name, planning / name)
            sequence_path = planning / "v3-execution-sequence.json"
            encoded = sequence_path.read_text(encoding="utf-8").replace(
                '"contract_version": 1', '"contract_version": ' + "9" * 5000, 1
            )
            sequence_path.write_text(encoded, encoding="utf-8")

            errors = validate_planning_contract(root)

        self.assertTrue(
            any("invalid JSON value" in error for error in errors), errors
        )


if __name__ == "__main__":
    unittest.main()
