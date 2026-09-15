"""Optional managed ChatGPT login through the official Codex app-server.

The app-server owns OAuth credentials in a separate CODEX_HOME. This module never
reads auth files or accepts tokens. See https://learn.chatgpt.com/docs/app-server
and https://learn.chatgpt.com/docs/auth (checked 2026-09-07).
"""

from __future__ import annotations

import atexit
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from itertools import islice
from urllib.parse import urlsplit

from .config import config_dir, load_config

REQUEST_TIMEOUT = 15
GENERATION_TIMEOUT = 90
LOGIN_TIMEOUT = 600
MAX_FRAME_BYTES = 1_000_000
MAX_PROMPT_BYTES = 64_000

_ERROR_HELP = {
    "codex_not_installed": "Codex CLI was not found. Install the official Codex CLI and restart the workbench, or set AI_DEMEMORY_CODEX_BIN to its absolute executable path before starting it.",
    "codex_binary_required": "DeMemory needs the native Codex executable, not a .cmd, .bat or .ps1 launcher. Set AI_DEMEMORY_CODEX_BIN to the full path of codex.exe (Windows) or codex, then restart the workbench. Check any existing override for a moved or missing file.",
}

# These are documented feature keys, not invented turn/start parameters.
_DISABLED_FEATURES = (
    "shell_tool", "unified_exec", "code_mode", "code_mode_host", "js_repl",
    "js_repl_tools_only", "apply_patch_freeform", "apps", "plugins", "hooks",
    "plugin_hooks", "codex_hooks", "multi_agent", "multi_agent_v2", "memories",
    "memory_tool", "browser_use", "computer_use", "image_generation", "view_image",
    "search_tool", "tool_search", "skill_search", "skill_mcp_dependency_install",
    "shell_snapshot", "shell_snapshot_v2", "workspace_dependencies", "remote_plugin",
)
_CONFIG = {
    "model_provider": "openai", "forced_login_method": "chatgpt",
    "cli_auth_credentials_store": "file", "history.persistence": "none",
    "web_search": "disabled", "mcp_servers": {}, "plugins": {},
    "agents.enabled": False, "skills.bundled.enabled": False,
    "skills.include_instructions": False, "features.skip_host_skill_discovery": True,
    "memories.generate_memories": False, "memories.use_memories": False,
    "shell_environment_policy.inherit": "none", "project_doc_max_bytes": 0,
    **{f"features.{name}": False for name in _DISABLED_FEATURES},
}


class CodexSubscriptionError(ValueError):
    """A stable, payload-free error safe to display in the workbench."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__(_ERROR_HELP.get(reason, f"Codex account operation failed: {reason}"))


def validate_vault(vault_root):
    """Check an explicit active vault before account-directory creation."""
    if (config_dir() / "codex-account").resolve().is_relative_to(Path(vault_root).resolve()):
        raise CodexSubscriptionError("account_directory_inside_vault")


def _account_home():
    home = config_dir() / "codex-account"
    for path in (home, *home.parents):
        if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
            raise CodexSubscriptionError("unsafe_account_directory")
    vault = load_config().default_vault
    if vault:
        validate_vault(vault)
    if any((home / name).exists() for name in ("config.toml", "AGENTS.md", ".agents", ".codex")):
        raise CodexSubscriptionError("unexpected_account_configuration")
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    return home


def _native_binary(value):
    if not value:
        return False
    path = Path(value)
    return path.is_absolute() and path.is_file() and path.suffix.lower() not in {".cmd", ".bat", ".ps1"}


def _windows_native_codex():
    """Known user installs only; no shell launchers, recursive scan or probes."""
    def local_root(value):
        return bool(value) and Path(value).is_absolute() and not str(value).startswith(("\\\\", "//"))

    def candidate(root, path):
        try:
            resolved = path.resolve()
            if resolved.is_relative_to(root.resolve()) and _native_binary(resolved):
                return resolved
        except (OSError, RuntimeError):
            pass
        return None

    install = os.environ.get("CODEX_INSTALL_DIR")
    local = os.environ.get("LOCALAPPDATA")
    roots = [Path(install)] if local_root(install) else []
    if local_root(local):
        roots.append(Path(local) / "Programs" / "OpenAI" / "Codex" / "bin")
    for root in roots:
        found = candidate(root, root / "codex.exe")
        if found:
            return str(found)
    if not local_root(local):
        return None
    desktop = Path(local) / "OpenAI" / "Codex" / "bin"
    try:
        with os.scandir(desktop) as entries:
            children = list(islice(entries, 65))
        if len(children) > 64:
            return None
        found = []
        for child in children:
            path = candidate(desktop, Path(child.path) / "codex.exe")
            if path:
                try:
                    found.append((path.stat().st_mtime_ns, str(path)))
                except OSError:
                    continue
        return max(found)[1] if found else None
    except OSError:
        return None


def _command():
    configured = os.environ.get("AI_DEMEMORY_CODEX_BIN")
    # Windows PATH may contain a shell launcher before the native CLI. Never
    # execute that launcher or silently replace an explicitly configured path.
    executable = configured
    if not executable:
        executable = shutil.which("codex.exe") if sys.platform == "win32" else None
        executable = executable or shutil.which("codex")
        if sys.platform == "win32" and not _native_binary(executable):
            executable = _windows_native_codex() or executable
    if not executable:
        raise CodexSubscriptionError("codex_not_installed")
    path = Path(executable)
    if not _native_binary(executable):
        raise CodexSubscriptionError("codex_binary_required")
    command = [str(path), "app-server"]
    for key, value in _CONFIG.items():
        encoded = json.dumps(value, separators=(",", ":"))
        # Empty TOML inline tables use {}, matching JSON for the only object here.
        command.extend(("-c", f"{key}={encoded}"))
    return command


def _environment(home):
    allowed = {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "LANG", "LC_ALL"}
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    env.update(CODEX_HOME=str(home), HOME=str(home), USERPROFILE=str(home), CODEX_SQLITE_HOME=str(home))
    return env


class _AppServer:
    """One owned child, bounded JSON lines, and a hard lifetime watchdog."""

    def __init__(self, lifetime=GENERATION_TIMEOUT):
        self.home = _account_home()
        self.scratch = tempfile.TemporaryDirectory(prefix="request-", dir=self.home)
        self.events = []
        self.incoming = queue.Queue(maxsize=32)
        self.failure = None
        self.sequence = 0
        self.closed = False
        self.close_lock = threading.RLock()
        self.process = None
        self.reader = None
        self.watchdog = None
        try:
            self.process = subprocess.Popen(
                _command(), cwd=self.scratch.name, env=_environment(self.home),
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                start_new_session=os.name != "nt",
            )
            self.reader = threading.Thread(target=self._read, name="dememory-codex-reader", daemon=True)
            self.reader.start()
            self.watchdog = threading.Timer(lifetime, self._expire)
            self.watchdog.daemon = True
            self.watchdog.start()
            self.request("initialize", {"clientInfo": {"name": "ai_dememory", "version": "3"},
                                        "capabilities": {"experimentalApi": True}})
            self.send({"method": "initialized"})
        except Exception:
            self.close()
            raise

    def _read(self):
        try:
            while not self.closed:
                line = self.process.stdout.readline(MAX_FRAME_BYTES + 1)
                if not line:
                    self.failure = self.failure or "codex_process_exited"
                    return
                if len(line) > MAX_FRAME_BYTES:
                    self.failure = "codex_response_too_large"
                    return
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError
                self.incoming.put_nowait(value)
        except queue.Full:
            self.failure = "codex_output_overflow"
        except (ValueError, UnicodeError, OSError):
            self.failure = "codex_protocol_error"

    def _kill(self):
        process = self.process
        if process is None or process.poll() is not None:
            return
        if os.name == "nt":
            # Only our live Popen PID; never enumerate unrelated host processes.
            try:
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
            except (OSError, subprocess.TimeoutExpired):
                pass
            if process.poll() is None:
                process.kill()
        else:
            import signal
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def _expire(self):
        self.failure = "codex_timeout"
        self.close()

    def close(self):
        with self.close_lock:
            if self.closed:
                return
            self.closed = True
            if self.watchdog:
                self.watchdog.cancel()
            self._kill()
            if self.process:
                self.process.wait(timeout=6)
                for stream in (self.process.stdin, self.process.stdout):
                    if stream:
                        stream.close()
            if self.reader and self.reader is not threading.current_thread():
                self.reader.join(timeout=2)
            self.scratch.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def send(self, message):
        try:
            self.process.stdin.write(json.dumps(message, separators=(",", ":")).encode() + b"\n")
            self.process.stdin.flush()
        except (OSError, ValueError) as exc:
            raise CodexSubscriptionError("codex_process_exited") from exc

    def receive(self, deadline):
        while time.monotonic() < deadline:
            try:
                message = self.incoming.get(timeout=min(0.1, max(0.001, deadline-time.monotonic())))
            except queue.Empty:
                if self.failure:
                    raise CodexSubscriptionError(self.failure)
                continue
            if "method" in message and "id" in message:
                # Never service server-initiated execution, approval, or credential requests.
                self.send({"id": message["id"], "error": {"code": -32601, "message": "Tools disabled"}})
                raise CodexSubscriptionError("codex_tool_request_rejected")
            return message
        raise CodexSubscriptionError("codex_timeout")

    def request(self, method, params, timeout=REQUEST_TIMEOUT):
        self.sequence += 1
        request_id = self.sequence
        self.send({"id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        while True:
            response = self.receive(deadline)
            if response.get("id") == request_id:
                if "error" in response:
                    raise CodexSubscriptionError("codex_request_rejected")
                result = response.get("result")
                if not isinstance(result, dict):
                    raise CodexSubscriptionError("codex_protocol_error")
                return result
            if len(self.events) >= 128:
                raise CodexSubscriptionError("codex_output_overflow")
            self.events.append(response)

    def authenticated(self):
        account = self.request("account/read", {"refreshToken": False}).get("account")
        if account is None:
            return False
        if not isinstance(account, dict) or account.get("type") != "chatgpt":
            raise CodexSubscriptionError("chatgpt_account_required")
        return True


_login_lock = threading.RLock()
_pending = None


def start_login(method="device"):
    """Start only after an explicit UI action; the caller opens the returned URL."""
    global _pending
    if method not in {"device", "browser"}:
        raise ValueError("Login method must be device or browser")
    with _login_lock:
        cancel_login()
        server = _AppServer(LOGIN_TIMEOUT)
        try:
            result = server.request("account/login/start", {"type": "chatgptDeviceCode" if method == "device" else "chatgpt"})
            url = result.get("verificationUrl") if method == "device" else result.get("authUrl")
            parsed = urlsplit(url or "")
            if parsed.scheme != "https" or parsed.username or parsed.password or parsed.hostname not in {"auth.openai.com", "auth0.openai.com", "chatgpt.com"}:
                raise CodexSubscriptionError("invalid_login_url")
            login_id = result.get("loginId")
            if not isinstance(login_id, str) or not login_id or len(login_id) > 256:
                raise CodexSubscriptionError("codex_protocol_error")
            code = result.get("userCode", "")
            if not isinstance(code, str) or len(code) > 128:
                raise CodexSubscriptionError("codex_protocol_error")
            _pending = (server, login_id)
            return {"verification_url": url, "user_code": code, "login_id": login_id}
        except Exception:
            server.close()
            raise


def login_status():
    global _pending
    with _login_lock:
        if _pending:
            server, _ = _pending
            try:
                authenticated = server.authenticated()
                completed = next((event.get("params", {}) for event in server.events
                                  if event.get("method") == "account/login/completed"), None)
                if authenticated or completed is not None:
                    _pending = None
                    server.close()
                    return {"authenticated": authenticated, "pending": False,
                            **({"error": "login_failed"} if not authenticated else {})}
                return {"authenticated": False, "pending": True}
            except CodexSubscriptionError as exc:
                _pending = None
                server.close()
                return {"authenticated": False, "pending": False, "error": exc.reason, "message": str(exc)}
        try:
            with _AppServer() as server:
                return {"authenticated": server.authenticated(), "pending": False}
        except CodexSubscriptionError as exc:
            return {"authenticated": False, "pending": False, "error": exc.reason, "message": str(exc)}


def cancel_login():
    global _pending
    with _login_lock:
        if _pending:
            server, login_id = _pending
            _pending = None
            try:
                server.request("account/login/cancel", {"loginId": login_id}, timeout=2)
            except CodexSubscriptionError:
                pass
            finally:
                server.close()


def list_models():
    with _AppServer() as server:
        if not server.authenticated():
            raise CodexSubscriptionError("chatgpt_login_required")
        models, cursor = [], None
        for _ in range(5):
            result = server.request("model/list", {"limit": 100, "includeHidden": False, "cursor": cursor})
            for item in result.get("data", []):
                if isinstance(item, dict) and isinstance(item.get("model"), str):
                    models.append(item["model"])
            cursor = result.get("nextCursor")
            if not cursor:
                return list(dict.fromkeys(models))
        raise CodexSubscriptionError("codex_model_catalog_too_large")


def generate(profile, prompt, max_output_tokens):
    """Request one text-only turn; max_output_tokens is guidance, not a server cap."""
    if not isinstance(prompt, str) or not prompt or len(prompt.encode()) > MAX_PROMPT_BYTES:
        raise CodexSubscriptionError("invalid_prompt")
    if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 16_384:
        raise CodexSubscriptionError("invalid_output_limit")
    model = profile.get("model") if isinstance(profile, dict) else None
    if not isinstance(model, str) or not model or len(model) > 200:
        raise CodexSubscriptionError("model_required")
    effort = profile.get("reasoning_effort")
    if effort is not None and (not isinstance(effort, str) or not effort or len(effort) > 32):
        raise CodexSubscriptionError("invalid_reasoning_effort")
    with _AppServer() as server:
        if not server.authenticated():
            raise CodexSubscriptionError("chatgpt_login_required")
        if effort is not None:
            catalog = server.request("model/list", {"limit": 100, "includeHidden": False}).get("data", [])
            selected = next((item for item in catalog if isinstance(item, dict) and item.get("model") == model), {})
            supported = {item.get("reasoningEffort") for item in selected.get("supportedReasoningEfforts", [])
                         if isinstance(item, dict)}
            if effort not in supported:
                raise CodexSubscriptionError("unsupported_reasoning_effort")
        # Read-only sandbox does not prohibit command execution. Require the
        # installed runtime to recognize and disable every execution feature.
        effective = server.request("config/read", {"includeLayers": False}).get("config", {})
        if (effective.get("mcp_servers") != {} or effective.get("plugins") != {}
                or effective.get("model_provider") != "openai"
                or effective.get("forced_login_method") != "chatgpt"):
            raise CodexSubscriptionError("unsupported_tools_isolation")
        features = server.request("experimentalFeature/list", {"limit": 200}).get("data", [])
        flags = {item.get("name"): item.get("enabled") for item in features if isinstance(item, dict)}
        # UnifiedExec is a stable selector that some clients force on; ShellTool
        # gates registration, and environments=[] also removes execution targets.
        # Official registry: codex-rs/core/src/tools/spec_plan.rs (2026-09-07).
        required = {"shell_tool", "code_mode", "code_mode_host", "js_repl", "plugins", "hooks", "multi_agent_v2"}
        if any(flags.get(name) is not False for name in required):
            raise CodexSubscriptionError("unsupported_tools_isolation")
        if flags.get("skip_host_skill_discovery") is not True:
            raise CodexSubscriptionError("unsupported_tools_isolation")
        if any(flags.get(name) is True for name in _DISABLED_FEATURES if name != "unified_exec"):
            raise CodexSubscriptionError("unsupported_tools_isolation")
        thread = server.request("thread/start", {
            "model": model, "modelProvider": "openai", "cwd": server.scratch.name,
            "sandbox": "read-only", "approvalPolicy": "never", "ephemeral": True,
            "dynamicTools": [], "environments": [],
            "baseInstructions": "Transform the supplied text. Use no tools. Return only the requested result.",
            "developerInstructions": f"Aim for at most {max_output_tokens} output tokens.",
        })
        thread_data = thread.get("thread", {})
        if (thread_data.get("ephemeral") is not True or thread.get("sandbox", {}).get("type") != "readOnly"
                or thread.get("instructionSources") or thread.get("modelProvider", "openai") != "openai"
                or thread.get("model", model) != model):
            raise CodexSubscriptionError("unsupported_thread_isolation")
        thread_id = thread_data.get("id")
        response = server.request("turn/start", {
            "threadId": thread_id, "input": [{"type": "text", "text": prompt, "text_elements": []}],
            **({"effort": effort} if effort is not None else {}),
            "sandboxPolicy": {"type": "readOnly", "access": {"type": "restricted", "includePlatformDefaults": False,
                                "readableRoots": [server.scratch.name]}},
        })
        turn_id = response.get("turn", {}).get("id")
        deadline = time.monotonic() + GENERATION_TIMEOUT
        text, usage = "", None
        while True:
            event = server.events.pop(0) if server.events else server.receive(deadline)
            params = event.get("params", {})
            if params.get("threadId") not in (None, thread_id) or params.get("turnId") not in (None, turn_id):
                continue
            method = event.get("method")
            if method == "item/agentMessage/delta":
                text += params.get("delta", "")
                if len(text.encode()) > min(MAX_FRAME_BYTES, max_output_tokens * 8):
                    raise CodexSubscriptionError("codex_response_too_large")
            elif method == "item/started":
                if params.get("item", {}).get("type") not in {"userMessage", "agentMessage", "reasoning"}:
                    raise CodexSubscriptionError("codex_tool_request_rejected")
            elif method == "thread/tokenUsage/updated":
                last = params.get("tokenUsage", {}).get("last", {})
                if all(type(last.get(key)) is int and last[key] >= 0 for key in ("inputTokens", "outputTokens")):
                    usage = {"input_tokens": last["inputTokens"], "output_tokens": last["outputTokens"]}
            elif method == "turn/completed":
                if params.get("turn", {}).get("status") != "completed":
                    raise CodexSubscriptionError("codex_generation_failed")
                if not text:
                    raise CodexSubscriptionError("codex_empty_response")
                return {"text": text, **({"usage": usage} if usage else {})}


close = cancel_login
atexit.register(cancel_login)
