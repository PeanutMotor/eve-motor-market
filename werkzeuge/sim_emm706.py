"""SIMULATION emm706 - "Eigene BPC" blendet die Invention-Karte aus.

Nutzer 25.10.2026: "denke nochmal nach simuliere pruefe erstelle verschiedene
szenarien finde moegliche fehler, verbesserungen".

Spielt die Entscheidung "faellt die Invention-Karte dieses Items weg?" gegen
alle VIER Quellen durch, die `inv_manual_override` fuellen koennen - im Code
nachgelesen, nicht geraten:

  (1) mw_bauplan_fenster.py:2028  manueller Haken "Eigene BPC", NUR fuer das
                                  Endprodukt; beim Abwaehlen wieder entfernt
  (2) mw_bauplan_fenster.py:6230  Rebuild-Absicherung, ebenfalls nur Endprodukt
  (3) main_window.py:8196         "Load own BPCs" aus ESI: setzt es fuer JEDES
                                  Item mit eigener BPO - auch Komponenten,
                                  ohne dass der Nutzer irgendetwas anhakt
  (4) main_window.py:11303        Buendel, je Ende (im Buendel filtern wir nicht)

Quelle (3) ist der Grund fuer diese Datei.
"""

BUENDEL_ID = -1          # Platzhalter, echter Wert aus industry.BUENDEL_ID


def faellt_karte_weg_ALT(tid, bp_id, top_type_id, bd_type,
                         override, bd_own_bpc):
    """Erste Fassung (ausgeliefert): jedes Item im Override faellt weg,
    ausser im Buendel."""
    if bd_type == BUENDEL_ID:
        return False
    return bp_id in override


def faellt_karte_weg_NEU(tid, bp_id, top_type_id, bd_type,
                         override, bd_own_bpc):
    """AUSGELIEFERTE Fassung (mw_bauplan_tabs.py, _fill_invention_tab):

        _obc_an = (_bd_type != BUENDEL_ID and bool(_bd_own_bpc))
        ...
        if _obc_an and tid == top_type_id:

    Nur das ENDPRODUKT, und nur wenn der Nutzer den Haken wirklich gesetzt
    hat. Ein automatisch erkannter BPO-Besitz einer Komponente darf keine
    Karte verschwinden lassen - fuer Komponenten gibt es keinen Haken in der
    Rueckfall-Karte, der Weg zurueck fehlte."""
    _obc_an = (bd_type != BUENDEL_ID and bool(bd_own_bpc))
    return bool(_obc_an and tid == top_type_id)


def rueckweg_vorhanden(tid, top_type_id, bd_type):
    """Gibt es nach dem Ausblenden noch einen sichtbaren Weg zurueck?
    `_own_bpc_fallback_card` zeigt NUR das Endprodukt (sie kehrt bei
    top_type_id == BUENDEL_ID sofort zurueck und kennt kein anderes Item)."""
    if bd_type == BUENDEL_ID:
        return False
    return tid == top_type_id


SZENARIEN = [
    # (Name, tid, bp_id, top_type_id, bd_type, override, bd_own_bpc,
    #  soll_wegfallen)
    ("A Einzelplan T2, Haken AN (der gewuenschte Fall)",
     100, 900, 100, 100, {900: True}, True, True),

    ("B Einzelplan T2, Haken AUS",
     100, 900, 100, 100, {}, False, False),

    ("C Einzelplan, Haken AN, dann wieder AUS (Override geleert)",
     100, 900, 100, 100, {}, False, False),

    ("D Einzelplan: KOMPONENTE mit eigener BPO aus ESI (Quelle 3!) - "
     "Nutzer hat NICHTS angehakt",
     55, 555, 100, 100, {555: True}, False, False),

    ("E Einzelplan: Endprodukt-Haken AN, Komponente zusaetzlich per ESI",
     55, 555, 100, 100, {900: True, 555: True}, True, False),

    ("F Einzelplan: Endprodukt bei E (dasselbe Szenario, andere Zeile)",
     100, 900, 100, 100, {900: True, 555: True}, True, True),

    ("G Buendel-Ende mit eigener BPC",
     100, 900, BUENDEL_ID, BUENDEL_ID, {900: True}, True, False),

    ("H Einzelplan T1 (gar keine Invention, kommt nie in die Liste)",
     100, 900, 100, 100, {}, False, False),
]


def main():
    fehler = 0
    print("=" * 72)
    print("SZENARIEN: faellt die Invention-Karte weg?")
    print("=" * 72)
    for (name, tid, bp_id, top, bd_type, ov, own, soll) in SZENARIEN:
        alt = faellt_karte_weg_ALT(tid, bp_id, top, bd_type, ov, own)
        neu = faellt_karte_weg_NEU(tid, bp_id, top, bd_type, ov, own)
        mark_alt = "OK " if alt == soll else "FEHLER"
        mark_neu = "OK " if neu == soll else "FEHLER"
        if alt != soll:
            fehler += 1
        print(f"\n{name}")
        print(f"   soll={soll!s:5}  ALT={alt!s:5} [{mark_alt}]   "
              f"NEU={neu!s:5} [{mark_neu}]")
        # Die eigentliche Gefahr: weggefallen OHNE Weg zurueck.
        for bez, wert in (("ALT", alt), ("NEU", neu)):
            if wert and not rueckweg_vorhanden(tid, top, bd_type):
                print(f"   !! {bez}: Karte weg, aber KEIN Weg zurueck - "
                      f"der Haken ist fuer dieses Item nirgends erreichbar")

    print("\n" + "=" * 72)
    print(f"Ausgelieferte Fassung: {fehler} Szenario(en) falsch behandelt")
    print("=" * 72)

    # --- Zusatzpruefung: der Erklaertext der Rueckfall-Karte ---------------
    print("\nTEXT-PRUEFUNG der Rueckfall-Karte")
    print("-" * 72)
    for (name, tid, bp_id, top, bd_type, ov, own, soll) in SZENARIEN:
        if not faellt_karte_weg_ALT(tid, bp_id, top, bd_type, ov, own):
            continue
        # Der Text sagt "You ticked 'Own BPC' for this item".
        if not own:
            print(f"   !! {name}\n      -> Text behauptet 'Du hast angehakt', "
                  f"der Nutzer hat aber NICHTS angehakt (ESI-Automatik)")
    print("   (keine Ausgabe = kein falscher Text)")


if __name__ == "__main__":
    main()
