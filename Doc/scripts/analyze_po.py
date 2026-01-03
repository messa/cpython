#!/usr/bin/env python3
"""Analyze .po files to find untranslated ones."""

from pathlib import Path
import polib


def analyze_po_files(locale_dir: Path):
    """Analyze all .po files in the locale directory."""
    results = []

    for po_path in sorted(locale_dir.rglob("*.po")):
        try:
            po = polib.pofile(str(po_path))

            total = len(po)
            translated = len(po.translated_entries())
            untranslated = len(po.untranslated_entries())
            fuzzy = len(po.fuzzy_entries())

            # Calculate file size
            size = po_path.stat().st_size

            results.append({
                'path': po_path,
                'relative': po_path.relative_to(locale_dir),
                'total': total,
                'translated': translated,
                'untranslated': untranslated,
                'fuzzy': fuzzy,
                'size': size,
                'percent_done': (translated / total * 100) if total > 0 else 0,
            })
        except Exception as e:
            print(f"Error processing {po_path}: {e}")

    return results


def main():
    locale_dir = Path(__file__).parent.parent / "locales" / "cs" / "LC_MESSAGES"

    results = analyze_po_files(locale_dir)

    # Find completely untranslated files (0% translated) sorted by size
    untranslated = [r for r in results if r['translated'] == 0 and r['total'] > 0]
    untranslated.sort(key=lambda x: x['size'])

    print("=" * 80)
    print("Completely untranslated files (sorted by size):")
    print("=" * 80)
    for r in untranslated[:20]:
        print(f"{r['size']:>8} bytes | {r['total']:>3} entries | {r['relative']}")

    print()
    print("=" * 80)
    print("Partially translated files (sorted by % done):")
    print("=" * 80)
    partial = [r for r in results if 0 < r['percent_done'] < 100]
    partial.sort(key=lambda x: x['percent_done'])
    for r in partial[:20]:
        print(f"{r['percent_done']:>5.1f}% | {r['translated']:>3}/{r['total']:>3} | {r['size']:>8} bytes | {r['relative']}")


if __name__ == "__main__":
    main()
