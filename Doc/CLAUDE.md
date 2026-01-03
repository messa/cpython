# Czech Translation of Python Documentation

Note: "Translate a .po file" means adding Czech translations to msgstr fields using the workflow below, not compiling .po to .mo.

## Translation workflow using po_tool.py

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

## Check .po files for syntax errors

```bash
# Check single file
scripts/po_tool.py check tutorial/whatnow.po

# Check all files
find locales/cs/LC_MESSAGES -name "*.po" -exec msgfmt --check -o /dev/null {} \; 2>&1 | grep -v "warning:"
```

Common issues:
- **Mismatched quotes**: Czech uses `„` (U+201E) for opening and `"` (U+201C) for closing. ASCII `"` inside msgstr breaks parsing.
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
