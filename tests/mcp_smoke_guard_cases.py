"""Shared adversarial fixtures for the strict MCP smoke documentation guards."""

from __future__ import annotations

import shlex


def _fenced_markdown(
    delimiter: str, body: str, *, language: str = "bash"
) -> str:
    return f"\n{delimiter}{language}\n{body}\n{delimiter}\n"


def _nested_eval(command: str, *, depth: int = 5) -> str:
    for _ in range(depth):
        command = shlex.join(("eval", command))
    return command


def _brace_overflow_transport() -> str:
    choices = ",".join([f"x{index}" for index in range(40)] + ["client-"])
    return f"$CLI --root /tmp/vault mcp-{{{choices}}}smoke --command python3"


def _group_overflow_transport() -> str:
    assignments = " ".join(f"A{index}=x" for index in range(20))
    return (
        "$CLI --root /tmp/vault "
        f"$({assignments} printf %s mcp-client-smoke) --command python3"
    )


def _parameter_overflow_transport() -> str:
    return (
        "a"
        + "".join(f"${{X{index}:+x}}" for index in range(1, 7))
        + "i-dememory --root /tmp/vault mcp-client-sm"
        + "".join(f"${{Y{index}:+x}}" for index in range(1, 7))
        + "oke --command python3"
    )


def _candidate_region_overflow() -> str:
    return (
        "ai-dememory --root /tmp/vault mcp-client-smoke --server-name "
        + ("x" * ((16 * 1024) + 1))
    )


def _candidate_token_overflow() -> str:
    tail = " ".join(f"token-{index}" for index in range(257))
    return f"ai-dememory --root /tmp/vault mcp-client-smoke {tail}"


def _candidate_count_overflow() -> str:
    return "\n".join(
        "ai-dememory --root /tmp/vault mcp-client-smoke "
        f"--server-name candidate-{index}"
        for index in range(65)
    )


def _assignment_correlation_overflow() -> str:
    return "\n".join(f"ROOT_{index}=--root" for index in range(65))


MCP_SMOKE_CANDIDATE_LIMIT_POCS = (
    (
        "candidate-region-over-16-kib",
        _candidate_region_overflow(),
        "candidate region exceeds the inspection limit",
    ),
    (
        "candidate-over-256-tokens",
        _candidate_token_overflow(),
        "candidate token count exceeds the inspection limit",
    ),
    (
        "document-over-64-candidates",
        _candidate_count_overflow(),
        "candidate count exceeds the inspection limit",
    ),
    (
        "assignment-correlation-over-64-records",
        _assignment_correlation_overflow(),
        "assignment correlation exceeds the inspection limit",
    ),
)


CROSS_LINE_ASSIGNMENT_ALIAS = (
    "ROOT=--root\nCMD=mcp-client-smoke\n"
    "ai-dememory $ROOT /tmp/vault $CMD --command python3"
)


STRICT_MCP_SMOKE_REGION_POCS = (
    (
        "fenced-cross-line-aliases",
        CROSS_LINE_ASSIGNMENT_ALIAS,
    ),
    (
        "powershell-splat",
        "$ARGS=@('--root','C:/vault','mcp-client-smoke','--command','python3')\n"
        "& $CLI @ARGS",
    ),
)


STRICT_MCP_SMOKE_FOLLOWUP_REJECTED_REGIONS = (
    (
        "powershell-splat-literal-launcher",
        "$ARGS=@('--root','C:/vault','mcp-client-smoke','--command','python3')\n"
        "& ai-dememory @ARGS",
    ),
    (
        "assignment-aliases-across-blank-line",
        "ROOT=--root\nCMD=mcp-client-smoke\n\n"
        "ai-dememory $ROOT /tmp/vault $CMD --command python3",
    ),
    (
        "posix-scalar-argv-bundle-unquoted",
        "ARGS='--root /tmp/vault mcp-client-smoke --command python3'\n"
        "ai-dememory $ARGS",
    ),
    (
        "cmd-scalar-argv-bundle",
        "set ARGS=--root C:/vault mcp-client-smoke --command python3\n"
        "ai-dememory %ARGS%",
    ),
    (
        "posix-scalar-bundle-after-literal-doctor",
        "ARGS='--root /tmp/vault mcp-client-smoke --command python3'\n"
        "ai-dememory doctor ; ai-dememory $ARGS",
    ),
    (
        "powershell-collection-after-literal-doctor",
        "$ARGS=@('--root','C:/vault','mcp-client-smoke','--command','python3')\n"
        "ai-dememory doctor ; ai-dememory @ARGS",
    ),
    (
        "posix-scalar-bundle-in-dollar-substitution",
        "ARGS='--root /tmp/vault mcp-client-smoke --command python3'\n"
        "ai-dememory doctor $(ai-dememory $ARGS)",
    ),
    (
        "posix-scalar-bundle-in-backtick-substitution",
        "ARGS='--root /tmp/vault mcp-client-smoke --command python3'\n"
        "ai-dememory doctor `ai-dememory $ARGS`",
    ),
    (
        "powershell-collection-in-dollar-substitution",
        "$ARGS=@('--root','C:/vault','mcp-client-smoke','--command','python3')\n"
        "ai-dememory doctor $(ai-dememory @ARGS)",
    ),
    (
        "dynamic-subcommand-in-nested-dollar-substitution",
        "ai-dememory --root /tmp/vault doctor "
        "$(ai-dememory --root /tmp/vault $SUBCOMMAND --command python3)",
    ),
    (
        "dynamic-subcommand-in-nested-backtick-substitution",
        "ai-dememory --root /tmp/vault doctor "
        "`ai-dememory --root /tmp/vault $SUBCOMMAND --command python3`",
    ),
    (
        "defaulted-subcommand-in-nested-dollar-substitution",
        "ai-dememory --root /tmp/vault doctor "
        "$(ai-dememory --root /tmp/vault "
        "${SUBCOMMAND:-mcp-client-smoke} --command python3)",
    ),
    (
        "dynamic-subcommand-after-literal-doctor-semicolon",
        "ai-dememory --root /tmp/vault doctor ; "
        "$CLI --root /tmp/vault $SUBCOMMAND --command python3",
    ),
    (
        "dynamic-subcommand-after-literal-doctor-and",
        "ai-dememory --root /tmp/vault doctor && "
        "$CLI --root /tmp/vault $SUBCOMMAND --command python3",
    ),
    (
        "dynamic-subcommand-after-literal-doctor-pipe",
        "ai-dememory --root /tmp/vault doctor | "
        "$CLI --root /tmp/vault $SUBCOMMAND --command python3",
    ),
    (
        "dynamic-fragment-after-literal-doctor",
        "ai-dememory --root /tmp/vault doctor ; "
        "ai-dememory --root /tmp/vault "
        "mcp-${PART:-client-}smoke --command python3",
    ),
    (
        "eval-wrapper-doctor-with-dynamic-payload",
        "eval $CLI --root /tmp/vault doctor --command $PAYLOAD",
    ),
    (
        "dynamic-prefix-before-literal-doctor",
        "$EMPTY ai-dememory --root /tmp/vault doctor",
    ),
    (
        "dynamic-prefix-before-dynamic-doctor",
        "$WRAPPER $CLI --root /tmp/vault doctor",
    ),
)


STRICT_MCP_SMOKE_FOLLOWUP_REJECTED_DOCUMENTS = (
    (
        "inline-html-opener-span-before-real-fence",
        "\n`<!--`"
        + _fenced_markdown("```", CROSS_LINE_ASSIGNMENT_ALIAS),
    ),
)


STRICT_MCP_SMOKE_FOLLOWUP_ALLOWED_REGIONS = (
    (
        "assigned-note-with-policy-words",
        "NOTE='mcp-client-smoke uses --root'\n$CLI --output $PATH",
    ),
    (
        "assigned-note-with-smoke-words",
        'NOTE="ai-dememory mcp-client-smoke"\n$CLI --output $PATH',
    ),
    (
        "assigned-note-output-reference",
        "NOTE='mcp-client-smoke uses --root'\n$CLI --output $NOTE",
    ),
    (
        "assignment-aliases-used-only-in-comment",
        "ROOT=--root\nCMD=mcp-client-smoke\n# ai-dememory $ROOT $CMD",
    ),
    (
        "posix-scalar-argv-bundle-quoted",
        "ARGS='--root /tmp/vault mcp-client-smoke --command python3'\n"
        'ai-dememory "$ARGS"',
    ),
    (
        "powershell-collection-on-explicit-doctor-route",
        "$ARGS=@('--root','C:/vault','mcp-client-smoke','--command','python3')\n"
        "ai-dememory doctor --output @ARGS",
    ),
    (
        "env-wrapper-on-explicit-doctor-route",
        "env X=1 ai-dememory --root /tmp/vault doctor --command $PATH",
    ),
    (
        "env-dynamic-launcher-on-explicit-doctor-route",
        "env X=1 $CLI --root /tmp/vault doctor --command $PATH",
    ),
    (
        "sudo-env-dynamic-launcher-on-explicit-doctor-route",
        "sudo env X=1 command $CLI --root /tmp/vault doctor --command $PATH",
    ),
    (
        "nohup-dynamic-launcher-on-explicit-doctor-route",
        "nohup $CLI --root /tmp/vault doctor --command $PATH",
    ),
    (
        "python-flags-on-explicit-doctor-route",
        "python3 -u scripts/ai_dememory.py --root /tmp/vault "
        "doctor --command $PATH",
    ),
    (
        "py-selector-and-flags-on-explicit-doctor-route",
        "py -3.13 -I scripts/ai_dememory.py --root C:/vault "
        "doctor --command $PATH",
    ),
    (
        "python-module-flags-on-explicit-doctor-route",
        "python3 -I -m ai_dememory_tool.cli --root /tmp/vault "
        "doctor --command $PATH",
    ),
    (
        "adjacent-quoted-target-used-as-search-query",
        'ai-"dememory" --root /tmp/vault search mcp-"client-smoke"',
    ),
    (
        "echoed-adjacent-quoted-route",
        'echo ai-"dememory" --root /tmp/vault mcp-"client-smoke"',
    ),
    (
        "escaped-target-used-as-search-query",
        "ai-dememory --root /tmp/vault search mcp-client-\\smoke",
    ),
    (
        "echoed-escaped-route",
        "echo ai-\\dememory --root /tmp/vault mcp-client-\\smoke",
    ),
    (
        "literal-doctor-with-obfuscated-comment",
        'ai-dememory --root /tmp/vault doctor # mcp-"client-smoke"',
    ),
    (
        "cmd-scalar-argv-bundle-quoted",
        "set ARGS=--root C:/vault mcp-client-smoke --command python3\n"
        'ai-dememory "%ARGS%"',
    ),
)


STRICT_MCP_SMOKE_COMMENT_ALLOWED_DOCUMENTS = (
    (
        "html-commented-backtick-fence",
        "\n<!--\n```bash\n"
        + CROSS_LINE_ASSIGNMENT_ALIAS
        + "\n```\n-->\n",
    ),
    (
        "powershell-block-comment-in-fence",
        _fenced_markdown(
            "```",
            "<#\n$ROOT='--root'\n$CMD='mcp-client-smoke'\n"
            "ai-dememory $ROOT C:/vault $CMD --command python3\n#>",
            language="powershell",
        ),
    ),
)


STRICT_MCP_SMOKE_CROSS_LINE_ALIAS_DOCUMENTS = (
    (
        "backtick-fence",
        _fenced_markdown("```", CROSS_LINE_ASSIGNMENT_ALIAS),
    ),
    (
        "tilde-fence",
        _fenced_markdown("~~~", CROSS_LINE_ASSIGNMENT_ALIAS),
    ),
    (
        "blockquoted-backtick-fence",
        "\n> ```bash\n"
        + "\n".join(
            f"> {line}" for line in CROSS_LINE_ASSIGNMENT_ALIAS.splitlines()
        )
        + "\n> ```\n",
    ),
    (
        "list-contained-tilde-fence",
        "\n- ~~~bash\n"
        + "\n".join(
            f"  {line}" for line in CROSS_LINE_ASSIGNMENT_ALIAS.splitlines()
        )
        + "\n  ~~~\n",
    ),
    (
        "raw-contiguous-plain-text",
        f"\n{CROSS_LINE_ASSIGNMENT_ALIAS}\n",
    ),
    (
        "indented-commonmark-block",
        "\n"
        + "\n".join(
            f"    {line}" for line in CROSS_LINE_ASSIGNMENT_ALIAS.splitlines()
        )
        + "\n",
    ),
)


# These named cases are regression anchors for the most recent bypass classes.
# General stable docs may discuss them; owned MCP evidence wrappers must reject them.
LATEST_STRICT_MCP_SMOKE_POCS = (
    (
        "literal-concatenation",
        '& ("ai-" + "dememory") --root C:/vault '
        '("mcp-" + "client-smoke") --command python3',
    ),
    (
        "posix-assignment-aliases",
        "CLI=ai-dememory\nCMD=mcp-client-smoke\n"
        "$CLI --root /tmp/vault $CMD --command python3",
    ),
    (
        "powershell-join",
        "& (-join ('ai-','dememory')) --root C:/vault "
        "(-join ('mcp-','client-smoke')) --command python3",
    ),
    (
        "powershell-string-concat",
        "& ([string]::Concat('ai-','dememory')) --root C:/vault "
        "([string]::Concat('mcp-','client-smoke')) --command python3",
    ),
    (
        "powershell-format",
        "& ('{0}{1}' -f 'ai-','dememory') --root C:/vault "
        "('{0}{1}' -f 'mcp-','client-smoke') --command python3",
    ),
    (
        "powershell-assignment-aliases",
        "$cli = 'ai-dememory'\n$command = 'mcp-client-smoke'\n"
        "& $cli --root C:/vault $command --command python3",
    ),
    (
        "cmd-assignment-aliases",
        'set "CLI=ai-dememory"\nset "COMMAND=mcp-client-smoke"\n'
        "%CLI% --root C:/vault %COMMAND% --command python3",
    ),
    (
        "powershell-null-concatenation",
        "& ($null + 'ai-dememory') --root C:/vault "
        "($null + 'mcp-client-smoke') --command python3",
    ),
    (
        "html-entities",
        "<code>ai&#45;dememory --root C:/vault "
        "mcp&#45;client&#45;smoke --command python3</code>",
    ),
    (
        "html-nesting",
        "<code>ai-<span>de</span>memory --root C:/vault "
        "mcp-client-<!--split-->smoke --command python3</code>",
    ),
    (
        "multiline-html-comments",
        "<code>ai-<!--\nsplit\n-->dememory --root C:/vault "
        "mcp-client-<!--\nsplit\n-->smoke --command python3</code>",
    ),
    *((name, command) for name, command, _ in MCP_SMOKE_CANDIDATE_LIMIT_POCS),
)


STRICT_MCP_SMOKE_COMMENT_ALLOWED_TEXT = (
    "# mcp-client-smoke uses --root\n$CLI --output $PATH"
)


STRICT_MCP_SMOKE_ALLOWED_TEXTS = (
    "The --root policy permits `$PATH` placeholders.",
    "$CLI --root /tmp/vault doctor --command $PATH",
    "$PYTHON scripts/ai_dememory.py --root /tmp/vault doctor --command $PATH",
    STRICT_MCP_SMOKE_COMMENT_ALLOWED_TEXT,
)


STRICT_MCP_SMOKE_TRANSPORTS = (
    "ai-dememory --root /tmp/vault mcp-${PART:-client-}smoke --command python3",
    "ai-dememory --root /tmp/vault $SUBCOMMAND --command python3",
    'ai-dememory --root C:/vault "mcp-$($part)smoke" --command python3',
    "env X=1 ai-dememory --root /tmp/vault $SUBCOMMAND --command python3",
    "sudo env X=1 command ai-dememory --root /tmp/vault "
    "mcp-${PART:-client-}smoke --command python3",
    "env X=1 $CLI --root /tmp/vault $SUBCOMMAND --command python3",
    "sudo env X=1 command $CLI --root /tmp/vault "
    "$SUBCOMMAND --command python3",
    "nohup $CLI --root /tmp/vault $SUBCOMMAND --command python3",
    "env X=1 ai-'dememory' --root /tmp/vault "
    "mcp-'client-smoke' --command python3",
    'nohup ai-"dememory" --root /tmp/vault '
    'mcp-"client-smoke" --command python3',
    "python3 -u scripts/ai_dememory.py --root /tmp/vault "
    "$SUBCOMMAND --command python3",
    "py -3.13 -I scripts/ai_dememory.py --root C:/vault "
    "%SUBCOMMAND% --command python3",
    "python3 -u scripts/ai_dememory.py --root /tmp/vault "
    'mcp-"client-smoke" --command python3',
    "py -3.13 -I scripts/ai_dememory.py --root C:/vault "
    "mcp-'client-smoke' --command python3",
    "python3 -B -E -I -O -P -q -s -S -u scripts/ai_dememory.py "
    '--root /tmp/vault mcp-"client-smoke" --command python3',
    "python3 -Z scripts/ai_dememory.py --root /tmp/vault "
    'mcp-"client-smoke" --command python3',
    "python3 -bb scripts/ai_dememory.py --root /tmp/vault "
    'mcp-"client-smoke" --command python3',
    "python3 -I -m ai_dememory_tool.cli --root /tmp/vault "
    'mcp-"client-smoke" --command python3',
    "python3 -X python scripts/ai_dememory.py --root /tmp/vault "
    'mcp-"client-smoke" --command python3',
    "python3 -W python scripts/ai_dememory.py --root /tmp/vault "
    'mcp-"client-smoke" --command python3',
    "ai-dememory --root /tmp/vault mcp-client-\\smoke --command python3",
    "ai-\\dememory --root /tmp/vault mcp-client-smoke --command python3",
    "ai-\\dememory --root /tmp/vault mcp-client-\\smoke --command python3",
    "ai-\\dememory --root /tmp/vault mcp-client-\\smoke "
    '--config "/tmp/ai-dememory/mcp-client-smoke/config.json" '
    "--command ai-dememory",
    "python3 scripts/ai_dememory.py --root /tmp/vault "
    'mcp-"client-smoke" --command python3 '
    "--command-arg /tmp/checkout/scripts/ai_dememory.py "
    "# ai-dememory mcp-client-smoke",
    'bash -c "ai-dememory --root /tmp/vault $SUBCOMMAND --command python3"',
    "eval ai-dememory --root /tmp/vault $SUBCOMMAND --command python3",
    "`ai-dememory --root C:/vault $SUBCOMMAND --command python3",
    "ai-dememory --root /tmp/vault `printf mcp-client-smoke` --command python3",
    "ai-dememory --root C:/vault (Get-Variable subcommand).Value --command python3",
    "$(printf ai-dememory) --root /tmp/vault mcp-client-smoke",
    "& ('ai-dememory') --root C:/vault mcp-client-smoke",
    "ai-dememory --root C:/vault %~n1 --command python3",
    "ai-dememory --root C:/vault %1 --command python3",
    "ai-dememory --root /tmp/vault {mcp-client-,}smoke",
    'env X=1 bash -c "ai-dememory --root /tmp/vault $SUBCOMMAND --command python3"',
    'sudo -u root bash -c "ai-dememory --root /tmp/vault '
    '$SUBCOMMAND --command python3"',
    'command eval "ai-dememory --root /tmp/vault $SUBCOMMAND --command python3"',
    'eval -- "ai-dememory --root /tmp/vault $SUBCOMMAND --command python3"',
    _nested_eval("ai-dememory --root /tmp/vault $SUBCOMMAND --command python3"),
    "$CLI --root /tmp/vault ${SUBCOMMAND:-mcp-client-smoke} --command python3",
    "$CLI --root /tmp/vault ${SUBCOMMAND:=mcp-client-smoke} --command python3",
    "$CLI --root /tmp/vault ${SUBCOMMAND=mcp-client-smoke} --command python3",
    "$CLI --root /tmp/vault mcp-${PART:-client-}smoke --command python3",
    "$CLI --root /tmp/vault $(printf mcp-client-smoke) --command python3",
    "%~n1 ai-dememory --root C:/vault mcp-client-smoke --command python3",
    "python3 -m ai_dememory_tool.cli --root /tmp/vault $SUBCOMMAND --command python3",
    "exec ai-dememory --root /tmp/vault mcp-client-smoke --command python3",
    "nohup ai-dememory --root /tmp/vault mcp-client-smoke --command python3",
    "nice ai-dememory --root /tmp/vault mcp-client-smoke --command python3",
    "uv run ai-dememory --root /tmp/vault mcp-client-smoke --command python3",
    "poetry run ai-dememory --root /tmp/vault mcp-client-smoke --command python3",
    "setsid ai-dememory --root /tmp/vault mcp-client-smoke --command python3",
    "timeout 10 ai-dememory --root /tmp/vault mcp-client-smoke --command python3",
    "stdbuf -oL ai-dememory --root /tmp/vault mcp-client-smoke --command python3",
    "Start-Process ai-dememory -ArgumentList '--root',C:/vault,"
    "mcp-client-smoke,'--command',python3",
    "$(command -v ai-dememory) --root /tmp/vault $SUBCOMMAND --command python3",
    "${CLI:-ai-dememory} --root /tmp/vault $SUBCOMMAND --command python3",
    "& (Get-Command ai-dememory) --root C:/vault $SUBCOMMAND --command python3",
    "python3 $(printf scripts/ai_dememory.py) --root /tmp/vault "
    "$SUBCOMMAND --command python3",
    "$PYTHON scripts/ai_dememory.py --root /tmp/vault $SUBCOMMAND --command python3",
    "$PYTHON -m ai_dememory_tool.cli --root /tmp/vault $SUBCOMMAND --command python3",
    "ai-d[e](https://e.test)memory --root C:/vault "
    "mcp-client-s**m**oke --command python3",
    'ai-dememory --root /tmp/vault "$SUBCOMMAND --command python3',
    "<code>ai-dememory --root /tmp/vault\n"
    "$SUBCOMMAND --command python3</code>",
    "Use `$CLI --root /tmp/vault mcp-client-smoke --command $EVIL` after review.",
    "Run `$CLI --root /tmp/vault ${SUBCOMMAND:-mcp-client-smoke} "
    "--command python3` after review.",
    "$EMPTY ai-dememory --root /tmp/vault $SUBCOMMAND --command python3",
    "$(true) ai-dememory --root /tmp/vault $SUBCOMMAND --command python3",
    'env -S "ai-dememory --root /tmp/vault $SUBCOMMAND --command python3"',
    "env -S 'ai-dememory --root /tmp/vault mcp-client-smoke --command python3'",
    "eval 'ai-dememory --root /tmp/vault mcp-client-smoke --command python3'",
    "iex 'ai-dememory --root C:/vault mcp-client-smoke --command python3'",
    "ai-dememory --root $(printf /tmp/vault) $SUBCOMMAND --command python3",
    "ai-dememory --root /tmp/vault $(true\n)mcp-client-smoke "
    "--command python3 --command-arg=-c --command-arg pass",
    _parameter_overflow_transport(),
    _brace_overflow_transport(),
    _group_overflow_transport(),
    *(case for _, case in LATEST_STRICT_MCP_SMOKE_POCS),
)


def strict_transport_markdown(transport: str) -> str:
    """Embed a transport as users could add it to an operational wrapper."""

    if transport.startswith(("Use ", "Run ", "ai-d[e]", "<code>")):
        return f"\n{transport}\n"
    return f"\n```bash\n{transport}\n```\n"


def strict_allow_markdown() -> str:
    """Render non-smoke examples that strict operational wrappers must allow."""

    prose, *commands = STRICT_MCP_SMOKE_ALLOWED_TEXTS
    fenced_commands = "\n\n".join(
        f"```bash\n{command}\n```" for command in commands
    )
    return f"\n{prose}\n\n{fenced_commands}\n"
