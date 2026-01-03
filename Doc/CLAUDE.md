# Czech Translation of Python Documentation

## Check .po files for syntax errors

```bash
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
