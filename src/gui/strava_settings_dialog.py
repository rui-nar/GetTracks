"""Dialog for entering Strava API credentials."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)
from PyQt6.QtCore import Qt

from src.config.settings import Config


class StravaSettingsDialog(QDialog):
    """Modal dialog for entering and saving Strava API credentials."""

    def __init__(self, config: Config, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("Strava Connection")
        self.setMinimumWidth(460)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)

        # ── Instructions ──────────────────────────────────────────────
        hint = QLabel(
            "Create a free Strava API application at "
            "<a href='https://www.strava.com/settings/api'>strava.com/settings/api</a>.<br>"
            "Set the <b>Authorization Callback Domain</b> to <code>localhost</code>."
        )
        hint.setOpenExternalLinks(True)
        hint.setWordWrap(True)
        hint.setTextFormat(Qt.TextFormat.RichText)
        root.addWidget(hint)

        # ── Credentials form ──────────────────────────────────────────
        box = QGroupBox("Strava API credentials")
        form = QFormLayout(box)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(8)

        self._client_id_edit = QLineEdit(self._config.get("strava.client_id", "") or "")
        self._client_id_edit.setPlaceholderText("e.g. 12345")
        form.addRow("Client ID:", self._client_id_edit)

        secret_row = QWidget()
        secret_layout = QHBoxLayout(secret_row)
        secret_layout.setContentsMargins(0, 0, 0, 0)
        secret_layout.setSpacing(4)
        self._client_secret_edit = QLineEdit(self._config.get("strava.client_secret", "") or "")
        self._client_secret_edit.setPlaceholderText("hex string from Strava")
        self._client_secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        show_btn = QPushButton("Show")
        show_btn.setFixedWidth(48)
        show_btn.setCheckable(True)
        show_btn.toggled.connect(self._toggle_secret_visibility)
        secret_layout.addWidget(self._client_secret_edit)
        secret_layout.addWidget(show_btn)
        form.addRow("Client Secret:", secret_row)

        self._redirect_uri_edit = QLineEdit(
            self._config.get("strava.redirect_uri", "") or "http://localhost:8000/callback"
        )
        form.addRow("Redirect URI:", self._redirect_uri_edit)

        root.addWidget(box)

        # ── Buttons ───────────────────────────────────────────────────
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        btns.rejected.connect(self.reject)
        btns.accepted.connect(self._on_save)
        root.addWidget(btns)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _toggle_secret_visibility(self, checked: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        self._client_secret_edit.setEchoMode(mode)
        self.sender().setText("Hide" if checked else "Show")

    def _on_save(self) -> None:
        self._config.set("strava.client_id", self._client_id_edit.text().strip())
        self._config.set("strava.client_secret", self._client_secret_edit.text().strip())
        self._config.set("strava.redirect_uri", self._redirect_uri_edit.text().strip()
                         or "http://localhost:8000/callback")
        self._config.save_user_settings()
        self.accept()
