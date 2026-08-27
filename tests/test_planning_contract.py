from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLANNING = ROOT / "contracts" / "planning"
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from planning_contract import (  # noqa: E402
    validate_json_schema,
    validate_planning_contract,
    validate_sequence_semantics,
)


class PlanningContractTests(unittest.TestCase):
    def test_normative_contract_passes_schema_and_semantic_validation(self) -> None:
        self.assertEqual(validate_planning_contract(ROOT), [])

    def test_execution_sequence_has_one_consistent_public_frontier(self) -> None:
        sequence = json.loads(
            (PLANNING / "v3-execution-sequence.json").read_text(encoding="utf-8")
        )
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
        sequence = json.loads(
            (PLANNING / "v3-execution-sequence.json").read_text(encoding="utf-8")
        )
        roadmap = (ROOT / "docs" / "v3-hybrid-visual-multiplatform-roadmap.md").read_text(
            encoding="utf-8"
        )
        begin = "<!-- BEGIN NORMATIVE TASK STATE TABLE -->"
        end = "<!-- END NORMATIVE TASK STATE TABLE -->"
        self.assertEqual(roadmap.count(begin), 1)
        self.assertEqual(roadmap.count(end), 1)
        table = roadmap.split(begin, 1)[1].split(end, 1)[0]
        lines = [line.strip() for line in table.splitlines() if line.strip()]
        self.assertEqual(
            lines[:2],
            [
                "| Task ID | Objective | Batch | State | Notes |",
                "| --- | --- | --- | --- | --- |",
            ],
        )

        # Only the explicitly delimited ID, Batch, and State cells are normative.
        # Objective and Notes remain human prose and are deliberately not parsed.
        roadmap_tasks: dict[str, dict[str, str]] = {}
        for line in lines[2:]:
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            self.assertEqual(len(cells), 5, line)
            task_cell, _, batch_cell, state_cell, _ = cells
            self.assertTrue(task_cell.startswith("`") and task_cell.endswith("`"), line)
            self.assertTrue(batch_cell.startswith("`") and batch_cell.endswith("`"), line)
            self.assertTrue(state_cell.startswith("`") and state_cell.endswith("`"), line)
            task_id = task_cell[1:-1]
            self.assertNotIn(task_id, roadmap_tasks)
            roadmap_tasks[task_id] = {
                "batch": batch_cell[1:-1],
                "status": state_cell[1:-1],
            }

        contract_tasks = {
            item["id"]: {"batch": item["batch"], "status": item["status"]}
            for item in sequence["tasks"]
        }
        self.assertEqual(roadmap_tasks, contract_tasks)

        frontier_lines = [
            line for line in roadmap.splitlines() if line.startswith("Current frontier: ")
        ]
        self.assertEqual(len(frontier_lines), 1)
        frontier_text = frontier_lines[0].removeprefix("Current frontier: ")
        self.assertTrue(frontier_text.endswith("."))
        frontier_cells = [cell.strip() for cell in frontier_text[:-1].split(",")]
        self.assertTrue(
            all(cell.startswith("`") and cell.endswith("`") for cell in frontier_cells)
        )
        self.assertEqual(
            [cell[1:-1] for cell in frontier_cells], sequence["current_frontier"]
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
        sequence = json.loads(
            (PLANNING / "v3-execution-sequence.json").read_text(encoding="utf-8")
        )
        cyclic = deepcopy(sequence)
        tasks = {item["id"]: item for item in cyclic["tasks"]}
        tasks["BRG-014"]["depends_on"] = ["BRG-019"]

        errors = validate_sequence_semantics(cyclic, ROOT)

        self.assertTrue(any("task dependency cycle" in error for error in errors))

    def test_semantic_guard_rejects_task_dependency_from_unreachable_batch(self) -> None:
        sequence = json.loads(
            (PLANNING / "v3-execution-sequence.json").read_text(encoding="utf-8")
        )
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
        sequence = json.loads(
            (PLANNING / "v3-execution-sequence.json").read_text(encoding="utf-8")
        )
        compatible = deepcopy(sequence)
        tasks = {item["id"]: item for item in compatible["tasks"]}
        tasks["BRG-003"]["depends_on"].append("BRG-017")

        self.assertEqual(validate_sequence_semantics(compatible, ROOT), [])


if __name__ == "__main__":
    unittest.main()
