#!/usr/bin/env python3
"""Add Czech translations to tutorial/interactive.po."""

from pathlib import Path
import polib


# Czech translations for the untranslated entries
TRANSLATIONS = {
    # Entry at line 26 (rst:7)
    "Some versions of the Python interpreter support editing of the current input line and history substitution, similar to facilities found in the Korn shell and the GNU Bash shell.  This is implemented using the `GNU Readline`_ library, which supports various styles of editing.  This library has its own documentation which we won't duplicate here.":
    "Některé verze interpretu Pythonu podporují úpravy aktuálního vstupního řádku a nahrazování z historie, podobně jako v shellu Korn nebo GNU Bash. Toto je implementováno pomocí knihovny `GNU Readline`_, která podporuje různé styly editace. Tato knihovna má vlastní dokumentaci, kterou zde nebudeme duplikovat.",

    # Entry at line 39 (rst:19)
    "Completion of variable and module names is :ref:`automatically enabled <rlcompleter-config>` at interpreter startup so that the :kbd:`Tab` key invokes the completion function; it looks at Python statement names, the current local variables, and the available module names.  For dotted expressions such as ``string.a``, it will evaluate the expression up to the final ``'.'`` and then suggest completions from the attributes of the resulting object.  Note that this may execute application-defined code if an object with a :meth:`~object.__getattr__` method is part of the expression.  The default configuration also saves your history into a file named :file:`.python_history` in your user directory. The history will be available again during the next interactive interpreter session.":
    "Doplňování názvů proměnných a modulů je :ref:`automaticky povoleno <rlcompleter-config>` při spuštění interpretu, takže klávesa :kbd:`Tab` vyvolá funkci doplňování; ta prohledává názvy příkazů Pythonu, aktuální lokální proměnné a dostupné názvy modulů. Pro tečkové výrazy jako ``string.a`` vyhodnotí výraz až po poslední ``'.'`` a poté navrhne doplnění z atributů výsledného objektu. Všimněte si, že toto může spustit kód definovaný aplikací, pokud je součástí výrazu objekt s metodou :meth:`~object.__getattr__`. Výchozí konfigurace také ukládá vaši historii do souboru s názvem :file:`.python_history` ve vašem uživatelském adresáři. Historie bude opět k dispozici během další interaktivní relace interpretu.",

    # Entry at line 58 (rst:38)
    "This facility is an enormous step forward compared to earlier versions of the interpreter; however, some wishes are left: It would be nice if the proper indentation were suggested on continuation lines (the parser knows if an :data:`~token.INDENT` token is required next).  The completion mechanism might use the interpreter's symbol table.  A command to check (or even suggest) matching parentheses, quotes, etc., would also be useful.":
    "Tato funkce je obrovským krokem vpřed ve srovnání s dřívějšími verzemi interpretu; nicméně některá přání zůstávají: Bylo by hezké, kdyby na pokračovacích řádcích bylo navrhováno správné odsazení (parser ví, zda je jako další vyžadován token :data:`~token.INDENT`). Mechanismus doplňování by mohl využívat tabulku symbolů interpretu. Užitečný by byl také příkaz pro kontrolu (nebo dokonce navrhování) odpovídajících závorek, uvozovek atd.",

    # Entry at line 69 (rst:45)
    "One alternative enhanced interactive interpreter that has been around for quite some time is IPython_, which features tab completion, object exploration and advanced history management.  It can also be thoroughly customized and embedded into other applications.  Another similar enhanced interactive environment is bpython_.":
    "Jedním z alternativních vylepšených interaktivních interpretů, který existuje už poměrně dlouho, je IPython_, který nabízí doplňování tabulátorem, prozkoumávání objektů a pokročilou správu historie. Lze jej také důkladně přizpůsobit a vložit do jiných aplikací. Dalším podobným vylepšeným interaktivním prostředím je bpython_.",
}


def main():
    po_path = Path(__file__).parent.parent / "locales" / "cs" / "LC_MESSAGES" / "tutorial" / "interactive.po"

    print(f"Loading: {po_path}")
    po = polib.pofile(str(po_path))

    print(f"Before: {len(po.translated_entries())} translated, {len(po.untranslated_entries())} untranslated")

    translated_count = 0
    for entry in po.untranslated_entries():
        if entry.msgid in TRANSLATIONS:
            entry.msgstr = TRANSLATIONS[entry.msgid]
            translated_count += 1
            print(f"  Translated entry at line {entry.linenum}")

    po.save()

    # Reload to verify
    po = polib.pofile(str(po_path))
    print(f"After: {len(po.translated_entries())} translated, {len(po.untranslated_entries())} untranslated")
    print(f"Added {translated_count} translations")


if __name__ == "__main__":
    main()
