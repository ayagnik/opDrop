#!/usr/bin/env python3
"""
Operation Drop Protocol — Command Console GUI Edition (Cinematic, 100% Offline)
"""

import html
import json
import random
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from hints import get_hints_for_base, SQUADRONS_BY_BASE, HINT_LOCATION_ALIASES

from PyQt6.QtCore import Qt, QUrl, QTimer, QEasingCurve, QRect, QPropertyAnimation
from PyQt6.QtGui import QFont, QAction, QKeyEvent
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QWidget, QFileDialog, QMessageBox, QInputDialog, QLineEdit, QComboBox,
    QScrollArea, QFrame
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings

import pandas as pd

try:
    import winsound
    HAVE_WINSOUND = True
except Exception:
    HAVE_WINSOUND = False


APP_DIR = Path(__file__).parent
TEMPLATES_DIR = APP_DIR / "templates"
ASSETS_DIR = APP_DIR / "assets"
ASSIGN_CSV = APP_DIR / "assignments.csv"
MAP_HTML = TEMPLATES_DIR / "map.html"

PING_WAV = ASSETS_DIR / "ping.wav"
HINT_WAV = ASSETS_DIR / "hint_pulse.wav"
SCAN_WAV = ASSETS_DIR / "scan_telemetry.wav"
DECOY_WAV = ASSETS_DIR / "decoy_alarm.wav"
LOCK_WAV = ASSETS_DIR / "target_lock.wav"
DENIED_WAV = ASSETS_DIR / "access_denied.wav"

# --- Canonical coords for common DoD bases (100% offline)
BASE_COORDS = {
    "keesler air force base, ms": (30.4113, -88.9243),
    "eglin air force base, fl": (30.4607, -86.5254),
    "mountain home air force base, id": (43.0487, -115.8665),
    "malmstrom air force base, mt": (47.4781, -111.2035),
    "volkel air base, netherlands": (51.6561, 5.6236),
    "osan air base, south korea": (37.0992, 127.0081),
    "hickam air force base, hi": (21.3331, -157.9256),
    "lackland air force base, tx": (29.3863, -98.6009),
    "hill air force base, ut": (41.1245, -111.9740),
    "davis-monthan air force base, az": (32.1708, -110.8699),
    "wright-patterson air force base, oh": (39.8219, -84.0496),
    "andersen air force base, guam": (13.5596, 144.9263),
    "misawa air base, japan": (40.6983, 141.3745),
    "mcguire air force base, nj": (40.0172, -74.5902),
    "scott air force base, il": (38.5438, -89.8528),
    "fort meade, md": (39.1086, -76.7433),
    "fort gordon, ga": (33.4209, -82.1387),
    "jbsa-lackland, tx": (29.3863, -98.6009),
    "joint base pearl harbor-hickam, hi": (21.3331, -157.9256),
}

# Friendly aliases → canonical keys above
BASE_ALIASES = {
    "keesler afb": "keesler air force base, ms",
    "eglin afb": "eglin air force base, fl",
    "mountain home afb": "mountain home air force base, id",
    "malmstrom afb": "malmstrom air force base, mt",
    "volkel ab": "volkel air base, netherlands",
    "osan ab": "osan air base, south korea",
    "hickam afb": "hickam air force base, hi",
    "lackland afb": "lackland air force base, tx",
    "hill afb": "hill air force base, ut",
    "davis-monthan afb": "davis-monthan air force base, az",
    "wright patterson afb": "wright-patterson air force base, oh",
    "andersen afb": "andersen air force base, guam",
    "misawa ab": "misawa air base, japan",
    "mcguire afb": "mcguire air force base, nj",
    "scott afb": "scott air force base, il",
    "fort meade": "fort meade, md",
    "ft meade": "fort meade, md",
    "fort gordon": "fort gordon, ga",
    "ft gordon": "fort gordon, ga",
    "fort eisenhower": "fort gordon, ga",
    "fort eisenhower, ga": "fort gordon, ga",
    "jbsa-lackland": "jbsa-lackland, tx",
    "jbsa lackland": "jbsa-lackland, tx",
    "joint base pearl harbor-hickam": "joint base pearl harbor-hickam, hi",
    "jbphh": "joint base pearl harbor-hickam, hi",
}

# Canonical key → US State polygon name in US_STATES_GEOJSON
BASE_STATE_NAMES = {
    "fort meade, md": "Maryland",
    "fort gordon, ga": "Georgia",
    "jbsa-lackland, tx": "Texas",
    "lackland air force base, tx": "Texas",
    "joint base pearl harbor-hickam, hi": "Hawaii",
    "hickam air force base, hi": "Hawaii",
    "keesler air force base, ms": "Mississippi",
    "eglin air force base, fl": "Florida",
    "mountain home air force base, id": "Idaho",
    "malmstrom air force base, mt": "Montana",
    "hill air force base, ut": "Utah",
    "davis-monthan air force base, az": "Arizona",
    "wright-patterson air force base, oh": "Ohio",
    "mcguire air force base, nj": "New Jersey",
    "scott air force base, il": "Illinois",
}

CANDIDATE_DECOY_STATES = [
    "Maryland", "Georgia", "Texas", "Hawaii",
    "Florida", "Mississippi", "North Dakota", "Colorado",
    "California", "Virginia", "Ohio", "Alaska",
    "Arizona", "Utah", "Illinois", "New Jersey",
    "Montana", "Idaho", "New Mexico", "Louisiana",
]

# Classic humorous Fake-Out / Red Herring decoy bases
DECOY_BASES: List[Tuple[str, Tuple[float, float]]] = [
    ("Minot AFB, ND (Frozen Tundra Sector)", (48.4156, -101.3580)),
    ("Cannon AFB, NM (High Desert Sector)", (34.3828, -103.3228)),
    ("Fort Polk, LA (Bayou Box Sector)", (31.0448, -93.2089)),
    ("Eareckson Air Station, Shemya Island, AK", (52.7123, 174.1136)),
    ("Pituffik Space Base, Greenland (Arctic Sector)", (76.5312, -68.7031)),
]


class DropProtocolApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Operation Drop Protocol")
        self.setStyleSheet("QMainWindow { background-color: black; }")
        self.resize(1560, 920)

        # --- Top HUD header
        self.header = QLabel("OPERATION DROP PROTOCOL")
        self.header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header.setFont(QFont("Arial", 26, QFont.Weight.Bold))
        self.header.setStyleSheet("color:#00FFFF; background:black; padding:8px; border-bottom:1px solid #003A3A;")

        # --- Web map view (Leaflet inside Qt WebEngine — 100% offline)
        self.web = QWebEngineView()
        self.web.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True
        )
        self.web.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False
        )
        self.web.page().setBackgroundColor(Qt.GlobalColor.black)
        self.web.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.web.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.web.load(QUrl.fromLocalFile(str(MAP_HTML.resolve())))

        # --- Live Drop Board Right Sidebar
        self.board_panel = QFrame()
        self.board_panel.setFixedWidth(410)
        self.board_panel.setStyleSheet(
            "QFrame { background-color: #020E17; border-left: 1px solid #005577; }"
        )
        board_layout = QVBoxLayout(self.board_panel)
        board_layout.setContentsMargins(10, 10, 10, 10)
        board_layout.setSpacing(6)

        board_title = QLabel("LIVE DROP ROSTER")
        board_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        board_title.setFont(QFont("Courier", 14, QFont.Weight.Bold))
        board_title.setStyleSheet(
            "color: #00FF99; background: #002233; padding: 8px; border: 1px solid #00AA77; border-radius: 4px;"
        )
        board_layout.addWidget(board_title)

        self.board_scroll = QScrollArea()
        self.board_scroll.setWidgetResizable(True)
        self.board_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.board_content = QLabel("No assignments revealed yet.\n\nClick REVEAL NEXT or press SPACE to begin.")
        self.board_content.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.board_content.setWordWrap(True)
        self.board_content.setFont(QFont("Courier", 10))
        self.board_content.setStyleSheet("color: #B0F0FF; padding: 6px; background: transparent;")
        self.board_scroll.setWidget(self.board_content)
        board_layout.addWidget(self.board_scroll, 1)

        # --- Confirm line (typewriter effect)
        self.confirm = QLabel("")
        self.confirm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.confirm.setFont(QFont("Courier", 15))
        self.confirm.setStyleSheet("color:#7EE6FF; background:black; padding:6px 0 10px 0;")

        # --- Controls Bar
        self.btn_open = QPushButton("LOAD CSV")
        self.combo_officer = QComboBox()
        self.combo_officer.setMinimumWidth(220)
        self.combo_officer.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.combo_officer.setStyleSheet(
            "QComboBox { background: #001F2B; color: #00FFFF; border: 1px solid #00FFFF; padding: 8px 12px; "
            "font-family: Courier; font-size: 13px; font-weight: bold; }"
            "QComboBox QAbstractItemView { background: #02141E; color: #00FF99; selection-background-color: #004C66; }"
        )
        self.combo_officer.currentIndexChanged.connect(self._on_officer_selected)

        self.btn_reveal = QPushButton("REVEAL NEXT  [SPACE]")
        self.btn_continue = QPushButton("CONTINUE  [SPACE]")
        self.btn_replay = QPushButton("REPLAY")
        self.btn_fakeout = QPushButton("FAKE-OUT (1/3): ON")
        self.btn_pass_toggle = QPushButton("PASS: ON")
        self.btn_summary = QPushButton("SUMMARY BOARD")
        self.btn_all = QPushButton("AUTO-REVEAL ALL")

        base_btn_style = (
            "QPushButton{background:#002C3A; color:white; border:1px solid #00FFFF; padding:10px 14px; font-weight:bold;}"
            "QPushButton:hover{background:#004C66;}"
            "QPushButton:disabled{background:#001820; color:#577; border:1px solid #022;}"
        )
        for b in (self.btn_open, self.btn_reveal, self.btn_replay, self.btn_summary, self.btn_all):
            b.setStyleSheet(base_btn_style)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.btn_continue.setStyleSheet(
            "QPushButton{background:#003B26; color:#00FF99; border:2px solid #00FF99; padding:10px 20px; font-weight:bold;}"
            "QPushButton:hover{background:#00593A; color:white;}"
            "QPushButton:disabled{background:#001820; color:#577; border:1px solid #022;}"
        )
        self.btn_continue.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_continue.setDisabled(True)

        self.fakeout_enabled = True
        self._update_fakeout_btn_style()
        self.btn_fakeout.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.require_passphrase = True
        self._update_pass_btn_style()
        self.btn_pass_toggle.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.btn_open.clicked.connect(self.load_csv_prompt)
        self.btn_reveal.clicked.connect(self.reveal_next)
        self.btn_continue.clicked.connect(self.advance_hint)
        self.btn_replay.clicked.connect(self.replay_current)
        self.btn_fakeout.clicked.connect(self.toggle_fakeout_mode)
        self.btn_pass_toggle.clicked.connect(self.toggle_passphrase_mode)
        self.btn_summary.clicked.connect(self.toggle_summary_view)
        self.btn_all.clicked.connect(self.auto_reveal_all)

        controls = QHBoxLayout()
        controls.addStretch(1)
        controls.addWidget(self.btn_open)
        controls.addSpacing(6)
        controls.addWidget(self.combo_officer)
        controls.addSpacing(8)
        controls.addWidget(self.btn_reveal)
        controls.addSpacing(8)
        controls.addWidget(self.btn_continue)
        controls.addSpacing(8)
        controls.addWidget(self.btn_replay)
        controls.addSpacing(8)
        controls.addWidget(self.btn_fakeout)
        controls.addSpacing(8)
        controls.addWidget(self.btn_pass_toggle)
        controls.addSpacing(8)
        controls.addWidget(self.btn_summary)
        controls.addSpacing(8)
        controls.addWidget(self.btn_all)
        controls.addStretch(1)

        # --- Main Split Area (Map + Live Drop Board)
        mid_row = QHBoxLayout()
        mid_row.setContentsMargins(0, 0, 0, 0)
        mid_row.setSpacing(6)
        mid_row.addWidget(self.web, 1)
        mid_row.addWidget(self.board_panel)

        # --- Layout
        center = QWidget()
        center.setStyleSheet("background-color: black;")
        v = QVBoxLayout(center)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)
        v.addWidget(self.header)
        v.addLayout(mid_row, 1)
        v.addWidget(self.confirm)
        v.addLayout(controls)
        self.setCentralWidget(center)

        # Keep legacy overlay attributes for compatibility
        self.overlay = QLabel("", center)
        self.overlay.hide()
        self.unit_overlay = QLabel("", center)
        self.unit_overlay.hide()

        # --- State & Timers
        self.rows: List[Dict] = []
        self.idx = 0
        self._typewriter_gen = 0
        self._seq_gen = 0
        self._reveal_in_progress = False
        self._last_loc = None
        self._used_hints_by_base: Dict[str, Set[str]] = {}
        self._active_officer: Optional[Dict] = None
        self._active_base: str = ""
        self._active_hints: List[str] = []
        self._active_hint_idx: int = 0
        self._active_candidate_Progression: List[List[str]] = []
        self._revealed_history: List[Dict] = []
        self._drop_count = 0
        self._decoy_idx = 0
        self._suppress_combo_signal = False
        self._load_assignments_default()

        # For AUTO mode pacing
        self.auto_mode = False
        self.auto_delay_ms = 3200

        # Menu (quick fullscreen & sidebar toggles)
        view_menu = self.menuBar().addMenu("View")
        act_full = QAction("Toggle Fullscreen (F11)", self)
        act_full.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(act_full)

        act_board = QAction("Toggle Live Drop Board", self)
        act_board.triggered.connect(lambda: self.board_panel.setVisible(not self.board_panel.isVisible()))
        view_menu.addAction(act_board)

        self.act_pass = QAction("Require Passphrases", self)
        self.act_pass.setCheckable(True)
        self.act_pass.setChecked(self.require_passphrase)
        self.act_pass.triggered.connect(self.toggle_passphrase_mode)
        view_menu.addAction(self.act_pass)

    # ---------- Keyboard Shortcuts ----------
    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key.Key_F11:
            self.toggle_fullscreen()
            event.accept()
            return
        if key in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.btn_continue.isEnabled():
                self.advance_hint()
                event.accept()
                return
            elif self.btn_reveal.isEnabled() and not self._reveal_in_progress:
                self.reveal_next()
                event.accept()
                return
        super().keyPressEvent(event)

    # ---------- Helpers ----------
    def _update_fakeout_btn_style(self):
        if self.fakeout_enabled:
            self.btn_fakeout.setText("FAKE-OUT (1/3): ON")
            self.btn_fakeout.setStyleSheet(
                "QPushButton{background:#3A1800; color:#FFAA00; border:1px solid #FFAA00; padding:10px 14px; font-weight:bold;}"
                "QPushButton:hover{background:#552400;}"
            )
        else:
            self.btn_fakeout.setText("FAKE-OUT: OFF")
            self.btn_fakeout.setStyleSheet(
                "QPushButton{background:#001F2B; color:#7799AA; border:1px solid #004455; padding:10px 14px; font-weight:bold;}"
                "QPushButton:hover{background:#003344;}"
            )

    def toggle_fakeout_mode(self):
        self.fakeout_enabled = not self.fakeout_enabled
        self._update_fakeout_btn_style()

    def _update_pass_btn_style(self):
        if self.require_passphrase:
            self.btn_pass_toggle.setText("PASS: ON")
            self.btn_pass_toggle.setStyleSheet(
                "QPushButton{background:#002B3A; color:#00FFFF; border:1px solid #00FFFF; padding:10px 12px; font-weight:bold;}"
                "QPushButton:hover{background:#00445C;}"
            )
        else:
            self.btn_pass_toggle.setText("PASS: OFF")
            self.btn_pass_toggle.setStyleSheet(
                "QPushButton{background:#001F2B; color:#7799AA; border:1px solid #004455; padding:10px 12px; font-weight:bold;}"
                "QPushButton:hover{background:#003344;}"
            )

    def toggle_passphrase_mode(self):
        self.require_passphrase = not self.require_passphrase
        if hasattr(self, "act_pass"):
            self.act_pass.setChecked(self.require_passphrase)
        self._update_pass_btn_style()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _populate_officer_combo(self):
        self._suppress_combo_signal = True
        self.combo_officer.clear()
        for i, row in enumerate(self.rows):
            r = self._clean_field(row, "rank")
            f = self._clean_field(row, "first")
            l = self._clean_field(row, "last")
            self.combo_officer.addItem(f"[{i + 1}/{len(self.rows)}] {r} {f} {l}".strip())
        if 0 <= self.idx < len(self.rows):
            self.combo_officer.setCurrentIndex(self.idx)
        self._suppress_combo_signal = False

    def _on_officer_selected(self, index: int):
        if self._suppress_combo_signal or index < 0 or index >= len(self.rows):
            return
        self._seq_gen += 1
        self._active_officer = None
        self._active_hints = []
        self._active_hint_idx = 0
        self._reveal_in_progress = False
        self.btn_continue.setDisabled(True)
        self.btn_continue.setText("CONTINUE  [SPACE]")
        self.btn_reveal.setDisabled(False)
        self.web.page().runJavaScript("if (window.hideHintCard) hideHintCard();")
        self.idx = index
        self._set_confirm(
            f"[SYSTEM] Selected officer #{index + 1}. Click REVEAL NEXT or press SPACE.",
            color="#7EE6FF",
        )

    def replay_current(self):
        if not self.rows:
            return
        self._seq_gen += 1
        target_idx = max(0, self.idx - 1)
        self._active_officer = None
        self._active_hints = []
        self._active_hint_idx = 0
        self._reveal_in_progress = False
        self.btn_continue.setDisabled(True)
        self.btn_continue.setText("CONTINUE  [SPACE]")
        self.btn_reveal.setDisabled(False)
        self.idx = target_idx
        self._suppress_combo_signal = True
        self.combo_officer.setCurrentIndex(self.idx)
        self._suppress_combo_signal = False
        self.reveal_next()

    def _load_assignments_default(self):
        try:
            if not ASSIGN_CSV.exists():
                ASSIGN_CSV.write_text(
                    "last,first,rank,base,unit,,passphrase\n"
                    "Doe,Jane,2Lt,Keesler AFB,81 Communications Sq,,Doe\n",
                    encoding="utf-8",
                )
            df = pd.read_csv(ASSIGN_CSV)
            df.columns = [c.strip() for c in df.columns]
            self.rows = df.to_dict(orient="records")
            self.idx = 0
            self._populate_officer_combo()
        except Exception as e:
            QMessageBox.critical(self, "CSV Error", f"Failed to load assignments.csv\n\n{e}")

    def load_csv_prompt(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select assignments CSV", str(APP_DIR), "CSV Files (*.csv)")
        if not path:
            return
        try:
            df = pd.read_csv(path)
            df.columns = [c.strip() for c in df.columns]
            for col in ("last", "first", "rank", "base"):
                if col not in df.columns:
                    raise ValueError(f"Missing column: {col}")
            self.rows = df.to_dict(orient="records")
            self.idx = 0
            self.auto_mode = False
            self._seq_gen += 1
            self._reveal_in_progress = False
            self._active_officer = None
            self._active_hints = []
            self._active_hint_idx = 0
            self._drop_count = 0
            self._revealed_history.clear()
            self._update_drop_board()
            self._populate_officer_combo()
            self.btn_reveal.setDisabled(False)
            self.btn_continue.setDisabled(True)
            self.btn_continue.setText("CONTINUE  [SPACE]")
            self.btn_all.setDisabled(False)
            self.web.page().runJavaScript(
                "if (window.clearAllPins) clearAllPins(); "
                "if (window.toggleSummaryModal) toggleSummaryModal(null, false); "
                "if (window.resetToWorld) resetToWorld();"
            )
            self._set_confirm("[SYSTEM] Roster loaded successfully.", color="#9ad")
        except Exception as e:
            QMessageBox.critical(self, "CSV Error", f"Failed to load CSV\n\n{e}")

    def _play_sound(self, wav_path: Path):
        target = wav_path if wav_path.exists() else PING_WAV
        if not target.exists():
            return
        if HAVE_WINSOUND:
            try:
                winsound.PlaySound(str(target), winsound.SND_FILENAME | winsound.SND_ASYNC)
            except Exception:
                pass

    def _play_ping(self):
        self._play_sound(PING_WAV)

    def _typewriter(self, label: QLabel, text: str, speed_ms=14, color="#00FF99"):
        self._typewriter_gen += 1
        gen = self._typewriter_gen
        label.setStyleSheet(f"color:{color}; background:black; padding:6px 0 10px 0;")
        label.setText("")

        def step(i=0):
            if gen != self._typewriter_gen:
                return
            if i <= len(text):
                label.setText(text[:i])
                QTimer.singleShot(speed_ms, lambda: step(i + 1))

        step(0)

    def _set_confirm(self, text: str, color="#7EE6FF"):
        self._typewriter_gen += 1
        self.confirm.setStyleSheet(f"color:{color}; background:black; padding:6px 0 10px 0;")
        self.confirm.setText(text)

    def _verify_passphrase(self, expected_passphrase: str, name_str: str) -> bool:
        expected_passphrase = (expected_passphrase or "").strip().lower()

        while True:
            dlg = QInputDialog(self)
            dlg.setWindowTitle("Authorization Required")
            dlg.setLabelText(f"Enter operation passphrase for: {name_str}")
            dlg.setOkButtonText("AUTHENTICATE")
            dlg.setCancelButtonText("ABORT")
            dlg.setTextEchoMode(QLineEdit.EchoMode.Password)
            dlg.setModal(True)
            dlg.setStyleSheet(
                "QDialog, QInputDialog { background-color: #04121C; color: #00FFFF; }"
                "QLabel { color: #00FFFF; font-family: Courier; font-size: 14px; font-weight: bold; }"
                "QLineEdit { background-color: #001F2D; color: #00FF99; border: 1px solid #00FFFF; "
                "padding: 6px; font-family: Courier; font-size: 15px; }"
                "QPushButton { background-color: #002C3A; color: white; border: 1px solid #00FFFF; "
                "padding: 6px 14px; font-weight: bold; }"
                "QPushButton:hover { background-color: #004C66; }"
            )

            accepted = dlg.exec()
            if not accepted:
                self._set_confirm("[SYSTEM] Authorization aborted.", color="#F66")
                return False

            entered = dlg.textValue().strip().lower()
            if entered == expected_passphrase:
                self._set_confirm("[ACCESS GRANTED] Beginning decryption...", color="#00FF99")
                self._play_sound(HINT_WAV)
                QApplication.processEvents()
                return True
            else:
                self._set_confirm("[ACCESS DENIED] Incorrect passphrase. Try again.", color="#F55")
                self._play_sound(DENIED_WAV)
                QApplication.processEvents()

    # ---------- Hints & Progressive State Narrowing ----------
    def _clean_field(self, row: Dict, key: str) -> str:
        val = row.get(key, "")
        return "" if pd.isna(val) else str(val).strip()

    def _get_state_for_base(self, base: str) -> str:
        key = self._normalize_base(base)
        if key in BASE_STATE_NAMES:
            return BASE_STATE_NAMES[key]
        for k, st in BASE_STATE_NAMES.items():
            if key in k or k in key:
                return st
        return "Maryland"

    def _build_candidate_state_funnel(self, target_state: str) -> List[List[str]]:
        """
        Builds 4 progressive candidate state sets (11 -> 8 -> 6 -> 5):
        - Hint 1 (11): target + 3 other real Drop Night states + 7 random states
        - Hint 2 (8):  target + 3 other real Drop Night states + 4 random states
        - Hint 3 (6):  target + 2 other real Drop Night states + 3 random states
        - Hint 4 (5):  target + 1 other real Drop Night state  + 3 random states
        """
        core_drop_states = ["Maryland", "Georgia", "Texas", "Hawaii"]
        other_core = [s for s in core_drop_states if s.lower() != target_state.lower()]
        random.shuffle(other_core)

        extra_decoys = [
            s for s in CANDIDATE_DECOY_STATES
            if s.lower() != target_state.lower() and s not in other_core
        ]
        random.shuffle(extra_decoys)

        step1 = sorted([target_state] + other_core[:3] + extra_decoys[:7])  # 11 states (4 real, 7 random)
        step2 = sorted([target_state] + other_core[:3] + extra_decoys[:4])  # 8 states  (4 real, 4 random)
        step3 = sorted([target_state] + other_core[:2] + extra_decoys[:3])  # 6 states  (3 real, 3 random)
        step4 = sorted([target_state] + other_core[:1] + extra_decoys[:3])  # 5 states  (2 real, 3 random)
        return [step1, step2, step3, step4]

    def _pick_hints_for_base(self, base: str, count: int = 4) -> List[str]:
        all_hints = get_hints_for_base(base)
        if not all_hints:
            return []
        key = self._normalize_base(base)
        used = self._used_hints_by_base.setdefault(key, set())
        available = [h for h in all_hints if h not in used]
        if len(available) < count:
            used.clear()
            available = list(all_hints)
        chosen = random.sample(available, min(count, len(available)))
        used.update(chosen)
        return chosen

    def _show_current_hint(self):
        if not self._active_officer or not self._active_hints:
            return
        rank = self._clean_field(self._active_officer, "rank")
        first = self._clean_field(self._active_officer, "first")
        last = self._clean_field(self._active_officer, "last")
        name_str = f"{rank} {first} {last}".strip()

        total = len(self._active_hints)
        num = self._active_hint_idx + 1
        hint_text = self._active_hints[self._active_hint_idx]
        candidates = (
            self._active_candidate_Progression[self._active_hint_idx]
            if self._active_hint_idx < len(self._active_candidate_Progression)
            else []
        )

        safe_name = name_str.replace("\\", "\\\\").replace('"', '\\"')
        safe_hint = hint_text.replace("\\", "\\\\").replace('"', '\\"')
        cand_json = json.dumps(candidates)

        js = f'if (window.showHintCard) showHintCard("{safe_name}", {num}, {total}, "{safe_hint}", {cand_json});'
        self.web.page().runJavaScript(js)
        self._play_sound(HINT_WAV)

        if num < total:
            self.btn_continue.setText(f"CONTINUE ({num}/{total})  [SPACE]")
            self._set_confirm(
                f"[INTEL CLUE {num}/{total}] {len(candidates)} candidate states remaining — press SPACE or click CONTINUE...",
                color="#00FF99",
            )
        else:
            self.btn_continue.setText("CONTINUE TO REVEAL  [SPACE]")
            self._set_confirm(
                f"[FINAL CLUE {num}/{total}] {len(candidates)} candidate states remain ({', '.join(candidates)}) — press SPACE or click CONTINUE!",
                color="#00FFFF",
            )

    def advance_hint(self):
        if not self._active_officer:
            return
        self._active_hint_idx += 1
        if self._active_hint_idx < len(self._active_hints):
            self._show_current_hint()
        else:
            officer = self._active_officer
            base = self._active_base
            self._active_officer = None
            self._active_hints = []
            self._active_hint_idx = 0
            self.btn_continue.setDisabled(True)
            self.btn_continue.setText("CONTINUE  [SPACE]")
            self.web.page().runJavaScript("if (window.hideHintCard) hideHintCard();")
            self._begin_map_reveal_sequence(officer, base)

    # ---------- Core Reveal Sequence ----------
    def reveal_next(self):
        if self._reveal_in_progress:
            return
        if not self.rows:
            self._set_confirm("[ERROR] No roster loaded.", color="#F66")
            return
        if self.idx >= len(self.rows):
            self.auto_mode = False
            self.btn_reveal.setDisabled(False)
            self.btn_all.setDisabled(False)
            self._set_confirm("[SYSTEM] All assignments revealed! Showing Class Drop Summary.", color="#00FF99")
            self.toggle_summary_view(force_show=True)
            return

        # Close summary modal if it was open
        self.web.page().runJavaScript("if (window.toggleSummaryModal) toggleSummaryModal(null, false);")

        officer = self.rows[self.idx]
        rank = self._clean_field(officer, "rank")
        first = self._clean_field(officer, "first")
        last = self._clean_field(officer, "last")
        base = self._clean_field(officer, "base")
        expected_pass = self._clean_field(officer, "passphrase")

        if expected_pass and self.require_passphrase and not self.auto_mode:
            name_str_pass = f"{rank} {last}".strip()
            if not self._verify_passphrase(expected_pass, name_str_pass):
                return

        self._suppress_combo_signal = True
        self.combo_officer.setCurrentIndex(self.idx)
        self._suppress_combo_signal = False

        self.idx += 1
        self._reveal_in_progress = True
        self.btn_reveal.setDisabled(True)

        self.web.page().runJavaScript("if (window.resetToWorld) resetToWorld();")
        hints_list = self._pick_hints_for_base(base, count=4)
        if hints_list and not self.auto_mode:
            target_state = self._get_state_for_base(base)
            self._active_officer = officer
            self._active_base = base
            self._active_hints = hints_list
            self._active_hint_idx = 0
            self._active_candidate_Progression = self._build_candidate_state_funnel(target_state)
            self.btn_continue.setDisabled(False)
            self._show_current_hint()
            return

        self._begin_map_reveal_sequence(officer, base)

    def _begin_map_reveal_sequence(self, officer: Dict, base: str):
        self._seq_gen += 1
        seq = self._seq_gen
        self._set_confirm("> Decrypting assignment payload...", color="#7EE6FF")
        self._play_sound(SCAN_WAV)
        self.web.page().runJavaScript("if (window.startTargetScan) startTargetScan();")
        QApplication.processEvents()

        def stage_two():
            if seq != self._seq_gen:
                return
            self._set_confirm("> Accessing global geospatial database...", color="#7EE6FF")
            QTimer.singleShot(800, stage_three)

        def stage_three():
            if seq != self._seq_gen:
                return
            self._drop_count += 1
            should_fakeout = (
                self.fakeout_enabled
                and not self.auto_mode
                and (self._drop_count % 3 == 0)
            )
            if should_fakeout:
                decoy_name, (dlat, dlon) = DECOY_BASES[self._decoy_idx % len(DECOY_BASES)]
                self._decoy_idx += 1
                self._play_sound(DECOY_WAV)
                self._set_confirm(
                    f"⚠ [SIGNAL ANOMALY] False telemetry lock at {decoy_name} — recalibrating...",
                    color="#FF5555",
                )
                safe_decoy = decoy_name.replace("\\", "\\\\").replace('"', '\\"')
                self.web.page().runJavaScript(
                    f'if (window.triggerDecoyBounce) triggerDecoyBounce([{dlat:.4f}, {dlon:.4f}], "{safe_decoy}");'
                )
                QTimer.singleShot(2300, start_geocode)
            else:
                self._set_confirm("> Locking onto base coordinates...", color="#00FF99")
                QTimer.singleShot(850, start_geocode)

        def start_geocode():
            if seq != self._seq_gen:
                return
            self._geocode_and_then(base, after_geo)

        def after_geo():
            if seq != self._seq_gen:
                return
            self._move_map_and_mark(officer, base, seq)

        QTimer.singleShot(650, stage_two)

    def _geocode_and_then(self, base: str, cb):
        lat, lon, used = self._resolve_coords(base)
        self._last_loc = (lat, lon, used) if lat is not None else None
        cb()

    def _normalize_base(self, base: str) -> str:
        b = (base or "").strip().lower()
        b = b.replace("–", "-").replace("—", "-")
        b = b.replace(" a f b", " afb")
        b = re.sub(r"\bft\.?\b", "fort", b)
        b = b.replace("air base", "ab")
        b = re.sub(r"\s+", " ", b)
        if b in BASE_ALIASES:
            return BASE_ALIASES[b]
        if b == "fort meade":
            return "fort meade, md"
        return b

    def _resolve_coords(self, base: str):
        key = self._normalize_base(base)
        if key in BASE_COORDS:
            lat, lon = BASE_COORDS[key]
            return lat, lon, key

        for alias, canon in BASE_ALIASES.items():
            if alias in key or key in alias:
                lat, lon = BASE_COORDS[canon]
                return lat, lon, canon

        for canon, (lat, lon) in BASE_COORDS.items():
            if key in canon or canon in key:
                return lat, lon, canon

        return None, None, None

    def _record_revealed_assignment(self, rank: str, first: str, last: str, base: str, unit: str):
        entry = {
            "name": f"{rank} {first} {last}".strip(),
            "base": base,
            "unit": unit or "Unassigned Unit",
        }
        # Avoid duplicate entries on replay
        self._revealed_history = [h for h in self._revealed_history if h["name"] != entry["name"]]
        self._revealed_history.append(entry)
        self._update_drop_board()

    def _update_drop_board(self):
        if not self._revealed_history:
            self.board_content.setText(
                "No assignments revealed yet.\n\nClick REVEAL NEXT or press SPACE to begin."
            )
            return

        by_base: Dict[str, List[Dict]] = {}
        for item in self._revealed_history:
            by_base.setdefault(item["base"], []).append(item)

        lines = [f"TOTAL DROPPED: {len(self._revealed_history)} / {len(self.rows)}\n"]
        for base_name, items in by_base.items():
            lines.append(f"━━ {base_name.upper()} ({len(items)}) ━━")
            for it in items:
                lines.append(f" • {it['name']}")
                if it["unit"]:
                    lines.append(f"   └ {it['unit']}")
            lines.append("")
        self.board_content.setText("\n".join(lines))

    def _build_summary_html(self) -> str:
        source = self._revealed_history
        if not source:
            return "<div style='text-align:center; padding:30px; color:#7EE6FF;'>No assignments revealed yet.</div>"

        by_base: Dict[str, List[Dict]] = {}
        for item in source:
            by_base.setdefault(item["base"], []).append(item)

        cards = []
        for base_name, items in by_base.items():
            rows_html = []
            for it in items:
                rows_html.append(
                    f"<div class='summary-item'>"
                    f"<div class='summary-officer'>▸ {html.escape(it['name'])}</div>"
                    f"<div class='summary-unit'>{html.escape(it['unit'])}</div>"
                    f"</div>"
                )
            cards.append(
                f"<div class='summary-base-card'>"
                f"<div class='summary-base-title'>{html.escape(base_name.upper())} ({len(items)})</div>"
                f"{''.join(rows_html)}"
                f"</div>"
            )
        return "".join(cards)

    def toggle_summary_view(self, force_show: Optional[bool] = None):
        html = self._build_summary_html()
        safe_html = json.dumps(html)
        force_arg = "null" if force_show is None else ("true" if force_show else "false")
        self.web.page().runJavaScript(
            f"if (window.toggleSummaryModal) toggleSummaryModal({safe_html}, {force_arg});"
        )

    def _get_squadron_candidates(self, base: str, actual_unit: str) -> List[str]:
        norm = (base or "").strip().lower().replace("–", "-")
        canon = HINT_LOCATION_ALIASES.get(norm, base)
        options = list(SQUADRONS_BY_BASE.get(canon, []))
        if actual_unit and actual_unit not in options:
            options.append(actual_unit)
        # If this base has multiple squadrons, cycle between them; otherwise include all known COS options for roulette suspense
        if len(options) < 2 and actual_unit:
            all_cos = [
                sq for sqs in SQUADRONS_BY_BASE.values() for sq in sqs if sq != actual_unit
            ]
            if all_cos:
                options.extend(random.sample(all_cos, min(2, len(all_cos))))
        return options

    def _move_map_and_mark(self, officer: Dict, base: str, seq: Optional[int] = None):
        self._reveal_in_progress = False
        if not self.auto_mode:
            self.btn_reveal.setDisabled(False)

        loc = getattr(self, "_last_loc", None)
        if not loc:
            self._set_confirm(f"[ERROR] Could not locate '{base}'.", color="#F66")
            return

        lat, lon, _ = loc
        rank = self._clean_field(officer, "rank")
        first = self._clean_field(officer, "first")
        last = self._clean_field(officer, "last")
        unit = self._clean_field(officer, "unit")
        label = base
        state_name = self._get_state_for_base(base)

        overlay_text = f"ASSIGNMENT CONFIRMED:  {rank} {first} {last}  ►  {label}"
        unit_text = f"UNIT ASSIGNMENT:  {unit.upper()}" if unit else ""
        officer_brief = f"{rank} {first} {last} — {label} ({unit})"
        candidate_units = self._get_squadron_candidates(base, unit)

        self._record_revealed_assignment(rank, first, last, label, unit)

        safe_label = label.replace("\\", "\\\\").replace('"', '\\"')
        safe_overlay = overlay_text.replace("\\", "\\\\").replace('"', '\\"')
        safe_unit = unit_text.replace("\\", "\\\\").replace('"', '\\"')
        safe_state = state_name.replace("\\", "\\\\").replace('"', '\\"')
        safe_brief = officer_brief.replace("\\", "\\\\").replace('"', '\\"')
        cand_units_json = json.dumps(candidate_units)

        js = f"""
            clearTargets();
            setView([{lat:.6f}, {lon:.6f}], 7);
            addPulseMarker([{lat:.6f}, {lon:.6f}], "{safe_label}", "{safe_state}", "{safe_brief}");
            if (window.showHudBanners) {{
                showHudBanners("{safe_unit}", "{safe_overlay}", {cand_units_json});
            }}
        """
        self.web.page().runJavaScript(js)

        self._typewriter(
            self.confirm,
            f"[TARGET LOCKED] {label}  |  COORDS {lat:.4f}, {lon:.4f}  |  Press SPACE for next officer",
            speed_ms=12,
        )
        self._play_sound(LOCK_WAV)
        current_seq = self._seq_gen if seq is None else seq
        if len(candidate_units) > 1:
            QTimer.singleShot(
                1500,
                lambda: self._play_sound(HINT_WAV) if self._seq_gen == current_seq else None,
            )

        if self.auto_mode:
            QTimer.singleShot(
                self.auto_delay_ms,
                lambda: self.reveal_next() if self._seq_gen == current_seq else None,
            )

    def auto_reveal_all(self):
        if not self.rows:
            self._set_confirm("[ERROR] No roster loaded.", color="#F66")
            return
        if self._active_officer is not None:
            # If clicked while mid-hints, step back 1 so the current officer is included in auto-reveal
            self.idx = max(0, self.idx - 1)
            self._active_officer = None
            self._active_hints = []
            self._active_hint_idx = 0
            self.web.page().runJavaScript("if (window.hideHintCard) hideHintCard();")
        self._seq_gen += 1
        self._reveal_in_progress = False
        if self.idx >= len(self.rows):
            self._set_confirm("[SYSTEM] All assignments already revealed.", color="#9ad")
            return
        self.auto_mode = True
        self.btn_all.setDisabled(True)
        self.btn_reveal.setDisabled(True)
        self.btn_continue.setDisabled(True)
        self.btn_continue.setText("CONTINUE  [SPACE]")
        self._set_confirm("[SYSTEM] Auto-reveal engaged. Standby…", color="#9ad")
        QTimer.singleShot(300, self.reveal_next)


def main():
    app = QApplication(sys.argv)
    win = DropProtocolApp()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
