#!/usr/bin/env python3
"""
Machine Translation Script for .po Files
==========================================

This script translates .po files from English to Czech using Google Translate API.

Requirements:
    pip install polib deep-translator

Usage:
    python translate_po_files.py <directory_with_po_files>

Example:
    python translate_po_files.py Doc/locales/cs/LC_MESSAGES/library/

Features:
    - Translates all untranslated strings (empty msgstr)
    - Handles long texts by splitting into chunks
    - Implements retry logic and rate limiting
    - Shows progress during translation
    - Saves after each file

Note:
    This script requires internet access to Google Translate.
    Run this on a machine with unrestricted internet access.
"""

import os
import sys
import time
import polib
from deep_translator import GoogleTranslator

def translate_text(text, translator, max_retries=3):
    """
    Translate text with retry logic and chunking for long texts.
    
    Args:
        text: Text to translate
        translator: GoogleTranslator instance
        max_retries: Number of retry attempts
        
    Returns:
        Translated text or original text if translation fails
    """
    if not text or not text.strip():
        return text
    
    for attempt in range(max_retries):
        try:
            # Google Translate has a 5000 character limit
            if len(text) > 4500:
                # Split into chunks at newlines
                chunks = []
                current = ""
                for line in text.split('\n'):
                    if len(current) + len(line) + 1 > 4500:
                        if current:
                            chunks.append(current)
                        current = line
                    else:
                        if current:
                            current += '\n' + line
                        else:
                            current = line
                if current:
                    chunks.append(current)
                
                # Translate each chunk
                translated_chunks = []
                for chunk in chunks:
                    translated = translator.translate(chunk)
                    translated_chunks.append(translated)
                    time.sleep(0.2)  # Rate limiting
                
                return '\n'.join(translated_chunks)
            else:
                translated = translator.translate(text)
                time.sleep(0.1)  # Rate limiting to avoid hitting API limits
                return translated
                
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"    Retry {attempt + 1}/{max_retries} after {wait_time}s (error: {str(e)[:50]})")
                time.sleep(wait_time)
            else:
                print(f"    Failed after {max_retries} attempts: {str(e)[:50]}")
                return text  # Return original text if all retries fail
    
    return text

def translate_po_file(po_path, translator):
    """
    Translate all untranslated strings in a .po file.
    
    Args:
        po_path: Path to the .po file
        translator: GoogleTranslator instance
        
    Returns:
        True if successful, False otherwise
    """
    filename = os.path.basename(po_path)
    print(f"\nProcessing: {filename}")
    
    try:
        po = polib.pofile(po_path)
    except Exception as e:
        print(f"  ERROR loading file: {e}")
        return False
    
    translated_count = 0
    total_count = 0
    
    # Count untranslated entries
    for entry in po:
        if entry.msgid and not entry.msgstr:
            total_count += 1
    
    if total_count == 0:
        print(f"  All strings already translated!")
        return True
    
    print(f"  Found {total_count} untranslated strings")
    
    # Translate each entry
    for idx, entry in enumerate(po, 1):
        if entry.msgid and not entry.msgstr:
            try:
                # Show progress
                if total_count > 10:
                    print(f"  Translating {idx}/{total_count}...", end='\r')
                
                # Translate
                translated = translate_text(entry.msgid, translator)
                if translated and translated != entry.msgid:
                    entry.msgstr = translated
                    translated_count += 1
                    
            except Exception as e:
                print(f"\n  ERROR translating entry {idx}: {e}")
                continue
    
    # Save the file
    try:
        po.save(po_path)
        print(f"  ✓ Translated {translated_count}/{total_count} strings")
        return True
    except Exception as e:
        print(f"  ERROR saving file: {e}")
        return False

def main():
    """Main function to orchestrate translation."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    po_dir = sys.argv[1]
    
    if not os.path.isdir(po_dir):
        print(f"ERROR: {po_dir} is not a directory")
        sys.exit(1)
    
    # Initialize translator
    print("Initializing Google Translator (en -> cs)...")
    try:
        translator = GoogleTranslator(source='en', target='cs')
    except Exception as e:
        print(f"ERROR initializing translator: {e}")
        print("\nMake sure you have installed: pip install deep-translator")
        sys.exit(1)
    
    # Find all .po files
    po_files = sorted([f for f in os.listdir(po_dir) if f.endswith('.po')])
    
    if not po_files:
        print(f"No .po files found in {po_dir}")
        sys.exit(1)
    
    print(f"\nFound {len(po_files)} .po files to process")
    print("=" * 70)
    
    start_time = time.time()
    success_count = 0
    
    for i, po_file in enumerate(po_files, 1):
        print(f"\n[{i}/{len(po_files)}]", end=' ')
        po_path = os.path.join(po_dir, po_file)
        if translate_po_file(po_path, translator):
            success_count += 1
    
    # Summary
    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print(f"✓ Successfully processed {success_count}/{len(po_files)} files")
    print(f"  Time elapsed: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
    print("=" * 70)

if __name__ == "__main__":
    main()
