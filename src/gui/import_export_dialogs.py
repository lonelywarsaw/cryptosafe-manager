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
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from core.import_export.exporter import ExportOptions, VaultExporter
from core.import_export.importer import VaultImporter, detect_format
from core.import_export.key_exchange import optional_private_key_pem, optional_public_key_pem
from core.import_export.sharing_service import SharingService
from core.import_export import qr_codec
from .strings import t


def _fill_combo(combo: QComboBox, items: List[tuple]) -> None:
    combo.clear()
    for value, label_key in items:
        combo.addItem(t(label_key), value)


class ExportDialog(QDialog):
    def __init__(self, parent, entries_provider, selected_ids: Optional[List[int]] = None):
        super().__init__(parent)
        self.setWindowTitle(t("s6_export_title"))
        self.resize(700, 520)
        self._entries_provider = entries_provider
        self._selected_ids = selected_ids or []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        form = QFormLayout()
        self._format = QComboBox()
        _fill_combo(
            self._format,
            [
                ("encrypted_json", "s6_fmt_encrypted_json"),
                ("csv", "s6_fmt_csv"),
                ("csv_encrypted_json", "s6_fmt_csv_enc"),
                ("bitwarden_json", "s6_fmt_bw"),
                ("bitwarden_encrypted_json", "s6_fmt_bw_enc"),
                ("lastpass_csv", "s6_fmt_lp"),
                ("lastpass_encrypted_json", "s6_fmt_lp_enc"),
            ],
        )
        form.addRow(t("s6_format"), self._format)
        self._master = QLineEdit()
        self._master.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(t("master_password"), self._master)
        self._export_pass = QLineEdit()
        self._export_pass.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(t("s6_export_password"), self._export_pass)
        self._pub_key = QLineEdit()
        self._pub_key.setPlaceholderText(t("s6_public_key_ph"))
        form.addRow(t("s6_public_key"), self._pub_key)
        root.addLayout(form)

        enc_box = QGroupBox(t("s6_encryption_settings"))
        enc_layout = QHBoxLayout(enc_box)
        self._key_bits = QComboBox()
        self._key_bits.addItems(["128", "256"])
        self._compress = QCheckBox(t("s6_gzip"))
        self._include_notes = QCheckBox(t("s6_include_notes"))
        self._include_notes.setChecked(True)
        enc_layout.addWidget(QLabel(t("s6_aes_bits")))
        enc_layout.addWidget(self._key_bits)
        enc_layout.addWidget(self._compress)
        enc_layout.addWidget(self._include_notes)
        enc_layout.addStretch()
        root.addWidget(enc_box)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels([t("s6_col_entry"), t("login")])
        for e in self._entries_provider():
            item = QTreeWidgetItem([str(e.get("title", "")), str(e.get("username", ""))])
            item.setData(0, Qt.ItemDataRole.UserRole, int(e.get("id", 0)))
            item.setCheckState(
                0,
                Qt.CheckState.Checked
                if not self._selected_ids or int(e.get("id", 0)) in self._selected_ids
                else Qt.CheckState.Unchecked,
            )
            self._tree.addTopLevelItem(item)
        root.addWidget(QLabel(t("s6_entry_selection")))
        root.addWidget(self._tree)

        self._preview = QLabel(t("s6_preview"))
        self._preview.setWordWrap(True)
        root.addWidget(self._preview)
        self._format.currentIndexChanged.connect(self._update_preview)
        self._tree.itemChanged.connect(lambda *_: self._update_preview())
        self._update_preview()

        btns = QHBoxLayout()
        run_btn = QPushButton(t("s6_export_btn"))
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
        fmt = self._format.currentData()
        count = len(self._chosen_ids())
        self._preview.setText(
            f"{t('s6_preview')}: {fmt}, {count}, notes={self._include_notes.isChecked()}"
        )

    def _run_export(self):
        fmt = self._format.currentData()
        master = self._master.text().strip()
        exp_pass = self._export_pass.text()
        pub_raw = self._pub_key.text().strip()
        try:
            pub_key = optional_public_key_pem(self._pub_key.text())
        except ValueError:
            QMessageBox.warning(self, t("app_title"), t("s6_invalid_pem"))
            return
        if pub_raw and not pub_key:
            QMessageBox.warning(self, t("app_title"), t("s6_invalid_pem"))
            return

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
            err = str(exc)
            if "PEM" in err or "MalformedFraming" in type(exc).__name__:
                QMessageBox.warning(self, t("app_title"), t("s6_invalid_pem"))
            else:
                QMessageBox.warning(self, t("app_title"), t("s6_export_failed") % err)
            return

        path, _ = QFileDialog.getSaveFileName(self, t("s6_save_export"), "", default_filter)
        if not path:
            return
        text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, indent=2)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        QMessageBox.information(self, t("app_title"), t("s6_export_done") % path)
        self.accept()


class ImportDialog(QDialog):
    def __init__(self, parent, importer: VaultImporter):
        super().__init__(parent)
        self.setWindowTitle(t("s6_import_title"))
        self.resize(680, 420)
        self._importer = importer
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        form = QFormLayout()
        self._file = QLineEdit()
        pick = QPushButton(t("s6_browse"))
        pick.clicked.connect(self._pick_file)
        row = QHBoxLayout()
        row.addWidget(self._file)
        row.addWidget(pick)
        wrap = QVBoxLayout()
        wrap.addLayout(row)
        form.addRow(t("s6_file"), wrap)
        self._master = QLineEdit()
        self._master.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(t("master_password"), self._master)
        self._export_pass = QLineEdit()
        self._export_pass.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(t("s6_export_password"), self._export_pass)
        self._private = QLineEdit()
        self._private.setPlaceholderText(t("s6_private_key_ph"))
        form.addRow(t("s6_private_key"), self._private)
        root.addLayout(form)

        self._mode = QComboBox()
        _fill_combo(
            self._mode,
            [("merge", "s6_mode_merge"), ("replace", "s6_mode_replace"), ("dry_run", "s6_mode_dry")],
        )
        self._dup = QComboBox()
        _fill_combo(self._dup, [("skip", "s6_dup_skip"), ("update", "s6_dup_update")])
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel(t("s6_conflict_mode")))
        mode_row.addWidget(self._mode)
        mode_row.addWidget(QLabel(t("s6_duplicate_policy")))
        mode_row.addWidget(self._dup)
        root.addLayout(mode_row)

        self._preview = QLabel(t("s6_preview"))
        self._preview.setWordWrap(True)
        root.addWidget(self._preview)
        preview_btn = QPushButton(t("s6_preview_btn"))
        preview_btn.clicked.connect(self._preview_import)
        run_btn = QPushButton(t("s6_import_btn"))
        run_btn.clicked.connect(self._run_import)
        row2 = QHBoxLayout()
        row2.addStretch()
        row2.addWidget(preview_btn)
        row2.addWidget(run_btn)
        root.addLayout(row2)

    def _pick_file(self):
        path, _ = QFileDialog.getOpenFileName(self, t("s6_select_import"), "", "All Files (*.*)")
        if path:
            self._file.setText(path)

    def _private_pem(self) -> Optional[str]:
        try:
            return optional_private_key_pem(self._private.text())
        except ValueError:
            raise

    def _preview_import(self):
        path = self._file.text().strip()
        if not path:
            return
        try:
            priv = self._private_pem()
            text = open(path, "r", encoding="utf-8", errors="replace").read()
            fmt = detect_format(text, path)
            entries = self._importer.parse_file(
                path, export_password=self._export_pass.text(), private_key_pem=priv
            )
            self._preview.setText(f"{t('s6_preview')}: {fmt}, {len(entries)}")
        except ValueError:
            QMessageBox.warning(self, t("app_title"), t("s6_invalid_pem"))
        except Exception as exc:
            self._preview.setText(t("s6_preview_failed") % exc)

    def _run_import(self):
        path = self._file.text().strip()
        if not path:
            return
        try:
            priv = self._private_pem()
            res = self._importer.import_file(
                path=path,
                mode=self._mode.currentData(),
                master_password=self._master.text().strip(),
                export_password=self._export_pass.text(),
                duplicate_policy=self._dup.currentData(),
                private_key_pem=priv,
            )
            QMessageBox.information(
                self,
                t("app_title"),
                t("s6_import_done") % (len(res.added), len(res.updated), len(res.skipped)),
            )
            self.accept()
        except ValueError:
            QMessageBox.warning(self, t("app_title"), t("s6_invalid_pem"))
        except Exception as exc:
            err = str(exc)
            if "PEM" in err or "MalformedFraming" in type(exc).__name__:
                QMessageBox.warning(self, t("app_title"), t("s6_invalid_pem"))
            else:
                QMessageBox.warning(self, t("app_title"), t("s6_import_failed") % err)


class ShareDialog(QDialog):
    def __init__(self, parent, selected_entry_provider):
        super().__init__(parent)
        self.setWindowTitle(t("s6_share_title"))
        self.resize(640, 420)
        self._selected_entry_provider = selected_entry_provider
        self._service = SharingService()
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        self._method = QComboBox()
        _fill_combo(
            self._method,
            [
                ("password_file", "s6_method_password"),
                ("public_key", "s6_method_pubkey"),
                ("share_link", "s6_method_link"),
            ],
        )
        self._perm = QComboBox()
        _fill_combo(self._perm, [("read_only", "s6_perm_readonly"), ("editable", "s6_perm_edit")])
        self._exp = QSpinBox()
        self._exp.setRange(1, 30)
        self._exp.setValue(7)
        form = QFormLayout()
        form.addRow(t("s6_delivery"), self._method)
        form.addRow(t("s6_permission"), self._perm)
        form.addRow(t("s6_expiration_days"), self._exp)
        self._pass = QLineEdit()
        self._pass.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(t("s6_share_password"), self._pass)
        self._pub = QLineEdit()
        self._pub.setPlaceholderText(t("s6_public_key_ph"))
        form.addRow(t("s6_public_key"), self._pub)
        root.addLayout(form)

        self._history = QLabel("")
        self._history.setWordWrap(True)
        root.addWidget(self._history)

        run = QPushButton(t("s6_generate_share"))
        run.clicked.connect(self._run)
        root.addWidget(run)

    def _run(self):
        entry = self._selected_entry_provider()
        if not entry:
            QMessageBox.warning(self, t("app_title"), t("s6_select_entry_first"))
            return
        method = self._method.currentData()
        perm = self._perm.currentData()
        expires = int(self._exp.value())
        try:
            if method == "password_file":
                pkg = self._service.create_password_share(
                    entry, self._pass.text(), permission=perm, expires_days=expires
                )
            elif method == "public_key":
                pub = optional_public_key_pem(self._pub.text())
                if not pub:
                    QMessageBox.warning(self, t("app_title"), t("s6_invalid_pem"))
                    return
                pkg = self._service.create_public_key_share(
                    entry, pub, permission=perm, expires_days=expires
                )
            else:
                token = self._service.create_share_link_token(entry, expires_days=expires)
                pkg = {"share_link_token": token}
            path, _ = QFileDialog.getSaveFileName(self, t("s6_save_export"), "", "JSON (*.json)")
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(pkg, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, t("app_title"), t("s6_share_done"))
            self.accept()
        except ValueError:
            QMessageBox.warning(self, t("app_title"), t("s6_invalid_pem"))
        except Exception as exc:
            QMessageBox.warning(self, t("app_title"), t("s6_share_failed") % exc)


class QRViewerDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(t("s6_qr_title"))
        self.resize(600, 600)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        self._type = QComboBox()
        self._type.addItems(["public_key", "share_package", "share_link"])
        self._payload = QLineEdit()
        self._payload.setPlaceholderText(t("s6_payload"))
        root.addWidget(self._type)
        root.addWidget(self._payload)
        self._img = QLabel("—")
        self._img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._img)
        self._info = QLabel(t("s6_preview"))
        self._info.setWordWrap(True)
        root.addWidget(self._info)
        buttons = QHBoxLayout()
        gen = QPushButton(t("s6_generate_qr"))
        gen.clicked.connect(self._gen)
        scan = QPushButton(t("s6_scan_image"))
        scan.clicked.connect(self._scan_image)
        copy = QPushButton(t("s6_copy_payload"))
        copy.clicked.connect(self._copy_payload)
        buttons.addWidget(gen)
        buttons.addWidget(scan)
        buttons.addWidget(copy)
        root.addLayout(buttons)
        self._expiry = QLabel("")
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
            self._info.setText(f"QR: {self._type.currentText()}, chunks={len(chunks)}")
            self._last_ts = int(payload.get("ts") or 0)
        except Exception as exc:
            QMessageBox.warning(self, t("app_title"), t("s6_qr_failed") % exc)

    def _scan_image(self):
        path, _ = QFileDialog.getOpenFileName(self, t("s6_scan_image"), "", "Images (*.png *.jpg *.jpeg *.webp)")
        if not path:
            return
        try:
            line = qr_codec.decode_qr_image(path)
            decoded = qr_codec.decode_chunks([line])
            self._payload.setText(json.dumps(decoded.get("data", {}), ensure_ascii=False))
            self._type.setCurrentText(decoded.get("type", "public_key"))
            self._info.setText(f"OK: {decoded.get('type')}")
        except Exception as exc:
            QMessageBox.warning(self, t("app_title"), t("s6_qr_failed") % exc)

    def _copy_payload(self):
        text = self._payload.text()
        if self.parent() and hasattr(self.parent(), "_copy_to_clipboard"):
            self.parent()._copy_to_clipboard(None, text, "all")
        else:
            QMessageBox.information(self, t("app_title"), t("clipboard_copied_type") % "payload")

    def _refresh_ttl(self):
        if not self._last_ts:
            return
        left = max(0, 300 - int(__import__("time").time() - self._last_ts))
        self._expiry.setText(f"TTL: {left}s")
