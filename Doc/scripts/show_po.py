#!/usr/bin/env python3
"""Show details of a .po file including untranslated entries."""

from pathlib import Path
from sys import argv, exit

import polib


def show_po_file(po_path: Path):
    """Show details of a .po file."""
    po = polib.pofile(str(po_path))

    print(f"File: {po_path}")
    print(f"Total entries: {len(po)}")
    print(f"Translated: {len(po.translated_entries())}")
    print(f"Untranslated: {len(po.untranslated_entries())}")
    print(f"Fuzzy: {len(po.fuzzy_entries())}")
    print()

    print("=" * 80)
    print("TRANSLATED ENTRIES:")
    print("=" * 80)
    for i, entry in enumerate(po.translated_entries(), 1):
        print(f"\n--- Entry {i} (line {entry.linenum}) ---")
        if entry.comment:
            print(f"# {entry.comment}")
        if entry.tcomment:
            print(f"#. {entry.tcomment}")
        print(f"msgid: {repr(entry.msgid[:100])}{'...' if len(entry.msgid) > 100 else ''}")
        print(f"msgstr: {repr(entry.msgstr[:100])}{'...' if len(entry.msgstr) > 100 else ''}")

    print()
    print("=" * 80)
    print("UNTRANSLATED ENTRIES:")
    print("=" * 80)
    for i, entry in enumerate(po.untranslated_entries(), 1):
        print(f"\n--- Entry {i} (line {entry.linenum}) ---")
        if entry.comment:
            print(f"# {entry.comment}")
        if entry.tcomment:
            print(f"#. {entry.tcomment}")
        if entry.occurrences:
            for occ in entry.occurrences:
                print(f"#: {occ[0]}:{occ[1]}")
        print(f"msgid:")
        print(entry.msgid)
        print(f"\nmsgstr: (empty)")

    if po.fuzzy_entries():
        print()
        print("=" * 80)
        print("FUZZY ENTRIES:")
        print("=" * 80)
        for i, entry in enumerate(po.fuzzy_entries(), 1):
            print(f"\n--- Entry {i} (line {entry.linenum}) ---")
            print(f"msgid: {repr(entry.msgid[:100])}")
            print(f"msgstr: {repr(entry.msgstr[:100])}")


def main():
    if len(argv) < 2:
        print("Usage: show_po.py <po_file>")
        exit(1)

    po_path = Path(argv[1])
    if not po_path.exists():
        # Try relative to locales
        po_path = Path(__file__).parent.parent / "locales" / "cs" / "LC_MESSAGES" / argv[1]

    if not po_path.exists():
        exit(f"Error: File not found: {po_path}")

    show_po_file(po_path)


if __name__ == "__main__":
    main()
