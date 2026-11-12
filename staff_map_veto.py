"""Standalone Arena Map Veto for staff. No tournament manager imports or data access."""
import json
import os
import sys
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QMessageBox, QScrollArea
from map_veto import VetoPage
from staff_update import StaffUpdateController, install_from_staged

ROOT = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'ArenaMapVeto'
DATA = ROOT / 'map_veto.json'
ASSETS = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)) / 'assets'
DEFAULT_MAPS = [('Barrio','barrio'), ('City Hall','city-hall'),
                ('Little Seoul','little-seoul'), ('Mirror Park','mirror-park'),
                ('Morningwood','morningwood'), ('Paleto V2','paleto-v2'),
                ('Sandy','sandy'), ('Southside','southside')]
STYLE='''
QWidget {background:transparent;color:#e8e8ec;font-family:"Rajdhani";font-size:13px;}
QWidget#appRoot {background:#242426;}
QLabel {background:transparent;border:none;}
QFrame {background:transparent;}
QFrame#sidebar {background:#323234;border-right:1px solid #49494c;}
QFrame#surface {background:#323234;border:1px solid #3c3c40;border-radius:0px;}
QFrame#task {background:#303033;border-bottom:1px solid #424245;}
QFrame#surface QLabel,QFrame#task QLabel {background:transparent;}
QProgressBar {background:#424246;border:0;border-radius:0px;height:7px;text-align:center;}
QProgressBar::chunk {background:#53d900;border-radius:0px;}
QLabel#muted {color:#93939c;font-size:12px;}
QLabel#heading {font-size:24px;font-weight:700;}
QLabel#subheading {font-size:17px;font-weight:700;}
QPushButton {background:#37373a;border:1px solid #4a4a4e;border-radius:0px;padding:8px 11px;text-align:center;font-weight:600;}
QPushButton:hover {background:#444449;border-color:#606066;}
QPushButton:disabled {color:#74747a;background:#303033;}
QPushButton#primary {background:#53d900;color:#18200e;border:1px solid #53d900;font-weight:700;}
QPushButton#primary:hover {background:#6bef15;}
QPushButton#nav {background:transparent;border:0;border-left:2px solid transparent;text-align:left;padding:10px 15px;color:#b9b9c0;font-size:13px;}
QPushButton#nav:hover {background:#3b3b3f;color:#fff;}
QPushButton#navActive {background:#394630;border:0;border-left:2px solid #58dd00;text-align:left;padding:10px 15px;color:#5be000;font-weight:700;font-size:13px;}
QPushButton#tab {background:transparent;border:0;border-bottom:1px solid transparent;border-radius:0;color:#aaaab3;padding:10px 12px;font-size:12px;}
QPushButton#tabActive {background:transparent;border:0;border-bottom:2px solid #57db00;border-radius:0;color:#5be000;padding:10px 12px;font-weight:700;font-size:12px;}
QLineEdit,QTextEdit,QComboBox,QDateEdit,QDateTimeEdit,QSpinBox {background:#333336;border:1px solid #4a4a4f;border-radius:0;padding:7px;selection-background-color:#4d712d;}
QLineEdit:focus,QTextEdit:focus,QComboBox:focus {border:1px solid #63c823;}
QTableWidget {background:#2d2d30;alternate-background-color:#323235;border:1px solid #454549;border-radius:0;gridline-color:#414145;}
QHeaderView::section {background:#323235;color:#9c9ca5;padding:8px;border:0;border-bottom:1px solid #48484d;font-size:12px;font-weight:600;}
QTableWidget::item {padding:5px;border-bottom:1px solid #3e3e42;}
QTableWidget::item:selected {background:#3a4b31;color:#eaf4e4;}
QTableWidget::item:focus {outline:0;border:0;border-bottom:1px solid #3e3e42;}
QComboBox QAbstractItemView {background:#333336;color:#e8e8ec;border:1px solid #555559;selection-background-color:#3a4b31;selection-color:#ffffff;outline:0;}
QComboBox QAbstractItemView::item {background:#333336;color:#e8e8ec;min-height:27px;padding:4px 8px;}
QComboBox QAbstractItemView::item:selected {background:#3a4b31;color:#ffffff;}
QComboBox::drop-down,QDateEdit::drop-down,QDateTimeEdit::drop-down {background:#39393c;border-left:1px solid #4a4a4f;width:23px;}
QSpinBox::up-button,QSpinBox::down-button {background:#39393c;border-left:1px solid #4a4a4f;width:22px;}
QSpinBox {padding-right:27px;}
QComboBox:focus,QSpinBox:focus,QDateEdit:focus {outline:0;border:1px solid #606066;}
QCheckBox {spacing:8px;background:transparent;}
QScrollArea {border:0;background:transparent;}
QTabWidget::pane {border:0;}
QGroupBox {border:1px solid #444449;margin-top:12px;padding:12px;border-radius:0;}
QGroupBox::title {color:#9d9da5;subcontrol-origin:margin;left:10px;}
QDialog {background:#2a2a2d;}
QToolTip {background:#37373a;color:#f0f0f2;border:1px solid #535358;padding:5px;}
'''

class StaffVetoWindow(QMainWindow):
    standalone = True

    def __init__(self):
        super().__init__()
        self.assets_directory = ROOT / 'map_images'
        self.setWindowTitle('Arena Map Veto — Staff Edition')
        self.resize(1450, 900)
        self.setMinimumSize(950, 620)
        ROOT.mkdir(parents=True, exist_ok=True)
        self.data = {'map_library': [], 'active_map_ids': [], 'map_vetoes': []}
        if DATA.exists():
            try:
                loaded = json.loads(DATA.read_text(encoding='utf-8'))
                if not isinstance(loaded, dict):
                    raise ValueError('Invalid saved data')
                for key in self.data:
                    if isinstance(loaded.get(key), list):
                        self.data[key] = loaded[key]
            except (OSError, ValueError, TypeError) as exc:
                QMessageBox.warning(self, 'Unable to load veto history', str(exc))
        self.install_default_maps()
        root = QWidget()
        root.setObjectName('appRoot')
        layout = QVBoxLayout(root)
        layout.setContentsMargins(25, 20, 25, 20)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.body = QWidget()
        self.cv = QVBoxLayout(self.body)
        self.cv.setContentsMargins(0, 0, 0, 0)
        self.cv.setSpacing(12)
        # Keep the heading, tabs and empty-state panel together at the top.
        # Without top alignment, Qt expands each widget to fill the scroll viewport
        # when no map pool or veto history exists.
        self.cv.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.body)
        layout.addWidget(scroll)
        self.setCentralWidget(root)
        self.veto = VetoPage(self)
        self.veto.render()
        self.updates = StaffUpdateController(self)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1800, self.updates.check)

    def install_default_maps(self):
        """Install bundled maps only on an empty library; never reset staff edits."""
        if self.data['map_library']:
            return
        import shutil
        import uuid
        source = ASSETS / 'maps'
        if not all((source / slug / image).is_file()
                   for _, slug in DEFAULT_MAPS for image in ('preview.png', 'spawns.png')):
            return  # Do not initialise an incomplete rotation.
        self.assets_directory.mkdir(parents=True, exist_ok=True)
        library = []
        for name, slug in DEFAULT_MAPS:
            paths = {}
            for key, filename in (('preview','preview.png'), ('spawns','spawns.png')):
                dest = self.assets_directory / (slug + '-' + filename)
                if not dest.exists():
                    shutil.copy2(source / slug / filename, dest)
                paths[key] = str(dest)
            library.append({'id': str(uuid.uuid5(uuid.NAMESPACE_URL, 'arena-map-veto/'+slug)),
                            'name': name, **paths})
        self.data['map_library'] = library
        self.data['active_map_ids'] = [m['id'] for m in library if m['name'] != 'City Hall']
        self.save()

    def header(self, title, subtitle):
        heading = QLabel('ARENA  /  ' + title)
        heading.setObjectName('heading')
        self.cv.addWidget(heading)
        sub = QLabel(subtitle)
        sub.setObjectName('muted')
        self.cv.addWidget(sub)

    def clear(self):
        while self.cv.count():
            item = self.cv.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def protected_backup(self, reason):
        """Protect the user's existing veto history before deletion."""
        if not DATA.exists():
            return True
        try:
            import shutil
            import datetime
            backup_dir = ROOT / 'backups'
            backup_dir.mkdir(exist_ok=True)
            stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            shutil.copy2(DATA, backup_dir / ('veto-' + stamp + '.json'))
            return True
        except OSError as exc:
            QMessageBox.critical(self, 'Backup failed', str(exc))
            return False

    def save(self):
        try:
            ROOT.mkdir(parents=True, exist_ok=True)
            temp = DATA.with_suffix('.tmp')
            with temp.open('w', encoding='utf-8') as output:
                json.dump(self.data, output, ensure_ascii=False, indent=2)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temp, DATA)
            return True
        except (OSError, TypeError, ValueError) as exc:
            QMessageBox.critical(self, 'Could not save map veto', str(exc))
            return False

def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--install-update':
        try:
            install_from_staged(sys.argv[2], int(sys.argv[3]))
        except Exception as exc:
            log = ROOT / 'staff-update-error.log'
            ROOT.mkdir(parents=True, exist_ok=True)
            log.write_text(str(exc), encoding='utf-8')
            if sys.platform == 'win32':
                import ctypes
                ctypes.windll.user32.MessageBoxW(None, str(exc), 'Staff update failed', 0x10)
        return
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Arena.MapVeto.Staff')
        except (OSError, AttributeError):
            pass
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    icon = ASSETS / 'arena_logo.ico'
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    font = ASSETS / 'Rajdhani-SemiBold.ttf'
    if font.exists():
        font_id = QFontDatabase.addApplicationFont(str(font))
        families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
        if families:
            app.setFont(QFont(families[0], 11))
    app.setStyleSheet(STYLE)
    window = StaffVetoWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
