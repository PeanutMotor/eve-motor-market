"""Run a blocking function on a background thread and emit the result."""
from PySide6.QtCore import QThread, Signal

from . import ladezeit


class Worker(QThread):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int)
    status = Signal(str)

    def __init__(self, fn, *args, with_progress=False, with_cancel=False,
                 with_status=False, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._cancelled = False
        if with_progress:
            kwargs["progress"] = self.progress.emit
        if with_cancel:
            kwargs["should_cancel"] = self.is_cancelled
        if with_status:
            kwargs["status"] = self.status.emit
        self._kwargs = kwargs

    def cancel(self):
        """Ask the job to stop. Cooperative: jobs that accept `should_cancel`
        check it and bail early; results are discarded either way."""
        self._cancelled = True
        try:
            self.requestInterruption()
        except Exception:
            pass

    def is_cancelled(self):
        return self._cancelled

    def run(self):
        try:
            # LADEZEIT-MESSUNG (nur mit EMM_LADEZEIT=1, sonst ohne Wirkung):
            # jeder Hintergrund-Job mit Wandzeit und teuersten Funktionen.
            with ladezeit.messen("Job " + str(getattr(self._fn, "__qualname__", self._fn))):
                ergebnis = self._fn(*self._args, **self._kwargs)
            self.done.emit(ergebnis)
        except Exception as e:  # surfaced to the UI as a friendly message
            self.failed.emit(str(e))
