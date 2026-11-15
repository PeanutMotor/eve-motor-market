"""UI thread watchdog (emm869) - pure, testable without Qt.

User 08.11.2026: "Beim start von MoMa bleibt es fast stehen ...
(Keine Rueckmeldung) ... der ladebalken bleibt stehen bis es dann
'plopp' macht und alles da ist." The window freezing means the UI
THREAD is blocked - not the network, a worker never freezes the
window. The freeze happens on his Windows machine and is not
reproducible offscreen, so rule 5 (reproduce first) needs eyes ON
SITE: a heartbeat timer ticks on the UI thread; this watchdog thread
notices when the beat stops and writes WHO is blocking - the live
stack of the UI thread via sys._current_frames() - into fehler.log.
One report per freeze, plus the recovery with the total duration.
Always on: the cost is one 250 ms timer and a sleeping thread.
"""
import sys
import threading
import time
import traceback

SCHWELLE_S = 1.0          # ab hier gilt die Oberflaeche als blockiert
TAKT_S = 0.25             # Pruef- und Herzschlag-Takt
# emm873: EIN Stack reicht nicht. Am 08.11.2026 stand in fehler.log eine
# Blockade von 43 s - mit genau einem Stack, aufgenommen nach 1.2 s. Der
# zeigt, wo es ANFING, nicht wo die Zeit blieb. Bei einer langen Blockade
# wird deshalb nachgeschaut, und zwar mit wachsendem Abstand (5, 10,
# 20 ... s), gedeckelt auf HOECHSTENS_PROBEN - sonst fuellt eine haengende
# Oberflaeche die Logdatei.
NACHSCHAU_S = 5.0
HOECHSTENS_PROBEN = 6


class UiWache:
    def __init__(self, log, schwelle=SCHWELLE_S):
        self._log = log                    # fn(wo, text)
        self._schwelle = float(schwelle)
        self._letzter = time.monotonic()
        self._gemeldet = False
        self._start_block = 0.0
        self._proben = 0            # emm873: Stacks dieser Blockade
        self._naechste = 0.0        # ab welcher Stillstandsdauer die naechste
        self._stop = threading.Event()
        self._thread = None
        self._ui_tid = None

    def herzschlag(self):
        """Vom QTimer im UI-Thread gerufen - solange das tickt, lebt
        die Oberflaeche."""
        self._letzter = time.monotonic()

    def start(self, ui_thread_id):
        self._ui_tid = int(ui_thread_id)
        self._letzter = time.monotonic()
        self._thread = threading.Thread(target=self._lauf, daemon=True,
                                        name="ui-wache")
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _stack_text(self):
        frames = sys._current_frames()
        f = frames.get(self._ui_tid)
        if f is None:
            return "(UI thread stack not reachable)"
        return "".join(traceback.format_stack(f))

    def _lauf(self):
        while not self._stop.wait(TAKT_S):
            still = time.monotonic() - self._letzter
            if still >= self._schwelle and not self._gemeldet:
                self._gemeldet = True
                self._start_block = self._letzter
                self._proben = 1
                self._naechste = NACHSCHAU_S
                try:
                    self._log("UI-Wache",
                              f"UI thread blocked for {still:.1f} s"
                              f" - live stack of the blocker:\n"
                              + self._stack_text())
                except Exception:
                    pass
            elif (still >= self._schwelle and self._gemeldet
                  and self._proben < HOECHSTENS_PROBEN
                  and still >= self._naechste):
                # WO BLEIBT DIE ZEIT WIRKLICH (emm873)? Die erste Probe
                # zeigt nur den Anfang der Blockade.
                self._proben += 1
                self._naechste = still * 2.0
                try:
                    self._log("UI-Wache",
                              f"still blocked after {still:.1f} s"
                              f" (sample {self._proben}"
                              f"/{HOECHSTENS_PROBEN}):\n"
                              + self._stack_text())
                except Exception:
                    pass
            elif still < self._schwelle and self._gemeldet:
                self._gemeldet = False
                dauer = self._letzter - self._start_block
                try:
                    self._log("UI-Wache",
                              f"UI thread responsive again (blocked for "
                              f"~{max(dauer, self._schwelle):.1f} s).")
                except Exception:
                    pass
