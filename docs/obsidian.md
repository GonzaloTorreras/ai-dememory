# Obsidian Support

Open this repository root as an Obsidian vault.

Recommended conventions:

- Use `memories/` for canonical reviewed memory.
- Use `inbox/` for raw notes and LLM proposals.
- Use `templates/` as the Obsidian template folder.
- Do not edit generated files in `indexes/`, `distilled/`, or `reports/`.
- Run validation and secret scanning before promoting notes.

Suggested workflow:

1. Capture rough notes in `inbox/`.
2. Convert reviewed notes with one of the templates in `templates/`.
3. Place durable facts in `memories/durable/`, project facts in
   `memories/projects/`, and short-lived context in `memories/active/`.
4. Run:

```bash
python3 scripts/validate_memory.py
python3 scripts/secret_scan.py
python3 scripts/index_memory.py
```

Durable memories should be short, evidence-backed, and conservative.
