from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
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


if __name__ == "__main__":
    unittest.main()
