"""Shared subprocess plumbing for adapters.

Every adapter runs external commands through this module so output parsing
is stable (LC_ALL=C) and failures are reported uniformly.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from typing import Callable, Iterator, Sequence

_VERSION_RE = re.compile(r"^\d+(\.\d+)*(-[a-z0-9]+)*$")


def split_name_version(line: str) -> tuple[str, str]:
    """Split 'name-1.2.3' (or 'name-1.2.3-r0') at the version start.

    Scans hyphen-separated segments; the first segment that looks like a
    version (starts with a digit) begins the version part.
    """
    segments = line.strip().split("-")
    for i, seg in enumerate(segments):
        if seg and seg[0].isdigit() and _VERSION_RE.fullmatch(seg):
            name = "-".join(segments[:i])
            version = "-".join(segments[i:])
            return name or line.strip(), version
    return line.strip(), ""


class AdapterError(Exception):
    """Base error for adapter operations."""


class CommandFailed(AdapterError):
    """An external command exited with an unexpected status."""

    def __init__(self, cmd: Sequence[str], returncode: int, stdout: str, stderr: str):
        self.cmd = list(cmd)
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        detail = stderr.strip() or stdout.strip()
        super().__init__(f"command failed ({returncode}): {' '.join(self.cmd)}"
                         + (f" — {detail}" if detail else ""))


class TimeoutExpired(AdapterError):
    """An external command exceeded its time budget."""

    def __init__(self, cmd: Sequence[str], timeout: float):
        self.cmd = list(cmd)
        self.timeout = timeout
        super().__init__(f"command timed out after {timeout:.0f}s: {' '.join(self.cmd)}")


def which(binary: str) -> str | None:
    return shutil.which(binary)


def run(
    cmd: Sequence[str],
    *,
    timeout: float = 60.0,
    check: bool = True,
    input: str | None = None,
) -> subprocess.CompletedProcess:
    """Run a command with a stable C locale and capture stdout/stderr."""
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    try:
        proc = subprocess.run(
            list(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            timeout=timeout,
            input=input,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutExpired(cmd, timeout) from exc
    if check and proc.returncode != 0:
        raise CommandFailed(cmd, proc.returncode, proc.stdout, proc.stderr)
    return proc


def check_rc(
    proc: subprocess.CompletedProcess,
    cmd: Sequence[str],
    allowed: tuple[int, ...] = (0,),
) -> subprocess.CompletedProcess:
    """Validate a non-checked run against an explicit set of exit codes."""
    if proc.returncode not in allowed:
        raise CommandFailed(cmd, proc.returncode, proc.stdout, proc.stderr)
    return proc


def privileged(cmd: Sequence[str]) -> list[str]:
    """Prefix a command with pkexec (graphical auth) or sudo (headless fallback)."""
    if shutil.which("pkexec"):
        return ["pkexec", *cmd]
    if shutil.which("sudo"):
        return ["sudo", *cmd]
    raise AdapterError(f"no privilege escalation available (pkexec/sudo) for: {' '.join(cmd)}")


def run_privileged(
    cmd: Sequence[str],
    *,
    timeout: float = 300.0,
) -> subprocess.CompletedProcess:
    """Run a privileged command (pkexec, falling back to sudo)."""
    return run(privileged(cmd), timeout=timeout)


def iter_stream(fh) -> Iterator[str]:
    """Yield logical lines from a text stream, normalizing \\r and \\n.

    Package managers sprinkle carriage returns all over progress output;
    this splits on either separator and drops empty chunks.
    """
    buf = ""
    while True:
        chunk = fh.readline()
        if not chunk:
            break
        buf += chunk
        while buf:
            idx_n = buf.find("\n")
            idx_r = buf.find("\r")
            if idx_n == -1 and idx_r == -1:
                break
            if idx_r == -1 or (idx_n != -1 and idx_n < idx_r):
                idx = idx_n
            else:
                idx = idx_r
            line, buf = buf[:idx], buf[idx + 1 :]
            if line.strip():
                yield line.strip()
    if buf.strip():
        yield buf.strip()


def run_stream(
    cmd: Sequence[str],
    on_line: Callable[[str], None],
    *,
    timeout: float = 60.0,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """Run a command, calling `on_line(text)` for each output line as it appears.

    stdout and stderr are merged so progress text (which some managers write
    to stderr) is surfaced in order.
    """
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    try:
        proc = subprocess.Popen(
            list(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            errors="replace",
        )
    except OSError as exc:
        raise AdapterError(f"could not start: {' '.join(cmd)} — {exc}") from exc
    assert proc.stdout is not None
    deadline = time.monotonic() + timeout
    try:
        for line in iter_stream(proc.stdout):
            on_line(line)
            if time.monotonic() > deadline:
                raise TimeoutExpired(cmd, timeout)
        proc.wait(timeout=max(0.0, deadline - time.monotonic()))
    except TimeoutExpired:
        proc.kill()
        proc.wait()
        raise
    if check and proc.returncode != 0:
        raise CommandFailed(cmd, proc.returncode, "", "")
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout="", stderr="")


def run_privileged_stream(
    cmd: Sequence[str],
    on_line: Callable[[str], None],
    *,
    timeout: float = 300.0,
) -> subprocess.CompletedProcess:
    """Run a privileged command with line-by-line progress callbacks."""
    return run_stream(privileged(cmd), on_line, timeout=timeout)
