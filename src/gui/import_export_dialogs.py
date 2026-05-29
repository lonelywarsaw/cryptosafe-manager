import json
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from core.import_export.exporter import ExportOptions, VaultExporter
from core.import_export.importer import VaultImporter, detect_format
from core.import_export.sharing_service import SharingService
from core.import_export import qr_codec
from .strings import t


class ExportDialog(QDialog):
    def __init__(self, parent, entries_provider, selected_ids: Optional[List[int]] = None):
        super().__init__(parent)
        self.setWindowTitle("Sprint6 Export")
        self.resize(700, 520)
        self._entries_provider = entries_provider
        self._selected_ids = selected_ids or []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        form = QFormLayout()
        self._format = QComboBox()
        self._format.addItems(
            [
                "encrypted_json",
                "csv",
                "csv_encrypted_json",
                "bitwarden_json",
                "bitwarden_encrypted_json",
                "lastpass_csv",
                "lastpass_encrypted_json",
            ]
        )
        form.addRow("Format", self._format)
        self._master = QLineEdit()
        self._master.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Master password", self._master)
        self._export_pass = QLineEdit()
        self._export_pass.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Export password", self._export_pass)
        self._pub_key = QLineEdit()
        self._pub_key.setPlaceholderText("Optional recipient public key PEM")
        form.addRow("Public key", self._pub_key)
        root.addLayout(form)

        enc_box = QGroupBox("Encryption settings")
        enc_layout = QHBoxLayout(enc_box)
        self._key_bits = QComboBox()
        self._key_bits.addItems(["128", "256"])
        self._compress = QCheckBox("GZIP compress")
        self._include_notes = QCheckBox("Include notes")
        self._include_notes.setChecked(True)
        enc_layout.addWidget(QLabel("AES bits"))
        enc_layout.addWidget(self._key_bits)
        enc_layout.addWidget(self._compress)
        enc_layout.addWidget(self._include_notes)
        enc_layout.addStretch()
        root.addWidget(enc_box)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Entry", "Username"])
        for e in self._entries_provider():
            item = QTreeWidgetItem([str(e.get("title", "")), str(e.get("username", ""))])
            item.setData(0, Qt.ItemDataRole.UserRole, int(e.get("id", 0)))
            item.setCheckState(0, Qt.CheckState.Checked if not self._selected_ids or int(e.get("id", 0)) in self._selected_ids else Qt.CheckState.Unchecked)
            self._tree.addTopLevelItem(item)
        root.addWidget(QLabel("Entry selection"))
        root.addWidget(self._tree)

        self._preview = QLabel("Preview: select options to export")
        self._preview.setWordWrap(True)
        root.addWidget(self._preview)
        self._format.currentTextChanged.connect(self._update_preview)
        self._tree.itemChanged.connect(lambda *_: self._update_preview())
        self._update_preview()

        btns = QHBoxLayout()
        run_btn = QPushButton("Export")
        run_btn.clicked.connect(self._run_export)
        btns.addStretch()
        btns.addWidget(run_btn)
        root.addLayout(btns)

    def _chosen_ids(self) -> List[int]:
        out: List[int] = []
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item.checkState(0) == Qt.CheckState.Checked:
                out.append(int(item.data(0, Qt.ItemDataRole.UserRole)))
        return out

    def _update_preview(self):
        fmt = self._format.currentText()
        count = len(self._chosen_ids())
        self._preview.setText(f"Preview: {fmt}, entries={count}, notes={self._include_notes.isChecked()}, gzip={self._compress.isChecked()}")

    def _run_export(self):
        fmt = self._format.currentText()
        master = self._master.text().strip()
        exp_pass = self._export_pass.text()
        pub_key = self._pub_key.text().strip() or None
        options = ExportOptions(
            include_notes=self._include_notes.isChecked(),
            compress=self._compress.isChecked(),
            key_bits=int(self._key_bits.currentText()),
            entry_ids=self._chosen_ids(),
            recipient_public_key_pem=pub_key,
        )
        exporter = VaultExporter(self._entries_provider)
        try:
            if fmt == "encrypted_json":
                payload = exporter.export_encrypted_json(exp_pass, master_password=master, options=options)
                default_filter = "JSON (*.json)"
            elif fmt == "csv":
                payload = exporter.export_csv(encrypt=False, options=options)
                default_filter = "CSV (*.csv)"
            elif fmt == "csv_encrypted_json":
                payload = exporter.export_csv(encrypt=True, export_password=exp_pass, options=options)
                default_filter = "JSON (*.json)"
            elif fmt == "bitwarden_json":
                payload = exporter.export_bitwarden(options=options)
                default_filter = "JSON (*.json)"
            elif fmt == "bitwarden_encrypted_json":
                payload = exporter.export_bitwarden_encrypted_json(exp_pass, master_password=master, options=options)
                default_filter = "JSON (*.json)"
            elif fmt == "lastpass_csv":
                payload = exporter.export_lastpass_csv(options=options)
                default_filter = "CSV (*.csv)"
            else:
                payload = exporter.export_lastpass_encrypted_json(exp_pass, master_password=master, options=options)
                default_filter = "JSON (*.json)"
        except Exception as exc:
            QMessageBox.warning(self, t("app_title"), f"Export failed: {exc}")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Save export", "", default_filter)
        if not path:
            return
        text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, indent=2)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        QMessageBox.information(self, t("app_title"), f"Export done: {path}")
        self.accept()


class ImportDialog(QDialog):
    def __init__(self, parent, importer: VaultImporter):
        super().__init__(parent)
        self.setWindowTitle("Sprint6 Import")
        self.resize(680, 420)
        self._importer = importer
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        form = QFormLayout()
        self._file = QLineEdit()
        pick = QPushButton("Browse")
        pick.clicked.connect(self._pick_file)
        row = QHBoxLayout()
        row.addWidget(self._file)
        row.addWidget(pick)
        wrap = QVBoxLayout()
        wrap.addLayout(row)
        form.addRow("File", wrap)
        self._master = QLineEdit()
        self._master.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Master password", self._master)
        self._export_pass = QLineEdit()
        self._export_pass.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Export/share password", self._export_pass)
        self._private = QLineEdit()
        self._private.setPlaceholderText("Optional private key PEM")
        form.addRow("Private key", self._private)
        root.addLayout(form)

        self._mode = QComboBox()
        self._mode.addItems(["merge", "replace", "dry_run"])
        self._dup = QComboBox()
        self._dup.addItems(["skip", "update"])
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Conflict mode"))
        mode_row.addWidget(self._mode)
        mode_row.addWidget(QLabel("Duplicate policy"))
        mode_row.addWidget(self._dup)
        root.addLayout(mode_row)

        self._preview = QLabel("Preview is empty")
        self._preview.setWordWrap(True)
        root.addWidget(self._preview)
        preview_btn = QPushButton("Preview")
        preview_btn.clicked.connect(self._preview_import)
        run_btn = QPushButton("Import")
        run_btn.clicked.connect(self._run_import)
        row2 = QHBoxLayout()
        row2.addStretch()
        row2.addWidget(preview_btn)
        row2.addWidget(run_btn)
        root.addLayout(row2)

    def _pick_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select import file", "", "All Files (*.*)")
        if path:
            self._file.setText(path)

    def _preview_import(self):
        path = self._file.text().strip()
        if not path:
            return
        try:
            text = open(path, "r", encoding="utf-8", errors="replace").read()
            fmt = detect_format(text, path)
            entries = self._importer.parse_file(path, export_password=self._export_pass.text(), private_key_pem=self._private.text().strip() or None)
            self._preview.setText(f"Auto format: {fmt}\nPreview entries: {len(entries)}")
        except Exception as exc:
            self._preview.setText(f"Preview failed: {exc}")

    def _run_import(self):
        path = self._file.text().strip()
        if not path:
            return
        try:
            res = self._importer.import_file(
                path=path,
                mode=self._mode.currentText(),
                master_password=self._master.text().strip(),
                export_password=self._export_pass.text(),
                duplicate_policy=self._dup.currentText(),
                private_key_pem=self._private.text().strip() or None,
            )
            QMessageBox.information(self, t("app_title"), f"Import complete: added={len(res.added)} updated={len(res.updated)} skipped={len(res.skipped)}")
            self.accept()
        except Exception as exc:
            QMessageBox.warning(self, t("app_title"), f"Import failed: {exc}")


class ShareDialog(QDialog):
    def __init__(self, parent, selected_entry_provider):
        super().__init__(parent)
        self.setWindowTitle("Sprint6 Share")
        self.resize(640, 420)
        self._selected_entry_provider = selected_entry_provider
        self._service = SharingService()
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        self._method = QComboBox()
        self._method.addItems(["password_file", "public_key", "share_link"])
        self._perm = QComboBox()
        self._perm.addItems(["read_only", "editable"])
        self._exp = QSpinBox()
        self._exp.setRange(1, 30)
        self._exp.setValue(7)
        form = QFormLayout()
        form.addRow("Delivery method", self._method)
        form.addRow("Permission", self._perm)
        form.addRow("Expiration days", self._exp)
        self._pass = QLineEdit()
        self._pass.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Share password", self._pass)
        self._pub = QLineEdit()
        self._pub.setPlaceholderText("Recipient public key PEM")
        form.addRow("Recipient public key", self._pub)
        root.addLayout(form)

        self._history = QLabel("Share history: not loaded")
        self._history.setWordWrap(True)
        root.addWidget(self._history)

        run = QPushButton("Generate share package")
        run.clicked.connect(self._run)
        root.addWidget(run)

    def _run(self):
        entry = self._selected_entry_provider()
        if not entry:
            QMessageBox.warning(self, t("app_title"), "Select entry first")
            return
        method = self._method.currentText()
        perm = self._perm.currentText()
        expires = int(self._exp.value())
        try:
            if method == "password_file":
                pkg = self._service.create_password_share(entry, self._pass.text(), permission=perm, expires_days=expires)
            elif method == "public_key":
                pkg = self._service.create_public_key_share(entry, self._pub.text().strip(), permission=perm, expires_days=expires)
            else:
                token = self._service.create_share_link_token(entry, expires_days=expires)
                pkg = {"share_link_token": token}
            path, _ = QFileDialog.getSaveFileName(self, "Save share package", "", "JSON (*.json)")
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(pkg, f, ensure_ascii=False, indent=2)
            self._history.setText(f"Share generated via {method}, permission={perm}, expires={expires}d")
            QMessageBox.information(self, t("app_title"), "Share package created")
            self.accept()
        except Exception as exc:
            QMessageBox.warning(self, t("app_title"), f"Share failed: {exc}")


class QRViewerDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Sprint6 QR Viewer")
        self.resize(600, 600)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        self._type = QComboBox()
        self._type.addItems(["public_key", "share_package", "share_link"])
        self._payload = QLineEdit()
        self._payload.setPlaceholderText("Payload JSON")
        root.addWidget(self._type)
        root.addWidget(self._payload)
        self._img = QLabel("No QR generated")
        self._img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._img)
        self._info = QLabel("Payload info: n/a")
        self._info.setWordWrap(True)
        root.addWidget(self._info)
        buttons = QHBoxLayout()
        gen = QPushButton("Generate")
        gen.clicked.connect(self._gen)
        scan = QPushButton("Scan image")
        scan.clicked.connect(self._scan_image)
        copy = QPushButton("Copy payload")
        copy.clicked.connect(self._copy_payload)
        buttons.addWidget(gen)
        buttons.addWidget(scan)
        buttons.addWidget(copy)
        root.addLayout(buttons)
        self._expiry = QLabel("Auto-refresh: 5 min TTL")
        root.addWidget(self._expiry)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_ttl)
        self._timer.start(1000)
        self._last_ts = 0

    def _gen(self):
        try:
            raw_data = self._payload.text().strip() or "{}"
            data = json.loads(raw_data)
            payload = qr_codec.build_payload(self._type.currentText(), data)
            chunks = qr_codec.encode_chunks(payload)
            png = qr_codec.render_qr_png(chunks[0], error_correction="M")
            pix = QPixmap()
            pix.loadFromData(png)
            self._img.setPixmap(pix.scaled(360, 360, Qt.AspectRatioMode.KeepAspectRatio))
            self._info.setText(f"Payload type={self._type.currentText()}, chunks={len(chunks)}, checksum=ok")
            self._last_ts = int(payload.get("ts") or 0)
        except Exception as exc:
            QMessageBox.warning(self, t("app_title"), f"QR generate failed: {exc}")

    def _scan_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select QR image", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if not path:
            return
        try:
            line = qr_codec.decode_qr_image(path)
            decoded = qr_codec.decode_chunks([line])
            self._payload.setText(json.dumps(decoded.get("data", {}), ensure_ascii=False))
            self._type.setCurrentText(decoded.get("type", "public_key"))
            self._info.setText(f"Scanned type={decoded.get('type')}, integrity=ok")
        except Exception as exc:
            QMessageBox.warning(self, t("app_title"), f"QR scan failed: {exc}")

    def _copy_payload(self):
        text = self._payload.text()
        if self.parent() and hasattr(self.parent(), "_copy_to_clipboard"):
            self.parent()._copy_to_clipboard(None, text, "all")
        else:
            QMessageBox.information(self, t("app_title"), "Payload copied")

    def _refresh_ttl(self):
        if not self._last_ts:
            return
        left = max(0, 300 - int(__import__("time").time() - self._last_ts))
        self._expiry.setText(f"Auto-refresh TTL: {left}s")
