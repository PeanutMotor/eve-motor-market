"""Welche Preise stecken wirklich in der Datenbank - und von welchem Hub?

NUTZERFRAGE 06.11.2026: "my blueprints profit per Unit, woher kommt das?
wo wird vergleicht genommen? immer Jita oder oben gewaehlter Hub?"

Die Antwort steht im Code (emm437): Einkauf UND Verkauf kommen aus dem
MARKET SCAN, und stammt der nicht vom Hub oben, wird gar nicht gerechnet.
Nur: ob das im Einzelfall auch passiert, sieht man von aussen nicht - die
Preise liegen in `ledger.db`, und die ist ein halbes Gigabyte gross.

DIESES WERKZEUG liest die paar Zeilen, auf die es ankommt, und schreibt
sie als Text heraus. Es AENDERT NICHTS (nur lesende Abfragen).

AUFRUF:
    python werkzeuge\\pruefe_scan_quelle.py
    python werkzeuge\\pruefe_scan_quelle.py --item 12058
"""
import argparse
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eve_trader import config                                   # noqa: E402


def _isk(v):
    return "-" if not v else f"{float(v):,.0f}".replace(",", "'")


# DIE AUSGABE IN EINE DATEI zu schreiben ist NICHT Aufgabe dieses
# Skripts - die .bat leitet um ("> berichte\\scan_quelle.txt 2>&1").
# Erster Versuch war eine Doppelausgabe hier drin; sie fing aber genau
# den Fall NICHT, auf den es ankommt: stirbt das Skript VOR dem
# Dateioeffnen (Importfehler, fehlende Datenbank), entsteht gar keine
# Datei und der Fehler steht nur in einem Fenster, das sich schliesst.
# Die Umleitung in der .bat faengt auch den.
def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--item", type=int, action="append", default=None,
                   help="type_id, dessen Preise je Quelle gezeigt werden "
                        "(mehrfach moeglich)")
    a = p.parse_args()

    db = config.db_path()
    print(f"Datenbank: {db}")
    print(f"Groesse:   {os.path.getsize(db) / 1e6:.0f} MB\n")

    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as c:
        c.row_factory = sqlite3.Row

        # (1) DAS SCAN-LABEL. Genau dieser Wert wird mit dem Hub oben
        # verglichen; stimmen sie nicht ueberein, verweigert die
        # Blaupausen-Seite die Rechnung und verlangt einen neuen Scan.
        print("--- scan_meta (hieran haengt der Hub-Abgleich) ---")
        try:
            for r in c.execute("SELECT k, v FROM scan_meta ORDER BY k"):
                print(f"  {r['k']:14} = {r['v']!r}")
        except sqlite3.Error as e:
            print(f"  Tabelle nicht lesbar: {e}")

        # (2) WAS LIEGT WIRKLICH DRIN. Der Scan legt je Handelsplatz eine
        # eigene Zeilengruppe ab. Stehen hier mehrere Quellen, ist die
        # entscheidende Frage, welche die Blaupausen-Seite benutzt.
        print("\n--- market_snapshot: Preise je Quelle ---")
        try:
            for r in c.execute(
                    "SELECT COALESCE(source,'(ohne Quelle)') AS q, "
                    "COUNT(*) AS n, MAX(updated_at) AS neu, "
                    "MIN(updated_at) AS alt FROM market_snapshot "
                    "GROUP BY q ORDER BY n DESC"):
                print(f"  {r['q']:34} {r['n']:7} Preise   "
                      f"neuester {r['neu']}   aeltester {r['alt']}")
        except sqlite3.Error as e:
            print(f"  Tabelle nicht lesbar: {e}")

        # (3) MARKTTIEFE JE QUELLE. Das ist die Zahl, an der sich
        # entscheidet, ab wann ein "Gewinn" nur noch eine Fantasie ist:
        # steht hinter einem Preis eine einzige Order mit zwei Stueck,
        # ist das kein Markt, sondern ein Angebot.
        print("\n--- Markttiefe: wie viele Stueck stehen je Preis dahinter ---")
        try:
            for r in c.execute(
                    "SELECT COALESCE(source,'(ohne)') AS q, COUNT(*) AS n, "
                    "SUM(CASE WHEN sell_min>0 THEN 1 ELSE 0 END) AS mit_preis, "
                    "SUM(CASE WHEN sell_min>0 AND COALESCE(sell_qty,0)<=2 "
                    "         THEN 1 ELSE 0 END) AS tief2, "
                    "SUM(CASE WHEN sell_min>0 AND COALESCE(sell_qty,0)<=5 "
                    "         THEN 1 ELSE 0 END) AS tief5, "
                    "SUM(CASE WHEN sell_min>0 AND COALESCE(sell_qty,0)<=20 "
                    "         THEN 1 ELSE 0 END) AS tief20 "
                    "FROM market_snapshot GROUP BY q ORDER BY n DESC"):
                _mp = r["mit_preis"] or 0
                def _q(v):
                    return f"{v or 0:6} ({(v or 0) / _mp * 100:4.1f} %)" if _mp \
                        else f"{v or 0:6}"
                print(f"  {r['q']}")
                print(f"      Zeilen {r['n']:6}   davon mit Verkaufspreis "
                      f"{_mp:6}")
                print(f"      hoechstens  2 Stueck im Angebot: {_q(r['tief2'])}")
                print(f"      hoechstens  5 Stueck im Angebot: {_q(r['tief5'])}")
                print(f"      hoechstens 20 Stueck im Angebot: {_q(r['tief20'])}")
        except sqlite3.Error as e:
            print(f"  nicht lesbar: {e}")

        # (4) EINZELNE ITEMS. Hier sieht man schwarz auf weiss, ob ein
        # T2-Modul am Nullsec-Hub ueberhaupt einen Verkaufspreis hat -
        # ohne den rutscht jede Gewinnrechnung tief ins Minus, und das
        # ist dann kein Rechenfehler, sondern "dort kauft das niemand".
        for tid in (a.item or []):
            print(f"\n--- type_id {tid} je Quelle ---")
            try:
                rows = list(c.execute(
                    "SELECT COALESCE(source,'(ohne Quelle)') AS q, sell_min, "
                    "buy_max, sell_qty, updated_at FROM market_snapshot "
                    "WHERE type_id=? ORDER BY q", (tid,)))
            except sqlite3.Error as e:
                print(f"  nicht lesbar: {e}")
                continue
            if not rows:
                print("  in KEINER Quelle vorhanden")
            for r in rows:
                print(f"  {r['q']:34} sell {_isk(r['sell_min']):>16}  "
                      f"buy {_isk(r['buy_max']):>16}  "
                      f"Menge {r['sell_qty'] or 0:>8}  {r['updated_at']}")

    print("\nFertig. Es wurde nichts geaendert (nur gelesen).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
