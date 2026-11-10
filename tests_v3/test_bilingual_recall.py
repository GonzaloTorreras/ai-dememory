from ai_dememory.search import SearchIndex
from ai_dememory.vault import Vault
from tests_v3.test_core import V3TestCase


class BilingualRecallTests(V3TestCase):
    def test_independent_vocabulary_holdout_and_translation_ceiling(self):
        from tests_v3.recall_benchmark import measure
        result = measure()
        self.assertEqual(result["source_vocabulary"], {"cases":6,"before":0,"after":6})
        self.assertEqual(result["translation_ceiling"], {"cases":4,"after":0})
        self.assertEqual(result["wrong_constraint_matches"], {"cases":2,"after":0})

    def test_original_source_words_recover_a_translated_claim_without_a_model(self):
        vault = Vault.create(self.root / "vault")
        source = {"provider": "fixture", "session": "s", "turn": "t", "evidence_kind": "user_statement",
                  "excerpt": "Prefiero copias de seguridad todas las noches."}
        memory = vault._remember("The project uses scheduled nightly backups.", "Recovery policy",
                                 source=source, scope="project:alpha")
        index = SearchIndex(vault)
        self.assertEqual(index.search("copias seguridad noches", scope="project:alpha", include_source=False), [])
        hits = index.search("copias seguridad noches", scope="project:alpha", include_source=True)
        self.assertEqual([h.memory_id for h in hits], [memory.memory_id])
        self.assertEqual(hits[0].details["match_fields"], ["source_excerpt"])
        self.assertEqual(index.search("copias seguridad noches", scope="project:beta"), [])

    def test_source_only_expansion_requires_all_terms_not_a_wrong_entity_or_quantity(self):
        vault = Vault.create(self.root / "vault")
        vault._remember("Lidia returns eight shovels to the northern shed.", "Equipment return",
                        source={"provider":"fixture", "session":"s", "turn":"t", "evidence_kind":"user_statement",
                                "excerpt":"Lidia devuelve ocho palas al cobertizo norte."})
        self.assertEqual(SearchIndex(vault).search("Sofía devuelve cinco palas"), [])

    def test_language_tags_do_not_pretend_to_translate_missing_words(self):
        vault = Vault.create(self.root / "vault")
        vault.remember("Keep the butter below six degrees overnight.", "Cold storage")
        self.assertEqual(SearchIndex(vault).search("mantequilla seis grados"), [])
