# Personal Memory Vault

This repository stores your private ai-dememory Markdown vault.

Markdown under `memories/` is canonical. SQLite indexes, distilled context, and
reports are generated artifacts and can be rebuilt.

## Daily Commands

```bash
ai-dememory doctor
ai-dememory validate
ai-dememory secret-scan
ai-dememory index
ai-dememory eval-recall
ai-dememory search "topic" --limit 5
```

## Safety

- Do not store secrets, tokens, private keys, cookies, service-account JSON, or
  `.env` contents.
- LLM-created notes belong in `inbox/llm-captures/` until reviewed.
- Durable memories require human review before promotion.
