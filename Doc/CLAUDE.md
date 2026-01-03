# Czech Translation of Python Documentation

Note: "Translate a .po file" means adding Czech translations to msgstr fields using the workflow below, not compiling .po to .mo.

## Translation workflow using `po_tool.py`

All commands should be run from the `Doc/` directory (the directory where this CLAUDE.md file is located).

```bash
# 1. Find files to translate (sorted by size, shows untranslated files)
scripts/analyze_po.py

# 2. Check status of a specific file
scripts/po_tool.py status tutorial/whatnow.po

# 2b. Show detailed contents of a .po file (optional)
scripts/show_po.py tutorial/whatnow.po

# 3. Export untranslated entries to a template file
scripts/po_tool.py export tutorial/whatnow.po           # exports first 15
scripts/po_tool.py export tutorial/whatnow.po -n 20     # exports first 20

# 4. Fill in translations in the generated *_todo.txt file

# 5. Apply translations back to .po file (also runs msgfmt --check)
scripts/po_tool.py apply tutorial/whatnow.po tutorial_whatnow_todo.txt

# 6. Build and verify
make html SPHINXOPTS="-D language=cs"

# 7. Delete the temporary *_todo.txt file (do not commit it)
rm tutorial_whatnow_todo.txt
```

## Alternative: Using po-translator agent

For automated translation using Claude, use the `po-translator` agent:

```
/agents po-translator
```

Or ask Claude to "use po-translator to translate some entries".

The agent uses MCP server (`scripts/po_mcp_server.py`) with two tools:
- `get_entries_to_translate` - fetches untranslated entries with context
- `submit_translations` - applies translations with validation

The MCP server requires `mcp` and `polib` packages:
```bash
make _ensure-package PACKAGE=polib
make _ensure-package PACKAGE=mcp
```

## Translation guidelines

See `/.claude/agents/po-translator.md` for detailed translation rules:
- Which terms to translate vs. keep in English
- Czech language conventions
- RST markup and format string handling

## Check .po files for syntax errors

```bash
# Check single file
scripts/po_tool.py check tutorial/whatnow.po

# Check all files
find locales/cs/LC_MESSAGES -name "*.po" -exec msgfmt --check -o /dev/null {} \; 2>&1 | grep -v "warning:"
```

Common issues:
- **Quotes in translations**: Czech uses `„` (U+201E opening) and `"` (U+201C closing).
  - **Via polib/MCP server**: Use either Czech quotes or ASCII `"` - polib handles escaping automatically.
  - **Direct .po file editing**: ASCII `"` must be escaped as `\"`. Czech quotes need no escaping.
- **Format string mismatch**: When msgid has `#, python-format` but contains `%` as literal text (e.g., `35%`, `99%`), change to `#, no-python-format`.
- **RST inline markup**: Literals like `` ``close`` `` must have spaces around them. `` ``close``nete `` breaks RST.
- **Split references**: RST roles like `:exc:`, `:meth:`, `:class:` must not be split across lines.

## Install sphinx-intl

```bash
make _ensure-package PACKAGE=sphinx-intl
```

## Build Czech documentation

```bash
# Create venv (first time only)
make venv

# Build HTML with Czech translation
make html SPHINXOPTS="-D language=cs"
```

Output will be in `build/html/`.

To build without treating warnings as errors (useful for debugging):
```bash
make html SPHINXOPTS="-D language=cs" SPHINXERRORHANDLING=""
```
