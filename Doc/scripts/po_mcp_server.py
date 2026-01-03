#!/usr/bin/env python3
"""
MCP server for Czech translation of Python documentation.

Provides tools for translating .po files:
- get_entries_to_translate: Get untranslated entries from .po files
- submit_translations: Apply translations to .po files

Requires: mcp, polib

Possible future improvements:
- TODO: Add request ID to log messages for tracing (e.g., using contextvars)
- TODO: Use anyio.to_thread.run_sync() for blocking operations (polib.pofile,
  subprocess.run) to avoid blocking the event loop
"""

import asyncio
import json
import logging
from logging.handlers import WatchedFileHandler
from pathlib import Path
from subprocess import run
from typing import Any

import polib
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool


# Resolve base directories using realpath to prevent path traversal
_SCRIPT_DIR = Path(__file__).resolve().parent
_DOC_DIR = _SCRIPT_DIR.parent.resolve()
LOCALE_DIR = (_DOC_DIR / "locales" / "cs" / "LC_MESSAGES").resolve()

# Ensure LOCALE_DIR is within DOC_DIR (sanity check)
if not str(LOCALE_DIR).startswith(str(_DOC_DIR)):
    raise RuntimeError("LOCALE_DIR must be within Doc directory")


# Setup logging
_LOG_FILE = _SCRIPT_DIR / "po_mcp_server.log"
_LOG_FORMAT = "%(asctime)s [%(process)d] %(name)s %(levelname)5s: %(message)s"

logger = logging.getLogger("po_mcp_server")
logger.setLevel(logging.DEBUG)

# File handler - DEBUG level
_file_handler = WatchedFileHandler(_LOG_FILE, encoding="utf-8")
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
logger.addHandler(_file_handler)

# Stderr handler - WARNING+ only (to avoid breaking MCP protocol)
_stderr_handler = logging.StreamHandler()
_stderr_handler.setLevel(logging.WARNING)
_stderr_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
logger.addHandler(_stderr_handler)

logger.info("MCP server starting, LOCALE_DIR=%s", LOCALE_DIR)


def get_all_po_files() -> list[Path]:
    """Get all .po files in the locale directory."""
    return sorted(LOCALE_DIR.rglob("*.po"))


def get_untranslated_stats() -> list[dict]:
    """Get stats about untranslated entries in all .po files."""
    stats = []
    for po_path in get_all_po_files():
        try:
            po = polib.pofile(str(po_path))
            untranslated = len(po.untranslated_entries())
            if untranslated > 0:
                relative = po_path.relative_to(LOCALE_DIR)
                stats.append({
                    "file": str(relative),
                    "untranslated": untranslated,
                    "total": len(po),
                })
        except Exception:
            continue
    # Sort by untranslated count (smallest first - easiest to complete)
    return sorted(stats, key=lambda x: x["untranslated"])


class PathSecurityError(Exception):
    """Raised when a path fails security validation."""
    pass


def validate_po_path(po_file: str) -> Path:
    """
    Validate and resolve a .po file path securely.

    Args:
        po_file: Relative path to .po file (e.g., 'tutorial/whatnow.po')

    Returns:
        Resolved absolute Path within LOCALE_DIR

    Raises:
        PathSecurityError: If path is invalid, outside allowed directory,
                          or doesn't have .po extension
    """
    if not po_file:
        logger.warning("Security: empty path provided")
        raise PathSecurityError("Empty path provided")

    # Reject absolute paths
    if po_file.startswith("/") or (len(po_file) > 1 and po_file[1] == ":"):
        logger.warning("Security: absolute path rejected: %s", po_file)
        raise PathSecurityError("Absolute paths are not allowed")

    # Reject obvious path traversal attempts
    if ".." in po_file:
        logger.warning("Security: path traversal rejected: %s", po_file)
        raise PathSecurityError("Path traversal (..) is not allowed")

    # Construct path relative to LOCALE_DIR and resolve
    candidate = (LOCALE_DIR / po_file).resolve()

    # Security check: ensure resolved path is within LOCALE_DIR
    try:
        candidate.relative_to(LOCALE_DIR)
    except ValueError:
        logger.warning("Security: path escapes allowed directory: %s -> %s", po_file, candidate)
        raise PathSecurityError(
            f"Path escapes allowed directory: {po_file}"
        )

    # Validate .po extension
    if candidate.suffix.lower() != ".po":
        logger.warning("Security: invalid extension rejected: %s", po_file)
        raise PathSecurityError(
            f"Only .po files are allowed, got: {candidate.suffix}"
        )

    # Check file exists
    if not candidate.exists():
        logger.debug("File not found: %s", po_file)
        raise PathSecurityError(f"File not found: {po_file}")

    # Check it's a regular file (not directory, symlink to outside, etc.)
    if not candidate.is_file():
        logger.warning("Security: not a regular file: %s", po_file)
        raise PathSecurityError(f"Not a regular file: {po_file}")

    logger.debug("Path validated: %s -> %s", po_file, candidate)
    return candidate


def format_entry_context(entry: polib.POEntry) -> dict:
    """Format a PO entry with full context for translation."""
    result = {
        "msgid": entry.msgid,
    }

    # Add msgid_plural if present
    if entry.msgid_plural:
        result["msgid_plural"] = entry.msgid_plural

    # Add context if present
    if entry.msgctxt:
        result["context"] = entry.msgctxt

    # Add source references
    if entry.occurrences:
        result["references"] = [
            f"{occ[0]}:{occ[1]}" for occ in entry.occurrences[:3]
        ]

    # Add translator comments
    if entry.tcomment:
        result["translator_comment"] = entry.tcomment

    # Add extracted comments (from source code)
    if entry.comment:
        result["extracted_comment"] = entry.comment

    # Add flags (like python-format, fuzzy)
    if entry.flags:
        result["flags"] = list(entry.flags)

    return result


def run_msgfmt_check(po_path: Path) -> tuple[bool, list[str]]:
    """Run msgfmt --check on a .po file. Returns (success, errors)."""
    result = run(
        ["msgfmt", "--check", "-o", "/dev/null", str(po_path)],
        capture_output=True,
        text=True
    )
    # Filter out warnings, only return errors
    errors = [line for line in result.stderr.splitlines() if "warning:" not in line]
    return (len(errors) == 0, errors)


# Create MCP server
server = Server("po-translation-tools")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="get_entries_to_translate",
            description=(
                "Get untranslated entries from .po files for Czech translation. "
                "If no file is specified, automatically selects a file with fewest "
                "untranslated entries (easiest to complete). Returns entries with "
                "full context including source references and comments."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file": {
                        "type": "string",
                        "description": (
                            "Path to .po file (relative to locale dir, e.g., "
                            "'tutorial/whatnow.po'). If not specified, auto-selects."
                        ),
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of entries to return (default: 5)",
                        "default": 5,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="submit_translations",
            description=(
                "Apply Czech translations to a .po file. Validates translations "
                "using msgfmt and reports any errors (mismatched format strings, "
                "invalid syntax, etc.)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file": {
                        "type": "string",
                        "description": "Path to .po file (relative to locale dir)",
                    },
                    "translations": {
                        "type": "array",
                        "description": "List of translations to apply",
                        "items": {
                            "type": "object",
                            "properties": {
                                "msgid": {
                                    "type": "string",
                                    "description": "Original English text (must match exactly)",
                                },
                                "msgstr": {
                                    "type": "string",
                                    "description": "Czech translation",
                                },
                            },
                            "required": ["msgid", "msgstr"],
                        },
                    },
                },
                "required": ["file", "translations"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    logger.info("Tool call: %s, arguments: %s", name, arguments)

    if name == "get_entries_to_translate":
        return await handle_get_entries(arguments)

    elif name == "submit_translations":
        return await handle_submit_translations(arguments)

    else:
        logger.warning("Unknown tool requested: %s", name)
        return [TextContent(
            type="text",
            text=json.dumps({"error": f"Unknown tool: {name}"})
        )]


async def handle_get_entries(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle get_entries_to_translate tool call."""
    file_arg = arguments.get("file")
    count = arguments.get("count", 5)
    logger.debug("get_entries: file=%s, count=%d", file_arg, count)

    # If no file specified, find one with fewest untranslated entries
    if file_arg is None:
        stats = get_untranslated_stats()
        if not stats:
            logger.info("All files are fully translated!")
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "message": "All files are fully translated!",
                    "entries": [],
                })
            )]
        # Pick file with fewest untranslated (easiest to complete)
        file_arg = stats[0]["file"]
        logger.debug("Auto-selected file: %s (untranslated: %d)", file_arg, stats[0]["untranslated"])

    # Validate and resolve path securely
    try:
        po_path = validate_po_path(file_arg)
    except PathSecurityError as e:
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": str(e),
            })
        )]

    # Load .po file
    try:
        po = polib.pofile(str(po_path))
    except Exception as e:
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": f"Failed to parse .po file: {e}",
            })
        )]

    # Get untranslated entries
    untranslated = po.untranslated_entries()
    entries_to_return = untranslated[:count]

    # Format entries with context
    formatted_entries = [
        format_entry_context(entry) for entry in entries_to_return
    ]

    relative_path = po_path.relative_to(LOCALE_DIR)

    result = {
        "success": True,
        "file": str(relative_path),
        "entries": formatted_entries,
        "returned_count": len(formatted_entries),
        "remaining_in_file": len(untranslated) - len(formatted_entries),
        "total_in_file": len(po),
    }

    logger.info(
        "get_entries: returned %d entries from %s (remaining: %d)",
        len(formatted_entries), relative_path, len(untranslated) - len(formatted_entries)
    )
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def handle_submit_translations(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle submit_translations tool call."""
    file_arg = arguments.get("file")
    translations = arguments.get("translations", [])
    logger.debug("submit_translations: file=%s, count=%d", file_arg, len(translations))

    if not file_arg:
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": "File parameter is required",
            })
        )]

    if not translations:
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": "No translations provided",
            })
        )]

    # Validate and resolve path securely
    try:
        po_path = validate_po_path(file_arg)
    except PathSecurityError as e:
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": str(e),
            })
        )]

    # Load .po file
    try:
        po = polib.pofile(str(po_path))
    except Exception as e:
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": f"Failed to parse .po file: {e}",
            })
        )]

    # Apply translations
    applied = []
    not_found = []
    already_translated = []

    for trans in translations:
        msgid = trans.get("msgid", "")
        msgstr = trans.get("msgstr", "")

        if not msgid or not msgstr:
            continue

        # Find matching entry
        found = False
        for entry in po:
            if entry.msgid == msgid:
                found = True
                if entry.msgstr:
                    already_translated.append(msgid[:50] + "..." if len(msgid) > 50 else msgid)
                else:
                    entry.msgstr = msgstr
                    # Remove fuzzy flag if present
                    if "fuzzy" in entry.flags:
                        entry.flags.remove("fuzzy")
                    applied.append(msgid[:50] + "..." if len(msgid) > 50 else msgid)
                break

        if not found:
            not_found.append(msgid[:50] + "..." if len(msgid) > 50 else msgid)

    # Save if any translations were applied
    if applied:
        po.save()
        logger.info("Saved %d translations to %s", len(applied), file_arg)

        # Run validation
        valid, errors = run_msgfmt_check(po_path)
        if not valid:
            logger.warning("Validation failed for %s: %s", file_arg, errors)

        result = {
            "success": True,
            "applied_count": len(applied),
            "applied": applied,
            "validation": {
                "valid": valid,
                "errors": errors if errors else None,
            },
        }

        if not_found:
            result["not_found"] = not_found
        if already_translated:
            result["already_translated"] = already_translated

        # If validation failed, warn but don't revert
        if not valid:
            result["warning"] = (
                "Translations applied but validation failed. "
                "Please review and fix the errors."
            )
    else:
        result = {
            "success": False,
            "error": "No translations were applied",
            "not_found": not_found if not_found else None,
            "already_translated": already_translated if already_translated else None,
        }

    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
