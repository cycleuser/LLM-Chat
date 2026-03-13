"""OpenCode integration client.

Supports multiple connection methods:
1. CLI direct interaction (most reliable)
2. HTTP API (when server is running with auth)

Usage:
    client = OpenCodeClient()
    sessions = client.list_sessions()
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .models import (
    OpenCodeSession,
    OpenCodeStatus,
)

logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4096


class OpenCodeClient:
    """Client for interacting with OpenCode.

    Supports:
    - CLI direct commands (recommended)
    - HTTP API when server is running

    Example:
        client = OpenCodeClient()
        if client.is_available():
            sessions = client.list_sessions()
            for session in sessions:
                print(f"{session.title}: {session.status}")
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        password: str | None = None,
    ):
        self._host = host
        self._port = port
        self._password = password
        self._cli_path = self._find_cli()
        self._server_port: int | None = None
        self._detect_server()

    def _find_cli(self) -> str | None:
        """Find OpenCode CLI binary."""
        # Check common locations
        paths = [
            "/Applications/OpenCode.app/Contents/MacOS/opencode-cli",
            "/usr/local/bin/opencode",
            "/usr/bin/opencode",
            shutil.which("opencode"),
        ]
        for path in paths:
            if path and Path(path).exists():
                logger.debug(f"Found OpenCode CLI at: {path}")
                return path
        return None

    def _detect_server(self) -> None:
        """Detect running OpenCode server."""
        import subprocess

        try:
            # Try to find running OpenCode server process
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            for line in result.stdout.splitlines():
                if "opencode-cli" in line and "serve" in line:
                    # Extract port from command line
                    import re

                    port_match = re.search(r"--port\s+(\d+)", line)
                    if port_match:
                        self._server_port = int(port_match.group(1))
                        logger.info(f"Detected OpenCode server on port {self._server_port}")
                    break
        except Exception as e:
            logger.debug(f"Error detecting server: {e}")

    @property
    def cli_path(self) -> str | None:
        return self._cli_path

    @property
    def server_port(self) -> int | None:
        return self._server_port

    def _run_cli(self, *args: str, input_data: str | None = None) -> tuple[int, str, str]:
        """Run OpenCode CLI command."""
        if not self._cli_path:
            return 1, "", "OpenCode CLI not found"

        cmd = [self._cli_path] + list(args)
        logger.debug(f"Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                input=input_data,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 1, "", "Command timed out"
        except Exception as e:
            return 1, "", str(e)

    def is_available(self) -> bool:
        """Check if OpenCode is available."""
        return self._cli_path is not None

    def has_server(self) -> bool:
        """Check if OpenCode server is running."""
        return self._server_port is not None

    # ── Sessions ─────────────────────────────────────────────────────────────

    def list_sessions(self) -> list[OpenCodeSession]:
        """List all sessions."""
        code, stdout, stderr = self._run_cli("session", "list", "--json")

        if code != 0:
            logger.debug(f"Failed to list sessions: {stderr}")
            # Try parsing non-JSON output
            return self._parse_session_table(stdout)

        try:
            data = json.loads(stdout)
            return [OpenCodeSession.from_dict(s) for s in data]
        except json.JSONDecodeError:
            return self._parse_session_table(stdout)

    def _parse_session_table(self, output: str) -> list[OpenCodeSession]:
        """Parse session table output."""
        sessions = []
        for line in output.strip().splitlines():
            if line.startswith("ses_"):
                parts = line.split()
                if len(parts) >= 3:
                    sessions.append(
                        OpenCodeSession(
                            id=parts[0],
                            project_id="",
                            title=" ".join(parts[1:-2]) if len(parts) > 3 else parts[1],
                        )
                    )
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        code, _, stderr = self._run_cli("session", "delete", session_id)
        return code == 0

    # ── Export/Import ─────────────────────────────────────────────────────────

    def export_session(self, session_id: str) -> dict[str, Any] | None:
        """Export session data as JSON."""
        code, stdout, stderr = self._run_cli("export", session_id)

        if code != 0:
            logger.warning(f"Failed to export session: {stderr}")
            return None

        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return None

    # ── Stats ────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any] | None:
        """Get token usage and cost statistics."""
        code, stdout, stderr = self._run_cli("stats", "--json")

        if code != 0:
            return None

        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return None

    # ── Models ───────────────────────────────────────────────────────────────

    def list_models(self) -> list[dict[str, Any]]:
        """List available models."""
        code, stdout, _ = self._run_cli("models", "--json")

        if code != 0:
            return []

        try:
            data = json.loads(stdout)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    # ── Run ──────────────────────────────────────────────────────────────────

    def run_message(self, message: str, project: str = ".") -> tuple[int, str]:
        """Run OpenCode with a message.

        Args:
            message: The message/prompt to send
            project: Project directory (default: current)

        Returns:
            Tuple of (exit_code, output)
        """
        code, stdout, stderr = self._run_cli(
            "-C",
            project,
            "run",
            message,
        )
        return code, stdout or stderr

    # ── Configuration ────────────────────────────────────────────────────────

    def get_config_path(self) -> Path | None:
        """Get OpenCode config directory."""
        config_dir = Path.home() / ".config" / "opencode"
        if config_dir.exists():
            return config_dir
        return None

    def get_data_path(self) -> Path | None:
        """Get OpenCode data directory."""
        data_dir = Path.home() / ".local" / "share" / "opencode"
        if data_dir.exists():
            return data_dir
        return None

    def get_status(self) -> OpenCodeStatus:
        """Get OpenCode status."""
        if self._cli_path:
            return OpenCodeStatus(
                healthy=True,
                version=self._get_version(),
                connected=self._server_port is not None,
            )
        return OpenCodeStatus(healthy=False, connected=False)

    def _get_version(self) -> str:
        """Get OpenCode version."""
        code, stdout, _ = self._run_cli("--version")
        if code == 0:
            return stdout.strip()
        return ""

    # ── Convenience Methods ──────────────────────────────────────────────────

    def start_interactive(self, project: str = ".") -> subprocess.Popen:
        """Start interactive OpenCode session.

        Returns a Popen object that you can interact with.
        """
        if not self._cli_path:
            raise RuntimeError("OpenCode CLI not found")

        return subprocess.Popen(
            [self._cli_path, "-C", project],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def get_current_project(self) -> Path | None:
        """Get the current working directory as project."""
        return Path.cwd()

    def get_log_path(self) -> Path | None:
        """Get OpenCode log directory."""
        log_dir = Path.home() / ".local" / "share" / "opencode" / "log"
        if log_dir.exists():
            return log_dir
        return None


def is_opencode_available() -> bool:
    """Check if OpenCode is installed and available."""
    client = OpenCodeClient()
    return client.is_available()


def get_opencode_info() -> dict[str, Any]:
    """Get OpenCode installation info."""
    client = OpenCodeClient()
    return {
        "available": client.is_available(),
        "cli_path": client.cli_path,
        "server_running": client.has_server(),
        "server_port": client.server_port,
        "config_dir": str(client.get_config_path()) if client.get_config_path() else None,
        "data_dir": str(client.get_data_path()) if client.get_data_path() else None,
        "log_dir": str(client.get_log_path()) if client.get_log_path() else None,
        "version": client._get_version() if client.is_available() else None,
    }
