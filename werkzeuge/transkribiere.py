r"""Sprache -> Text (Deutsch) fuer die YouTube-Tutorials (19.09.2026).

Aufruf:  python werkzeuge\transkribiere.py "C:\Pfad\video.mp4" [weitere ...]
oder:    Datei(en) auf werkzeuge\transkribiere.bat ziehen.

Schreibt neben jede Datei SECHS Dateien (Fassung 4, 20.09.2026):
  <name>.de.txt       Fliesstext mit Zeitmarken je Absatz (zum Lesen)
  <name>.de.srt       Untertitel (fuer YouTube)
  <name>.en.txt       englische Fassung, gleiche Absaetze   <- NEU
  <name>.en.srt       englische Untertitel                  <- NEU
  <name>.dub.csv      fuer ElevenLabs Dubbing Studio (mit englischer Spalte)
  <name>.sprech.txt   Sprechskript mit Start/Ende/Dauer je Block, dazu der
                      PREMIERE-Timecode (hh:mm:ss:ff) zum Eintippen

ENGLISCH KOMMT DIREKT AUS WHISPER (Nutzer-Wunsch 20.09.2026: "kannst du
direkt auf englisch uebersetzen?"). Das Modell kann das selbst:
`transcribe(..., task="translate")` uebersetzt IMMER nach Englisch - in
genau der Fassung von faster-whisper, die hier laeuft (Signatur geprueft:
`task: str = 'transcribe'`, Doku "Task to execute (transcribe or
translate)"). Es ist ein ZWEITER Durchlauf, das Transkribieren dauert also
ungefaehr doppelt so lange; abschalten mit  set MOMA_EN=0.

EHRLICH DAZU: das ist eine MASCHINELLE Uebersetzung. Sie sitzt bei normalen
Saetzen gut, aber EVE-Begriffe (Blueprint, Invention, Runplaner, ISK, Namen
von Strukturen) kommen oft schief heraus. Die .en.txt ist ein Rohentwurf -
fuer die Vertonung lohnt es sich, sie einmal durchzugehen oder sie dem
Assistenten zu geben.

FUER ELEVENLABS (nachgeschlagen 20.09.2026, Doku "Dubbing Studio"): ein SRT
laesst sich dort NICHT importieren - die Zeitsteuerung kommt ueber eine CSV
mit den Spalten speaker, start_time, end_time, transcription, translation.
Erlaubte Zeitformate laut Doku: Sekunden, hh:mm:ss:frame und hh:mm:ss,mmm;
hier wird hh:mm:ss,mmm geschrieben (deshalb MUSS die CSV in Anfuehrungs-
zeichen stehen - das Komma steckt in der Zeit selbst; das csv-Modul macht
das von sich aus).

Die .sprech.txt ist fuer den Fall, dass die Stimme nur in der normalen
Sprachausgabe erzeugt wird: sie nennt je Block Start, Ende und die DAUER in
Sekunden - daran sieht man sofort, wie lang der erzeugte Ton hoechstens
werden darf, damit er noch ins Bild passt.

Laeuft KOMPLETT auf diesem Rechner (faster-whisper, Modell "medium",
~1,5 GB, wird beim ersten Lauf einmalig geladen). Kein Ton verlaesst den PC.
"""
import csv
import os
import sys
import time
import warnings

# Hinweise von huggingface_hub (Symlinks, HF_TOKEN) sind fuer uns bedeutungslos
# und erschreckten beim ersten Lauf (19.09.2026) - still stellen.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "0")
warnings.filterwarnings("ignore")

MODELL = os.environ.get("MOMA_WHISPER", "medium")
FASSUNG = 5
# Name in der Spalte `speaker`. Dubbing Studio trennt danach die Stimmen;
# bei einem Sprecher ist nur wichtig, dass ueberall dasselbe steht.
SPRECHER = os.environ.get("MOMA_SPRECHER", "Peanut Motor")
# Englische Fassung mitschreiben? Standard JA (dafuer ist sie gebaut).
MIT_EN = os.environ.get("MOMA_EN", "1").strip().lower() not in ("0", "nein", "no")
# BILDRATE FUER DEN PREMIERE-TIMECODE (Nutzer 20.09.2026: "ich fuege dann
# spaeter Tonspur und Video in Adobe Premiere Pro zusammen"). Premiere
# springt auf hh:mm:ss:ff, nicht auf Millisekunden - wer die Startzeit dort
# eintippen will, braucht Frames. Eigene Bildrate: set MOMA_FPS=25
# In Premiere nachzusehen unter Sequenz > Sequenzeinstellungen.
# 60 ist die Bildrate SEINES Projekts (Screenshot der Sequenzeinstellungen
# vom 20.09.2026: Timebase 60.00 frames/second, Display Format "60 fps
# Timecode") - eine GLATTE Rate, also kein Drop-Frame und keine Drift.
try:
    FPS = float(os.environ.get("MOMA_FPS", "60") or 60)
except ValueError:
    FPS = 60.0
if FPS <= 0:
    FPS = 60.0


def _srt_zeit(s):
    """hh:mm:ss,mmm - GANZ in Millisekunden gerechnet.

    Vorher stand hier `int((s - int(s)) * 1000)`: aus 21.2 wurde damit
    ",199" statt ",200", weil 21.2 als Gleitkommazahl knapp darunter liegt.
    Fuer Untertitel egal, fuer die Dubbing-CSV unschoen - und billig zu
    beheben. `round` auf die ganze Zahl, dann erst zerlegen (sonst koennte
    beim Aufrunden ",1000" herauskommen).
    """
    ms = max(0, int(round(float(s) * 1000)))
    sek_ganz, ms_rest = divmod(ms, 1000)
    h, r = divmod(sek_ganz, 3600)
    m, sek = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{sek:02d},{ms_rest:03d}"


def _tc(s, fps=None):
    """hh:mm:ss:ff - der Timecode, den Premiere im Zeitfeld annimmt.

    GRENZE, ehrlich dazugesagt: das ist die einfache Rechnung mit ganzen
    Bildern. Bei 25, 30, 50 oder 60 fps stimmt sie genau. Bei 29.97 oder
    59.94 (NTSC) arbeitet Premiere mit Drop-Frame-Timecode; dann laeuft
    diese Angabe ueber die Laenge langsam davon - rund eine Sekunde je
    tausend Sekunden Film. Fuer ein Tutorial von ein paar Minuten ist das
    unter einer halben Sekunde, fuer eine Stunde nicht mehr.
    """
    f = float(fps or FPS)
    ms = max(0, int(round(float(s) * 1000)))
    sek_ganz, ms_rest = divmod(ms, 1000)
    bild = int(ms_rest * f / 1000.0)
    bild = min(bild, int(f) - 1 if f >= 1 else 0)
    h, r = divmod(sek_ganz, 3600)
    m, sek = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{sek:02d}:{bild:02d}"


def bloecke(segmente, sek_max=30.0, sek_satz=20.0):
    """Segmente zu Absaetzen zusammenfassen -> [{start, ende, text}, ...].

    EIGENE FUNKTION, damit sie ohne faster-whisper pruefbar ist (die
    Absatzlogik stand frueher mitten in der Transkriptions-Schleife und war
    damit nur mit Modell und Tondatei zu testen).

    Ein Absatz endet nach `sek_max` Sekunden - oder schon nach `sek_satz`,
    wenn der Text gerade auf einem Satzzeichen steht. So faellt der Schnitt
    moeglichst auf eine Sprechpause.
    """
    aus, teile, start = [], [], 0.0
    for seg in segmente:
        text = (getattr(seg, "text", None) or "").strip()
        if not text:
            continue
        if not teile:
            start = float(seg.start)
        teile.append(text)
        ende = float(seg.end)
        if (ende - start >= sek_max
                or (ende - start >= sek_satz and text[-1:] in ".!?")):
            aus.append({"start": start, "ende": ende, "text": " ".join(teile)})
            teile = []
    if teile:
        aus.append({"start": start, "ende": float(ende), "text": " ".join(teile)})
    return aus


def zuordnen_en(bl, en_segmente):
    """Englische Segmente den DEUTSCHEN Bloecken zuordnen -> [text, ...].

    Der Uebersetzungslauf schneidet die Segmente anders als der deutsche -
    man kann die Texte also nicht einfach der Reihe nach nebeneinander
    legen. Zugeordnet wird ueber die ZEIT: ein englisches Segment gehoert zu
    dem Block, in dessen Fenster seine MITTE faellt. Die Mitte, nicht der
    Anfang: ein Segment, das ueber eine Blockgrenze laeuft, landet damit
    dort, wo der groessere Teil liegt.

    Rein und ohne Whisper pruefbar.
    """
    aus = ["" for _ in bl]
    if not bl:
        return aus
    for seg in en_segmente or []:
        text = (getattr(seg, "text", None) or "").strip()
        if not text:
            continue
        mitte = (float(seg.start) + float(seg.end)) / 2.0
        ziel = None
        for i, b in enumerate(bl):
            if b["start"] <= mitte < b["ende"]:
                ziel = i
                break
        if ziel is None:
            # Ausserhalb aller Fenster (Rundung an den Raendern): der
            # zeitlich naechste Block bekommt es - weglassen waere
            # schlechter, dann fehlte ein Satz in der Vertonung.
            ziel = min(range(len(bl)),
                       key=lambda i: min(abs(mitte - bl[i]["start"]),
                                         abs(mitte - bl[i]["ende"])))
        aus[ziel] = (aus[ziel] + " " + text).strip()
    return aus


def schreibe_dub_csv(pfad, bl, sprecher=SPRECHER, en=None):
    """CSV fuer ElevenLabs Dubbing Studio (Manual Dub).

    `en` sind die englischen Texte je Block (aus zuordnen_en). Fehlen sie,
    bleibt `translation` LEER - leer ist ehrlicher als den deutschen Text zu
    wiederholen: sonst vertont man versehentlich zweimal dasselbe.
    """
    with open(pfad, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(["speaker", "start_time", "end_time",
                    "transcription", "translation"])
        for i, b in enumerate(bl):
            w.writerow([sprecher, _srt_zeit(b["start"]), _srt_zeit(b["ende"]),
                        b["text"], (en or [""] * len(bl))[i] if en else ""])
    return pfad


def schreibe_sprechskript(pfad, bl, kopf=""):
    """Sprechskript: je Block Start, Ende, DAUER und der Text.

    Die Dauer ist das eigentlich Nuetzliche - sie sagt, wie lang der erzeugte
    Ton hoechstens sein darf, damit er noch in dieselbe Stelle im Video passt.
    """
    with open(pfad, "w", encoding="utf-8") as f:
        if kopf:
            f.write(kopf + "\n")
        f.write("# Je Block: Start --> Ende (Dauer). Der erzeugte Ton sollte\n"
                "# nicht laenger als die Dauer werden, sonst verschiebt sich\n"
                "# alles Nachfolgende.\n"
                f"# PREMIERE: die Zeile 'PR' ist der Timecode bei {FPS:g} fps -\n"
                "# im Zeitfeld eintippen, Abspielkopf springt hin, Ton einfuegen.\n"
                "# Andere Bildrate:  set MOMA_FPS=25  vor dem Lauf.\n\n")
        for i, b in enumerate(bl, 1):
            d = max(0.0, b["ende"] - b["start"])
            f.write(f"[{i:03d}] {_srt_zeit(b['start'])} --> "
                    f"{_srt_zeit(b['ende'])}  ({d:.1f} s)\n")
            f.write(f"      PR {_tc(b['start'])}\n")
            f.write(b["text"] + "\n\n")
    return pfad


def transkribiere(pfad):
    from faster_whisper import WhisperModel
    t0 = time.time()
    print(f"Modell {MODELL} laden (beim ersten Mal ~1,5 GB Download, ohne Anzeige - bitte warten) ...", flush=True)
    modell = WhisperModel(MODELL, device="cpu", compute_type="int8")
    print(f"  {time.time() - t0:.0f} s. Transkribiere {os.path.basename(pfad)} ...", flush=True)
    segmente, info = modell.transcribe(pfad, language="de", beam_size=5,
                                       vad_filter=True)
    basis = os.path.splitext(pfad)[0]
    srt, gesammelt = [], []
    for i, seg in enumerate(segmente, 1):
        text = seg.text.strip()
        if not text:
            continue
        srt.append(f"{i}\n{_srt_zeit(seg.start)} --> {_srt_zeit(seg.end)}\n{text}\n")
        gesammelt.append(seg)
        print(f"  {_srt_zeit(seg.start)}  {text[:80]}", flush=True)
    bl = bloecke(gesammelt)
    # ZWEITER LAUF: dasselbe Modell, aber task="translate" -> Englisch.
    en_texte, en_srt = None, []
    if MIT_EN:
        print("  Englische Fassung (zweiter Durchlauf, task=translate) ...",
              flush=True)
        en_seg, _ = modell.transcribe(pfad, language="de", beam_size=5,
                                      vad_filter=True, task="translate")
        en_gesammelt = []
        for i, seg in enumerate(en_seg, 1):
            text = seg.text.strip()
            if not text:
                continue
            en_srt.append(f"{i}\n{_srt_zeit(seg.start)} --> "
                          f"{_srt_zeit(seg.end)}\n{text}\n")
            en_gesammelt.append(seg)
        en_texte = zuordnen_en(bl, en_gesammelt)
    kopf = (f"# Transkript (Deutsch) - {os.path.basename(pfad)} - "
            f"Modell {MODELL} - Fassung {FASSUNG} - Dauer {info.duration:.0f} s")
    with open(basis + ".de.txt", "w", encoding="utf-8") as f:
        f.write(kopf + "\n\n")
        f.write("\n\n".join(
            f"[{int(b['start'] // 60):02d}:{int(b['start'] % 60):02d}] {b['text']}"
            for b in bl) + "\n")
    with open(basis + ".de.srt", "w", encoding="utf-8") as f:
        f.write("\n".join(srt))
    dateien = [".de.txt", ".de.srt"]
    if en_texte is not None:
        with open(basis + ".en.txt", "w", encoding="utf-8") as f:
            f.write(kopf.replace("(Deutsch)", "(English, machine translation)")
                    + "\n\n")
            f.write("\n\n".join(
                f"[{int(b['start'] // 60):02d}:{int(b['start'] % 60):02d}] {tx}"
                for b, tx in zip(bl, en_texte) if tx) + "\n")
        with open(basis + ".en.srt", "w", encoding="utf-8") as f:
            f.write("\n".join(en_srt))
        dateien += [".en.txt", ".en.srt"]
    schreibe_dub_csv(basis + ".dub.csv", bl, en=en_texte)
    schreibe_sprechskript(basis + ".sprech.txt", bl, kopf)
    dateien += [".dub.csv", ".sprech.txt"]
    print(f"FERTIG ({time.time() - t0:.0f} s):", flush=True)
    for e in dateien:
        print(f"  {basis}{e}", flush=True)
    print("  -> .dub.csv in ElevenLabs Dubbing Studio (Manual Dub) laden.",
          flush=True)
    if en_texte is not None:
        print("  -> Das Englisch ist MASCHINELL. EVE-Begriffe (Blueprint,\n"
              "     Invention, ISK, Strukturnamen) vorher durchsehen.",
              flush=True)
    else:
        print("  -> Ohne Englisch gelaufen (MOMA_EN=0): die Spalte\n"
              "     'translation' ist leer.", flush=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    fehler = 0
    for p in sys.argv[1:]:
        p = p.strip().lstrip("\ufeff")      # BOM aus PowerShell-Listen (Fassung 2)
        if not os.path.exists(p):
            print(f"FEHLT: {p!r}")
            fehler += 1
            continue
        transkribiere(p)
    sys.exit(1 if fehler else 0)
