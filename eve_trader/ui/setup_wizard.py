"""Guided one-time setup so the user never has to hunt for anything.

Opens the EVE developer portal, hands over the exact values to paste, and takes
the Client-ID. After this, linking a character is a single click forever.
"""
import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout,
)

from .. import config
from ..sprache import t
from . import icons, theme

PORTAL_URL = "https://developers.eveonline.com/applications"


def _step(num, text):
    row = QHBoxLayout()
    badge = QLabel(str(num))
    badge.setFixedSize(24, 24)
    badge.setAlignment(Qt.AlignCenter)
    badge.setStyleSheet(
        f"background:{theme.CYAN_FILL};color:{theme.CYAN};border-radius:12px;font-weight:700;")
    lab = QLabel(text)
    lab.setWordWrap(True)
    row.addWidget(badge, 0, Qt.AlignTop)
    row.addSpacing(8)
    row.addWidget(lab, 1)
    return row


class _CopyRow(QFrame):
    def __init__(self, label, value):
        super().__init__()
        self.setObjectName("Card")
        self._value = value
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        cap = QLabel(label)
        cap.setObjectName("Muted")
        cap.setFixedWidth(110)
        val = QLineEdit(value)
        val.setReadOnly(True)
        btn = QPushButton(t("Copy"))
        btn.setIcon(icons.icon("check"))
        btn.clicked.connect(self._copy)
        self._btn = btn
        lay.addWidget(cap)
        lay.addWidget(val, 1)
        lay.addWidget(btn)

    def _copy(self):
        QApplication.clipboard().setText(self._value)
        self._btn.setText(t("Copied \u2713"))


class SetupWizard(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle(t("One-time setup"))
        self.setMinimumWidth(560)
        self.setStyleSheet(theme.QSS)
        port = int(settings.get("callback_port", 8635))

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(14)

        title = QLabel(t("Connect EVE once"))
        title.setObjectName("H1")
        root.addWidget(title)
        intro = QLabel(t("Set this up once; from then on a single click on "
                         "\u201eLink character\u201c is enough. Takes about 2 minutes."))
        intro.setObjectName("Muted")
        intro.setWordWrap(True)
        root.addWidget(intro)

        root.addLayout(_step(1, t("Open the EVE developer portal and log in (same "
                                  "credentials as in the game).")))
        open_btn = QPushButton(t("\u2460 Open EVE portal"))
        open_btn.setIcon(icons.icon("eye"))
        open_btn.setObjectName("Primary")
        open_btn.clicked.connect(lambda: webbrowser.open(PORTAL_URL))
        root.addWidget(open_btn, alignment=Qt.AlignLeft)

        root.addLayout(_step(2, t("There: \u201eCreate New Application\u201c. Connection "
                                  "Type: \u201eAuthentication & API Access\u201c. Enter these "
                                  "values:")))
        root.addWidget(_CopyRow(t("Callback URL"), config.callback_url(port)))
        root.addWidget(_CopyRow("Scopes",
                                " ".join(config.DEFAULT_SCOPES
                                         + [config.ASSETS_SCOPE, config.UI_SCOPE,
                                            # Standort-Hinweis ist Standard AN (emm316)
                                            config.LOCATION_SCOPE])))
        hint = QLabel(t("Pick the scopes from the list in the portal (use the search "
                        "box). Name and description of the app are up to you."))
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        root.addWidget(hint)

        root.addLayout(_step(3, t("Save, then copy the \u201eClient ID\u201c and paste it "
                                  "here:")))
        self.client_field = QLineEdit(settings.get("client_id", ""))
        self.client_field.setPlaceholderText(t("Paste Client ID here"))
        root.addWidget(self.client_field)

        self.err = QLabel("")
        self.err.setStyleSheet(f"color:{theme.RED}")
        root.addWidget(self.err)

        btns = QHBoxLayout()
        btns.addStretch()
        later = QPushButton(t("Later"))
        later.setIcon(icons.icon("close"))
        later.clicked.connect(self.reject)
        save = QPushButton(t("Done & save"))
        save.setIcon(icons.icon("check"))
        save.setObjectName("Primary")
        save.clicked.connect(self._save)
        btns.addWidget(later)
        btns.addWidget(save)
        root.addLayout(btns)

    def _save(self):
        cid = self.client_field.text().strip()
        if not cid:
            self.err.setText(t("Please paste the Client ID."))
            return
        self.settings["client_id"] = cid
        config.save_settings(self.settings)
        self.accept()
