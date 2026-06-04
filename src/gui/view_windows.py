"""View windows: live state monitor and audit log viewer. / Окна просмотра: монитор состояния и журнал аудита."""



import json

import sys

import os



sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))



from PyQt6.QtWidgets import (

    QWidget, QVBoxLayout, QLabel, QGridLayout, QTableWidget, QTableWidgetItem,

    QHBoxLayout, QPushButton, QComboBox, QMessageBox, QFileDialog, QHeaderView,

    QApplication,

)

from PyQt6.QtCore import QTimer, Qt



from core.state_manager import get_state_manager

from core.audit.integrity import verify_integrity

from core.audit.log_formatters import format_csv, format_json_lines

from core.audit.log_verifier import summarize_entry

from database import db

from .strings import t

from .user_errors import user_facing_error





class StateMonitorWindow(QWidget):

    """Live panel showing session, clipboard, and inactivity timers. / Панель с таймерами сессии, буфера и неактивности."""



    def __init__(self, parent=None):

        """Builds labels and starts periodic refresh timer. / Создаёт метки и запускает периодическое обновление."""

        super().__init__(parent)

        self.setWindowTitle(t("state_monitor"))

        self.setMinimumSize(320, 200)

        layout = QVBoxLayout(self)

        self._labels = {}

        grid = QGridLayout()

        grid.addWidget(QLabel(t("state_session")), 0, 0)

        self._labels["session"] = QLabel("—")

        grid.addWidget(self._labels["session"], 0, 1)

        grid.addWidget(QLabel(t("state_clipboard")), 1, 0)

        self._labels["clipboard"] = QLabel("—")

        grid.addWidget(self._labels["clipboard"], 1, 1)

        grid.addWidget(QLabel(t("state_inactivity")), 2, 0)

        self._labels["inactivity"] = QLabel("—")

        grid.addWidget(self._labels["inactivity"], 2, 1)

        layout.addLayout(grid)

        self._timer = QTimer(self)

        self._timer.timeout.connect(self._refresh)

        self._timer.start(500)



    def _refresh(self):

        sm = get_state_manager()

        state = sm.get_state()

        self._labels["session"].setText(t("status_locked") if state["locked"] else t("status_unlocked"))

        self._labels["clipboard"].setText("%d / %d" % (state["clipboard_seconds_left"], state["clipboard_timeout"]))

        self._labels["inactivity"].setText(str(state["inactivity_seconds"]))



    def showEvent(self, event):

        super().showEvent(event)

        self._refresh()





class AuditLogViewer(QWidget):

    """Table viewer for audit events with integrity check and export. / Таблица событий аудита с проверкой целостности и экспортом."""



    def __init__(self, parent=None):

        """Builds filter, verify/export controls, and event table. / Создаёт фильтр, проверку/экспорт и таблицу событий."""

        super().__init__(parent)

        layout = QVBoxLayout(self)

        self._integrity_label = QLabel(t("audit_integrity_unknown"))

        self._integrity_label.setWordWrap(True)

        layout.addWidget(self._integrity_label)



        bar = QHBoxLayout()

        self._filter = QComboBox()

        self._filter.addItem(t("audit_filter_all"), "")

        for ev in (

            "UserLoggedIn", "UserLoggedOut", "EntryCreated", "EntryUpdated", "EntryDeleted",

            "ClipboardCopied", "ClipboardCleared",

        ):

            self._filter.addItem(ev, ev)

        self._filter.currentIndexChanged.connect(self._reload)

        bar.addWidget(QLabel(t("audit_filter_label")))

        bar.addWidget(self._filter)

        self._btn_verify = QPushButton(t("audit_verify"))

        self._btn_verify.clicked.connect(self._on_verify)

        bar.addWidget(self._btn_verify)

        btn_export = QPushButton(t("audit_export_json"))

        btn_export.clicked.connect(self._on_export)

        bar.addWidget(btn_export)

        bar.addStretch()

        layout.addLayout(bar)



        self._table = QTableWidget(0, 5)

        self._table.setHorizontalHeaderLabels(

            [t("audit_col_time"), t("audit_col_event"), t("audit_col_severity"), t("audit_col_details"), t("audit_col_entry")]

        )

        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        self._table.setSortingEnabled(True)

        layout.addWidget(self._table)



        self._reload()

        QTimer.singleShot(0, self._on_verify)



    def _reload(self):

        event_type = self._filter.currentData()

        rows = db.list_audit_logs(limit=500, event_type=event_type or None)

        self._table.setRowCount(len(rows))

        for i, row in enumerate(rows):

            summary = summarize_entry(row)

            self._table.setItem(i, 0, QTableWidgetItem(summary["timestamp"]))

            self._table.setItem(i, 1, QTableWidgetItem(summary["event_type"]))

            self._table.setItem(i, 2, QTableWidgetItem(summary["severity"]))

            self._table.setItem(i, 3, QTableWidgetItem(summary["details"]))

            eid = row.get("entry_id")

            self._table.setItem(i, 4, QTableWidgetItem("" if eid is None else str(eid)))



    def _on_verify(self):

        self._btn_verify.setEnabled(False)

        self._integrity_label.setText(t("audit_verifying"))

        QApplication.processEvents()

        try:

            total = db.count_audit_logs()

            if total == 0:

                self._integrity_label.setText(t("audit_empty"))

                QMessageBox.information(self, t("logs"), t("audit_empty"))

                return



            result = verify_integrity(sample_limit=None)

            checked = int(result.get("checked") or 0)

            valid = int(result.get("valid_entries") or 0)

            total_db = int(result.get("total_in_db") or total)

            breaks = result.get("breaks") or []



            if result.get("verified"):

                msg = t("audit_integrity_ok") % (valid, checked)

                if result.get("partial"):

                    msg += " " + (t("audit_integrity_partial") % (checked, total_db))

                self._integrity_label.setText(msg)

                QMessageBox.information(self, t("logs"), msg)

            else:

                n = len(breaks)

                msg = t("audit_integrity_fail") % n

                self._integrity_label.setText(msg)

                detail = breaks[0].get("reason", "") if breaks else ""

                if detail:

                    msg = f"{msg}\n({detail})"

                QMessageBox.warning(self, t("logs"), msg)

        except Exception as exc:

            self._integrity_label.setText(t("audit_integrity_error"))

            QMessageBox.warning(self, t("logs"), user_facing_error(exc, fallback_key="audit_integrity_error"))

        finally:

            self._btn_verify.setEnabled(True)



    def _on_export(self):

        rows = db.list_audit_logs(limit=5000)

        export_rows = []

        for row in rows:

            s = summarize_entry(row)

            s["sequence_number"] = row.get("sequence_number")

            s["signature"] = row.get("signature")

            export_rows.append(s)

        path, _ = QFileDialog.getSaveFileName(self, t("audit_export_json"), "", "JSON (*.json);;CSV (*.csv)")

        if not path:

            return

        try:

            if path.lower().endswith(".csv"):

                text = format_csv(

                    export_rows,

                    ["timestamp", "event_type", "severity", "details", "sequence_number", "signature"],

                )

            else:

                text = format_json_lines(export_rows)

            with open(path, "w", encoding="utf-8") as f:

                f.write(text)

            QMessageBox.information(self, t("logs"), t("audit_export_done"))

        except Exception:

            QMessageBox.warning(self, t("logs"), t("error_generic"))


