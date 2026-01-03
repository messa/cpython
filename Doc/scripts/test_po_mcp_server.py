#!/usr/bin/env python3
"""
Basic tests for po_mcp_server.py MCP server.

This script verifies that:
1. The MCP server module has no syntax errors and can be imported
2. The server starts and responds to MCP protocol messages via stdio

Expected to be run via cpython/Doc/venv/bin/python:
    cd Doc
    venv/bin/python scripts/test_po_mcp_server.py

Requires: mcp, polib (install via `make _ensure-package PACKAGE=...`)
"""

import json
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SERVER_SCRIPT = SCRIPT_DIR / "po_mcp_server.py"


def test_import():
    """Test that the module can be imported without errors."""
    print("Testing import...", end=" ")
    import po_mcp_server  # noqa: F401
    print("OK")


def read_jsonrpc_message(proc, timeout_lines=20):
    """
    Read a JSON-RPC message from MCP server stdout.

    MCP stdio transport sends one JSON object per line.
    Skip notification messages and return the first response with an id.
    """
    for _ in range(timeout_lines):
        line = proc.stdout.readline()
        if not line:
            raise AssertionError("Server closed stdout unexpectedly")
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            return msg
        except json.JSONDecodeError as e:
            raise AssertionError(f"Invalid JSON from server: {line!r}") from e
    raise AssertionError("No valid message received within line limit")


def read_response_with_id(proc, expected_id, timeout_lines=20):
    """Read messages until we get a response with the expected id."""
    for _ in range(timeout_lines):
        msg = read_jsonrpc_message(proc)
        if msg.get("id") == expected_id:
            return msg
        # Skip notifications (no id field)
    raise AssertionError(f"No response with id={expected_id} received")


def test_mcp_initialize():
    """Test that the server responds to MCP initialize request."""
    print("Testing MCP initialize...", end=" ")

    # MCP uses JSON-RPC 2.0 over stdio (one JSON per line)
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0",
            },
        },
    }

    # Start the server
    proc = subprocess.Popen(
        [sys.executable, str(SERVER_SCRIPT)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        # Send initialize request (one JSON per line)
        proc.stdin.write(json.dumps(init_request) + "\n")
        proc.stdin.flush()

        # Read response
        response = read_response_with_id(proc, 1)

        # Verify response structure
        assert response.get("jsonrpc") == "2.0", f"Invalid jsonrpc version: {response}"
        assert "result" in response, f"Missing result in response: {response}"

        result = response["result"]
        assert "protocolVersion" in result, f"Missing protocolVersion: {result}"
        assert "serverInfo" in result, f"Missing serverInfo: {result}"
        assert result["serverInfo"]["name"] == "po-translation-tools", f"Wrong server name: {result}"

        print("OK")

    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_list_tools():
    """Test that the server returns tool list."""
    print("Testing tools/list...", end=" ")

    # Initialize first, then list tools
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"},
        },
    }

    initialized_notification = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
    }

    list_tools_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }

    proc = subprocess.Popen(
        [sys.executable, str(SERVER_SCRIPT)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        # Send all messages (one JSON per line)
        for msg in [init_request, initialized_notification, list_tools_request]:
            proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()

        # Read tools/list response (skip initialize response)
        tools_response = read_response_with_id(proc, 2)

        assert "result" in tools_response, f"Missing result: {tools_response}"

        tools = tools_response["result"].get("tools", [])
        tool_names = [t["name"] for t in tools]

        assert "get_entries_to_translate" in tool_names, f"Missing get_entries_to_translate: {tool_names}"
        assert "submit_translations" in tool_names, f"Missing submit_translations: {tool_names}"

        print("OK")

    finally:
        proc.terminate()
        proc.wait(timeout=5)


def main():
    """Run all tests."""
    print(f"Testing {SERVER_SCRIPT}\n")

    # Add script dir to path for import test
    sys.path.insert(0, str(SCRIPT_DIR))

    tests = [test_import, test_mcp_initialize, test_list_tools]
    failed = 0

    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"FAILED: {e}")
            failed += 1

    print()
    if failed:
        print(f"{failed}/{len(tests)} tests failed")
        sys.exit(1)
    else:
        print(f"All {len(tests)} tests passed")
        sys.exit(0)


if __name__ == "__main__":
    main()
