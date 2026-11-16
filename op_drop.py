#!/usr/bin/env python3
"""
Disclaimer: The author of this code (Aaron Yagnik) is a silly goose and wrote this in about 2 hours so
there are a lot of style issues and the code isn't exactly super cleaned up... but it works!

Operation Drop Protocol — Command Console GUI Edition (Cinematic)
Aaron Yagnik-level drama: radar video bg, dark map, pulsing target, slide-in overlays.

REQUIRED:
Setup (recommended):
  python3 -m venv venv && source venv/bin/activate
  pip install PyQt6 PyQt6-WebEngine geopy pandas simpleaudio

Run:
  python op_drop.py

CSV format: See the example file and make a copy named "assignments.csv"
    last,first,rank,base,unit,,passphrase

NOTES:
YOU SHOULD HARDCODE THE COORDINATES AND ALIASES
    This will allow this whole thing to work with a crappy internet connection
    Make sure 'BASE_ALIASES' match with the stuff in the CSV
    Map all BASE_ALIASES to BASE_COORDS
You will need a relatively good Wi-Fi connection to get the map zoom function to work.
The password to enter is whatever is in the passphrase column of the CSV.
The ping sound doesn't work and I ran out of time to finish it. Give it a shot if you have a chance!
"""

from email.mime import base
import sys
import time
from pathlib import Path
from typing import Dict, List

from PyQt6.QtCore import Qt, QUrl, QTimer, QEasingCurve, QRect, QPropertyAnimation
from PyQt6.QtGui import QFont, QAction
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QWidget, QFileDialog, QMessageBox, QInputDialog, QLineEdit
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings


import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

try:
    import simpleaudio
    HAVE_AUDIO = True
    print("Yay, Aaron is so cool :)")
except Exception:
    HAVE_AUDIO = False


APP_DIR = Path(__file__).parent
TEMPLATES_DIR = APP_DIR / "templates"
ASSETS_DIR = APP_DIR / "assets"
ASSIGN_CSV = APP_DIR / "assignments.csv"
MAP_HTML = TEMPLATES_DIR / "map.html"
PING_WAV = ASSETS_DIR / "ping.wav"

# --- Canonical coords for common DoD bases (expand as needed)
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
}


class DropProtocolApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Operation Drop Protocol")
        self.setStyleSheet("background-color: black;")
        self.resize(1500, 900)

        # --- Top HUD header
        self.header = QLabel("OPERATION DROP PROTOCOL")
        self.header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        self.header.setStyleSheet("color:#00FFFF; padding:8px; border-bottom:1px solid #003A3A;")

        # --- Web map view (Leaflet inside Qt WebEngine)
        self.web = QWebEngineView()
        self.web.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        self.web.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.web.load(QUrl.fromLocalFile(str(MAP_HTML.resolve())))
        self.web.setStyleSheet("opacity:0; transition:opacity 2s;")
        QTimer.singleShot(500, lambda: self.web.setStyleSheet("opacity:1; transition:opacity 2s;"))


        # --- Overlay panel that slides in (assignment text)
        self.overlay = QLabel("")  # Set text dynamically
        self.overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overlay.setFont(QFont("Courier", 20, QFont.Weight.Medium))
        self.overlay.setStyleSheet(
            "background: rgba(0, 0, 0, 0.65);"
            "color: #00FF99;"
            "border: 1px solid #007755;"
            "padding: 14px;"
            "border-radius: 10px;"
        )
        self.overlay.setVisible(False)
        
        # --- Unit overlay (appears at the top of the map)
        self.unit_overlay = QLabel("")
        self.unit_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.unit_overlay.setFont(QFont("Courier", 18, QFont.Weight.Medium))
        self.unit_overlay.setStyleSheet(
            "background: rgba(0, 0, 0, 0.55);"
            "color: #00FFFF;"
            "border: 1px solid #0077AA;"
            "padding: 10px;"
            "border-radius: 8px;"
        )
        self.unit_overlay.setParent(self.centralWidget())
        self.unit_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.unit_overlay.raise_()
        self.unit_overlay.hide()

        # --- Confirm line (typewriter effect)
        self.confirm = QLabel("")
        self.confirm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.confirm.setFont(QFont("Courier", 16))
        self.confirm.setStyleSheet("color:#7EE6FF; padding:6px 0 14px 0;")

        # --- Controls
        self.btn_reveal = QPushButton("REVEAL NEXT")
        self.btn_all = QPushButton("AUTO-REVEAL ALL")
        self.btn_open = QPushButton("LOAD CSV")
        for b in (self.btn_reveal, self.btn_all, self.btn_open):
            b.setStyleSheet(
                "QPushButton{background:#002C3A; color:white; border:1px solid #00FFFF; padding:10px;}"
                "QPushButton:hover{background:#004C66;}"
                "QPushButton:disabled{background:#001820; color:#6aa; border:1px solid #033;}"
            )

        self.btn_reveal.clicked.connect(self.reveal_next)
        self.btn_all.clicked.connect(self.auto_reveal_all)
        self.btn_open.clicked.connect(self.load_csv_prompt)

        controls = QHBoxLayout()
        controls.addStretch(1)
        controls.addWidget(self.btn_open)
        controls.addSpacing(10)
        controls.addWidget(self.btn_reveal)
        controls.addSpacing(10)
        controls.addWidget(self.btn_all)
        controls.addStretch(1)

        # --- Layout
        center = QWidget()
        v = QVBoxLayout(center)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)
        v.addWidget(self.header)
        v.addWidget(self.web, 1)
        v.addWidget(self.confirm)
        v.addLayout(controls)
        self.setCentralWidget(center)

        # Float the overlay above the map
        self.overlay.setParent(self.centralWidget())
        self.overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.overlay.raise_()
        self.overlay.hide()


        # --- Data
        self.rows: List[Dict] = []
        self.idx = 0
        self._load_assignments_default()

        # Geocoder with rate limit
        self.geocoder = Nominatim(user_agent="drop_protocol_gui")
        self.geocode = RateLimiter(self.geocoder.geocode, min_delay_seconds=1, swallow_exceptions=True)

        # For AUTO mode pacing
        self.auto_mode = False
        self.auto_delay_ms = 2600

        # Menu (quick fullscreen toggle)
        view_menu = self.menuBar().addMenu("View")
        act_full = QAction("Toggle Fullscreen", self)
        act_full.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(act_full)

        # Place overlay off-screen initially (slide-in from top)
        QTimer.singleShot(300, self._init_overlay_pos)

    # ---------- Helpers ----------
    def _init_overlay_pos(self):
        # Position overlay just above its final spot (slide-in illusion)
        geo = self.overlay.geometry()
        if geo.width() == 0:  # ensure a default width/height if not yet laid out
            self.overlay.setFixedHeight(60)
        # Make sure it's visible space-wise but hidden
        self.overlay.setVisible(False)

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _load_assignments_default(self):
        try:
            if not ASSIGN_CSV.exists():
                # Seed example if missing
                ASSIGN_CSV.write_text(
                    "last,first,rank,base\n"
                    "Doe,Jane,2Lt,Kadena Air Base\n"
                    "Smith,John,2Lt,Joint Base Langley–Eustis\n"
                    "Perez,Alex,Capt,Hurlburt Field\n"
                )
            df = pd.read_csv(ASSIGN_CSV)
            self.rows = df.to_dict(orient="records")
            self.idx = 0
        except Exception as e:
            QMessageBox.critical(self, "CSV Error", f"Failed to load assignments.csv\n\n{e}")

    def load_csv_prompt(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select assignments CSV", str(APP_DIR), "CSV Files (*.csv)")
        if not path:
            return
        try:
            df = pd.read_csv(path)
            for col in ("last", "first", "rank", "base"):
                if col not in df.columns:
                    raise ValueError(f"Missing column: {col}")
            self.rows = df.to_dict(orient="records")
            self.idx = 0
            self._set_confirm("[SYSTEM] Roster loaded successfully.", color="#9ad")
        except Exception as e:
            QMessageBox.critical(self, "CSV Error", f"Failed to load CSV\n\n{e}")

    def _play_ping(self):
        if HAVE_AUDIO and PING_WAV.exists():
            try:
                simpleaudio.WaveObject.from_wave_file(str(PING_WAV)).play()
            except Exception:
                pass

    def _typewriter(self, label: QLabel, text: str, speed_ms=14, color="#00FF99"):
        label.setStyleSheet(f"color:{color};")
        label.setText("")
        def step(i=0):
            if i <= len(text):
                label.setText(text[:i])
                QTimer.singleShot(speed_ms, lambda: step(i + 1))
        step(0)

    def _set_confirm(self, text: str, color="#7EE6FF"):
        self.confirm.setStyleSheet(f"color:{color}; padding:6px 0 14px 0;")
        self.confirm.setText(text)
        
    def _show_unit_overlay(self, unit_text: str):
        """Show the unit name centered above the map (inside the same window)."""
        parent = self.centralWidget()

        target_width = min(800, int(parent.width() * 0.7))
        self.unit_overlay.setFixedWidth(target_width)
        h = self.unit_overlay.sizeHint().height() or 50

        map_top = self.header.height()
        final_y = map_top + 20  # ~20px below header
        final_x = (parent.width() - target_width) // 2

        # Make sure it's a child widget (not a window)
        self.unit_overlay.setParent(parent)
        self.unit_overlay.setWindowFlags(Qt.WindowType.Widget)
        self.unit_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        # Position and show
        self.unit_overlay.setGeometry(final_x, final_y, target_width, h)
        self.unit_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.unit_overlay.setText(unit_text)
        self.unit_overlay.show()
        self.unit_overlay.raise_()

        # Animate with geometry instead of opacity (opacity causes separate window behavior)
        start_rect = QRect(final_x, final_y - 20, target_width, h)
        final_rect = QRect(final_x, final_y, target_width, h)
        anim = QPropertyAnimation(self.unit_overlay, b"geometry")
        anim.setDuration(500)
        anim.setStartValue(start_rect)
        anim.setEndValue(final_rect)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._unit_anim = anim



    def _slide_overlay_in(self):
        parent = self.centralWidget()

        # Size overlay
        target_width = min(900, int(parent.width() * 0.8))
        self.overlay.setFixedWidth(target_width)
        h = self.overlay.sizeHint().height() or 80

        # --- Position over the MAP area (not the whole window)
        # Map area is directly below the header and has height = self.web.height()
        map_top = self.header.height()
        map_bottom = map_top + self.web.height()

        # Keep your current vertical band (near the bottom of the map)
        final_y = map_bottom - h - 12            # 12px padding off the map bottom

        # Center horizontally within the parent
        final_x = (parent.width() - target_width) // 2

        start_rect = QRect(final_x, final_y, target_width, h)   # start at final spot (no slide up)
        final_rect = QRect(final_x, final_y, target_width, h)

        self.overlay.setGeometry(start_rect)
        self.overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overlay.show()
        self.overlay.raise_()

        anim = QPropertyAnimation(self.overlay, b"geometry")
        anim.setDuration(550)
        anim.setStartValue(start_rect)
        anim.setEndValue(final_rect)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._anim = anim



    def _new_anim(self, widget: QWidget, start_rect: QRect, end_rect: QRect):
        anim = QPropertyAnimation(widget, b"geometry")
        anim.setDuration(550)
        anim.setStartValue(start_rect)
        anim.setEndValue(end_rect)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        return anim
    
    def _verify_passphrase(self, expected_passphrase: str, name_str: str) -> bool:
        """
        Blocks until the correct passphrase is entered.
        User cannot cancel or escape. The only valid exit is success.
        """
        expected_passphrase = (expected_passphrase or "").strip().lower()

        while True:
            # Create custom input dialog manually (no cancel)
            dlg = QInputDialog(self)
            dlg.setWindowTitle("Authorization Required")
            dlg.setLabelText(f"Enter operation passphrase for: {name_str}")
            dlg.setOkButtonText("AUTHENTICATE")
            dlg.setCancelButtonText("")
            dlg.setTextEchoMode(QLineEdit.EchoMode.Password)
            dlg.setModal(True)

            # Remove the Cancel button entirely
            dlg.setOption(QInputDialog.InputDialogOption.NoButtons, False)
            for button in dlg.findChildren(QPushButton):
                if "Cancel" in button.text():
                    button.hide()

            # Force them to stay until correct
            dlg.exec()
            entered = dlg.textValue().strip().lower()

            if entered == expected_passphrase:
                self._set_confirm("[ACCESS GRANTED] Beginning decryption...", color="#00FF99")
                self._play_ping()
                QApplication.processEvents()
                return True
            else:
                self._set_confirm("[ACCESS DENIED] Incorrect passphrase. Try again.", color="#F55")
                self._play_ping()
                QApplication.processEvents()

    # ---------- Core actions ----------
    def reveal_next(self):
        if not self.rows:
            self._set_confirm("[ERROR] No roster loaded.", color="#F66")
            return
        if self.idx >= len(self.rows):
            self._set_confirm("[SYSTEM] All assignments revealed. Transmission complete.", color="#9ad")
            return

        officer = self.rows[self.idx]
        self.idx += 1
        name_str = f"{officer['rank']} {officer['first']} {officer['last']}"
        base = officer["base"]
        
        expected_pass = officer.get("passphrase", "").strip()
        if expected_pass:
            name_str_pass = f"{officer['rank']} {officer['last']}"
            if not self._verify_passphrase(expected_pass, name_str_pass):
                return  # stop here if incorrect

        # Step 1: Initial system message (slow pace)
        self._set_confirm("> Decrypting assignment payload...", color="#7EE6FF")
        self.overlay.setVisible(False)
        QApplication.processEvents()

        # Step 2: Simulate staged progress updates (like a classified data decode)
        def stage_two():
            self._set_confirm("> Accessing geospatial database...", color="#7EE6FF")
            QTimer.singleShot(1200, stage_three)

        def stage_three():
            self._set_confirm("> Locating base coordinates...", color="#7EE6FF")
            QTimer.singleShot(1000, start_geocode)

        # Step 3: Perform geocode lookup with a slight delay
        def start_geocode():
            self._set_confirm("> Target acquisition in progress...", color="#00FF99")
            QTimer.singleShot(500, lambda: self._geocode_and_then(base, after_geo))

        # Step 4: Once geocoding done, reveal map + overlay
        def after_geo():
            # small pause before showing the overlay to sync with map movement
            QTimer.singleShot(1200, lambda: self._move_map_and_mark(officer, base))

        # Kick off the staged sequence
        QTimer.singleShot(500, stage_two)


    def _geocode_and_then(self, base: str, cb):
        lat, lon, used = self._resolve_coords(base)
        self._last_loc = (lat, lon, used) if lat is not None else None
        cb()
    
    def _normalize_base(self, base: str) -> str:
        b = base.strip().lower()
        b = b.replace("–", "-")        # normalize weird dashes
        b = b.replace(" a f b", " afb")
        b = b.replace("ft", "fort")
        b = b.replace("air base", " ab")
        # direct alias
        if b in BASE_ALIASES:
            return BASE_ALIASES[b]
        # add common state hints for ambiguous names
        if b == "fort meade":
            return "fort meade, md"
        return b

    def _resolve_coords(self, base: str):
        """
        Returns (lat, lon, label_used) or (None, None, None)
        Order: exact table hit → alias → geocode with US bias + suffix fallbacks.
        """
        key = self._normalize_base(base)
        print("Key for geocode:", key)
        # Exact in table?
        if key in BASE_COORDS:
            lat, lon = BASE_COORDS[key]
            return lat, lon, key

        # Try with common suffixes
        suffix_trials = [
            key,
            f"{key}, usa",
            f"{key}, united states",
        ]
        # If user didn't give a state, try hints for classic ambiguities
        if "fort meade" in key and "md" not in key:
            suffix_trials.insert(0, "fort meade, md, usa")

        loc = None
        for q in suffix_trials:
            try:
                # Bias to US; Nominatim via geopy supports country_codes + bounded viewbox
                loc = self.geocode(q, exactly_one=True, country_codes="us")
                if loc:
                    return float(loc.latitude), float(loc.longitude), q
            except Exception:
                continue

        # Last chance: explicit suffixes (AB/AFB/Base/Field)
        for extra in (" air base", " afb", " ab", " base", " field"):
            try:
                loc = self.geocode(key + extra, exactly_one=True, country_codes="us")
                if loc:
                    return float(loc.latitude), float(loc.longitude), key + extra
            except Exception:
                continue

        return None, None, None


    def _move_map_and_mark(self, officer: Dict, base: str):
        loc = getattr(self, "_last_loc", None)
        if not loc:
            self._set_confirm(f"[ERROR] Could not locate '{base}'.", color="#F66")
            return

        lat, lon, used_label = loc
        label = base  # show the original label to the user

        js = f"""
            clearTargets();
            setView([{lat:.6f}, {lon:.6f}], 8);
            addPulseMarker([{lat:.6f}, {lon:.6f}], "{label.replace('"','\\"')}");
        """
        self.web.page().runJavaScript(js)

        overlay_text = (
            f"ASSIGNMENT CONFIRMED:  {officer['rank']} {officer['first']} {officer['last']}  ►  {label}"
        )
        self.overlay.setText(overlay_text)
        
        unit = officer.get("unit", "").strip()
        if unit:
            self._show_unit_overlay(f"UNIT ASSIGNMENT:  {unit.upper()}")
        else:
            self.unit_overlay.hide()
        # self.overlay.setParent(self.centralWidget())
        # self.overlay.raise_()
        # self.overlay.setVisible(False)

        self._slide_overlay_in()
        # self._typewriter(self.overlay, overlay_text, speed_ms=10)
        self._typewriter(self.confirm,
                        f"[TARGET LOCKED] {label}  |  COORDS {lat:.4f}, {lon:.4f}",
                        speed_ms=12)
        self._play_ping()

        if self.auto_mode:
            QTimer.singleShot(self.auto_delay_ms, self.reveal_next)

    def auto_reveal_all(self):
        if not self.rows:
            self._set_confirm("[ERROR] No roster loaded.", color="#F66")
            return
        if self.idx >= len(self.rows):
            self._set_confirm("[SYSTEM] All assignments already revealed.", color="#9ad")
            return
        self.auto_mode = True
        self.btn_all.setDisabled(True)
        self.btn_reveal.setDisabled(True)
        self._set_confirm("[SYSTEM] Auto-reveal engaged. Standby…", color="#9ad")
        QTimer.singleShot(300, self.reveal_next)
    
    def resizeEvent(self, event):
        """Recenter overlays on window resize or fullscreen toggle."""
        super().resizeEvent(event)

        if self.overlay.isVisible():
            # Recenter without triggering animation again
            parent = self.centralWidget()
            target_width = min(900, int(parent.width() * 0.8))
            h = self.overlay.sizeHint().height() or 80
            map_top = self.header.height()
            map_bottom = map_top + self.web.height()
            final_y = map_bottom - h - 12
            final_x = (parent.width() - target_width) // 2
            self.overlay.setGeometry(final_x, final_y, target_width, h)

        if self.unit_overlay.isVisible():
            # Same logic for top overlay
            parent = self.centralWidget()
            target_width = min(800, int(parent.width() * 0.7))
            h = self.unit_overlay.sizeHint().height() or 50
            map_top = self.header.height()
            final_y = map_top + 20
            final_x = (parent.width() - target_width) // 2
            self.unit_overlay.setGeometry(final_x, final_y, target_width, h)


def main():
    app = QApplication(sys.argv)
    win = DropProtocolApp()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
