#!/usr/bin/env python3
"""本地 stdio MCP 服务：统一暴露希沃课堂观察工具。"""

from __future__ import annotations

import json
import sys
import traceback
from typing import Any, Dict

from tools import TOOL_REGISTRY, call_tool

SERVER_INFO = {
    "name": "seewo-mcp",
    "version": "1.0.0",
}


def _ok(message_id: Any, result: Dict[str, Any]) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def _error(message_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": message}}


def _handle_request(payload: Dict[str, Any]) -> Dict[str, Any] | None:
    message_id = payload.get("id")
    method = payload.get("method")
    params = payload.get("params") or {}

    if method == "initialize":
        return _ok(
            message_id,
            {
                "protocolVersion": "2026-07-01",
                "serverInfo": SERVER_INFO,
                "capabilities": {"tools": {}},
            },
        )

    if method == "notifications/initialized":
        return None

    if method == "ping":
        return _ok(message_id, {"ok": True})

    if method == "tools/list":
        tools = [meta["tool_spec"] for meta in TOOL_REGISTRY.values()]
        return _ok(message_id, {"tools": tools})

    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}
        result = call_tool(tool_name, arguments)
        text = json.dumps(result, ensure_ascii=False)
        return _ok(
            message_id,
            {
                "content": [{"type": "text", "text": text}],
                "structuredContent": result,
            },
        )

    return _error(message_id, -32601, f"未知方法：{method}")


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
            response = _handle_request(payload)
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            response = _error(payload.get("id") if "payload" in locals() else None, -32000, str(exc))

        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
