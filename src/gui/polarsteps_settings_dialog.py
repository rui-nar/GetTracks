"""Dialog for entering Polarsteps credentials."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)
from PyQt6.QtCore import Qt

from src.config.settings import Config


class PolarstepsSettingsDialog(QDialog):
    """Modal dialog for entering and saving Polarsteps credentials."""

    def __init__(self, config: Config, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("Polarsteps Connection")
        self.setMinimumWidth(500)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)

        hint = QLabel(
            "Enter your Polarsteps username and session token.<br>"
            "To get the token: log into "
            "<a href='https://www.polarsteps.com'>polarsteps.com</a>, "
            "open DevTools (F12) → Application → Cookies → copy the value of "
            "<code>remember_token</code>."
        )
        hint.setOpenExternalLinks(True)
        hint.setWordWrap(True)
        hint.setTextFormat(Qt.TextFormat.RichText)
        root.addWidget(hint)

        box = QGroupBox("Polarsteps credentials")
        form = QFormLayout(box)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(8)

        self._username_edit = QLineEdit(self._config.get("polarsteps.username", "") or "")
        self._username_edit.setPlaceholderText("your Polarsteps username")
        form.addRow("Username:", self._username_edit)

        token_row = QWidget()
        token_layout = QHBoxLayout(token_row)
        token_layout.setContentsMargins(0, 0, 0, 0)
        token_layout.setSpacing(4)
        self._token_edit = QLineEdit(self._config.get("polarsteps.remember_token", "") or "")
        self._token_edit.setPlaceholderText("remember_token cookie value")
        self._token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        show_btn = QPushButton("Show")
        show_btn.setFixedWidth(48)
        show_btn.setCheckable(True)
        show_btn.toggled.connect(self._toggle_token_visibility)
        token_layout.addWidget(self._token_edit)
        token_layout.addWidget(show_btn)
        form.addRow("Remember Token:", token_row)

        root.addWidget(box)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        btns.rejected.connect(self.reject)
        btns.accepted.connect(self._on_save)
        root.addWidget(btns)

    def _toggle_token_visibility(self, checked: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        self._token_edit.setEchoMode(mode)
        self.sender().setText("Hide" if checked else "Show")

    def _on_save(self) -> None:
        self._config.set("polarsteps.username", self._username_edit.text().strip())
        self._config.set("polarsteps.remember_token", self._token_edit.text().strip())
        self._config.save_user_settings()
        self.accept()
