"""Cross-platform lifecycle controls for child processes owned by ai-dememory."""

from __future__ import annotations

import locale
import os
from contextlib import contextmanager
from pathlib import Path
import signal
import subprocess
import tempfile
import threading
import time
from typing import Any, Iterator


DEFAULT_TERMINATION_GRACE_SECONDS = 3
DEFAULT_MAX_CAPTURE_OUTPUT_BYTES = 4 * 1024 * 1024
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_WINDOWS_CREATE_SUSPENDED = 0x00000004


class BoundedTextDrain:
    """Continuously drain one text pipe while retaining only a bounded tail."""

    def __init__(self, stream: Any, *, max_chars: int = 64 * 1024) -> None:
        if max_chars < 1024:
            raise ValueError("max_chars must be at least 1024")
        self._stream = stream
        self._max_chars = max_chars
        self._tail = ""
        self._lock = threading.Lock()
        self._thread = threading.Thread(
            target=self._run,
            name="ai-dememory-bounded-stderr",
            daemon=True,
        )
        self._thread.start()

    def _run(self) -> None:
        try:
            while True:
                chunk = self._stream.readline(4096)
                if not chunk:
                    return
                with self._lock:
                    self._tail = (self._tail + str(chunk))[-self._max_chars :]
        except (OSError, ValueError):
            return

    def tail(self) -> str:
        with self._lock:
            return self._tail

    def join(self, timeout: float = DEFAULT_TERMINATION_GRACE_SECONDS) -> bool:
        self._thread.join(timeout=max(0.0, timeout))
        return not self._thread.is_alive()


def attach_bounded_stderr_drain(
    process: subprocess.Popen[Any],
    *,
    max_chars: int = 64 * 1024,
) -> BoundedTextDrain | None:
    """Drain a child's stderr pipe and attach the bounded diagnostic tail."""

    if process.stderr is None:
        return None
    drain = BoundedTextDrain(process.stderr, max_chars=max_chars)
    setattr(process, "_ai_dememory_stderr_drain", drain)
    return drain


def bounded_stderr_tail(process: subprocess.Popen[Any]) -> str:
    """Return diagnostics retained by attach_bounded_stderr_drain."""

    drain = getattr(process, "_ai_dememory_stderr_drain", None)
    return drain.tail() if isinstance(drain, BoundedTextDrain) else ""


def join_bounded_stderr_drain(
    process: subprocess.Popen[Any],
    *,
    timeout: float = DEFAULT_TERMINATION_GRACE_SECONDS,
) -> bool:
    """Wait briefly for an attached stderr drain after the child is reaped."""

    drain = getattr(process, "_ai_dememory_stderr_drain", None)
    return drain.join(timeout) if isinstance(drain, BoundedTextDrain) else True


def _create_windows_kill_job() -> int:
    """Create a non-inheritable Job Object that kills every member on close."""

    if os.name != "nt":
        return 0
    import ctypes
    from ctypes import wintypes

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_job = kernel32.CreateJobObjectW
    create_job.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    create_job.restype = wintypes.HANDLE
    set_job_information = kernel32.SetInformationJobObject
    set_job_information.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    set_job_information.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    job = create_job(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    limits.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not set_job_information(
        job,
        _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
        ctypes.byref(limits),
        ctypes.sizeof(limits),
    ):
        error = ctypes.get_last_error()
        close_handle(job)
        raise ctypes.WinError(error)
    return int(job)


def _assign_windows_job(process: subprocess.Popen[Any], job: int) -> None:
    if os.name != "nt":
        return
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    assign = kernel32.AssignProcessToJobObject
    assign.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    assign.restype = wintypes.BOOL
    process_handle = int(getattr(process, "_handle", 0))
    if not process_handle or not assign(wintypes.HANDLE(job), wintypes.HANDLE(process_handle)):
        raise ctypes.WinError(ctypes.get_last_error())


def _resume_windows_process(process: subprocess.Popen[Any]) -> None:
    """Resume the one primary thread after race-free Job Object assignment."""

    if os.name != "nt":
        return
    import ctypes
    from ctypes import wintypes

    thread_suspend_resume = 0x0002
    th32cs_snapthread = 0x00000004
    invalid_handle_value = ctypes.c_void_p(-1).value

    class THREADENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ThreadID", wintypes.DWORD),
            ("th32OwnerProcessID", wintypes.DWORD),
            ("tpBasePri", wintypes.LONG),
            ("tpDeltaPri", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_snapshot = kernel32.CreateToolhelp32Snapshot
    create_snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    create_snapshot.restype = wintypes.HANDLE
    thread_first = kernel32.Thread32First
    thread_first.argtypes = [wintypes.HANDLE, ctypes.POINTER(THREADENTRY32)]
    thread_first.restype = wintypes.BOOL
    thread_next = kernel32.Thread32Next
    thread_next.argtypes = [wintypes.HANDLE, ctypes.POINTER(THREADENTRY32)]
    thread_next.restype = wintypes.BOOL
    open_thread = kernel32.OpenThread
    open_thread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    open_thread.restype = wintypes.HANDLE
    resume_thread = kernel32.ResumeThread
    resume_thread.argtypes = [wintypes.HANDLE]
    resume_thread.restype = wintypes.DWORD
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    snapshot = create_snapshot(th32cs_snapthread, 0)
    if not snapshot or int(snapshot) == invalid_handle_value:
        raise ctypes.WinError(ctypes.get_last_error())
    thread_id = 0
    try:
        entry = THREADENTRY32()
        entry.dwSize = ctypes.sizeof(entry)
        has_entry = bool(thread_first(snapshot, ctypes.byref(entry)))
        while has_entry:
            if int(entry.th32OwnerProcessID) == process.pid:
                thread_id = int(entry.th32ThreadID)
                break
            has_entry = bool(thread_next(snapshot, ctypes.byref(entry)))
    finally:
        close_handle(snapshot)
    if not thread_id:
        raise RuntimeError("suspended Windows child has no primary thread")

    thread = open_thread(thread_suspend_resume, False, thread_id)
    if not thread:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        previous_suspend_count = int(resume_thread(thread))
        if previous_suspend_count == 0xFFFFFFFF:
            raise ctypes.WinError(ctypes.get_last_error())
        if previous_suspend_count < 1:
            raise RuntimeError("Windows child was not suspended before Job Object assignment")
    finally:
        close_handle(thread)


def _close_windows_job(process: subprocess.Popen[Any], *, terminate: bool) -> bool:
    if os.name != "nt":
        return True
    import ctypes
    from ctypes import wintypes

    job = int(getattr(process, "_ai_dememory_job_handle", 0) or 0)
    if not job:
        return False
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    terminate_job = kernel32.TerminateJobObject
    terminate_job.argtypes = [wintypes.HANDLE, wintypes.UINT]
    terminate_job.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    ok = True
    if terminate:
        ok = bool(terminate_job(wintypes.HANDLE(job), 1))
    # KILL_ON_JOB_CLOSE also catches descendants that outlived a normally
    # completed leader. The retained handle prevents PID reuse from changing
    # the ownership target.
    ok = bool(close_handle(wintypes.HANDLE(job))) and ok
    setattr(process, "_ai_dememory_job_handle", 0)
    setattr(process, "_ai_dememory_job_assigned", False)
    return ok


def process_group_options(*, hidden: bool = True) -> dict[str, Any]:
    """Return Popen options that give one command an independently reaped tree."""

    if os.name == "nt":
        creationflags = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        creationflags |= _WINDOWS_CREATE_SUSPENDED
        if hidden:
            creationflags |= int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return {"creationflags": creationflags, "start_new_session": False}
    return {"creationflags": 0, "start_new_session": True}


def _post_spawn_checkpoint(process: subprocess.Popen[Any]) -> None:
    """Internal cancellation/test checkpoint after the owned child exists."""

    del process


class _DeferredProcessSignals:
    def __init__(self) -> None:
        self.events: list[tuple[int, object]] = []


def _replay_process_signal(signum: int, frame: object, handler: Any) -> None:
    if handler == signal.SIG_IGN:
        return
    if callable(handler):
        handler(signum, frame)
        return
    # Normalize the default Windows SIGBREAK action to Python cancellation so
    # the owned tree is reaped before KeyboardInterrupt becomes visible.
    signal.default_int_handler(signum, frame)


@contextmanager
def _defer_process_signals() -> Iterator[_DeferredProcessSignals]:
    """Defer and then replay console cancellation at an owned boundary."""

    state = _DeferredProcessSignals()
    if threading.current_thread() is not threading.main_thread():
        yield state
        return
    signals = [signal.SIGINT]
    sigbreak = getattr(signal, "SIGBREAK", None)
    if isinstance(sigbreak, int):
        signals.append(sigbreak)
    previous: dict[int, Any] = {}
    installed: list[int] = []

    def request_interrupt(signum: int, frame: object) -> None:
        state.events.append((signum, frame))

    try:
        for signum in signals:
            previous[signum] = signal.getsignal(signum)
            signal.signal(signum, request_interrupt)
            installed.append(signum)
        yield state
    finally:
        for signum in reversed(installed):
            signal.signal(signum, previous[signum])
        # Compose with an outer transaction fence or custom handler.  Replaying
        # after restoration preserves SIG_IGN/default behavior instead of
        # converting every console event into an unconditional KeyboardInterrupt.
        for signum, frame in state.events:
            handler = previous.get(signum, signal.SIG_DFL)
            _replay_process_signal(signum, frame, handler)


@contextmanager
def _owned_process_cancel_guard(process: subprocess.Popen[Any]) -> Iterator[None]:
    """Let cancellation unwind into the scoped process cleanup boundary."""

    if threading.current_thread() is not threading.main_thread():
        yield
        return
    signals = [signal.SIGINT]
    sigbreak = getattr(signal, "SIGBREAK", None)
    if isinstance(sigbreak, int):
        signals.append(sigbreak)
    previous: dict[int, Any] = {}
    installed: list[int] = []

    def cancel(signum: int, frame: object) -> None:
        handler = previous.get(signum, signal.SIG_DFL)
        # Do not reap from inside a Python signal handler: SIGINT can interrupt
        # Popen.wait() while subprocess owns an internal lock.  Delegating lets
        # the interrupted frame unwind first; start_owned_process() then reaps
        # the tree from its guarded finally block.
        _replay_process_signal(signum, frame, handler)

    try:
        for signum in signals:
            previous[signum] = signal.getsignal(signum)
            signal.signal(signum, cancel)
            installed.append(signum)
        yield
    finally:
        for signum in reversed(installed):
            signal.signal(signum, previous[signum])


def _cleanup_owned_process(
    process: subprocess.Popen[Any],
    *,
    grace_seconds: float = DEFAULT_TERMINATION_GRACE_SECONDS,
) -> bool:
    """Attempt exactly one bounded tree cleanup for a scoped child."""

    try:
        # Console cancellation must not split terminate/kill/wait. Replay it
        # only after the bounded cleanup has reached a consistent boundary.
        with _defer_process_signals():
            if getattr(process, "_ai_dememory_cleanup_attempted", False) is True:
                return getattr(process, "_ai_dememory_cleanup_complete", False) is True
            setattr(process, "_ai_dememory_cleanup_attempted", True)
            complete = terminate_process_tree(process, grace_seconds=grace_seconds)
            setattr(process, "_ai_dememory_cleanup_complete", complete)
    except BaseException:
        setattr(process, "_ai_dememory_cleanup_attempted", False)
        setattr(process, "_ai_dememory_cleanup_complete", False)
        raise
    return complete


def _pre_owned_cleanup_checkpoint(_process: subprocess.Popen[Any]) -> None:
    """Internal seam immediately before scoped process cleanup."""


@contextmanager
def start_owned_process(
    command: list[str],
    *,
    hidden: bool = True,
    **popen_kwargs: Any,
) -> Iterator[subprocess.Popen[Any]]:
    """Scope a command inside an owned POSIX session or Windows Job Object."""

    options = dict(popen_kwargs)
    options.update(process_group_options(hidden=hidden))
    process: subprocess.Popen[Any] | None = None
    job = 0
    try:
        # A real SIGINT is deferred only across Popen's CALL->STORE boundary
        # and Windows Job assignment. Once `process` is local, every exit path
        # is protected by this generator's finally block.
        with _defer_process_signals():
            process = subprocess.Popen(command, **options)
            _post_spawn_checkpoint(process)
            if os.name == "nt":
                job = _create_windows_kill_job()
                setattr(process, "_ai_dememory_job_handle", job)
                setattr(process, "_ai_dememory_job_assigned", False)
                _assign_windows_job(process, job)
                setattr(process, "_ai_dememory_job_assigned", True)
                _resume_windows_process(process)
        with _owned_process_cancel_guard(process):
            try:
                yield process
            finally:
                # Keep the lifetime guard installed across the complete normal
                # scope-exit -> cleanup transition.
                with _defer_process_signals():
                    _pre_owned_cleanup_checkpoint(process)
                    _cleanup_owned_process(process)
    finally:
        if process is not None and getattr(
            process,
            "_ai_dememory_cleanup_complete",
            False,
        ) is not True:
            # Spawn/setup can fail before the lifetime guard is installed.
            with _defer_process_signals():
                _pre_owned_cleanup_checkpoint(process)
                _cleanup_owned_process(process)


def noninteractive_git_environment() -> dict[str, str]:
    """Return an environment in which Git cannot prompt or start a pager."""

    return {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_PAGER": "cat",
        "PAGER": "cat",
    }


def process_is_running(pid: int) -> bool:
    """Return whether a process currently occupies *pid* (diagnostic only)."""

    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        process_query_limited_information = 0x1000
        still_active = 259
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetExitCodeProcess.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return False
        try:
            exit_code = wintypes.DWORD()
            return bool(
                kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                and exit_code.value == still_active
            )
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def process_start_identity(pid: int) -> str | None:
    """Return a stable start identity used to distinguish recycled PIDs."""

    if pid <= 0 or not process_is_running(pid):
        return None
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class FILETIME(ctypes.Structure):
            _fields_ = [
                ("low", wintypes.DWORD),
                ("high", wintypes.DWORD),
            ]

        process_query_limited_information = 0x1000
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetProcessTimes.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(FILETIME),
            ctypes.POINTER(FILETIME),
            ctypes.POINTER(FILETIME),
            ctypes.POINTER(FILETIME),
        ]
        kernel32.GetProcessTimes.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return None
        try:
            created = FILETIME()
            exited = FILETIME()
            kernel = FILETIME()
            user = FILETIME()
            if not kernel32.GetProcessTimes(
                handle,
                ctypes.byref(created),
                ctypes.byref(exited),
                ctypes.byref(kernel),
                ctypes.byref(user),
            ):
                return None
            ticks = (int(created.high) << 32) | int(created.low)
            return f"windows-filetime:{ticks}"
        finally:
            kernel32.CloseHandle(handle)

    proc_stat = Path(f"/proc/{pid}/stat")
    if proc_stat.is_file():
        try:
            raw = proc_stat.read_text(encoding="ascii")
            fields = raw.rsplit(")", 1)[1].split()
            return f"proc-start-ticks:{fields[19]}"
        except (OSError, IndexError, UnicodeError):
            return None
    try:
        completed = run_owned_capture(
            ["ps", "-o", "lstart=", "-p", str(pid)],
            timeout_seconds=2,
            env={**os.environ, "LC_ALL": "C"},
            max_output_bytes=8192,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = completed.stdout.strip()
    return f"ps-lstart:{value}" if completed.returncode == 0 and value else None


def process_matches_identity(pid: int, start_identity: str | None) -> bool:
    """Return True only when both the PID and recorded process identity match."""

    if not process_is_running(pid):
        return False
    if not start_identity:
        # Preserve legacy locks conservatively: an old PID-only record is
        # never declared stale while that PID is occupied.
        return True
    return process_start_identity(pid) == start_identity


def terminate_process_tree(
    process: subprocess.Popen[Any],
    *,
    grace_seconds: float = DEFAULT_TERMINATION_GRACE_SECONDS,
) -> bool:
    """Terminate and reap exactly one process group/tree started by this package."""

    if os.name == "nt":
        had_job = bool(getattr(process, "_ai_dememory_job_handle", 0))
        job_owned_process = bool(getattr(process, "_ai_dememory_job_assigned", False))
        job_closed = _close_windows_job(process, terminate=process.poll() is None)
        if not job_owned_process and process.poll() is None:
            # Popen retains a handle to the original process object, so this
            # fallback cannot target a recycled PID. It also closes the failure
            # path where a Job handle existed but assignment did not complete.
            process.kill()
        try:
            process.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            return False
        return bool(job_closed or not had_job)

    def group_exists() -> bool:
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    if group_exists():
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + max(0.0, grace_seconds)
        while group_exists() and time.monotonic() < deadline:
            time.sleep(0.01)
    if group_exists():
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + max(0.0, grace_seconds)
        while group_exists() and time.monotonic() < deadline:
            time.sleep(0.01)
    if process.poll() is None:
        process.kill()
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        return False
    return not group_exists()


def close_stdin_and_reap(
    process: subprocess.Popen[Any],
    *,
    grace_seconds: float = DEFAULT_TERMINATION_GRACE_SECONDS,
) -> bool:
    """Request graceful EOF, then terminate the owned tree if it does not exit."""

    stdin = process.stdin
    if stdin is not None and not stdin.closed:
        try:
            stdin.close()
        except OSError:
            pass
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        pass
    return _cleanup_owned_process(process, grace_seconds=grace_seconds)


def run_owned_process(
    command: list[str],
    timeout_seconds: float,
    **popen_kwargs: Any,
) -> tuple[int, bool, int]:
    """Run one bounded command and always reap its owned process tree."""

    options = dict(popen_kwargs)
    options.setdefault("stdin", subprocess.DEVNULL)
    with start_owned_process(command, **options) as process:
        try:
            returncode = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            reaped = _cleanup_owned_process(process)
            return (124 if reaped else 125), True, process.pid
        reaped = _cleanup_owned_process(process)
        return (returncode if reaped else 125), False, process.pid


def run_owned_capture(
    command: list[str],
    *,
    timeout_seconds: float,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
    check: bool = False,
    max_output_bytes: int = DEFAULT_MAX_CAPTURE_OUTPUT_BYTES,
) -> subprocess.CompletedProcess[str]:
    """Run a text command with bounded captured output and tree-safe timeout."""

    if max_output_bytes < 1024:
        raise ValueError("max_output_bytes must be at least 1024")
    encoding = locale.getpreferredencoding(False) or "utf-8"

    def read_outputs(
        stdout_file: Any,
        stderr_file: Any,
    ) -> tuple[str, str, int]:
        stdout_size = os.fstat(stdout_file.fileno()).st_size
        stderr_size = os.fstat(stderr_file.fileno()).st_size
        stderr_budget = min(stderr_size, max_output_bytes // 4)
        stdout_budget = min(stdout_size, max_output_bytes - stderr_budget)
        remaining = max_output_bytes - stdout_budget - stderr_budget
        stderr_budget += min(max(0, stderr_size - stderr_budget), remaining)
        stdout_file.seek(0)
        stderr_file.seek(0)
        stdout_text = stdout_file.read(stdout_budget).decode(encoding, errors="replace")
        stderr_text = stderr_file.read(stderr_budget).decode(encoding, errors="replace")
        # subprocess(..., text=True, stdout=PIPE) applies universal-newline
        # translation. Keep the same public contract while using disk-backed
        # bounded capture files to avoid pipe deadlocks.
        stdout_text = stdout_text.replace("\r\n", "\n").replace("\r", "\n")
        stderr_text = stderr_text.replace("\r\n", "\n").replace("\r", "\n")
        return stdout_text, stderr_text, stdout_size + stderr_size

    with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
        with start_owned_process(
            command,
            cwd=cwd,
            env=env,
            stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
            stdout=stdout_file,
            stderr=stderr_file,
            text=True,
            encoding=encoding,
            errors="replace",
        ) as process:
            if input_text is not None and process.stdin is not None:
                try:
                    process.stdin.write(input_text)
                    process.stdin.close()
                except (BrokenPipeError, OSError):
                    pass

            deadline = time.monotonic() + timeout_seconds
            output_limited = False
            timed_out = False
            while process.poll() is None:
                output_size = (
                    os.fstat(stdout_file.fileno()).st_size
                    + os.fstat(stderr_file.fileno()).st_size
                )
                if output_size > max_output_bytes:
                    output_limited = True
                    break
                if time.monotonic() >= deadline:
                    timed_out = True
                    break
                time.sleep(0.01)

            reaped = _cleanup_owned_process(process)
            stdout, stderr, output_size = read_outputs(stdout_file, stderr_file)
            if output_size > max_output_bytes:
                output_limited = True
            if timed_out:
                if not reaped:
                    stderr += "\n[ai-dememory: owned process tree could not be fully reaped]\n"
                raise subprocess.TimeoutExpired(
                    command,
                    timeout_seconds,
                    output=stdout,
                    stderr=stderr,
                )
            returncode = int(process.returncode if process.returncode is not None else 125)
            if output_limited:
                returncode = 125
                stderr += (
                    f"\n[ai-dememory: combined child output exceeded "
                    f"{max_output_bytes} bytes and the owned tree was terminated]\n"
                )
            elif not reaped:
                returncode = 125
                stderr += "\n[ai-dememory: owned process tree could not be fully reaped]\n"

    completed = subprocess.CompletedProcess(command, returncode, stdout, stderr)
    if check and completed.returncode != 0:
        raise subprocess.CalledProcessError(
            completed.returncode,
            command,
            output=completed.stdout,
            stderr=completed.stderr,
        )
    return completed
