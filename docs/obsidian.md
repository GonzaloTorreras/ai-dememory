# Obsidian Support

Use a separately initialized private vault as the Obsidian vault. Do not open
the ai-dememory source or package-distribution checkout as a personal memory
vault; its checked-in `memories/**` files are public demo and validation
fixtures.

Recommended conventions:

- Install `ai-dememory`, initialize a dedicated vault directory, and open that
  directory in Obsidian.
- In the private vault, use `memories/` for canonical reviewed memory and
  `inbox/` for raw notes and LLM proposals.
- Use the private vault's `templates/` directory as the Obsidian template
  folder.
- Do not edit generated files in the vault's `indexes/`, `distilled/`, or
  `reports/` directories.
- Run validation and secret scanning before promoting notes.

Suggested workflow:

1. Create the private vault:

```bash
ai-dememory init /path/to/private-memory-vault
```

2. Open `/path/to/private-memory-vault` in Obsidian.
3. Capture rough notes in `inbox/` and convert reviewed notes with the vault
   templates.
4. Place durable facts in `memories/durable/`, project facts in
   `memories/projects/`, and short-lived context in `memories/active/`.
5. Validate the explicit vault before indexing:

```bash
ai-dememory --root /path/to/private-memory-vault validate
ai-dememory --root /path/to/private-memory-vault secret-scan
ai-dememory --root /path/to/private-memory-vault index
```

Durable memories should be short, evidence-backed, conservative, and never
copied into the public source repository merely because both are open locally.
