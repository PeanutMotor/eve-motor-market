"""Qt style sheet - Caldari 'data terminal' look: tiefes Blauschwarz,
Teal-Daten, Amber-Warnungen, helle Schrift.

FARB-RUNDE (Nutzer, Sitzung 8): "mach das ganze Tool etwas dunkler,
coolere futuristischere Farben als Hintergrund - aber nicht komplett
schwarz." Umgesetzt als TIEFENSTAFFELUNG statt Einheitsschwarz: der
Hintergrund geht ins Blauschwarz (#080D16, sichtbarer Blaustich - kein
reines Schwarz), die Flaechen darueber sind kuehler und satter blau.
GEGENGEPRUEFT mit Kontrastrechnung: alle Text-Kombinationen liegen ueber
13:1 (vorher 11-16:1), und Panels/Kanten heben sich BESSER ab als zuvor
(Panel/BG 1.31 statt 1.38 bei dunklerem Grund, Border/Panel 2.02 statt
1.91). Dunkler UND kontrastreicher, nicht dunkler auf Kosten der
Lesbarkeit."""

import os as _os
import sys as _sys


def asset_pfad(*teile):
    """Pfad zu einer Datei in eve_trader/ui/assets - auch in der EXE.

    WARUM NICHT EINFACH `dirname(__file__)`: PyInstaller packt im
    --onefile-Modus nur die PYTHON-MODULE. Datendateien (unsere SVGs, spaeter
    Schriften) kommen ausschliesslich ueber `--add-data` mit und werden beim
    Start in ein temporaeres Verzeichnis ausgepackt, dessen Wurzel in
    `sys._MEIPASS` steht. Ohne diesen Umweg zeigte der Pfad in der
    ausgelieferten Fassung ins Leere - die Haken in den Checkboxen und die
    Hoch/Runter-Pfeile der Zahlenfelder waeren einfach nicht da gewesen,
    und zwar NUR in der EXE, wo man es beim Entwickeln nie sieht. Genau der
    Fehler, den der Nutzer in Sitzung 8 schon einmal gemeldet hatte
    ("ich kann bei allen Eingabefenstern die Pfeile nicht sehen").
    """
    basis = _os.path.dirname(_os.path.abspath(__file__))
    _mei = getattr(_sys, "_MEIPASS", None)
    if _mei:
        basis = _os.path.join(_mei, "eve_trader", "ui")
    # Vorwaertsschraegstriche: der Pfad landet in Qt-Stylesheets, und dort
    # wuerde ein Windows-Backslash als Escape gelesen.
    return _os.path.join(basis, "assets", *teile).replace("\\", "/")


# AUGENFREUNDLICH GEDAEMPFT (emm834, 05.11.2026). Ein Nutzer mit
# 4K-Monitor meldete ueber Discord, dass ihm von den Farben die Augen weh
# tun. GEMESSEN, statt geschaetzt:
#   * TEXT stand auf 17:1 gegen den Grund. Fuer eine dunkle Oberflaeche
#     gelten 7-12:1 als angenehm; darueber "blutet" das Weiss aus
#     (Halation) und das Auge ermuedet. Jetzt 11:1.
#   * BG hatte 0,40 % Leuchtdichte - praktisch Schwarz. Die Pupille weitet
#     sich darauf, und jedes helle Element blendet umso mehr. Jetzt 0,71 %.
#   * CYAN 73 % und AMBER 75 % Saettigung: stark gesaettigte Farben auf
#     fast-schwarzem Grund flimmern wahrgenommen. Jetzt 55 % / 60 %.
#   * RED hatte UMGEKEHRT zu wenig: 4,1:1 auf PANEL, unter der
#     Lesbarkeitsschwelle. Jetzt 4,6:1 - Daempfen heisst hier nicht
#     "alles leiser", sondern "jede Farbe auf ihren Zielwert".
# Die Farbwelt bleibt dieselbe (Farbtoene unveraendert, nur Helligkeit und
# Saettigung). Die Logo-Toene GOLD/GOLD_HELL/GOLD_TIEF und der
# Symbol-Grundton ICON bleiben, wie sie waren - Markenzeichen, keine
# Lesefarben. aa834 haelt die gemessenen Zielwerte fest.
BG = "#0C1424"        # Tiefes Blauschwarz - Weltraum, nicht Loch
PANEL = "#1A2C42"     # Karten/Panels: kuehles Marine
PANEL2 = "#121E2E"    # Sidebar/Tabellenkopf: dazwischen
PANEL_HELL = "#223A55"  # laufende Bauplan-Karten: eine Stufe heller als PANEL (emm337)
BORDER = "#3B5E7C"    # Kante: klar sichtbar, blau statt grau
TEXT = "#C2C9D0"      # gedaempft auf 11:1 (emm834), Farbton wie gehabt.
                      # Der Hex-Wert hat BEWUSST kein Buchstabenpaar:
                      # de_scan3 liest "CF" in einer Zeichenkette als Wort
                      # und meldete #C2C9CF als unuebersetzten Anzeigetext.
MUTED = "#889CAC"
CYAN = "#7BB8B0"      # Leuchtakzent, auf 33 % Saettigung gedaempft (emm918)
# ZWEITE DAEMPFUNG (emm918, Nutzer 14.11.2026: "Cyan blau tut mir
# ueberall in den Augen weh"). Vorher #57C1B3 (55 % Saettigung, 6,5:1 auf
# PANEL). Jetzt gleicher Farbton, Saettigung 33 % statt 55 % - das
# Flimmern auf dunklem Grund kommt von der Saettigung (emm834). Die
# Helligkeit bleibt fast gleich (8,2:1 statt 8,5:1 auf BG), weil aa175
# verlangt, dass der Symbol-Ton ICON (7,6:1) schwaecher bleibt als der
# Leuchtakzent; ein erster, dunklerer Versuch (#68A8A0, 6,9:1) riss
# genau diese Zusage. 6,3:1 auf PANEL, Abstand zu CYAN_RUN 50 statt 35
# (aa836: >= 30), zu BLUE 64. Gemessen mit den Formeln von aa834/836. Gilt fuer das Theme "caldari"; graphit (#6FB5AC, 39 %)
# lag schon so ruhig, daylight ist hell und bleibt.
# NUTZER (Sitzung 8): "das Leuchten der Buttons ist etwas zu stark, bitte
# reduzieren." Vorher waren Primary-Knoepfe FLAECHIG cyan - gegen den neuen
# dunklen Grund ein Scheinwerfer (12.3:1). Jetzt eine gedaempfte
# Teal-Fuellung mit cyanfarbener Schrift und Kante: der Knopf bleibt die
# klar erkennbare Hauptaktion (2.1:1 gegen den Grund), blendet aber nicht.
# Beschriftung bleibt mit 5.8:1 gut lesbar.
# SYMBOL-TON (Nutzer, Sitzung 8: "die Symbole sind gut, aber ich haette
# lieber ein futuristisches Grau/Schwarz, kein EVE-Caldari-Leuchtblau").
# Symbole sind Werkzeug, kein Signal - sie sollen die Zeile begleiten, nicht
# um Aufmerksamkeit kaempfen. Kuehles Stahlgrau (leichter Blaustich, damit
# es zur Palette passt, aber ohne Leuchten): 7.5:1 gegen den Grund, also
# klar erkennbar. Zustands-Symbole faerben die Aufrufer weiterhin bewusst
# ein (AMBER Handlung, RED Verlust, GREEN gut) - DA soll Farbe schreien.
# DREI HELLIGKEITSSTUFEN (Nutzer, Sitzung 8: "wenn die Symbole aktiv sind,
# etwas heller, mehr ins Weiss hinein"). Der Sprung von RUHE zu AKTIV ist
# bewusst gross (1.8-fache Leuchtkraft) - sonst merkt man ihn im Augenwinkel
# nicht. Bewusst NICHT reinweiss: das wuerde heller strahlen als der
# Fliesstext und die Rangfolge umdrehen.
# GOLDTON STATT GRAU (Nutzer, Sitzung 9: "ich finde alle Symbole doch
# etwas duester, wenn sie einfach nur grau sind"). Gewaehlt wurde ein
# GEDAEMPFTES Gold - es nimmt die Logofarbe auf, ist aber bewusst matter
# und weniger gesaettigt als das Signal-AMBER (#F2A23C). Diese Distanz
# ist Absicht: Amber bedeutet im Tool "eingefroren / Warnung / fehlt" -
# waeren die ~190 Symbole ebenso satt, verloere die Warnfarbe ihre
# Signalwirkung. Der DIM- und der ACTIVE-Ton folgen demselben Farbton
# (dunkler bzw. heller), damit die Rangfolge erhalten bleibt.
ICON_DIM = "#8A7550"         # inaktiv/nebensaechlich
ICON = "#C9A06A"             # Ruhe: Standard-Ton aller Symbole
ICON_ACTIVE = "#E4C79A"      # aktiv/gehovert/ausgewaehlt
CYAN_FILL = "#15514A"        # ruhige Akzentflaeche (Primary-Knopf)
# NUTZER (Sitzung 8): "Aktualisierungsbutton hat Kontrastprobleme."
# Die Beschriftung war CYAN auf CYAN_FILL - gleiche Farbfamilie, nur
# 5.8:1, und die geringe FARB-Distanz liess es matschig wirken (der reine
# Helligkeitswert verschweigt das). Jetzt ein stark aufgehelltes Cyan:
# 8.3:1 und deutlich abgesetzt, ohne den Akzentcharakter zu verlieren.
CYAN_ON_FILL = "#DFFAF4"
CYAN_FILL_HOVER = "#1B6A60"  # beim Hovern etwas heller
CYAN_FILL_PRESS = "#0F3C37"  # beim Druecken dunkler
# FORTSCHRITTSBALKEN DER PLAN-KARTEN (Nutzer 26.09.2026: "die
# Fortschrittsbalken kann man kaum lesen in der Farbkombination von der
# Schrift drinnen"): der Balken war leuchtendes CYAN mit MUTED-Schrift
# darueber. Jetzt dieselbe ruhige Flaeche wie der Primary-Knopf und
# dieselbe helle Beschriftung (CYAN_ON_FILL, >= 7:1 - aa173) - fertig
# in einem gleich gedaempften Gruen.
GREEN_FILL = "#1E5A3A"
GREEN_ON_FILL = "#E3F8EA"
AMBER = "#D9A057"   # 60 % statt 75 % Saettigung (emm834)
# NUTZER (Sitzung 8): "standardmaessig schon einen gelben Rahmen darum
# machen, bevor man Mouseover macht." Gedaempftes Amber fuer den RUHENDEN
# Reiter - erkennbar als zur Navigation gehoerig, laesst aber Luft nach
# oben: Hover und aktiver Reiter bekommen das volle AMBER. Drei Stufen
# also, wie bei den Symbolen. (2.7:1 gegen die Reiterflaeche, damit sogar
# etwas praesenter als die alte blaugraue Kante mit 2.3:1.)
AMBER_DIM = "#7A5626"
# LOGO-PALETTE (Wabe mit Innenkante, Sitzung 8). Gehoert ins Theme, nicht
# ins Symbol-Modul - die Waechter aa170/aa175 haben genau das eingefordert.
GOLD_HELL = "#FFD98A"     # oberer Verlaufspunkt
GOLD = "#F2A23C"          # Mitte. WAR identisch mit AMBER; seit emm834
                          # ist AMBER gedaempft, das LOGO bleibt kraeftig.
GOLD_TIEF = "#B87326"     # unterer Verlaufspunkt + Innenkante
LOGO_KERN = "#0B0F17"     # Wabenfuellung, dunkler als BG fuer Kontrast
RED = "#F5615D"      # HELLER als vorher: war mit 4,1:1 auf PANEL unter der
                     # Lesbarkeitsschwelle (emm834). Bleibt bewusst im
                     # ORANGE-Rot: ein rosigeres Rot kam der Planfarbe
                     # "Rose" (f6) zu nahe - aa402 hat das gefangen.
# PLAN-FARBEN (Nutzer 23.09.2026: "Schau mal die Farben, Blau sieht man
# kaum, waehle anderes Blau / Fuege weitere 4 Farben hinzu / Benenne alle 8
# Farben anders, waehle keine EVE-Fraktionen als Namen [...] wir muessen gar
# keine Namen geben, die Farbe sagt schon genug aus / Nimm kein Rot oder Full
# Green [...] Das Rot sieht aus wie Verlustzahlen. nimm ein anderes Rot").
#
# DIE SCHLUESSEL SIND ABSICHTLICH NUMMERN. Sie werden im Plan GESPEICHERT.
# Ein Name ("caldari") waere eine Aussage ueber den Plan, die der Nutzer nie
# gemacht hat - und beim naechsten Umfaerben eine Luege. Eine Nummer ist nur
# ein Platz in dieser Tabelle; wer den Farbwert aendert, aendert die Farbe
# aller Plaene auf diesem Platz und nichts sonst.
#
# ZWEI FARBEN SIND HIER VERBOTEN, weil sie im ganzen Werkzeug etwas anderes
# bedeuten: RED (#E5544B) = Verlust und GREEN (#4FD17A) = Gewinn. Eine Karte
# in Signalrot laese sich wie eine Verlustmeldung, ohne eine zu sein. Darum
# steht auf Platz 6 ein Rose - das "andere Rot", blasser und kuehler als
# RED - und Gruen fehlt ganz; Petrol (Platz 2) ist der naechste Ton, der
# nicht nach "Gewinn" aussieht. Geprueft wird das in aa402: jeder Wert haelt
# im RGB-Raum Abstand zu RED, GREEN und GREEN_BRIGHT, und die acht halten
# Abstand untereinander - sonst waeren zwei Plaene nicht unterscheidbar.
#
# HELLIGKEIT: die Flaeche liegt mit 18 % auf PANEL (#16273B). Unter etwa 60 %
# Helligkeit verschwindet ein Ton darin - daran ist das alte Blau (#3A6EA5)
# gescheitert ("Blau sieht man kaum"). Alle acht Werte liegen darueber.
PLAN_FARBEN = {
    "f1": "#4C90F0",   # Blau - hell genug, um auf PANEL zu stehen
    "f2": "#2FB2D4",   # Petrol - der Platz, an dem sonst Gruen staende
    "f3": "#8C7BF0",   # Indigo
    "f4": "#B36BE0",   # Violett
    "f5": "#D95FC4",   # Magenta
    "f6": "#DE7E9B",   # Rose - das "andere Rot", kein Verlustrot
    "f7": "#D9B38C",   # Sand
    "f8": "#93A8C4",   # Stahl
}
# ALTBESTAND: die vier Fraktionsschluessel der ersten Fassung stecken schon in
# gespeicherten Plaenen. Sie werden beim Lesen auf den naechstliegenden neuen
# Platz gebogen, damit keine Karte ihre Farbe verliert (gelesen wird ueber
# MainWindow._plan_farb_norm - EINE Stelle).
PLAN_FARBEN_ALT = {
    "caldari": "f1",
    "gallente": "f2",
    "amarr": "f7",
    "minmatar": "f6",
}
GREEN = "#56BF79"
VIOLET = "#A687F5"    # Science im Runplaner (Copying/Invention) und
                      # erfindbare T2-Namen. Seit 10.10.2026 NICHT mehr die
                      # Reaktions-Stufen - die laufen in BLUE (Nutzer: "es
                      # sieht mehr aus wie ein Regenbogen wirrwar").
VIOLET_2 = "#C79BE8"  # HISTORISCH: war die zweite Reaktions-Stufe
                      # (Sitzung 12); seit 10.10.2026 im Runplaner unbenutzt.
                      # Konstante bleibt - Anker/Icons-Kommentare lesen sie.
CYAN_RUN = "#59B7D4"  # "wird gerade gebaut" (ESI-Job laeuft). BEWUSST NICHT
                      # violett: violett ist die Farbe der Reaktions-STUFE,
                      # ein laufender Job ist ein ZUSTAND - zwei
                      # verschiedene Aussagen brauchen zwei Farben.
GREEN_BRIGHT = "#70D495"   # Abstand zur Planfarbe "Stahl" (f8) gewahrt (aa402)   # Zusage-Gruen ("kann gebaut werden") - bewusst
                           # heller als GREEN (Handlung, nicht Status)
BLUE = "#5F9DE3"      # ALLE Bau-Stufen 1-4 im Runplaner (Fuel, Unrefined,
                      # Reaktionen, Komponenten; Nutzer 10.10.2026) - farbig
                      # bleiben nur Science (VIOLET), Reprocessing (GREEN)
                      # und das Endprodukt (AMBER).
                      # STAND HIER FRUEHER WEITER UNTEN, hinter den Paletten.
                      # Seit der Theme-Wahl (emm836) muessen ALLE Farbwerte
                      # oberhalb des Theme-Blocks stehen - ein Literal
                      # darunter wuerde den Theme-Wert stumm ueberschreiben.

# =====================================================================
# THEME-WAHL (emm836)
# =====================================================================
# DISCORD-MELDUNG (05.11.2026, zweiter Teil - der erste wurde emm834): dem
# Nutzer tun von den Farben die Augen weh. emm834 hat die EINE Farbwelt
# gemessen entschaerft; hier kommt die WAHL dazu.
#
# WARUM DAS OHNE GROSSE UMBAUTEN GEHT - GEMESSEN, NICHT GEHOFFT: alle 1472
# Farbzugriffe im Programm lauten `theme.XYZ`, KEIN EINZIGER
# `from .theme import BG`. Ein Modul-Attribut laesst sich also an EINER
# Stelle umlegen, und jede dieser 1472 Stellen zieht nach. Ausserhalb
# dieser Datei stehen nur noch drei feste Farbwerte im ganzen Programm.
#
# DIE WERTE OBEN SIND DAS VORGABE-THEME ("caldari") - sie bleiben als
# Literale stehen, damit ihre Begruendungen (emm834 und frueher) dort
# bleiben, wo die Zahl steht. Ein anderes Theme ueberschreibt sie hier.
#
# WIRKT NACH NEUSTART, aus demselbem Grund wie die Oberflaechen-Groesse
# (emm835): QSS unten ist ein f-String, der beim IMPORT dieser Datei
# gebaut wird, und Qt-Stilvorlagen werden beim Fensteraufbau einmal
# gesetzt. Ein Umlegen zur Laufzeit faerbte einen Teil der Oberflaeche um
# und den anderen nicht - schlimmer als ein Neustart.
#
# WAS EIN THEME *NICHT* AENDERN KANN, und das steht hier, damit niemand es
# fuer einen Fehler haelt: rund 45 Stellen im Programm schreiben
# `rgba(70,224,200,0.08)` und aehnlich - Schleier und Toenungen mit FEST
# EINGETRAGENEN Akzent-Zahlen. Sie tragen noch das Cyan/Amber von VOR
# emm834. Solange das so ist, darf ein Theme die HELLIGKEIT und die
# SAETTIGUNG der Akzente verschieben, aber nicht den FARBTON wechseln
# (Cyan nach Gruen o.ae.) - sonst stuenden die Schleier in der alten
# Farbe. Steht in OFFENE_PUNKTE.
THEME_VORGABE = "caldari"
THEMES = {
    "caldari": {},      # leer = die Literale oben, siehe Begruendung
    # ------------------------------------------------------------------
    # GRAPHIT: neutrales Grau ohne Blaustich. Fuer wen die blaue Farbwelt
    # selbst anstrengt - der Grund ist derselbe hell wie bei caldari
    # (0,69 % statt 0,71 % Leuchtdichte), die Akzente sind aber noch
    # einmal deutlich entsaettigt: Cyan 39 % statt 55 %, Amber 49 % statt
    # 60 %. Alle Textkombinationen gemessen im selben Zielband wie
    # caldari (Text 8,8-11,0:1, Akzente >= 4,9:1, Panel/Grund 1,25).
    "graphit": {
        "BG": "#121417",
        "PANEL": "#24282E",
        "PANEL2": "#1A1D21",
        "PANEL_HELL": "#31373F",
        "BORDER": "#4C525B",
        "TEXT": "#C6C8CB",
        "MUTED": "#91969C",
        "CYAN": "#6FB5AC",
        "CYAN_FILL": "#1E4A45",
        "CYAN_ON_FILL": "#DCF2EE",
        "CYAN_FILL_HOVER": "#27605A",
        "CYAN_FILL_PRESS": "#153833",
        "GREEN_FILL": "#245138",
        "GREEN_ON_FILL": "#E1F3E7",
        "AMBER": "#CFA369",
        "AMBER_DIM": "#7A6038",
        "ICON_DIM": "#7E7560",
        "ICON": "#BFA585",
        "ICON_ACTIVE": "#DCCBB0",
        # RED UND GREEN_BRIGHT STEHEN HIER ABSICHTLICH NICHT: sie erben die
        # Vorgabe-Werte. Erst entsaettigt eingetragen (#E8706C / #7FCE9A),
        # dann GEMESSEN mit der Methode von aa402 - und beide fielen durch:
        # das gedaempfte Rot kam der Planfarbe "Rose" (f6) auf 50 statt 70
        # Abstand, das gedaempfte Hellgruen der Planfarbe "Stahl" (f8) auf
        # 60. Genau die Falle, in die emm834 schon einmal gelaufen ist.
        # Nachziehen ins Orange half nicht: dann ruecken sie an AMBER.
        # LEHRE: Signalfarben sind keine STIMMUNGSfarben. Verlust und
        # Gewinn muessen in jedem Theme gleich laut sein, und ihr Abstand
        # zu den acht Planfarben ist bei der Vorgabe schon ausgemessen.
        # Entsaettigt werden die FLAECHEN und die ruhigen Akzente.
        "GREEN": "#68B97F",
        "VIOLET": "#A795DE",
        "VIOLET_2": "#C4B2EA",
        # DIESE ZWEI SIND NACHGEMESSEN WORDEN, nicht geschaetzt. Erst
        # standen hier #6FAEC4 und #7A9BC4 - beim Entsaettigen waren sie
        # einander auf 22 Punkte nahegekommen (Vorgabe: 31). Im Runplaner
        # bedeuten sie Verschiedenes (CYAN_RUN = "wird gerade gebaut",
        # BLUE = Bau-Stufe), die muessen auseinander zu halten sein.
        # Jetzt 34, und auch zu CYAN (40 statt 25) und VIOLET (65) weiter
        # auseinander als bei der Vorgabe.
        "CYAN_RUN": "#5CA6CC",
        # Nach dem Trennen noch einmal nachgebessert: #6E8CC0 stand mit
        # 4,4:1 auf dem Panel knapp UNTER der Lesbarkeitsschwelle -
        # gefunden von aa836, nicht von Auge. Jetzt 5,3:1, und die
        # Abstaende halten weiter (CYAN_RUN 35, VIOLET 46, CYAN 43).
        "BLUE": "#7E9CCB",
    },
    "tageslicht": {
        "BG": "#DFE4EB",
        "PANEL": "#FBFCFD",
        "PANEL2": "#D2D8E1",
        "PANEL_HELL": "#E2EAF6",
        "BORDER": "#A3AFC0",
        "TEXT": "#2B323A",
        "MUTED": "#5C6673",
        "CYAN": "#116F65",
        "CYAN_FILL": "#CFE9E4",
        "CYAN_ON_FILL": "#0B4A43",
        "CYAN_FILL_HOVER": "#B9DFD8",
        "CYAN_FILL_PRESS": "#A3D3CA",
        "GREEN_FILL": "#D2EADC",
        "GREEN_ON_FILL": "#14532C",
        "AMBER": "#8A5A0B",
        "AMBER_DIM": "#B99B6B",
        "ICON_DIM": "#AD9873",
        "ICON": "#8A6B3C",
        "ICON_ACTIVE": "#5E4620",
        "RED": "#B33830",
        "GREEN": "#1C6E3C",
        "GREEN_BRIGHT": "#15803D",
        "VIOLET": "#6B3FA8",
        "VIOLET_2": "#8A64C0",
        "CYAN_RUN": "#1B6E8C",
        "BLUE": "#2A5CA8",
        # EIGENE PLANFARBEN, weil die acht der Vorgabe auf weissem Grund
        # verschwinden - dieselbe Forderung wie bei caldari ("Blau sieht
        # man kaum"), nur in die andere Richtung. f6 und f7 sind dabei
        # ein zweites Mal nachgezogen worden: in der ersten Fassung kamen
        # sie dem dunklen Verlust-Rot dieses Themes auf 60 bzw. 66
        # Punkte nahe (gefordert: 70). aa836 hat das gefunden.
        "PLAN_FARBEN": {
            "f1": "#2563B0", "f2": "#107C96", "f3": "#5244B8",
            "f4": "#7B3FA8", "f5": "#A52C8E", "f6": "#702058",
            "f7": "#6F5A2A", "f8": "#566880",
        },
    },
}


def toenung(farbe, alpha):
    """Eine Theme-Farbe als `rgba(r,g,b,a)` - fuer Schleier und Toenungen.

    WOZU DIESE FUNKTION UEBERHAUPT: im Programm standen rund 45 Stellen mit
    fest eingetippten Zahlen, `rgba(70,224,200,0.08)` und aehnlich. Zwei
    Schaeden daraus, beide GEMESSEN:
      * Sie waren VERALTET. 70,224,200 ist das Cyan von VOR emm834 - beim
        Daempfen der Palette hat sie niemand nachgezogen, weil sie nicht
        wie Farbkonstanten aussehen.
      * Sie koennen kein Theme. Ein Schleier in der Akzentfarbe des einen
        Themes steht im anderen falsch.
    Wer ab jetzt eine Toenung braucht, nimmt diese Funktion. Dann zieht sie
    bei JEDEM Theme und bei jeder kuenftigen Farbaenderung von selbst nach.
    """
    _h = str(farbe).lstrip("#")
    _r, _g, _b = (int(_h[0:2], 16), int(_h[2:4], 16), int(_h[4:6], 16))
    return f"rgba({_r},{_g},{_b},{alpha})"


def _stufe(farbe, schritt):
    """Eine Farbe um `schritt` (-1..1) abdunkeln oder aufhellen.
    Negativ dunkler, positiv heller. Bleibt im gueltigen Bereich."""
    _h = str(farbe).lstrip("#")
    _teile = [int(_h[i:i + 2], 16) for i in (0, 2, 4)]
    if schritt < 0:
        _neu = [int(round(_t * (1.0 + schritt))) for _t in _teile]
    else:
        _neu = [int(round(_t + (255 - _t) * schritt)) for _t in _teile]
    return "#" + "".join(f"{max(0, min(255, _w)):02X}" for _w in _neu)


def tiefe(grund, staerke=0.20):
    """Ein sehr sanfter senkrechter Verlauf aus EINER Grundfarbe (emm885).

    Nutzer 09.11.2026: "alle deine Programme sehen am Ende etwa gleich
    aus und das hat einen starken wiedererkennungswert, das ist ein
    wenig schlecht angesehn" - dazu die Vorgabe, es solle nach Feierabend
    und Weltraum aussehen, "nicht wie eine Exel Tabelle".

    Eine einzige flache Fuellung liest sich als Blatt. Ein Verlauf, den
    man nicht bewusst bemerkt, liest sich als Raum.

    NUR INS DUNKLE (Nutzer nach dem ersten Lauf: "Verlauf zu stark,
    lieber ins dunkle rein gehen nicht ins helle"). Die erste Fassung
    ging nach unten ins Hellere und drehte beim hellen Theme um; das
    war zu viel und sah nach Lichtquelle aus statt nach Tiefe. Jetzt
    wird NIE aufgehellt - in keinem Theme. Das braucht auch keine
    Theme-Abfrage mehr: Abdunkeln liest sich auf hellem wie auf dunklem
    Grund als Schatten, Aufhellen nur auf dunklem."""
    _oben = _stufe(grund, -staerke * 0.35)
    _unten = _stufe(grund, -staerke)
    return (f"qlineargradient(x1:0, y1:0, x2:0.2, y2:1, "
            f"stop:0 {_oben}, stop:0.45 {grund}, stop:1 {_unten})")


def schleier(alpha):
    """Eine neutrale Aufhellung bzw. Abdunklung um `alpha` - die Richtung
    bestimmt das Theme.

    DAS IST DER GRUND, WARUM ES DIESE FUNKTION BRAUCHT und nicht einfach
    `rgba(255,255,255,0.10)` genuegt: auf dunklem Grund hebt Weiss eine
    Flaeche hervor, auf hellem Grund ist es UNSICHTBAR. Die Fuellung der
    Fortschrittsbalken war genau so gebaut - im hellen Theme waere der
    Fortschritt schlicht verschwunden, und zwar stumm. Auf hellem Grund
    muss derselbe Griff abdunkeln statt aufhellen.
    """
    return (f"rgba(0,0,0,{alpha})" if THEME_HELL
            else f"rgba(255,255,255,{alpha})")


def vorhang(alpha):
    """Der abdunkelnde Schleier ueber einem gesperrten Fenster (Ladebalken,
    Overlay).

    BLEIBT IN JEDEM THEME DUNKEL, auch im hellen - das ist Absicht und
    keine vergessene Stelle. Ein Vorhang sagt "dahinter geht gerade
    nichts"; abdunkeln liest sich so, aufhellen nicht. Auf hellem Grund
    wirkt er sogar deutlicher als auf dunklem.
    """
    return f"rgba(10,15,20,{alpha})"


def theme_namen():
    """Die waehlbaren Themes als (Schluessel, Anzeigename) - EINE Stelle,
    aus der sich das Auswahlfeld der Einstellungen und die Pruefungen
    speisen. Der Anzeigename geht durch sprache.t()."""
    return (("caldari", "Caldari Blue (default)"),
            ("graphit", "Graphite (neutral grey)"),
            ("tageslicht", "Daylight (light)"))


def aktives_theme():
    """Der Schluessel des gewaehlten Themes - oder die Vorgabe.

    LIEST SELBST, statt sich den Wert geben zu lassen: QSS unten wird beim
    Import dieser Datei gebaut, da laeuft noch kein Fenster, das etwas
    uebergeben koennte. `config` importiert nur json und os, ein Zirkel
    ist also ausgeschlossen (nachgesehen, nicht angenommen).

    EINE KAPUTTE EINSTELLUNG DARF DEN START NIE KOSTEN - dieselbe Haltung
    wie bei der Oberflaechen-Groesse (emm835): im Zweifel die Vorgabe.
    """
    _wahl = _os.environ.get("EVE_MOMA_THEME")
    if not _wahl:
        try:
            from .. import config as _cfg_thm
            _wahl = str((_cfg_thm.load_settings() or {}).get("ui_theme") or "")
        except Exception:
            _wahl = ""
    return _wahl if _wahl in THEMES else THEME_VORGABE


# ALLE NAMEN, DIE EIN THEME SETZEN DARF - aus den Themes selbst
# abgeleitet statt von Hand gepflegt. Wer ein Theme um eine Farbe
# erweitert, braucht hier nichts nachzutragen; wer eine Farbe eintraegt,
# die es als Vorgabe-Literal nicht gibt, faellt sofort auf (aa837).
THEME_SCHLUESSEL = tuple(sorted({_k for _w in THEMES.values() for _k in _w}))
# DIE VORGABE-WERTE, GESICHERT BEVOR das erste Theme angewendet wird. Ohne
# sie waere ein Wechsel eine Einbahnstrasse: ein Theme, das eine Farbe
# NICHT setzt, wuerde sonst die des vorigen Themes erben statt die Vorgabe.
_VORGABE_WERTE = {_k: globals()[_k] for _k in THEME_SCHLUESSEL}


def _leuchtdichte(farbe):
    """WCAG-Leuchtdichte 0..1 eines #rrggbb-Werts."""
    _h = str(farbe).lstrip("#")
    _w = []
    for _i in (0, 2, 4):
        _c = int(_h[_i:_i + 2], 16) / 255.0
        _w.append(_c / 12.92 if _c <= 0.03928
                  else ((_c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * _w[0] + 0.7152 * _w[1] + 0.0722 * _w[2]


# VORAB DEKLARIERT, obwohl `_theme_anwenden()` sie gleich ueberschreibt.
# Ohne diese vier Zeilen entstehen sie nur ueber `globals()[...]` - fuer
# jeden Leser und fuer pyflakes sind sie dann undefinierte Namen (aa288
# hat das sofort gemeldet). Die Werte hier sind Platzhalter.
THEME_AKTIV = THEME_VORGABE
THEME_HELL = False
TIER_PALETTE = []
CHART_PALETTE = []


def _theme_anwenden(name):
    """Die Farben eines Themes in die Modul-Konstanten legen.

    ERST ALLES AUF DIE VORGABE ZURUECK, dann die Abweichungen - sonst
    erbt ein Theme stumm die Farben des vorigen, wenn es eine nicht
    selbst setzt. Beim ersten Aufruf ist das Zuruecksetzen wirkungslos
    (die Werte stehen schon), beim Umschalten im Betrieb ist es alles.
    """
    globals().update(_VORGABE_WERTE)
    globals().update(THEMES.get(name) or {})
    globals()["THEME_AKTIV"] = name
    # GEMESSEN STATT GEPFLEGT: ob ein Theme hell ist, steht nirgends als
    # Schalter, sondern faellt aus seinem eigenen Hintergrund. Ein
    # Schalter waere eine zweite Wahrheit - wer kuenftig ein Theme
    # eintraegt und ihn vergisst, haette ein helles Theme mit
    # Aufhellungs-Schleiern, also unsichtbaren Fortschrittsbalken.
    globals()["THEME_HELL"] = _leuchtdichte(globals()["BG"]) > 0.5
    # DIE PALETTEN WERDEN AUS DEN FARBEN GEBAUT und muessen deshalb hier
    # mit - sonst zeigten Diagramme und Fertigungstiefen nach einem
    # Wechsel weiter die Farben des alten Themes.
    globals()["TIER_PALETTE"] = [AMBER, CYAN, "#8FB8F0", "#C4A5E8",
                                 "#E0A0C8", "#9AA0B0", MUTED]
    globals()["CHART_PALETTE"] = [CYAN, AMBER, GREEN, "#7AA2F2", "#E56AB3",
                                  "#C8D14F", "#8A7AF2", "#4FD1C5",
                                  "#F27A7A", "#9AD14F"]


def _farbpaare(von, nach):
    """{alte Schreibweise: neue} fuer jede Farbe, die sich aendert.

    ZWEI SCHREIBWEISEN JE FARBE, und die zweite ist der Grund, warum es
    diese Funktion gibt: im Stylesheet steht eine Farbe mal als "#D9A057"
    und mal - durch `toenung()` - als "217,160,87" in einem rgba(). Wer
    nur die Hex-Form ersetzt, laesst alle Schleier und Toenungen in der
    alten Farbe stehen.
    """
    _p = {}
    for _k in THEME_SCHLUESSEL:
        _a, _n = von.get(_k), nach.get(_k)
        if not isinstance(_a, str) or not isinstance(_n, str) or _a == _n:
            continue
        if not (_a.startswith("#") and len(_a) == 7):
            continue
        _p[_a] = _n
        _p[",".join(str(int(_a[_i:_i + 2], 16)) for _i in (1, 3, 5))] = \
            ",".join(str(int(_n[_i:_i + 2], 16)) for _i in (1, 3, 5))
    return _p


def stile_nachziehen(wurzel, paare):
    """Die Farben in den EIGENEN Stilvorlagen aller Widgets austauschen.

    WOZU, OBWOHL DAS GLOBALE STYLESHEET SCHON NEU IST: gemessen an einem
    laufenden Fenster deckt das globale Stylesheet 77,5 % der Bildpunkte
    ab. Die restlichen rund 5 % sind Widgets, denen der Code beim Aufbau
    ein eigenes `setStyleSheet(...)` mitgegeben hat - 206 solche Stellen
    gibt es. Deren Text traegt die Farben von damals, und die meisten
    Seiten entstehen nur EINMAL beim Start, werden also nie neu gebaut.

    STATT 206 STELLEN ANZUFASSEN wird hier der fertige Text ersetzt: wir
    wissen, welche Farbe welche abgeloest hat, und tauschen genau diese
    Zeichenketten. Das trifft auch Stellen, die niemand im Blick hatte,
    und es kann keine vergessen.

    Gibt die Zahl der geaenderten Widgets zurueck.
    """
    if not paare:
        return 0
    from PySide6.QtWidgets import QWidget      # lokal, damit dieses Modul
    _n = 0                                     # ohne Qt importierbar bleibt
    for _w in [wurzel] + wurzel.findChildren(QWidget):
        try:
            _s = _w.styleSheet()
        except RuntimeError:                   # Widget schon abgeraeumt
            continue
        if not _s:
            continue
        _neu = _s
        for _a, _b in paare.items():
            if _a in _neu:
                _neu = _neu.replace(_a, _b)
        if _neu != _s:
            try:
                _w.setStyleSheet(_neu)
                _n += 1
            except RuntimeError:
                continue
    return _n


def umschalten(name):
    """Das Theme IM LAUFENDEN PROGRAMM wechseln.

    Gibt die FARBPAARE zurueck (alte Schreibweise -> neue), die der
    Aufrufer an `stile_nachziehen()` weiterreicht; ein leeres Dict heisst
    "nichts zu tun" und ist falsy.

    NUTZER AM 05.11.2026: "theme wechseln braucht einen restart, kann man
    das nicht direkt aendern bitte". Meine erste Antwort war "geht nicht,
    weil das Stylesheet beim Start gebaut wird" - das war bequem und
    falsch. NACHGEMESSEN an einem laufenden Fenster: setzt man nur das
    globale Stylesheet neu, aendern sich 77,5 % der Bildpunkte sofort
    (Hintergrund, Tabs, Tabellen, Eingabefelder, Knoepfe, Kanten). Die
    restlichen rund 5 % sind Widgets mit eigenem setStyleSheet.

    WER DAS AUFRUFT, MUSS ZWEI DINGE TUN (beides macht main_window):
        app.setStyleSheet(theme.QSS)          # neues Stylesheet verteilen
        theme.stile_nachziehen(fenster, p)    # die eigenen Stile umfaerben
    Ohne den ersten Schritt passiert sichtbar nichts: diese Funktion legt
    nur die Farben um, sie kennt die QApplication nicht.
    """
    if name not in THEMES or name == THEME_AKTIV:
        return {}
    _vorher = {_k: globals()[_k] for _k in THEME_SCHLUESSEL}
    _hell_vorher = THEME_HELL
    _theme_anwenden(name)
    globals()["QSS"] = _qss_bauen()
    _paare = _farbpaare(_vorher,
                        {_k: globals()[_k] for _k in THEME_SCHLUESSEL})
    # DER SCHLEIER DREHT MIT, und das faellt sonst durchs Raster: er ist
    # keine Theme-FARBE, sondern Weiss bzw. Schwarz je nach Grund (siehe
    # `schleier()`). GEMESSEN: ohne diese zwei Zeilen blieb beim Wechsel
    # ins helle Theme genau die Rinne des Fortschrittsbalkens weiss - ein
    # Fleck von 2,64 % der Bildflaeche, den ich erst im Bildvergleich
    # gefunden habe, nicht im Code.
    if THEME_HELL != _hell_vorher:
        _alt, _neu = ("255,255,255", "0,0,0") if THEME_HELL \
            else ("0,0,0", "255,255,255")
        _paare[f"rgba({_alt},"] = f"rgba({_neu},"
    return _paare


_theme_anwenden(aktives_theme())

# TYPOGRAFIE-SKALA (Nutzer, Sitzung 8: "jeder Tab dieselbe Schrift, Groessen
# und Farben einheitlich"). GENAU VIER Groessen + Display (>=25 fuer grosse
# Zahlen/Symbole). Die aa-Suite erzwingt die Skala - neue Zwischengroessen
# fallen rot.
FS_SMALL = "11px"     # dichte Nebeninfo (Tabellen-Details, Balkentext)
FS_BASE = "13px"      # Grundschrift (globales QSS unten)
FS_H2 = "15px"        # Ueberschriften, Tabs, KPI-Titel
FS_KPI = "19px"       # grosse Kennzahlen (Karten)
MONO = "Consolas, monospace"   # NUR fuer Zahlen/Kennwerte (Terminal-Optik)

# INDUSTRIE-SCHRIFT (Nutzer, Sitzung 8: "haettest du einen Industry-Font im
# Petto?"). EVEs eigene UI-Schrift (Shentox) ist lizenziert und darf nicht
# mitgeliefert werden. Gewaehlt wurde eine Kette, die OHNE Download
# funktioniert:
#   1. Bahnschrift - liegt auf JEDEM Windows 10/11 (Microsofts DIN-Variante:
#      technisch, schmal, gerade Schnitte - genau die Industrie-Optik).
#   2. dann die frueheren Schriften als Rueckfall, damit nichts bricht.
# Wer eine eigene Schrift will (z.B. Rajdhani, Chakra Petch, Saira), legt
# die .ttf/.otf einfach in eve_trader/ui/assets/fonts/ - load_custom_fonts()
# registriert beim Start ALLES, was dort liegt, und FONT_CUSTOM zieht die
# erste gefundene Familie nach vorn. Kein Code-Eingriff noetig.
FONT_STACK = ['"Bahnschrift"', '"Segoe UI"', '"Inter"', "sans-serif"]
FONT = ", ".join(FONT_STACK)

# ---------------------------------------------------------------------
# KANTENRUNDUNG - EINE STELLE (emm885)
#
# Nutzer 09.11.2026: "die runden ecken stoeren mich auch sehr, das ist
# ein starkes Claude merkmal ... alle deine Programme sehen am Ende etwa
# gleich aus". Dazu: "ganz Eckig will ich die kanten auch nicht."
#
# Vorher standen 130 Rundungen in zehn Dateien fest im Quelltext, in
# zwoelf verschiedenen Werten - gewachsen, nicht entworfen. Jetzt
# entscheidet EINE Zahl je Stufe (Regel 9). Wer die Optik drehen will,
# aendert hier vier Werte und sonst nichts.
#
# DIE STUFEN:
#   RAD_KLEIN  - Haken, Scrollbalken, kleine Felder
#   RAD        - der Normalfall: Knoepfe, Eingabefelder, Tabs
#   RAD_GROSS  - Karten, Dialoge, grosse Flaechen
#   RAD_PILLE  - Pillen und Abzeichen. BLEIBEN RUND: eine Pille mit
#                kleiner Rundung ist einfach ein Rechteck mit Rahmen,
#                und die Form IST hier die Bedeutung.
RAD_KLEIN = "2px"
RAD = "2px"
RAD_GROSS = "3px"
RAD_PILLE = "11px"
#   RAD_REITER - die Hauptreiter oben. Duerfen runder bleiben:
#                die Form sagt "das ist ein Reiter" (Nutzerwunsch
#                Sitzung 8), und das soll sie weiter sagen.
RAD_REITER = "6px"


def load_custom_fonts():
    """Registriert alle Schriften aus assets/fonts und stellt die erste
    gefundene Familie an den Anfang der Kette. Ohne eigene Dateien bleibt
    es bei Bahnschrift. Fehler sind bewusst folgenlos - eine kaputte
    Schriftdatei darf den Programmstart nicht verhindern."""
    global FONT, QSS
    ordner = asset_pfad("fonts")
    if not _os.path.isdir(ordner):
        return []
    from PySide6.QtGui import QFontDatabase
    familien = []
    for name in sorted(_os.listdir(ordner)):
        if not name.lower().endswith((".ttf", ".otf")):
            continue
        try:
            kennung = QFontDatabase.addApplicationFont(
                _os.path.join(ordner, name))
            if kennung >= 0:
                familien += QFontDatabase.applicationFontFamilies(kennung)
        except Exception:
            continue
    if familien:
        alt = FONT
        FONT = ", ".join([f'"{familien[0]}"'] + FONT_STACK)
        QSS = QSS.replace(alt, FONT)
    return familien

# FARB-PALETTEN (TIER_PALETTE fuer Fertigungs-Tiefen, CHART_PALETTE fuer
# Diagramme) - die einzigen erlaubten Hex-Quellen ausserhalb der Konstanten.
# SIE STEHEN NICHT MEHR HIER, sondern werden in `_theme_anwenden()` gebaut.
# Grund: seit dem Umschalten im Betrieb (emm837) muessen sie bei JEDEM
# Wechsel neu entstehen. Stuenden sie zusaetzlich hier, waere das eine
# zweite Wahrheit - und die hier wuerde beim Import gewinnen.

_CHECK_ICON = asset_pfad("check.svg")
# NUTZER-FUND (Sitzung 8): "ich kann bei allen Eingabefenstern die Pfeile
# fuer hoch/runter nicht sehen." URSACHE: sobald man QSpinBox::up-button im
# Stylesheet anfasst, zeichnet Qt die eingebauten Pfeile NICHT mehr - der
# Knopf blieb eine leere Flaeche. Also eigene Pfeil-Grafiken im
# Symbol-Stahlton (dieselbe Formsprache wie icons.py).
_SPIN_UP = asset_pfad("spin_up.svg")
_SPIN_DOWN = asset_pfad("spin_down.svg")

# SENKRECHTES POLSTER EINER TABELLENZELLE (emm515, Nutzer 11.10.2026:
# "teilweise auch unlesbar zerdrueckt" - die Status-Pillen des Blueprints-
# Reiters waren oben und unten abgeschnitten).
# `QTableWidget::item` unten im QSS nimmt oben und unten je 5 px Polster plus
# 1 px border-bottom; ein Zell-Widget bekommt also 11 px weniger als die
# Zeilenhoehe, und Qt legt beim Einpassen 1 px drauf. GEMESSEN (offscreen mit
# diesem QSS): Zeile 30 px -> Widget 18 px, die Pille brauchte 19 und wurde
# auf 14 gestaucht.
# WER EIN WIDGET IN EINE ZELLE SETZT, hebt die Zeilenhoehe um diesen Betrag
# ueber die sizeHint seines Widgets - sonst staucht Qt es stumm. Waechter
# aa533 haelt die Zahl am QSS-Polster fest.
ZELL_POLSTER_V = 12

# de_scan2: aus  (das Stylesheet ist CSS mit deutschen BEGRUENDUNGS-Kommentaren - nichts davon ist Anzeigetext)
def _qss_bauen():
    """Das globale Stylesheet aus den AKTUELLEN Farben bauen.

    WAR BIS emm837 EIN MODUL-STRING, der beim Import einmal entstand.
    Als Funktion kann ihn `umschalten()` neu erzeugen - das ist die
    ganze Voraussetzung dafuer, dass ein Theme-Wechsel ohne Neustart
    geht. Der Rumpf ist unveraendert; nur die beiden Zeilen hier und
    die Zuweisung am Ende sind neu.
    """
    return f"""
* {{
    font-family: {FONT};
    font-size: 13px;
    color: {TEXT};
}}
QWidget {{ background: transparent; }}
QMainWindow, QDialog {{ background: {tiefe(BG)}; }}

QTabWidget::pane {{ border: 1px solid {BORDER}; top: -1px; background: {BG}; }}
QTabBar::tab {{
    background: {PANEL2};
    color: {MUTED};
    padding: 10px 20px;
    font-size: 15px;
    font-weight: 600;
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: {RAD};
    border-top-right-radius: {RAD};
    margin-right: 3px;
}}
QTabBar::tab:selected {{
    color: {CYAN};
    background: {PANEL};
    font-weight: 800;
    border-top: 3px solid {CYAN};
    padding-top: 8px;
}}
QTabBar::tab:hover {{ color: {TEXT}; }}

QLabel#H1 {{ color: {AMBER}; font-size: 15px; font-family: {MONO}; }}
QLabel#Muted {{ color: {MUTED}; }}
QLabel#KpiValue {{ font-family: {MONO}; font-size: 15px; color: {TEXT}; }}

QFrame#Card {{
    background: {PANEL};
    border: 1.5px solid {BORDER};
    border-radius: {RAD_GROSS};
}}

QCheckBox {{
    spacing: 8px;
    color: {TEXT};
}}
/* KAESTCHEN IN BAEUMEN, TABELLEN UND LISTEN GENAUSO (Sitzung 17, Nutzer-
   Screenshot vom 2. PC: grellweisse Haken-Boxen im Rezept-Baum). Vorher war
   nur QCheckBox gestaltet - die Kaestchen der Item-Ansichten zeichnete
   Windows selbst, und das je nach System-Farbschema hell oder dunkel. */
QCheckBox::indicator, QTreeView::indicator, QTableView::indicator,
QListView::indicator {{
    width: 16px;
    height: 16px;
    /* emm862 (Nutzer-Screenshot: Haken-Box rechts "etwas
       abgeschnitten"): GANZZAHLIGE Border statt 1.5px - bei
       fraktionaler Windows-Skalierung (125/150 %) rundet eine
       1.5px-Kante je nach Pixellage auf 0 und der rechte/untere
       Rahmen verschwindet. 2px rundet nie weg. */
    border: 2px solid {MUTED};
    border-radius: {RAD_KLEIN};
    background: {PANEL2};
}}
QCheckBox::indicator:hover, QTreeView::indicator:hover,
QTableView::indicator:hover, QListView::indicator:hover {{
    border-color: {CYAN};
}}
QCheckBox::indicator:checked, QTreeView::indicator:checked,
QTableView::indicator:checked, QListView::indicator:checked {{
    background: {PANEL2};
    border: 2px solid {GREEN};   /* emm862 */
    image: url({_CHECK_ICON});
}}
QCheckBox::indicator:checked:hover, QTreeView::indicator:checked:hover,
QTableView::indicator:checked:hover, QListView::indicator:checked:hover {{
    border-color: {CYAN};
}}
QTreeView::indicator:indeterminate, QTableView::indicator:indeterminate,
QListView::indicator:indeterminate {{
    background: {PANEL2};
    border: 2px solid {AMBER};   /* emm862 */
}}
QCheckBox::indicator:disabled, QTreeView::indicator:disabled,
QTableView::indicator:disabled, QListView::indicator:disabled {{
    border-color: {BORDER};
    background: {PANEL};
}}

QPushButton {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: {RAD};
    padding: 5px 12px;
    color: {TEXT};
}}
QPushButton:hover {{ border-color: {CYAN}; color: {CYAN}; padding: 3px 12px 7px 12px; }}
QPushButton:pressed {{ background: {PANEL2}; padding: 7px 12px 3px 12px; }}
QPushButton#Primary {{ background: {CYAN_FILL}; color: {CYAN_ON_FILL}; border: 1px solid {CYAN}; font-weight: 600; }}
QPushButton#Primary:hover {{ background: {CYAN_FILL_HOVER}; border: 1px solid {CYAN}; padding: 3px 12px 7px 12px; }}
QPushButton#Primary:pressed {{ background: {CYAN_FILL_PRESS}; border: 1px solid {CYAN}; padding: 7px 12px 3px 12px; }}
QPushButton#Danger:hover {{ border-color: {RED}; color: {RED}; padding: 3px 12px 7px 12px; }}
QPushButton#Danger:pressed {{ background: {PANEL2}; padding: 7px 12px 3px 12px; }}

/* QPlainTextEdit gehoert dazu (Nutzer: "die Suchleiste ist schwer
   erkennbar, weil selbe Hintergrundfarbe") - ohne Eintrag hier faellt
   ein mehrzeiliges Eingabefeld auf den Fensterhintergrund zurueck und
   sieht aus wie Text, nicht wie ein Feld. */
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {PANEL2};
    border: 1px solid {BORDER};
    border-radius: {RAD_KLEIN};
    padding: 3px 6px;
    color: {TEXT};
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {CYAN};
}}
QComboBox::drop-down {{ border: none; }}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    width: 18px;
    border: none;
    border-left: 1px solid {BORDER};
    background: {PANEL};
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {BORDER};
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url({_SPIN_UP}); width: 11px; height: 11px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url({_SPIN_DOWN}); width: 11px; height: 11px;
}}
QComboBox QAbstractItemView {{
    background: {PANEL2}; border: 1px solid {BORDER};
    selection-background-color: {CYAN}; selection-color: {BG};
}}

QTableWidget {{
    background: {PANEL};
    border: 1px solid {BORDER};
    gridline-color: {BORDER};
    alternate-background-color: {PANEL2};
    /* Nutzer: "eine etwas weniger roboterische Schriftart". Vorher stand
       hier Consolas/monospace - das las sich wie ein Terminal. Zahlenspalten
       sind ohnehin rechtsbuendig, die Kante stimmt also weiterhin. */
    font-family: {FONT};
    color: {TEXT};
}}
QHeaderView::section {{
    background: {PANEL2};
    /* emm867 (Nutzer: "alle Column und uebertitel ... bitte ueberall
       anpassen auf amber"): Spaltennamen app-weit amber statt cyan. */
    color: {AMBER};
    border: none;
    border-bottom: 2px solid {toenung(AMBER, 0.4)};
    /* GREIFKANTE SICHTBAR MACHEN (emm876, Nutzer 09.11.2026: "ich kann
       gar nicht sehen wo die spalten zu ziehen sind, weil der anfang
       und ende der spalte nicht eingefaerbt ist, weiss ich nicht wo die
       maus hin soll zum ziehen"). Ohne Trenner muss die Maus eine
       unsichtbare Kante treffen. Dezentes Grau - kein zweiter
       Blickfang neben den amber Titeln. GANZZAHLIG: 1.5px rundet unter
       Windows bei 125/150 % weg (gemessen emm862), darum 1px. */
    border-right: 1px solid {toenung(MUTED, 0.45)};
    padding: 7px 8px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}}
QTableWidget::item {{ padding: 5px 6px; border-bottom: 1px solid {PANEL2}; }}
QTableWidget::item:selected {{ background: #1E3A40; color: {CYAN}; }}
QTreeWidget {{ background: {PANEL}; border: 1px solid {BORDER}; color: {TEXT};
    alternate-background-color: {PANEL2};
    font-family: {FONT}; }}
QTreeWidget::item {{ padding: 2px; }}
QTreeWidget::item:selected {{ background: #1E3A40; color: {CYAN}; }}

QStatusBar {{ background: {PANEL2}; color: {MUTED}; border-top: 1px solid {BORDER}; }}
QScrollBar:vertical {{ background: {BG}; width: 10px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: {RAD_KLEIN}; }}
QScrollBar::handle:vertical:hover {{ background: {CYAN}; }}
QToolTip {{
    background: {PANEL2};
    color: {TEXT};
    border: 1px solid {CYAN};
    border-radius: {RAD};
    padding: 7px 10px;
    font-family: {FONT};
    font-size: 13px;
}}

QMenu {{
    background: {PANEL};
    border: 1px solid {BORDER};
    padding: 4px;
}}
QMenu::item {{
    padding: 7px 18px;
    border-radius: {RAD_KLEIN};
    color: {TEXT};
}}
QMenu::item:selected {{
    background: {CYAN};
    color: {BG};
}}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 6px; }}

/* ---- Haupt-Navigation: Sidebar (links, freie Tools) ---- */
QFrame#Sidebar {{
    background: {tiefe(PANEL2, 0.12)};
    border-right: 1px solid {BORDER};
}}
QLabel#Brand {{
    /* Mit dem goldenen MM-Wappen daneben wirkte das Cyan wie ein zweites,
       konkurrierendes Signal (Sitzung 8). Der Schriftzug nimmt jetzt die
       Logo-Farbe auf - Wappen und Wortmarke lesen sich als EIN Zeichen.
       Etwas kleiner, damit das Wappen die Fuehrung behaelt. */
    color: {AMBER};
    font-size: 19px;
    font-weight: 800;
    letter-spacing: 1px;
    padding: 8px 4px 16px 4px;
}}
QLabel#NavSection {{
    color: {MUTED};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
    padding: 12px 6px 6px 6px;
}}
QPushButton#NavItem {{
    text-align: left;
    background: transparent;
    border: none;
    border-left: 3px solid transparent;
    border-radius: 0px;
    padding: 10px 10px 10px 9px;
    margin: 1px 0px;
    color: {MUTED};
    font-size: 15px;
    font-weight: 500;
}}
QPushButton#NavItem:hover {{
    background: {toenung(CYAN, 0.08)};
    color: {TEXT};
}}
QPushButton#NavItem:checked {{
    background: {toenung(CYAN, 0.14)};
    color: {CYAN};
    font-weight: 700;
    border-left: 3px solid {CYAN};
}}
QPushButton#NavGhost {{
    text-align: left;
    background: transparent;
    border: 1px dashed {BORDER};
    border-radius: {RAD};
    padding: 9px 10px;
    color: {MUTED};
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#NavGhost:hover {{ border-color: {AMBER}; color: {AMBER}; }}

/* ---- Haupt-Navigation: TopBar (Daytrade/Swing/Regional/Bauen) ---- */
QFrame#TopBar {{
    background: {PANEL};
    border-bottom: 1px solid {BORDER};
}}
QPushButton#NavPaid {{
    background: transparent;
    border: 2px solid transparent;
    border-radius: {RAD_GROSS};
    padding: 12px 22px;
    margin: 7px 4px;
    color: {MUTED};
    font-size: 15px;
    font-weight: 700;
}}
QPushButton#NavPaid:hover {{
    background: {toenung(AMBER, 0.14)};
    border-color: {toenung(AMBER, 0.5)};
    color: {TEXT};
}}
QPushButton#NavPaid:checked {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #F7B75C, stop:1 #E08A22);
    border: 2px solid #FBCB82;
    color: {BG};
    font-weight: 800;
}}
QPushButton#CreditsTag {{
    background: {toenung(AMBER, 0.12)};
    border: 1px solid {toenung(AMBER, 0.45)};
    border-radius: {RAD_PILLE};
    padding: 7px 16px;
    color: {AMBER};
    font-weight: 700;
    font-size: 13px;
}}
QPushButton#CreditsTag:hover {{ background: {toenung(AMBER, 0.22)}; }}

/* ---- Ganz oben: die Toolbar (Alles aktualisieren / Hub / Markt-Scan / ...) ---- */
QToolBar {{
    background: {PANEL2};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 8px 10px;
    spacing: 8px;
}}
QToolBar QPushButton {{
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
}}
QToolBar QComboBox {{
    padding: 6px 10px;
    min-height: 18px;
    font-size: 13px;
}}
QToolBar QLabel {{
    font-size: 13px;
}}
"""
# de_scan2: an


# Das Stylesheet, wie es beim Start gilt. `umschalten()` ersetzt es.
QSS = _qss_bauen()



# NACH dem QSS: aa311 schneidet die Knopf-Regel des QSS von "QPushButton {{"
# bis zum ersten "QPushButton:hover" aus - davor stuende diese hier.
def amber_rahmen_knopf():
    """EIN Stil fuer die amber umrandeten Aktions-Knoepfe (Nutzer 26.09.2026:
    "Buy Missing Blueprints und Best Decryptor optisch an Create Shopping
    List anpassen - Hintergrund normale Tool-Farbe, nur Umrandung und Text
    Amber"; "Create shopping list etwas groesser" - 15 px, naechste Stufe der
    Skala FS_*, 14 px ist verboten, aa170). Kein eigener
    Hintergrund in Ruhe - der Knopf behaelt die Flaeche des Themas; Hover
    toent leicht amber. Gesperrt: gedaempftes Amber, damit ein gesperrter
    Knopf nicht wie ein aktiver aussieht. Rahmen in allen Zustaenden gleich
    dick, sonst springt das Layout."""
    return (f"QPushButton{{border:1.5px solid {AMBER}; border-radius:{RAD}; "
            f"padding:7px 16px; color:{AMBER}; font-weight:700; "
            f"font-size:15px;}}"
            f"QPushButton:hover{{background:{toenung(AMBER, 0.16)};}}"
            f"QPushButton:disabled{{border:1.5px solid {AMBER_DIM}; "
            f"color:{AMBER_DIM};}}")


def kopier_knopf_stil():
    """Kleiner Kopier-Knopf wie die Run-Knoepfe im Runplaner (emm329): duenner
    AMBER_DIM-Rahmen, Amber-Text, Hover heller. Fuer "Copy T1 Blueprint" und
    "Copy Decryptor" in der Invention-Karte - beide gleich gross (Nutzer
    02.10.2026). Gesperrt: gedaempft, damit man ihn nicht fuer aktiv haelt."""
    return (f"QPushButton{{background:{PANEL2}; border:1px solid {AMBER_DIM}; "
            f"color:{AMBER}; border-radius:{RAD_KLEIN}; padding:0px 8px;}}"
            f"QPushButton:hover{{border-color:{AMBER}; background:{PANEL};}}"
            f"QPushButton:disabled{{border:1px solid {BORDER}; color:{MUTED};}}")

