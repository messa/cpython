#!/usr/bin/env python3
"""Tool for exporting and applying translations to .po files."""

from argparse import ArgumentParser, RawDescriptionHelpFormatter
from pathlib import Path
from re import search, split, DOTALL
from subprocess import run
from sys import exit

import polib


LOCALE_DIR = Path(__file__).parent.parent / "locales" / "cs" / "LC_MESSAGES"


def resolve_po_path(po_file: str) -> Path:
    """Resolve .po file path (relative to locale dir or absolute)."""
    po_path = Path(po_file)
    if not po_path.exists():
        po_path = LOCALE_DIR / po_file
    if not po_path.exists():
        exit(f"Error: File not found: {po_file}")
    return po_path


def cmd_export(args):
    """Export untranslated entries to a template file."""
    po_path = resolve_po_path(args.po_file)
    po = polib.pofile(str(po_path))

    untranslated = po.untranslated_entries()
    total_untranslated = len(untranslated)
    entries_to_export = untranslated[:args.limit]

    # Generate output filename
    relative = po_path.relative_to(LOCALE_DIR)
    output_name = str(relative).replace("/", "_").replace(".po", "_todo.txt")
    output_path = Path(__file__).parent.parent / output_name

    lines = []
    lines.append(f"# Source: {relative}")
    lines.append(f"# Untranslated entries: {total_untranslated} (showing first {len(entries_to_export)})")
    lines.append("")

    for i, entry in enumerate(entries_to_export, 1):
        lines.append(f"### {i}.")
        if entry.occurrences:
            for occ in entry.occurrences[:1]:  # Show first occurrence
                lines.append(f"# {occ[0]}:{occ[1]}")
        lines.append("msgid:")
        lines.append(entry.msgid)
        lines.append("msgstr:")
        lines.append("")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Exported {len(entries_to_export)} entries to: {output_path}")
    print(f"Total untranslated in file: {total_untranslated}")


def cmd_apply(args):
    """Apply translations from a template file to the .po file."""
    po_path = resolve_po_path(args.po_file)
    trans_path = Path(args.translations_file)
    if not trans_path.exists():
        trans_path = Path(__file__).parent.parent / args.translations_file
    if not trans_path.exists():
        exit(f"Error: Translations file not found: {args.translations_file}")

    # Parse translations file
    content = trans_path.read_text(encoding="utf-8")

    # Split by ### N. pattern
    entries_raw = split(r"\n### \d+\.\n", content)[1:]  # Skip header

    translations = []
    for entry_raw in entries_raw:
        # Parse msgid and msgstr
        match = search(
            r"(?:^#[^\n]*\n)?msgid:\n(.*?)\nmsgstr:\n(.*?)(?:\n\n|\n?$)",
            entry_raw,
            DOTALL
        )
        if match:
            msgid = match.group(1).strip()
            msgstr = match.group(2).strip()
            if msgid and msgstr:  # Only include if both are present
                translations.append((msgid, msgstr))

    if not translations:
        print("No translations found in the file.")
        return

    # Apply translations
    po = polib.pofile(str(po_path))
    applied = 0

    for msgid, msgstr in translations:
        for entry in po:
            if entry.msgid == msgid:
                if not entry.msgstr:  # Only update if not already translated
                    entry.msgstr = msgstr
                    applied += 1
                    print(f"  Applied translation for: {msgid[:50]}...")
                break

    if applied > 0:
        po.save()
        print(f"\nApplied {applied} translations to {po_path}")
        # Run syntax check
        run_msgfmt_check(po_path)
    else:
        print("No translations were applied.")


def cmd_status(args):
    """Show translation status of a .po file."""
    po_path = resolve_po_path(args.po_file)
    po = polib.pofile(str(po_path))

    total = len(po)
    translated = len(po.translated_entries())
    untranslated = len(po.untranslated_entries())
    fuzzy = len(po.fuzzy_entries())
    percent = (translated / total * 100) if total > 0 else 0

    print(f"File: {po_path}")
    print(f"Total: {total}")
    print(f"Translated: {translated} ({percent:.1f}%)")
    print(f"Untranslated: {untranslated}")
    print(f"Fuzzy: {fuzzy}")


def run_msgfmt_check(po_path: Path) -> bool:
    """Run msgfmt --check on a .po file. Returns True if OK, False if errors."""
    result = run(
        ["msgfmt", "--check", "-o", "/dev/null", str(po_path)],
        capture_output=True,
        text=True
    )
    # Filter out warnings, only show errors
    errors = [line for line in result.stderr.splitlines() if "warning:" not in line]
    if errors:
        print("\nmsgfmt errors:")
        for error in errors:
            print(f"  {error}")
        return False
    print("\nmsgfmt --check: OK")
    return True


def cmd_check(args):
    """Check .po file syntax using msgfmt."""
    po_path = resolve_po_path(args.po_file)
    success = run_msgfmt_check(po_path)
    if not success:
        raise SystemExit(1)


def main():
    parser = ArgumentParser(
        description="Tool for exporting and applying translations to .po files.",
        formatter_class=RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s export tutorial/interactive.po
  %(prog)s export tutorial/interactive.po --limit 20
  %(prog)s apply tutorial/interactive.po tutorial_interactive_todo.txt
  %(prog)s status tutorial/whatnow.po
  %(prog)s check tutorial/whatnow.po
"""
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Export command
    export_parser = subparsers.add_parser(
        "export",
        help="Export untranslated entries to a template file"
    )
    export_parser.add_argument("po_file", help="Path to .po file (relative to locale dir or absolute)")
    export_parser.add_argument(
        "--limit", "-n",
        type=int,
        default=15,
        help="Maximum number of entries to export (default: 15)"
    )
    export_parser.set_defaults(func=cmd_export)

    # Apply command
    apply_parser = subparsers.add_parser(
        "apply",
        help="Apply translations from a template file"
    )
    apply_parser.add_argument("po_file", help="Path to .po file")
    apply_parser.add_argument("translations_file", help="Path to translations file")
    apply_parser.set_defaults(func=cmd_apply)

    # Status command
    status_parser = subparsers.add_parser(
        "status",
        help="Show translation status of a .po file"
    )
    status_parser.add_argument("po_file", help="Path to .po file")
    status_parser.set_defaults(func=cmd_status)

    # Check command
    check_parser = subparsers.add_parser(
        "check",
        help="Check .po file syntax using msgfmt"
    )
    check_parser.add_argument("po_file", help="Path to .po file")
    check_parser.set_defaults(func=cmd_check)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
