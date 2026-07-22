#!/usr/bin/env python3
"""本地 Seewo MCP 服务桥接客户端。"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List


class SeewoMCPClient:
    """通过 stdio 与本地 MCP 服务通信。"""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.server_path = self.project_root / "mcp" / "server.py"
        self._proc: subprocess.Popen[str] | None = None
        self._req_id = 0
        self._lock = threading.Lock()
        self._ensure_started()
        self._request("initialize", {})
        self._request("notifications/initialized", expect_response=False)

    def _ensure_started(self) -> None:
        if self._proc and self._proc.poll() is None:
            return
        self._proc = subprocess.Popen(
            [sys.executable, str(self.server_path)],
            cwd=str(self.project_root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

    def _request(self, method: str, params: Dict[str, Any] | None = None, expect_response: bool = True) -> Dict[str, Any] | None:
        with self._lock:
            self._ensure_started()
            assert self._proc is not None
            if not self._proc.stdin or not self._proc.stdout:
                raise RuntimeError("MCP 服务管道未就绪")

            self._req_id += 1
            req_id = self._req_id
            payload: Dict[str, Any] = {"jsonrpc": "2.0", "method": method}
            if expect_response:
                payload["id"] = req_id
            if params is not None:
                payload["params"] = params

            self._proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self._proc.stdin.flush()

            if not expect_response:
                return None

            line = self._proc.stdout.readline()
            if not line:
                stderr_text = ""
                if self._proc.stderr:
                    stderr_text = self._proc.stderr.read()
                raise RuntimeError(f"MCP 服务无响应或已退出。{stderr_text}".strip())

            resp = json.loads(line)
            if "error" in resp:
                raise RuntimeError(resp["error"].get("message", "MCP 调用失败"))
            return resp.get("result", {})

    def list_tools(self) -> List[Dict[str, Any]]:
        result = self._request("tools/list", {}) or {}
        return result.get("tools", [])

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        result = self._request("tools/call", {"name": tool_name, "arguments": arguments}) or {}
        structured = result.get("structuredContent")
        if isinstance(structured, dict):
            return structured

        content = result.get("content") or []
        if content and isinstance(content[0], dict) and content[0].get("type") == "text":
            return json.loads(content[0].get("text") or "{}")
        return {}

    def close(self) -> None:
        if not self._proc:
            return
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None
