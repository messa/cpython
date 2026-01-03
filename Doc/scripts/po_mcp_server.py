#!/usr/bin/env python3
"""
MCP server for Czech translation of Python documentation.

Provides tools for translating .po files:
- get_entries_to_translate: Get untranslated entries from .po files
- submit_translations: Apply translations to .po files
- list_translations: List existing translations with pagination
- status: Get server status (script path and PID)

Requires: mcp, polib

Possible future improvements:
- TODO: Add request ID to log messages for tracing (e.g., using contextvars)
- TODO: Use anyio.to_thread.run_sync() for blocking operations (polib.pofile,
  subprocess.run) to avoid blocking the event loop
"""

from asyncio import run as asyncio_run
from base64 import b64encode
from hashlib import sha1
from json import dumps as json_dumps
from logging import getLogger, Formatter, StreamHandler, DEBUG, WARNING
from logging.handlers import WatchedFileHandler
from os import getpid
from pathlib import Path
from subprocess import run, TimeoutExpired
from typing import Any

from polib import pofile, POEntry
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool


# Resolve base directories using realpath to prevent path traversal
_SCRIPT_DIR = Path(__file__).resolve().parent
_DOC_DIR = _SCRIPT_DIR.parent.resolve()
LOCALE_DIR = (_DOC_DIR / "locales" / "cs" / "LC_MESSAGES").resolve()

# Limits
MAX_ENTRIES_COUNT = 50  # Maximum entries to return in one request

# Ensure LOCALE_DIR is within DOC_DIR (sanity check)
if not str(LOCALE_DIR).startswith(str(_DOC_DIR)):
    raise RuntimeError("LOCALE_DIR must be within Doc directory")


# Setup logging
_LOG_FILE = _SCRIPT_DIR / "po_mcp_server.log"
_LOG_FORMAT = "%(asctime)s [%(process)d] %(name)s %(levelname)5s: %(message)s"

logger = getLogger("po_mcp_server")
logger.setLevel(DEBUG)

# File handler - DEBUG level
_file_handler = WatchedFileHandler(_LOG_FILE, encoding="utf-8")
_file_handler.setLevel(DEBUG)
_file_handler.setFormatter(Formatter(_LOG_FORMAT))
logger.addHandler(_file_handler)

# Stderr handler - WARNING+ only (to avoid breaking MCP protocol)
_stderr_handler = StreamHandler()
_stderr_handler.setLevel(WARNING)
_stderr_handler.setFormatter(Formatter(_LOG_FORMAT))
logger.addHandler(_stderr_handler)

logger.info("MCP server starting, LOCALE_DIR=%s", LOCALE_DIR)


def get_all_po_files() -> list[Path]:
    """Get all .po files in the locale directory."""
    return sorted(LOCALE_DIR.rglob("*.po"))


def get_untranslated_stats() -> list[dict]:
    """
    Get stats about untranslated entries in all .po files.

    Returns:
        List of dicts sorted by untranslated count (smallest first), each with:
        - file: relative path to .po file
        - untranslated: number of untranslated entries
        - total: total number of entries
    """
    stats = []
    for po_path in get_all_po_files():
        try:
            po = pofile(str(po_path))
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


def compute_msgidhash(msgid: str) -> str:
    """
    Compute a short hash identifier for msgid.

    Returns msgid if shorter than 10 chars, otherwise first 9 chars
    of base64-encoded SHA1 hash. Used to reduce token count in MCP calls.
    """
    if len(msgid) < 10:
        return msgid
    hash_bytes = sha1(msgid.encode("utf-8")).digest()
    return b64encode(hash_bytes).decode("ascii")[:9]


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


def format_entry_context(entry: POEntry) -> dict:
    """
    Format a PO entry with full context for translation.

    Returns a dict with:
    - msgid: original text (always present)
    - msgidhash: short hash of msgid for compact API calls
    - msgid_plural: plural form (if present)
    - context: msgctxt value (if present)
    - references: list of "file:line" source references (up to 3)
    - translator_comment: translator notes (if present)
    - extracted_comment: comments from source code (if present)
    - flags: list of flags like "python-format", "fuzzy" (if present)
    """
    result = {
        "msgid": entry.msgid,
        "msgidhash": compute_msgidhash(entry.msgid),
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


def run_msgfmt_check(po_path: Path, timeout: float = 30.0) -> tuple[bool, list[str]]:
    """
    Run msgfmt --check on a .po file. Returns (success, errors).

    Raises:
        TimeoutExpired: If msgfmt takes longer than timeout seconds.
    """
    result = run(
        ["msgfmt", "--check", "-o", "/dev/null", str(po_path)],
        capture_output=True,
        text=True,
        timeout=timeout,
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
                                "msgidhash": {
                                    "type": "string",
                                    "description": "Short hash of msgid (alternative to msgid)",
                                },
                                "msgstr": {
                                    "type": "string",
                                    "description": "Czech translation",
                                },
                            },
                            "required": ["msgstr"],
                        },
                    },
                    "overwrite": {
                        "type": "boolean",
                        "description": "If false, skip already translated entries (default: true)",
                        "default": True,
                    },
                },
                "required": ["file", "translations"],
            },
        ),
        Tool(
            name="list_translations",
            description=(
                "List translations from a .po file. Returns paginated list of "
                "entries with msgid (original) and msgstr (translation). Useful "
                "for reviewing existing translations."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file": {
                        "type": "string",
                        "description": "Path to .po file (relative to locale dir)",
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of entries per page (default: 20, max: 50)",
                        "default": 20,
                    },
                    "page": {
                        "type": "integer",
                        "description": "Page number, starting from 1 (default: 1)",
                        "default": 1,
                    },
                },
                "required": ["file"],
            },
        ),
        Tool(
            name="status",
            description="Get server status: script path and process ID.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    logger.info(
        "Tool call: %s, arguments:\n%s",
        name,
        json_dumps(arguments, ensure_ascii=False, indent=2),
    )

    if name == "status":
        return [TextContent(
            type="text",
            text=json_dumps({
                "script_path": str(Path(__file__).resolve()),
                "pid": getpid(),
            })
        )]

    elif name == "get_entries_to_translate":
        return await handle_get_entries(arguments)

    elif name == "submit_translations":
        return await handle_submit_translations(arguments)

    elif name == "list_translations":
        return await handle_list_translations(arguments)

    else:
        logger.warning("Unknown tool requested: %s", name)
        return [TextContent(
            type="text",
            text=json_dumps({"error": f"Unknown tool: {name}"})
        )]


async def handle_get_entries(arguments: dict[str, Any]) -> list[TextContent]:
    """
    Handle get_entries_to_translate tool call.

    Arguments:
        file: path to .po file (optional, auto-selects if not provided)
        count: number of entries to return (default 5, max 50)

    Returns JSON with entries array and file stats.
    """
    file_arg = arguments.get("file")
    count = min(arguments.get("count", 5), MAX_ENTRIES_COUNT)
    logger.debug("get_entries: file=%s, count=%d", file_arg, count)

    # If no file specified, find one with fewest untranslated entries
    if file_arg is None:
        stats = get_untranslated_stats()
        if not stats:
            logger.info("All files are fully translated!")
            return [TextContent(
                type="text",
                text=json_dumps({
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
            text=json_dumps({
                "success": False,
                "error": str(e),
            })
        )]

    # Load .po file
    try:
        po = pofile(str(po_path))
    except Exception as e:
        return [TextContent(
            type="text",
            text=json_dumps({
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
    return [TextContent(type="text", text=json_dumps(result, ensure_ascii=False, indent=2))]


async def handle_submit_translations(arguments: dict[str, Any]) -> list[TextContent]:
    """
    Handle submit_translations tool call.

    Arguments:
        file: path to .po file (required)
        translations: list of {msgid, msgstr} or {msgidhash, msgstr} dicts
        overwrite: if False, skip already translated entries (default True)

    Each translation can identify the entry by either msgid (exact match)
    or msgidhash (short hash). Applies translations, runs msgfmt validation,
    returns results.
    """
    file_arg = arguments.get("file")
    translations = arguments.get("translations", [])
    overwrite = arguments.get("overwrite", True)
    logger.debug("submit_translations: file=%s, count=%d, overwrite=%s", file_arg, len(translations), overwrite)

    if not file_arg:
        return [TextContent(
            type="text",
            text=json_dumps({
                "success": False,
                "error": "File parameter is required",
            })
        )]

    if not translations:
        return [TextContent(
            type="text",
            text=json_dumps({
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
            text=json_dumps({
                "success": False,
                "error": str(e),
            })
        )]

    # Load .po file
    try:
        po = pofile(str(po_path))
    except Exception as e:
        return [TextContent(
            type="text",
            text=json_dumps({
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
        msgidhash = trans.get("msgidhash", "")
        msgstr = trans.get("msgstr", "")

        if (not msgid and not msgidhash) or not msgstr:
            continue

        # Find matching entry by msgid or msgidhash
        found = False
        for entry in po:
            # Match by exact msgid or by msgidhash
            if msgid:
                match = (entry.msgid == msgid)
            else:
                match = (compute_msgidhash(entry.msgid) == msgidhash)

            if match:
                found = True
                display_id = entry.msgid[:50] + "..." if len(entry.msgid) > 50 else entry.msgid
                if entry.msgstr and not overwrite:
                    already_translated.append(display_id)
                else:
                    entry.msgstr = msgstr
                    # Remove fuzzy flag if present
                    if "fuzzy" in entry.flags:
                        entry.flags.remove("fuzzy")
                    applied.append(display_id)
                break

        if not found:
            lookup_key = msgid if msgid else f"hash:{msgidhash}"
            not_found.append(lookup_key[:50] + "..." if len(lookup_key) > 50 else lookup_key)

    # Save if any translations were applied
    if applied:
        # Save to temporary file first, validate, then replace original
        temp_path = po_path.with_suffix(".po.tmp")
        try:
            po.save(str(temp_path))
            logger.debug("Saved translations to temp file: %s", temp_path)

            # Run validation on temp file
            try:
                valid, errors = run_msgfmt_check(temp_path)
            except TimeoutExpired:
                logger.error("msgfmt timed out for %s", temp_path)
                valid, errors = False, ["msgfmt validation timed out"]

            if not valid:
                # Validation failed - remove temp file and report error
                logger.warning("Validation failed for %s: %s", file_arg, errors)
                temp_path.unlink(missing_ok=True)
                return [TextContent(
                    type="text",
                    text=json_dumps({
                        "success": False,
                        "error": "Validation failed, changes not applied",
                        "validation_errors": errors,
                        "applied": applied,
                        "not_found": not_found if not_found else None,
                    }, ensure_ascii=False, indent=2)
                )]

            # Validation passed - atomically replace original with temp
            temp_path.replace(po_path)
            logger.info("Saved %d translations to %s", len(applied), file_arg)

        except Exception as e:
            # Clean up temp file on any error
            temp_path.unlink(missing_ok=True)
            raise

        result = {
            "success": True,
            "applied_count": len(applied),
            "applied": applied,
        }

        if not_found:
            result["not_found"] = not_found
        if already_translated:
            result["already_translated"] = already_translated
    else:
        result = {
            "success": False,
            "error": "No translations were applied",
            "not_found": not_found if not_found else None,
            "already_translated": already_translated if already_translated else None,
        }

    return [TextContent(type="text", text=json_dumps(result, ensure_ascii=False, indent=2))]


async def handle_list_translations(arguments: dict[str, Any]) -> list[TextContent]:
    """
    Handle list_translations tool call.

    Arguments:
        file: path to .po file (required)
        count: number of entries per page (default 20, max 50)
        page: page number starting from 1 (default 1)

    Returns JSON with paginated list of {msgid, msgidhash, msgstr} entries.
    """
    file_arg = arguments.get("file")
    count = min(arguments.get("count", 20), MAX_ENTRIES_COUNT)
    page = max(arguments.get("page", 1), 1)  # Ensure page >= 1
    logger.debug("list_translations: file=%s, count=%d, page=%d", file_arg, count, page)

    if not file_arg:
        return [TextContent(
            type="text",
            text=json_dumps({
                "success": False,
                "error": "File parameter is required",
            })
        )]

    # Validate and resolve path securely
    try:
        po_path = validate_po_path(file_arg)
    except PathSecurityError as e:
        return [TextContent(
            type="text",
            text=json_dumps({
                "success": False,
                "error": str(e),
            })
        )]

    # Load .po file
    try:
        po = pofile(str(po_path))
    except Exception as e:
        return [TextContent(
            type="text",
            text=json_dumps({
                "success": False,
                "error": f"Failed to parse .po file: {e}",
            })
        )]

    # Get all entries (excluding metadata entry with empty msgid)
    all_entries = [entry for entry in po if entry.msgid]
    total_entries = len(all_entries)

    # Calculate pagination
    start_idx = (page - 1) * count
    end_idx = start_idx + count
    page_entries = all_entries[start_idx:end_idx]

    # Format entries as simple {msgid, msgidhash, msgstr} dicts
    formatted_entries = [
        {
            "msgid": entry.msgid,
            "msgidhash": compute_msgidhash(entry.msgid),
            "msgstr": entry.msgstr,
        }
        for entry in page_entries
    ]

    # Calculate next page
    total_pages = (total_entries + count - 1) // count  # Ceiling division
    next_page = page + 1 if page < total_pages else None

    relative_path = po_path.relative_to(LOCALE_DIR)

    result = {
        "success": True,
        "file": str(relative_path),
        "entries": formatted_entries,
        "page": page,
        "count": len(formatted_entries),
        "totalEntries": total_entries,
        "totalPages": total_pages,
        "nextPage": next_page,
    }

    logger.info(
        "list_translations: returned %d entries from %s (page %d/%d)",
        len(formatted_entries), relative_path, page, total_pages
    )
    return [TextContent(type="text", text=json_dumps(result, ensure_ascii=False, indent=2))]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio_run(main())
