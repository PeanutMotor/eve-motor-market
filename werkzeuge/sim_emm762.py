"""SIMULATION emm762: WANN VERSTUMMT DIE SCHRUMPF-WARNUNG WIRKLICH?

ANLASS (Nutzer 29.10.2026, 18:50): "hart gesperrt ist okey, aber die
warnung scheint selten nicht da zu sein". Die Sperre des
Einkaufslisten-Knopfs soll bleiben (emm476 hat am 08.10. einen
Fehlkauf verhindert) - die Frage ist, warum die WARNUNG so selten
weggeht.

SEIN STAND, gemessen in settings.json (29.10., 18:49):
    Leziris Lezflow   ok 1445, letzte 172, seit 23 min   KLEIN
    alle anderen 9 Charaktere ok

DIE REGEL IN `bestand_schrumpf` (emm744):
    _klein = ok >= 50 and n < ok * 0.7
    if letzte != n or seit <= 0: seit = jetzt      # <-- Uhr zurueck
    if jetzt - seit >= 7200: n wird die neue Wahrheit

Die Uhr startet also bei JEDER ANDEREN ZAHL neu. Diese Simulation
fragt: wie lange steht die Warnung bei einem Charakter, dessen Abruf
(a) stabil klein bleibt und (b) klein bleibt, aber um ein paar Zeilen
schwankt - der Fall vom 28.10. (Peanut Motor 1859 -> 582, kein
ESI-Fehler, Material NICHT weg).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eve_trader.lagerorte import (bestand_schrumpf, SCHRUMPF_BAND,
                                  SCHRUMPF_BAND_MIN,
                                  SCHRUMPF_BESTAETIGUNG_SEK)

FEHLER = []


def lauf(name, folge, schritt_s=1800.0, start=1_000_000.0):
    """Eine Abrufreihe durchspielen -> (Warnungen, erster stiller Lauf).

    `folge`: die Asset-Zeilenzahlen, einer je Aktualisierung.
    `schritt_s`: Abstand zwischen zwei Aktualisierungen (er laedt die
    Seite etwa halbstuendlich neu; ESI cacht ~1 h).
    """
    stand = {name: {"ok": folge[0], "letzte": folge[0], "seit": 0.0}}
    jetzt = start
    warnungen = 0
    still_nach = None
    for i, n in enumerate(folge[1:], start=1):
        jetzt += schritt_s
        warn, stand = bestand_schrumpf({name: n}, stand, jetzt=jetzt)
        if warn:
            warnungen += 1
        elif still_nach is None:
            still_nach = (jetzt - start) / 3600.0
    return warnungen, still_nach, stand


print("=" * 70)
print("SIM emm762 - Schrumpf-Warnung: wann verstummt sie?")
print(f"Bestaetigungsfrist: {SCHRUMPF_BESTAETIGUNG_SEK / 3600:.0f} h")
print("=" * 70)

# --- A: STABIL KLEIN (sein Lezflow: alles weggeschoben, Charakter ruht) --
# 1445 -> 172, danach bleibt 172 exakt stehen. 8 Aktualisierungen a 30 min.
folge_a = [1445] + [172] * 8
w_a, still_a, _ = lauf("Leziris Lezflow", folge_a)
print(f"\nA  STABIL KLEIN   1445 -> 172 (8x exakt 172, alle 30 min)")
print(f"   Warnungen: {w_a} von 8   ->  still nach {still_a} h")
if still_a is None or still_a > 2.5:
    FEHLER.append("A: stabile kleine Zahl verstummt nicht nach ~2 h")

# --- B: KLEIN, ABER SCHWANKEND (der Fall vom 28.10.) -------------------
# Peanut Motor 1859 -> 582. Ein gekuerzter Abruf liefert NICHT jedes Mal
# dieselbe Zeilenzahl: der Charakter baut, Jobs liefern ab, Stacks
# wachsen und schrumpfen. Schon +-1 Zeile genuegt der Regel "letzte != n".
folge_b = [1859, 582, 584, 581, 585, 583, 586, 582, 584]
w_b, still_b, stand_b = lauf("Peanut Motor", folge_b)
print(f"\nB  SCHWANKEND     1859 -> 582+-2 (8 Abrufe, alle 30 min = 4 h)")
print(f"   Warnungen: {w_b} von 8   ->  still nach {still_b} h")
print(f"   Stand danach: {stand_b['Peanut Motor']}")
print(f"   (vor emm762: 8 von 8, nie still - jede einzelne Zeile")
print(f"    Abweichung warf die Uhr zurueck)")
if still_b is None or still_b > 2.5:
    FEHLER.append("B: der schwankende Abruf verstummt immer noch nicht")

# --- C: EINE ABWEICHUNG KURZ VOR ABLAUF -------------------------------
# Vor emm762 warf schon +1 Zeile die Uhr komplett zurueck. Jetzt bleibt
# sie im Band und die Bestaetigung laeuft normal durch.
folge_c = [1859] + [582] * 3 + [583] + [582] * 4
w_c, still_c, _ = lauf("Peanut Motor", folge_c)
print(f"\nC  EINE ABWEICHUNG kurz vor Ablauf (582,582,582,583,582...)")
print(f"   Warnungen: {w_c} von 8   ->  still nach {still_c} h")
if still_c is None or still_c > 2.5:
    FEHLER.append("C: +1 Zeile sperrt die Bestaetigung immer noch")

# --- E: EIN WEITERER EINBRUCH MUSS DIE UHR SEHR WOHL ZURUECKWERFEN -----
# Die Gegenrichtung: das Band darf die Warnung nicht verharmlosen. Faellt
# der Abruf nach einer Stunde NOCHMALS deutlich, ist das ein neuer
# Verdachtsfall - die Frist beginnt von vorn.
folge_e = [1859] + [582] * 2 + [300] * 2
w_e, still_e, _ = lauf("Peanut Motor", folge_e)
print(f"\nE  WEITERER EINBRUCH  1859 -> 582, 582 -> 300, 300")
print(f"   Warnungen: {w_e} von 4   ->  still nach {still_e} h")
if w_e != 4 or still_e is not None:
    FEHLER.append("E: ein weiterer Einbruch hat die Uhr nicht zurueckgeworfen")

# --- F: ALT-STAND OHNE `basis` (Rueckwaertsvertraeglichkeit) -----------
_alt_f = {"Peanut Motor": {"ok": 1859, "letzte": 582, "seit": 1_000_000.0}}
_w_f, _st_f = bestand_schrumpf({"Peanut Motor": 582}, _alt_f,
                               jetzt=1_001_800.0)
print(f"\nF  ALT-STAND ohne `basis` (aus der Zeit vor emm762)")
print(f"   Warnung: {len(_w_f)}   Stand danach: {_st_f['Peanut Motor']}")
if _st_f["Peanut Motor"].get("basis") != 582:
    FEHLER.append("F: der Alt-Stand bekommt keine Basis")
if _st_f["Peanut Motor"].get("seit") == 1_000_000.0:
    FEHLER.append("F: unerwartet - die alte Uhr lief unveraendert weiter")

# --- D: ECHTE RUECKKEHR (Material kommt an) ----------------------------
folge_d = [1445, 172, 172, 1448]
w_d, still_d, stand_d = lauf("Leziris Lezflow", folge_d)
print(f"\nD  RUECKKEHR      1445 -> 172 -> 172 -> 1448")
print(f"   Warnungen: {w_d} von 3   ->  still nach {still_d} h")
print(f"   Stand danach: {stand_d['Leziris Lezflow']}")
if w_d != 2 or still_d is None:
    FEHLER.append("D: die Rueckkehr beendet die Warnung nicht sofort")

# --- G: KLEINE BASIS (sein Lezflow am 29.10.) -------------------------
# ok 1445 -> basis 34: 10 % sind 3,4 Zeilen. Ein einziger abgelieferter
# Job bewegt mehr als das, und die Uhr stand nie durch. Seit emm767
# gilt zusaetzlich SCHRUMPF_BAND_MIN.
folge_g = [1445, 34, 31, 29, 33, 30, 32, 28, 31]
w_g, still_g, _ = lauf("Leziris Lezflow", folge_g)
print(f"\nG  KLEINE BASIS   1445 -> 34, danach 28..33 (8 Abrufe, 4 h)")
print(f"   Warnungen: {w_g} von 8   ->  still nach {still_g} h")
print(f"   (Band: 10 % von 34 = 3.4 Zeilen, Mindestmass {SCHRUMPF_BAND_MIN})")
if still_g is None or still_g > 2.5:
    FEHLER.append("G: kleine Basis verstummt nicht - Mindestband fehlt")

print("\n" + "=" * 70)
if FEHLER:
    print("ROT:")
    for f in FEHLER:
        print("  " + f)
    sys.exit(1)
print("ALLE PROBEN WIE ERWARTET")
print(f"""
BEFUND VOR emm762: Die Bestaetigung verlangte ZWEI STUNDEN LANG EXAKT
DIESELBE Zeilenzahl. Bei einem ruhenden Charakter (A) klappte das. Bei
einem, der weiterarbeitet (B/C) - und genau dort sitzt der gekuerzte
Abruf - genuegte EINE Zeile Abweichung, um die Uhr zurueckzuwerfen. Die
Warnung konnte dann nie verstummen, der Einkaufsknopf blieb gesperrt.

NACH emm762: Toleranzband {SCHRUMPF_BAND * 100:.0f} % um den Startwert der kleinen Phase.
A und B/C verstummen nach ~2 h, ein WEITERER Einbruch (E) wirft die Uhr
weiterhin zurueck, und Alt-Staende ohne `basis` (F) laufen sauber an.
Erkennungsschwelle und Knopf-Sperre sind unveraendert.
""")
