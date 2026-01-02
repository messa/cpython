# Czech Translation Guide for Python Documentation

This directory contains Czech translations for the Python library documentation.

## Translation Status

- **Total .po files**: 330
- **Total strings**: ~38,600
- **Current status**: Untranslated (template files)

## How to Translate

### Option 1: Automated Machine Translation (Recommended for initial draft)

A translation script is provided: `translate_po_files.py`

**Requirements:**
```bash
pip install polib deep-translator
```

**Usage:**
```bash
python translate_po_files.py Doc/locales/cs/LC_MESSAGES/library/
```

**Note:** This requires unrestricted internet access to Google Translate API. The script:
- Translates all untranslated strings
- Handles long texts automatically
- Shows progress
- Takes approximately 2-4 hours for all files

### Option 2: Professional Translation Tools

For better quality translations, use professional tools:

1. **Weblate** (https://weblate.org/)
   - Web-based collaborative translation platform
   - Used by many open-source projects
   - Supports .po files natively

2. **POEdit** (https://poedit.net/)
   - Desktop application for .po file editing
   - Has built-in translation memory
   - Available for Windows, Mac, Linux

3. **Transifex** (https://www.transifex.com/)
   - Cloud-based translation platform
   - Good for team collaboration

### Option 3: Manual Translation

Edit .po files directly. Each entry has this format:

```po
#: reference/location.rst:123
msgid "English text to translate"
msgstr ""  # Add Czech translation here
```

## File Structure

```
Doc/locales/cs/LC_MESSAGES/library/
├── abc.po              # Abstract Base Classes
├── argparse.po         # Command-line parsing
├── asyncio.po          # Asynchronous I/O
├── ...                 # (330 files total)
└── zoneinfo.po         # Timezone information
```

## Building Documentation with Translations

After translating, compile .po files to .mo files:

```bash
cd Doc
make gettext
msgfmt -o library/abc.mo library/abc.po  # For each file
# Or use the Makefile if available
```

## Translation Guidelines

1. **Preserve special markup**: Keep `:mod:`, `:class:`, `:pep:`, etc. unchanged
2. **Keep code examples**: Don't translate code blocks
3. **Technical terms**: Be consistent with established Czech Python terminology
4. **Review**: Machine translations need human review for accuracy

## Getting Help

- Python Czech translation team: (contact info)
- General Python translation: https://github.com/python/python-docs-cs
- Translation guide: https://devguide.python.org/documentation/translating/

## License

Translations are distributed under the same license as Python documentation (PSF License).
