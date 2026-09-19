from __future__ import annotations

from unittest.mock import patch

from ai_dememory.harness import recall_hook
from ai_dememory.search import SearchIndex, _canonical_snippet, _query_tokens
from ai_dememory.vault import Vault

from tests_v3.test_core import V3TestCase


class SearchQualityTests(V3TestCase):
    def _vault(self) -> Vault:
        return Vault.create(self.root / "vault")

    def test_title_match_outweighs_the_same_body_match(self) -> None:
        vault = self._vault()
        vault.remember("Unrelated body text.", "oxide")
        vault.remember("oxide", "Unrelated title")

        hits = SearchIndex(vault).search("oxide", importance_weight=0)

        self.assertEqual([hit.title for hit in hits], ["oxide", "Unrelated title"])

    def test_filters_filler_and_deduplicates_before_the_term_limit(self) -> None:
        query = "the " * 25 + "Deployment deployment DEPLOYMENT"

        self.assertEqual(_query_tokens(query), ["Deployment"])
        self.assertEqual(_query_tokens("no NO no deploy"), ["no", "deploy"])

    def test_snippet_centers_on_a_whole_token_match(self) -> None:
        content = "reconfiguration " + ("filler " * 40) + "config is the selected value."

        snippet = _canonical_snippet(content, ["config"])

        self.assertIn("config is the selected value", snippet)
        self.assertNotIn("reconfiguration", snippet)

    def test_no_informative_or_matching_term_returns_empty_results(self) -> None:
        vault = self._vault()
        vault.remember("The selected deployment is local.", "Deployment")
        index = SearchIndex(vault)

        self.assertEqual(index.search("the and por"), [])
        self.assertEqual(index.search("absent-term"), [])

    def test_importance_reorders_all_eligible_lexical_matches_before_limit(self) -> None:
        vault = self._vault()
        vault.remember("target phrase", "Normal")
        vault.remember("target phrase padding", "Important", importance="high")
        index = SearchIndex(vault)

        baseline = index.search("target phrase", limit=1, importance_weight=0)
        boosted = index.search("target phrase", limit=1, importance_weight=0.25)

        self.assertEqual(baseline[0].title, "Normal")
        self.assertEqual(boosted[0].title, "Important")
        self.assertEqual(boosted[0].details["importance"], "high")
        self.assertEqual(boosted[0].details["importance_origin"], "user")
        self.assertTrue(boosted[0].details["importance_applied"])
        self.assertEqual(boosted[0].details["importance_weight"], 0.25)
        self.assertEqual(boosted[0].details["confidence_status"], "unassessed")
        self.assertEqual(boosted[0].details["matching_terms"], ["target", "phrase"])

    def test_host_importance_is_visible_but_neutral_until_user_control_exists(self) -> None:
        vault = self._vault()
        vault.remember("target phrase", "Normal")
        vault._remember(
            "target phrase padding", "Host suggestion", importance="high", importance_origin="host"
        )
        index = SearchIndex(vault)

        hits = index.search("target phrase", limit=1, importance_weight=0.25)

        self.assertEqual(hits[0].title, "Normal")
        all_hits = index.search("target phrase", importance_weight=0.25)
        host_hit = next(hit for hit in all_hits if hit.title == "Host suggestion")
        self.assertEqual(host_hit.details["importance"], "high")
        self.assertFalse(host_hit.details["importance_applied"])

    def test_each_hit_reports_its_own_importance_origin_application(self) -> None:
        vault = self._vault()
        vault.remember("target phrase padding", "User high", importance="high")
        vault._remember(
            "target phrase padding", "Host high", importance="high", importance_origin="host"
        )

        hits = SearchIndex(vault).search("target phrase", importance_weight=0.25)
        applied = {hit.title: hit.details["importance_applied"] for hit in hits}

        self.assertTrue(applied["User high"])
        self.assertFalse(applied["Host high"])

    def test_scope_and_inactive_filters_apply_before_weighted_ranking(self) -> None:
        vault = self._vault()
        vault._remember("project target", "Alpha", scope="project:alpha", importance="low")
        vault._remember("project target", "Other", scope="project:beta", importance="high")
        vault._remember("project target", "Inactive", status="superseded", importance="high")

        hits = SearchIndex(vault).search("target", scope="project:alpha")

        self.assertEqual([hit.title for hit in hits], ["Alpha"])

    def test_confidence_is_reported_as_not_used_in_this_ranking_slice(self) -> None:
        vault = self._vault()
        vault._remember(
            "confidence target", "Confidence",
            confidence={"support": 0.9, "model": "synthetic", "rubric": "fixture"},
        )

        hit = SearchIndex(vault).search("confidence")[0]

        self.assertEqual(hit.details["confidence_status"], "advisory")
        self.assertFalse(hit.details["confidence_applied"])

    def test_match_details_only_list_query_terms_present_in_that_memory(self) -> None:
        vault = self._vault()
        vault.remember("The selected deployment is local.", "Deployment")

        hit = SearchIndex(vault).search("deployment absentterm")[0]

        self.assertEqual(hit.details["matching_terms"], ["deployment"])


class HarnessPromptQualityTests(V3TestCase):
    def _vault(self) -> Vault:
        return Vault.create(self.root / "vault")

    def test_useful_short_prompt_reaches_scoped_recall_but_greeting_stays_skipped(self) -> None:
        vault = self._vault()
        payload = {"hook_event_name": "UserPromptSubmit", "prompt": "deployment?"}
        with patch("ai_dememory.harness.CoreServices") as services:
            services.return_value.context.return_value = {"context": "", "memory_ids": []}
            result = recall_hook(vault, payload, "project:alpha")

        services.return_value.context.assert_called_once_with(
            "deployment?", limit=3, max_chars=2000, scope="project:alpha"
        )
        self.assertIn("No relevant memory found.", result["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(recall_hook(vault, {**payload, "prompt": "Hi"}, "project:alpha"), {})
