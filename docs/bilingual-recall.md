# Bilingual recall and optional Jev skills

## What improves without a model

The local FTS index now includes the literal evidence excerpt at lower weight
than the title or claim. If an agent summarized Spanish evidence in English (or
the reverse), a query can find the original wording. Source-only additions must
match all informative query terms; existing title/body matches retain their
lexical behavior. **Providers → Advanced retrieval → Search original evidence
wording** turns this off. No canonical file is rewritten.

An independently proposed synthetic holdout is runnable with:

```bash
python -m tests_v3.recall_benchmark
```

| Bucket | Before | After | Interpretation |
| --- | --- | --- | --- |
| Original-language source vocabulary | 0/6 | 6/6 | The wording exists in the evidence, not the translated summary |
| No words in the query language anywhere | 0/4 | 0/4 | Still needs translation/semantic candidate coverage |
| Wrong entity/quantity controls retrieved | 0/2 | 0/2 | The strict source-only conjunction avoids these added false hits |

These are isolated synthetic cases, not production accuracy. The last row does
not make lexical OR matching semantically reliable. It cannot resolve arbitrary
paraphrases, negation or conflicting constraints. Use short informative terms;
connected agents can make one bounded English/Spanish keyword retry when needed.
Do not add a reranker to fix candidates absent from its shortlist.

## Jev module settings

Jev is optional and disabled by default. The provider/profile/fallback and shared
budget already exist. New skill configuration lives in `module_settings.jev`:

```json
{
  "language": false,
  "usefulness": false,
  "recall_tags": false,
  "after_save": false,
  "automatic_scopes": [],
  "languages": {"es": "Spanish", "en": "English"},
  "purpose": ""
}
```

- Language classifies the canonical body (title is context only), selecting a
  configured label or `mixed`, `other`, `undetermined`.
- Usefulness estimates whether a claim has future retention value. It does not
  assess truth or grant permission. Meaningful dated outcomes may be useful.
- Enabled questions share one bounded request. No extra SDK, service or model
  process. Budget reservations, fallbacks and Activity are shared with providers.
- Recall tags read revision-bound metadata in existing operational SQLite; recall
  never calls Jev. Tags are advisory and never affect ranking or canonical fields.
- Automatic after-save processing needs separate ongoing consent and exact scopes.
  It runs only in the foreground workbench, baselines existing records, processes
  one new active item/minute and keeps receipts independently of the evictable cache.
  A new automation epoch conservatively skips current unprocessed records. Failed
  chains can be manually retried; repeated polling does not repeat paid failures.
- Disabling a skill/module stops future work; canonical memory remains usable.
  The current automatic runner is not an OS task or a hook-time network callback.

## Measure Jev before granting it effects

**Modules → Evaluate Jev on public synthetic examples** displays the actual eight
inputs. Explicit confirmation sends only those fixtures to the saved provider.
Expected labels stay local. The UI reports language accuracy, usefulness accuracy
against a keep-all baseline, useful records rejected and noise retained, plus
model/cache/latency. Costs/usage are in shared Activity; missing prices are not free.

The fixed 0.5 comparison threshold is a diagnostic, not an admission policy. A
promising small result still needs a separate representative holdout and measured
benefit before enabling rejection, ranking changes or semantic fallback. A mocked
8/8 validates code, not Jev. No real-model gain is claimed without a live receipt.

The design follows TypeSafe's [Choice](https://docs.typesafe.ai/primitives/choice),
[Noul](https://docs.typesafe.ai/primitives/noul) and
[memory cookbook](https://docs.typesafe.ai/cookbooks/basic_memory), while retaining
DeMemory's bounded storage, scope, provenance and opt-in constraints rather than
copying an unbounded example memory list.
