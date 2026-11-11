"""Arena Tournament Manager — PySide6 desktop UI; offline, local JSON storage."""
import sys, json, re, datetime, webbrowser, uuid, shutil, hashlib, urllib.request, zipfile, subprocess, os, threading
from pathlib import Path
from backup_manager import snapshot, list_snapshots, restore as restore_backup, read_validated, atomic_write
from overview_logic import overview, task_complete, deadline_status
from team_reconciliation import reconcile_teams
from map_veto import VetoPage
from notifications import due_events, event_key, send_discord, validate_webhook
from PySide6.QtCore import Qt, QDate, QDateTime, QSize, QUrl, QTimer, QObject, Signal, QByteArray
from PySide6.QtGui import QPixmap, QIcon, QPainter, QFontDatabase, QFont
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QFrame,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QStackedWidget,QScrollArea,QTableWidget,QTableWidgetItem,QHeaderView,QLineEdit,QDialog,QFormLayout,QDateEdit,QDateTimeEdit,QComboBox,QSpinBox,QCheckBox,QDialogButtonBox,QFileDialog,QMessageBox,QTextEdit,QInputDialog,QTabWidget,QTreeWidget,QTreeWidgetItem,QAbstractItemView,QSplitter,QProgressBar,QGroupBox,QSystemTrayIcon,QStyle)

BASE=Path.home()/'ArenaTournamentManager'; BASE.mkdir(exist_ok=True)
DATA=BASE/'tournaments.json'
ASSETS_DIR=Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))/'assets'
ASSET=ASSETS_DIR/'arena_logo.png'
ICON_ASSET=ASSETS_DIR/'arena_logo.ico'
GREEN='#58dc00'
VERSION='1.0.3'
BACKUPS=BASE/'backups'; BACKUPS.mkdir(exist_ok=True)
TASKS=[('announce','Announce tournament','manual'),('qopen','Announce qualifiers open','manual'),('qclose','Announce qualifiers closed','manual'),('received','Receive stream key document & tournament export from developer','manual'),('files','Upload stream key document & tournament export','auto'),('tickets','Add team players to their team ticket','manual'),('congrats','Send congratulations / acceptance and misc info','manual'),('guide','Send OBS guide in team tickets','manual'),('keys','DM stream keys to players','auto'),('bracket','Create bracket via Bracket HQ','manual'),('games','Create tournament games','manual'),('live','Announce tournament is live','manual'),('results','Record tournament results','manual')]
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


def load():
    if DATA.exists():
        try:
            d=json.loads(DATA.read_text(encoding='utf8'))
            for key,default in [('tournaments',[]),('players',{}),('discord_mappings',{}),('teams_db',{}),('transfer_windows',[]),('settings',{}),('deleted_tournaments',[]),('audit_log',[])]:d.setdefault(key,default)
            return d
        except Exception as e:raise RuntimeError(f'Cannot load saved database: {e}')
    return {'tournaments':[],'players':{},'discord_mappings':{},'teams_db':{},'transfer_windows':[],'settings':{},'deleted_tournaments':[],'audit_log':[]}



# Monochrome vector icons rendered locally; no third-party icon downloads.
NAV_PATHS={
    'Overview':'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    'Tournaments':'<path d="M8 21h8M12 17v4M7 4h10v6a5 5 0 0 1-10 0V4ZM7 6H4v2a4 4 0 0 0 4 4M17 6h3v2a4 4 0 0 1-4 4"/>',
    'Players':'<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M16 3.13a4 4 0 0 1 0 7.75M22 21v-2a4 4 0 0 0-3-3.87"/><circle cx="9" cy="7" r="4"/>',
    'Teams':'<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/>',
    'Unofficial Teams':'<path d="M3 7h18M5 12h14M8 17h8"/>',
    'Settings':'<path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-1.86 1.86-.06-.06A1.7 1.7 0 0 0 16 18.4a1.7 1.7 0 0 0-1 1.56V21h-6v-1.04A1.7 1.7 0 0 0 8 18.4a1.7 1.7 0 0 0-1.88.34l-.06.06-1.86-1.86.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.56-1H2v-4h1.04A1.7 1.7 0 0 0 4.6 9a1.7 1.7 0 0 0-.34-1.88L4.2 7.06 6.06 5.2l.06.06A1.7 1.7 0 0 0 8 5.6a1.7 1.7 0 0 0 1-1.56V3h6v1.04A1.7 1.7 0 0 0 16 5.6a1.7 1.7 0 0 0 1.88-.34l.06-.06 1.86 1.86-.06.06A1.7 1.7 0 0 0 19.4 9a1.7 1.7 0 0 0 1.56 1H22v4h-1.04A1.7 1.7 0 0 0 19.4 15Z"/>'
}
def nav_icon(name):
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#aebcbd" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{NAV_PATHS[name]}</svg>'
    pix=QPixmap(20,20);pix.fill(Qt.GlobalColor.transparent)
    painter=QPainter(pix);QSvgRenderer(QByteArray(svg.encode('utf-8'))).render(painter);painter.end()
    return QIcon(pix)

def parse_keys(raw):
    chunks=re.split(r'(?m)^PLAYER\s*-\s*USERID\s*$',raw)
    result=[]
    for block in chunks[1:]:
        lines=[line.strip() for line in block.splitlines() if line.strip()]
        publish=next((s for s in lines if s.startswith('https://') and s.endswith('/webRTC/publish')),None)
        command=next((s for s in lines if s.startswith('set_stream_key ')),None)
        preview=next((s for s in lines if s.startswith('https://') and s.endswith('/iframe')),None)
        if not all((publish,command,preview)):raise ValueError(f'Malformed Cloudflare block {len(result)+1}')
        play=command.split(' ',2)[2]
        if play.removesuffix('/webRTC/play')!=preview.removesuffix('/iframe'):raise ValueError('Preview/play URLs do not match')
        result.append({'publish':publish,'play':play,'preview':preview})
    if not result:raise ValueError('No Cloudflare keys found')
    if len({x['publish'] for x in result})!=len(result):raise ValueError('Duplicate keys found')
    return result

def label(text,style=None):
    w=QLabel(str(text));w.setWordWrap(True)
    if style:w.setObjectName(style)
    return w

def button(text,callback=None,primary=False):
    b=QPushButton(text)
    if primary:b.setObjectName('primary')
    if callback:b.clicked.connect(callback)
    return b

def layout_col(widget=None,spacing=12,margins=(0,0,0,0)):
    l=QVBoxLayout(widget);l.setSpacing(spacing);l.setContentsMargins(*margins);return l

def layout_row(widget=None,spacing=10,margins=(0,0,0,0)):
    l=QHBoxLayout(widget);l.setSpacing(spacing);l.setContentsMargins(*margins);return l

class UpdateSignals(QObject):
    found=Signal(dict)
    progress=Signal(str,int,int)
    staged=Signal(str)
    failed=Signal(str)

class NotificationSignals(QObject):
    failed=Signal(str)

class TournamentDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent);self.setWindowTitle('Create tournament');self.resize(550,600)
        v=layout_col(self,14,(24,24,24,24));v.addWidget(label('Create tournament','heading'))
        form=QFormLayout();form.setSpacing(17);form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft);form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow);v.addLayout(form)
        self.name=QLineEdit();self.name.setPlaceholderText('e.g. Season 5 — Tournament 3');form.addRow('Name',self.name)
        self.format=QComboBox();self.format.addItems(['Facecheck 1v1','Facecheck 2v2','3v3','4v4','5v5']);self.format.setCurrentText('5v5');form.addRow('Format',self.format)
        self.main=QSpinBox();self.main.setRange(1,128);self.main.setValue(8);form.addRow('Main teams',self.main)
        self.sub=QSpinBox();self.sub.setRange(0,128);self.sub.setValue(2);form.addRow('Substitute teams',self.sub)
        self.qual=QCheckBox('Use qualifier system');self.qual.setChecked(True);v.addWidget(self.qual)
        self.locked=QCheckBox('Use locked teams');self.locked.setChecked(True);v.addWidget(self.locked)
        v.addWidget(label('Tournament dates (select one or more)','subheading'))
        dr=QWidget();dl=layout_row(dr);self.date=QDateEdit(QDate.currentDate());self.date.setCalendarPopup(True);self.date.setDisplayFormat('dd-MM-yyyy');dl.addWidget(self.date)
        dl.addWidget(button('+ Add date',self.add_date));v.addWidget(dr)
        self.dates=[];self.dates_text=label('No dates added','muted');v.addWidget(self.dates_text)
        v.addWidget(button('Remove last date',self.remove_date));self.add_date()
        v.addStretch()
        actions=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);actions.button(QDialogButtonBox.StandardButton.Ok).setText('CREATE TOURNAMENT');actions.button(QDialogButtonBox.StandardButton.Ok).setObjectName('primary');actions.accepted.connect(self.accept);actions.rejected.connect(self.reject);v.addWidget(actions)
    def add_date(self):
        d=self.date.date().toString('yyyy-MM-dd')
        if d not in self.dates:self.dates.append(d);self.dates.sort()
        self.dates_text.setText('  ·  '.join(datetime.date.fromisoformat(x).strftime('%d-%m-%Y') for x in self.dates))
    def remove_date(self):
        if self.dates:self.dates.pop()
        self.dates_text.setText('  ·  '.join(datetime.date.fromisoformat(x).strftime('%d-%m-%Y') for x in self.dates) or 'No dates added')
    def accept(self):
        if not self.name.text().strip() or not self.dates:
            QMessageBox.warning(self,'Missing information','Enter a name and at least one date.');return
        super().accept()

class Window(QMainWindow):
    def __init__(self):
        super().__init__();self.data=load()
        self.reconcile_created,self.reconcile_ambiguous=reconcile_teams(self.data)
        if self.reconcile_created:
            if DATA.exists():snapshot(DATA,BACKUPS,'protected','team_id_reconciliation')
            atomic_write(DATA,self.data)
        self.notification_signals=NotificationSignals()
        self.notification_signals.failed.connect(self.notification_failed)
        self.active=None;self.section='Overview';self.tab='Checklist'
        self.update_info=None;self.update_busy=False;self.update_dialog=None;self.update_signals=UpdateSignals();self.update_signals.found.connect(self.update_found);self.update_signals.progress.connect(self.update_progress);self.update_signals.staged.connect(self.update_staged);self.update_signals.failed.connect(self.update_failed)
        self.setWindowTitle('Arena Tournament Manager');self.resize(1420,890);self.setMinimumSize(1050,680)
        if ICON_ASSET.exists():self.setWindowIcon(QIcon(str(ICON_ASSET)))
        elif ASSET.exists():self.setWindowIcon(QIcon(str(ASSET)))
        shell=QWidget();shell.setObjectName("appRoot");self.setCentralWidget(shell);root=layout_row(shell,0)
        self.sidebar=QFrame();self.sidebar.setObjectName('sidebar');self.sidebar.setFixedWidth(211);sv=layout_col(self.sidebar,3,(0,12,0,12));root.addWidget(self.sidebar)
        brand=QWidget();br=layout_row(brand,10,(16,0,12,0));brand.setMinimumHeight(54)
        if ASSET.exists():
            logo=QLabel();logo.setPixmap(QPixmap(str(ASSET)).scaled(30,30,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation));br.addWidget(logo)
        brandname=label('ARENA\nTOURNAMENT MANAGER');brandname.setStyleSheet('background:transparent;font-weight:750;font-size:12px;letter-spacing:0.4px;');br.addWidget(brandname,1);sv.addWidget(brand);sv.addSpacing(13);sv.addWidget(label('  MANAGEMENT','muted'));sv.addSpacing(5)
        self.nav={}
        for title in ('Overview','Tournaments','Players','Teams','Unofficial Teams','Map Veto','Settings'):
            b=button(title,lambda _,s=title:self.navigate(s))
            b.setIcon(nav_icon(title));b.setIconSize(QSize(16,16))
            self.nav[title]=b;sv.addWidget(b)
        sv.addStretch();sv.addWidget(label('●  Local database','muted'));sv.addWidget(label('Version '+VERSION,'muted'))
        self.content=QWidget();self.cv=layout_col(self.content,0,(22,22,22,22));root.addWidget(self.content,1)
        self.render()
        if self.reconcile_ambiguous:
            QTimer.singleShot(100,lambda:QMessageBox.warning(self,'Team reconciliation needs review','These team names could not be matched safely and were left unchanged:\n'+', '.join(self.reconcile_ambiguous)))
        QTimer.singleShot(1600,self.check_updates_background)
        self.tray = QSystemTrayIcon(self.windowIcon() if not self.windowIcon().isNull() else self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation), self)
        if QSystemTrayIcon.isSystemTrayAvailable():self.tray.show()
        self.notification_timer=QTimer(self);self.notification_timer.setInterval(60_000)
        self.notification_timer.timeout.connect(self.check_notifications)
        self.notification_timer.start()
        QTimer.singleShot(1200,self.startup_task_summary)
        QTimer.singleShot(2200,self.check_notifications)
    def notification_settings(self):
        settings=self.data.setdefault('settings',{}).setdefault('notifications',{})
        settings.setdefault('windows',True)
        settings.setdefault('discord',True)
        settings.setdefault('overdue',True)
        settings.setdefault('startup_summary',True)
        settings.setdefault('webhook','')
        return settings

    def startup_task_summary(self):
        if not self.notification_settings().get('startup_summary',True):return
        from overview_logic import active_tasks, task_complete
        pending=sum(1 for t in self.data.get('tournaments',[]) if str(t.get('status','')).casefold()!='finished'
                    for key,_,_ in active_tasks(t) if not task_complete(t,key))
        if pending:
            QMessageBox.information(self,'Outstanding tournament tasks',
                f'You have {pending} outstanding checklist task(s) across active tournaments.\n\nOpen Overview to see what needs attention.')

    def check_notifications(self):
        settings=self.notification_settings()
        ledger=self.data.setdefault('notification_history',{})
        # Keep only records from the last 120 days to bound local history growth.
        cutoff=(datetime.datetime.now()-datetime.timedelta(days=120)).isoformat()
        for k,v in list(ledger.items()):
            if isinstance(v,str) and v<cutoff:ledger.pop(k,None)
        for event in due_events(self.data):
            if event['kind']=='overdue' and not settings.get('overdue',True):continue
            if settings.get('windows',True) and QSystemTrayIcon.isSystemTrayAvailable():
                key=event_key(event,'windows')
                if key not in ledger:
                    state='Overdue' if event['kind']=='overdue' else 'Due within 24 hours'
                    self.tray.showMessage('Arena checklist — '+state,
                        f"{event['tournament']}: {event['label']}",QSystemTrayIcon.MessageIcon.Information,8000)
                    ledger[key]=datetime.datetime.now().isoformat()
                    self.save()
            url=settings.get('webhook','').strip()
            if settings.get('discord',True) and url and validate_webhook(url):
                key=event_key(event,'discord')
                if key not in ledger:
                    # Mark in-flight to prevent timer overlap; failed sends are retried.
                    ledger[key]=datetime.datetime.now().isoformat()
                    self.save()
                    def deliver(ev=event,marker=key,hook=url):
                        try:send_discord(hook,ev)
                        except Exception:
                            # Failure will be retried at the next check. No secrets in logs.
                            self.notification_signals.failed.emit(marker)
                    threading.Thread(target=deliver,daemon=True).start()

    def notification_failed(self,key):
        self.data.setdefault('notification_history',{}).pop(key,None)
        self.save()

    def edit_notification_settings(self):
        settings=self.notification_settings()
        dlg=QDialog(self);dlg.setWindowTitle('Checklist notifications');dlg.resize(550,310)
        form=QFormLayout(dlg)
        windows=QCheckBox('Windows desktop notifications');windows.setChecked(settings.get('windows',True));form.addRow(windows)
        discord=QCheckBox('Discord webhook notifications');discord.setChecked(settings.get('discord',True));form.addRow(discord)
        webhook=QLineEdit(settings.get('webhook',''));webhook.setEchoMode(QLineEdit.EchoMode.Password)
        webhook.setPlaceholderText('https://discord.com/api/webhooks/...')
        form.addRow('Discord webhook URL',webhook)
        overdue=QCheckBox('Notify when overdue');overdue.setChecked(settings.get('overdue',True));form.addRow(overdue)
        startup=QCheckBox('Show outstanding tasks on startup');startup.setChecked(settings.get('startup_summary',True));form.addRow(startup)
        form.addRow(label('Reminders are sent 24 hours before a deadline and once when overdue.\nThe application must be running to send notifications.','muted'))
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept);buttons.rejected.connect(dlg.reject);form.addRow(buttons)
        if dlg.exec()!=QDialog.DialogCode.Accepted:return
        url=webhook.text().strip()
        if url and not validate_webhook(url):
            QMessageBox.warning(self,'Invalid webhook','Enter a valid HTTPS Discord webhook URL.');return
        settings.update(windows=windows.isChecked(),discord=discord.isChecked(),webhook=url,
                        overdue=overdue.isChecked(),startup_summary=startup.isChecked())
        self.save();self.render()

    def save(self):
        # Completed tournament records are protected: compare with persisted state
        # and require an explicit acknowledgement before writing any changes.
        previous={}
        if DATA.exists():
            try:previous=json.loads(DATA.read_text(encoding='utf8'))
            except Exception as e:
                QMessageBox.critical(self,'Save blocked',f'Cannot read current database: {e}');return False
        old_by_id={str(t['id']):t for t in previous.get('tournaments',[])}
        changed=[]
        for t in self.data['tournaments']:
            old=old_by_id.get(str(t['id']))
            if old and old.get('status')=='Finished' and t!=old:
                keys=[k for k in set(t)|set(old) if t.get(k)!=old.get(k)]
                changed.append(f"{t['name']}: {', '.join(sorted(keys))}")
        if changed:
            if self.protected_backup('finished_tournament_override') is False:return False
            dlg=QDialog(self);dlg.setWindowTitle('Authorise changes to finished tournament');dlg.resize(540,270)
            v=layout_col(dlg,14,(24,24,24,24));v.addWidget(label('Protected historical changes','subheading'))
            v.addWidget(label('The following completed records will be modified:\n'+'\n'.join(changed),'muted'))
            ack=QCheckBox('I understand these historical changes and explicitly authorise saving them.');v.addWidget(ack)
            actions=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
            savebtn=actions.button(QDialogButtonBox.StandardButton.Save);savebtn.setEnabled(False)
            ack.toggled.connect(savebtn.setEnabled);actions.accepted.connect(dlg.accept);actions.rejected.connect(dlg.reject);v.addWidget(actions)
            if dlg.exec()!=QDialog.DialogCode.Accepted:
                self.data=previous;self.render();return False
            self.data.setdefault('audit_log',[]).append({'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'action':'finished_tournament_override','changes':changed})
        try:
            if DATA.exists():
                snapshot(DATA,BACKUPS,'rolling','before_save')
            atomic_write(DATA,self.data)
        except Exception as e:
            QMessageBox.critical(self,'Save failed',str(e));return False
        return True
    def t(self):return next((t for t in self.data['tournaments'] if t['id']==self.active),None)
    def clear(self):
        while self.cv.count():
            item=self.cv.takeAt(0)
            if item.widget():item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    child=item.layout().takeAt(0)
                    if child.widget():child.widget().deleteLater()
    def navigate(self,s):self.section=s;self.active=None;self.render()
    def open_t(self,id):self.active=id;self.section='Tournaments';self.tab='Checklist';self.render()
    def render(self):
        self.clear()
        for title,b in self.nav.items():b.setObjectName('navActive' if title==self.section else 'nav');b.style().unpolish(b);b.style().polish(b)
        if self.section=='Settings':self.settings_page()
        elif self.section=='Players':self.players_page()
        elif self.section=='Teams':self.teams_page()
        elif self.section=='Unofficial Teams':self.unofficial_teams_page()
        elif self.section=='Map Veto':self.map_veto_page()
        elif self.section=='Overview':self.overview_page()
        elif self.t():self.tournament_page()
        else:self.tournaments_page()
    def map_veto_page(self):
        self.veto_ui=VetoPage(self)
        self.veto_ui.render()

    def header(self,title,subtitle='',action=None):
        bar=QWidget();r=layout_row(bar)
        texts=QWidget();v=layout_col(texts,5);v.addWidget(label(title,'heading'))
        if subtitle:v.addWidget(label(subtitle,'muted'))
        r.addWidget(texts,1)
        if action:r.addWidget(button(action[0],action[1],True))
        self.cv.addWidget(bar);self.cv.addSpacing(18)
    def date_label(self,t):
        dates=t.get('dates') or [t.get('date','')]
        return ' · '.join(datetime.date.fromisoformat(x).strftime('%d-%m-%Y') if x else '' for x in dates)
    def overview_page(self):
        self.header('DASHBOARD','TOURNAMENT OPERATIONS / OVERVIEW',('+ NEW TOURNAMENT',self.create))
        items=overview(self.data)
        total_pending=sum(len(x['pending']) for x in items)
        attention=sum(bool(x['warnings']) for x in items)
        stats=QWidget();stats_row=layout_row(stats,10)
        for title,value,tone in [
            ('UPCOMING / ACTIVE',len(items),'#e8e8ec'),
            ('OUTSTANDING TASKS',total_pending,'#e8e8ec'),
            ('NEEDS ATTENTION',attention,'#f0bd75' if attention else '#58d900'),
            ('REGISTERED TEAMS',len(self.data.get('teams_db',{})),'#e8e8ec')]:
            card=QFrame();card.setObjectName('surface')
            column=layout_col(card,8,(15,13,15,13))
            heading=label(title,'muted')
            heading.setStyleSheet('color:#9e9ea5;font-size:11px;letter-spacing:0.5px;')
            column.addWidget(heading)
            value_label=label(str(value),'heading')
            value_label.setStyleSheet(f'font-size:28px;font-weight:700;color:{tone};')
            column.addWidget(value_label)
            stats_row.addWidget(card,1)
        self.cv.addWidget(stats)
        self.cv.addSpacing(17)

        body=QWidget();body_row=layout_row(body,13)
        left=QWidget();left_col=layout_col(left,10)
        right=QWidget();right_col=layout_col(right,10)
        left_col.addWidget(label('UPCOMING TOURNAMENTS','subheading'))
        if not items:
            empty=QFrame();empty.setObjectName('surface')
            ec=layout_col(empty,10,(18,18,18,18))
            ec.addWidget(label('NO UPCOMING TOURNAMENTS','subheading'))
            ec.addWidget(label('Create a tournament to begin preparation.','muted'))
            # Creation is available in the page header; avoid a duplicate action.
            left_col.addWidget(empty)
        for item in items:
            t=item['tournament']
            card=QFrame();card.setObjectName('surface')
            cv=layout_col(card,10,(16,13,16,13))
            title_row=QWidget();tr=layout_row(title_row,8)
            tr.addWidget(label(t.get('name','Untitled tournament').upper(),'subheading'),1)
            state=label(str(t.get('status','Preparing')).upper())
            state.setStyleSheet('color:#58d900;font-size:11px;')
            tr.addWidget(state)
            cv.addWidget(title_row)
            date=item['date'].strftime('%d-%m-%Y') if item['date'] else 'DATE NOT SET'
            cv.addWidget(label(f"{date}  /  {t.get('format','').upper()}",'muted'))
            progress_row=QWidget();pr=layout_row(progress_row,8)
            pr.addWidget(label('PREPARATION','muted'),1)
            pr.addWidget(label(f"{item['completed']} / {item['total']}",'muted'))
            cv.addWidget(progress_row)
            progress=QProgressBar();progress.setRange(0,max(1,item['total']))
            progress.setValue(item['completed']);progress.setTextVisible(False)
            cv.addWidget(progress)
            for warning in item['warnings'][:2]:
                warning_label=label('!  '+warning)
                warning_label.setStyleSheet('color:#f0bd75;')
                cv.addWidget(warning_label)
            pending=item['pending']
            for key,name,kind in pending[:2]:
                task=button(('□  ' if kind=='manual' else '→  ')+name,
                            lambda checked=False,tid=t['id'],k=key:self.open_overview_task(tid,k))
                task.setStyleSheet('text-align:left;background:#39393c;border:1px solid #454549;padding:7px 9px;')
                cv.addWidget(task)
            if len(pending)>2:
                cv.addWidget(label(f"+ {len(pending)-2} MORE OUTSTANDING TASKS",'muted'))
            cv.addWidget(button('OPEN TOURNAMENT  →',lambda checked=False,tid=t['id']:self.open_t(tid)))
            left_col.addWidget(card)
        left_col.addStretch()
        right_col.addWidget(label('ACTION REQUIRED','subheading'))
        side=QFrame();side.setObjectName('surface');sc=layout_col(side,10,(15,15,15,15))
        sc.addWidget(label(f'{total_pending} PENDING TASKS','subheading'))
        sc.addWidget(label(f'{attention} TOURNAMENTS NEED ATTENTION','muted'))
        shown=0
        for item in items:
            for key,name,kind in item['pending']:
                if shown>=5:break
                sc.addWidget(button(name,lambda checked=False,tid=item['tournament']['id'],k=key:self.open_overview_task(tid,k)))
                shown+=1
            if shown>=5:break
        if not shown:sc.addWidget(label('NO OUTSTANDING TASKS','muted'))
        right_col.addWidget(side)
        right_col.addStretch()
        body_row.addWidget(left,3)
        body_row.addWidget(right,1)
        self.cv.addWidget(body,1)
        self.cv.addSpacing(18)
        self.cv.addWidget(label('HISTORICAL ANALYTICS','subheading'))
        history=QWidget();hr=layout_row(history,12)
        all_tournaments=self.data.get('tournaments',[])
        completed=[t for t in all_tournaments if t.get('status','').lower() in ('finished','completed')]
        appearances=self.player_records()
        metrics=[('TOTAL TOURNAMENTS',len(all_tournaments)),
                 ('COMPLETED TOURNAMENTS',len(completed)),
                 ('KNOWN PLAYERS',len(appearances)),
                 ('PLAYERS WITH APPEARANCES',sum(bool(p.get('appearances')) for p in appearances.values()))]
        for heading,value in metrics:
            panel=QFrame();panel.setObjectName('surface');pc=layout_col(panel,7,(14,12,14,12))
            pc.addWidget(label(heading,'muted'))
            metric=label(str(value),'heading');metric.setStyleSheet('color:#58dc00;font-size:24px;')
            pc.addWidget(metric);hr.addWidget(panel,1)
        self.cv.addWidget(history)
        monthly={}
        for tournament in all_tournaments:
            dates=tournament.get('dates') or ([tournament.get('date')] if tournament.get('date') else [])
            if dates:
                month=str(dates[0])[:7]
                if len(month)==7:monthly[month]=monthly.get(month,0)+1
        chart=QFrame();chart.setObjectName('surface');cc=layout_col(chart,10,(16,14,16,14))
        cc.addWidget(label('TOURNAMENT ACTIVITY BY MONTH','subheading'))
        if monthly:
            for month,amount in sorted(monthly.items())[-8:]:
                line=QWidget();lr=layout_row(line,10)
                name=label(month,'muted');name.setMinimumWidth(85);lr.addWidget(name)
                bar=QProgressBar();bar.setRange(0,max(monthly.values()));bar.setValue(amount);bar.setTextVisible(False)
                lr.addWidget(bar,1);lr.addWidget(label(str(amount)));cc.addWidget(line)
        else:cc.addWidget(label('No tournament history recorded yet.','muted'))
        self.cv.addSpacing(12);self.cv.addWidget(chart)


    def open_overview_task(self,tournament_id,key):
        self.open_t(tournament_id)
        if key=='files':self.change_tab('Files')
        elif key=='keys':self.change_tab('Streams')
        elif key=='results':self.change_tab('Results')
        elif key=='bracket':self.change_tab('Bracket')

    def tournaments_page(self):
        self.header('TOURNAMENTS','TOURNAMENT MANAGEMENT / ALL EVENTS',('+ NEW TOURNAMENT',self.create))
        controls=QWidget();cr=layout_row(controls,10)
        search=QLineEdit();search.setPlaceholderText('SEARCH TOURNAMENTS...')
        cr.addWidget(search,1)
        cr.addWidget(button('RECENTLY DELETED',self.restore_tournament))
        self.cv.addWidget(controls)
        self.cv.addSpacing(12)
        filters=QWidget();filter_row=layout_row(filters,5)
        active_filter={'value':'ALL'};filter_buttons={}
        for status in ('ALL','UPCOMING','ACTIVE','COMPLETED'):
            tab=button(status,lambda checked=False,key=status:set_filter(key))
            filter_buttons[status]=tab;filter_row.addWidget(tab)
        filter_row.addStretch();self.cv.addWidget(filters)
        self.cv.addSpacing(12)
        count=label('','muted');self.cv.addWidget(count)
        holder=QWidget();rows_layout=layout_col(holder,8)
        self.cv.addWidget(holder,1)

        def refresh():
            while rows_layout.count():
                item=rows_layout.takeAt(0)
                if item.widget():item.widget().deleteLater()
            tournaments=[t for t in reversed(self.data['tournaments'])
                         if search.text().strip().lower() in
                         (t.get('name','')+' '+t.get('format','')+' '+t.get('status','')).lower()
                         and (active_filter['value']=='ALL' or
                              (active_filter['value']=='COMPLETED' and t.get('status','').lower() in ('finished','completed')) or
                              (active_filter['value']=='ACTIVE' and t.get('status','').lower() in ('active','in progress','live')) or
                              (active_filter['value']=='UPCOMING' and t.get('status','').lower() not in ('finished','completed','active','in progress','live')))]
            count.setText(f'{len(tournaments)} / {len(self.data["tournaments"])} TOURNAMENTS')
            if not tournaments:
                rows_layout.addWidget(label('NO MATCHING TOURNAMENTS' if search.text().strip() else 'NO TOURNAMENTS YET','muted'))
            else:
                self.tournament_rows(tournaments,rows_layout)
            rows_layout.addStretch()
        def set_filter(value):
            active_filter['value']=value
            for key,tab in filter_buttons.items():
                tab.setObjectName('tabActive' if key==value else 'tab')
                tab.style().unpolish(tab);tab.style().polish(tab)
            refresh()
        search.textChanged.connect(refresh)
        set_filter('ALL')

    def tournament_rows(self,ts,target=None):
        target=target or self.cv
        if not ts:
            target.addWidget(label('No tournaments yet. Create one to get started.','muted'))
            return
        for t in ts:
            card=QFrame();card.setObjectName('surface')
            r=layout_row(card,12,(15,12,15,12))
            info=QWidget();v=layout_col(info,5)
            v.addWidget(label(t.get('name','UNTITLED').upper(),'subheading'))
            v.addWidget(label(f"{self.date_label(t)}  /  {t.get('format','')}  /  {t.get('status','')}",'muted'))
            r.addWidget(info,1)
            r.addWidget(button('OPEN TOURNAMENT  →',
                               lambda checked=False,tid=t['id']:self.open_t(tid)))
            target.addWidget(card)

    def delete_tournament(self):
        t=self.t()
        if not t:return
        dlg=QDialog(self);dlg.setWindowTitle('Delete tournament');dlg.resize(490,300)
        v=layout_col(dlg,14,(24,24,24,24))
        v.addWidget(label('Move tournament to Recently Deleted','subheading'))
        v.addWidget(label(f"You're deleting: {t['name']}\n\nThis removes it from active tournament lists, but retains its record for recovery. Permanent players and teams are not deleted.",'muted'))
        v.addWidget(label('Type DELETE to continue','muted'))
        typed=QLineEdit();typed.setPlaceholderText('DELETE');v.addWidget(typed)
        ack=QCheckBox('I understand and explicitly authorise deleting this tournament.');v.addWidget(ack)
        actions=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        confirm=actions.button(QDialogButtonBox.StandardButton.Ok)
        confirm.setText('Move to Recently Deleted');confirm.setEnabled(False)
        def enable():confirm.setEnabled(typed.text()=='DELETE' and ack.isChecked())
        typed.textChanged.connect(enable);ack.toggled.connect(enable)
        actions.accepted.connect(dlg.accept);actions.rejected.connect(dlg.reject);v.addWidget(actions)
        if dlg.exec()!=QDialog.DialogCode.Accepted:return
        if self.protected_backup('delete_tournament') is False:return
        old_active=self.active
        self.data['tournaments']=[item for item in self.data['tournaments'] if item['id']!=old_active]
        self.data.setdefault('deleted_tournaments',[]).append({'deleted_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'tournament':t})
        self.data.setdefault('audit_log',[]).append({'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'action':'tournament_deleted','tournament_id':old_active,'name':t['name']})
        if self.save():self.navigate('Tournaments')

    def restore_tournament(self):
        deleted=self.data.setdefault('deleted_tournaments',[])
        if not deleted:
            QMessageBox.information(self,'Recently Deleted','No deleted tournaments to restore.');return
        dlg=QDialog(self);dlg.setWindowTitle('Recently Deleted');dlg.resize(590,440)
        col=layout_col(dlg,12,(22,22,22,22))
        col.addWidget(label('RECENTLY DELETED','heading'))
        col.addWidget(label('Restore a deleted tournament to your active tournament list.','muted'))
        scroll=QScrollArea();scroll.setWidgetResizable(True)
        container=QWidget();items=layout_col(container,9)
        for entry in reversed(list(deleted)):
            panel=QFrame();panel.setObjectName('surface');row=layout_row(panel,12,(14,12,14,12))
            info=QWidget();iv=layout_col(info,4)
            iv.addWidget(label(entry['tournament'].get('name','Untitled'),'subheading'))
            iv.addWidget(label('DELETED '+entry.get('deleted_at','')[:10],'muted'))
            row.addWidget(info,1)
            def restore(checked=False,record=entry):
                if self.protected_backup('restore_tournament') is False:return
                if record not in deleted:return
                t=record['tournament']
                if any(str(x['id'])==str(t['id']) for x in self.data['tournaments']):
                    t['id']=max([int(x['id']) for x in self.data['tournaments']]+[0])+1
                deleted.remove(record);self.data['tournaments'].append(t)
                self.data.setdefault('audit_log',[]).append(
                    {'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                     'action':'tournament_restored','tournament_id':t['id']})
                if self.save():dlg.accept();self.open_t(t['id'])
            row.addWidget(button('RESTORE',restore,True));items.addWidget(panel)
        items.addStretch();scroll.setWidget(container);col.addWidget(scroll,1)
        footer=QWidget();fr=layout_row(footer,8);fr.addStretch();fr.addWidget(button('CLOSE',dlg.reject));col.addWidget(footer)
        dlg.exec()

    def create(self):
        d=TournamentDialog(self)
        if d.exec()!=QDialog.DialogCode.Accepted:return
        id=max([int(t['id']) for t in self.data['tournaments']]+[int(e['tournament']['id']) for e in self.data.get('deleted_tournaments',[])]+[0])+1
        t={'id':id,'name':d.name.text().strip(),'date':d.dates[0],'dates':d.dates,'format':d.format.currentText(),'main':d.main.value(),'subs':d.sub.value(),'qualifiers':d.qual.isChecked(),'locked':d.locked.isChecked(),'status':'Preparing','tasks':{},'teams':[],'spares':[],'bracket_url':'','results':{},'keys_imported':False,'teams_imported':False}
        self.data['tournaments'].append(t);self.save();self.open_t(id)
    def display_player_name(self,player):
        uid=str(player.get('arena_id',player.get('userId','')))
        record=self.data.get('players',{}).get(uid,{})
        return record.get('name') or player.get('name') or uid

    def task_done(self,t,key):
        return task_complete(t,key)
    def tournament_page(self):
        t=self.t();back=QWidget();br=layout_row(back,8);br.addWidget(button('←  ALL TOURNAMENTS',lambda:self.navigate('Tournaments')));br.addStretch();self.cv.addWidget(back)
        self.cv.addSpacing(13);self.header(t['name'],f"{self.date_label(t)}  ·  {t['format']}  ·  {t['main']} main / {t['subs']} substitute teams  ·  {t['status']}")
        tabs=QWidget();r=layout_row(tabs,2)
        for name in ['Checklist','Teams','Streams','Bracket','Results','Files']:
            b=button(name,lambda _,s=name:self.change_tab(s));b.setObjectName('tabActive' if self.tab==name else 'tab');r.addWidget(b)
        r.addStretch()
        r.addWidget(button('Delete tournament',self.delete_tournament))
        self.cv.addWidget(tabs);self.cv.addSpacing(18)
        {'Checklist':self.checklist,'Teams':self.tournament_teams,'Streams':self.streams,'Bracket':self.bracket_page,'Results':self.results_page,'Files':self.files_page}[self.tab](t)
    def change_tab(self,s):self.tab=s;self.render()
    def checklist(self,t):
        tasks=[task for task in TASKS if t['qualifiers'] or task[0] not in ('qopen','qclose')]
        done=sum(self.task_done(t,k) for k,_,_ in tasks)
        self.cv.addWidget(label(f'Tournament preparation       {done} / {len(tasks)} complete','subheading'))
        progress=QProgressBar();progress.setRange(0,len(tasks));progress.setValue(done);progress.setTextVisible(False);self.cv.addWidget(progress)
        self.cv.addSpacing(8)
        scroll=QScrollArea();scroll.setWidgetResizable(True);holder=QWidget();v=layout_col(holder,0)
        for i,(key,name,kind) in enumerate(tasks,1):
            row=QFrame();row.setObjectName('task');r=layout_row(row,12,(13,10,13,10))
            # Draw the checkbox explicitly: the native Qt checkbox indicator can
            # disappear against dark palettes on some Windows themes.
            completed=self.task_done(t,key)
            cb=QPushButton('✓' if completed else '')
            cb.setCheckable(kind=='manual')
            cb.setChecked(completed)
            cb.setFixedSize(23,23)
            cb.setCursor(Qt.CursorShape.PointingHandCursor if kind=='manual' else Qt.CursorShape.ArrowCursor)
            cb.setToolTip('Click to mark complete or incomplete' if kind=='manual' else 'Completed automatically')
            cb.setStyleSheet(
                'QPushButton {border:2px solid #718580;border-radius:5px;'
                'background:#192326;color:#102016;font-size:16px;font-weight:900;padding:0;}'
                'QPushButton:checked {background:#83e38b;border-color:#83e38b;}'
                'QPushButton:disabled {background:#253032;border-color:#52635c;color:#102016;}'
            )
            if kind=='manual':
                cb.toggled.connect(lambda value,k=key:self.set_task(k,value))
                row.mousePressEvent=lambda event,checkbox=cb:checkbox.click() if event.button()==Qt.MouseButton.LeftButton else None
            else:
                cb.setEnabled(False)
            r.addWidget(cb)
            txt=label(f'{i:02d}    {name}');txt.setStyleSheet('color:#8fa39a;' if self.task_done(t,key) else '');r.addWidget(txt,1)
            deadline=t.get('task_deadlines',{}).get(key)
            state=deadline_status(t,key)
            if deadline:
                due_text=deadline.replace('T','  ')
                status={'overdue':'OVERDUE','due_soon':'Due soon','upcoming':'Scheduled','complete':'Completed'}.get(state,'Scheduled')
                due_label=label(f'{status} · {due_text}')
                due_label.setStyleSheet('color:#f4a69b;' if state=='overdue' else ('color:#e6c27b;' if state=='due_soon' else 'color:#93b5a2;'))
                r.addWidget(due_label)
            r.addWidget(button('Edit due date' if deadline else 'Set due date',lambda _,k=key:self.edit_task_deadline(k)))
            action={'files':('Upload files',lambda:self.change_tab('Files')),'keys':('Manage DMs',lambda:self.change_tab('Streams')),'bracket':('Set link',self.set_bracket),'results':('Enter results',lambda:self.change_tab('Results'))}.get(key)
            if kind=='auto' and self.task_done(t,key):r.addWidget(label('✓ Complete','muted'))
            if action:r.addWidget(button(*action))
            elif self.task_done(t,key):r.addWidget(label('✓ Complete','muted'))
            v.addWidget(row)
        v.addStretch();scroll.setWidget(holder);self.cv.addWidget(scroll,1)
        footer=QWidget();f=layout_row(footer);f.addStretch();f.addWidget(button('Finish tournament',self.finish,True));self.cv.addWidget(footer)
    def edit_task_deadline(self,key):
        t=self.t()
        if not t:return
        existing=t.get('task_deadlines',{}).get(key,'')
        dialog=QDialog(self);dialog.setWindowTitle('Checklist deadline')
        form=QFormLayout(dialog)
        picker=QDateTimeEdit(dialog)
        picker.setCalendarPopup(True)
        picker.setDisplayFormat('dd-MM-yyyy HH:mm')
        picker.setDateTime(QDateTime.fromString(existing,'yyyy-MM-ddTHH:mm') if existing else QDateTime.currentDateTime())
        form.addRow('Complete by',picker)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel,dialog)
        clear=buttons.addButton('Remove deadline',QDialogButtonBox.ButtonRole.ResetRole)
        buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject)
        clear.clicked.connect(lambda:(dialog.setProperty('clear_deadline',True),dialog.accept()))
        form.addRow(buttons)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        deadlines=t.setdefault('task_deadlines',{})
        old=dict(deadlines)
        if dialog.property('clear_deadline'):deadlines.pop(key,None)
        else:deadlines[key]=picker.dateTime().toString('yyyy-MM-ddTHH:mm')
        if not self.save():
            t['task_deadlines']=old
            return
        self.render()

    def set_task(self,key,value):
        tournament=self.t()
        if tournament is None:return
        tournament.setdefault('tasks',{})[key]=bool(value)
        if self.save():self.render()
    def player_records(self):
        records={str(uid):dict(info,arena_id=str(uid),appearances=[]) for uid,info in self.data.get('players',{}).items()}
        for t in self.data['tournaments']:
            for team in t.get('teams',[]):
                for p in team['members']:
                    uid=str(p['arena_id']);rec=records.setdefault(uid,{'arena_id':uid,'name':p['name'],'discord_id':'','notes':'','appearances':[]})
                    rec['appearances'].append((t['name'],team['name'],self.date_label(t)))
                    rec.setdefault('name',p['name'])
        return records
    def table(self,headers):
        table=QTableWidget(0,len(headers));table.setHorizontalHeaderLabels(headers);table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);table.setAlternatingRowColors(True);table.verticalHeader().hide();table.verticalHeader().setDefaultSectionSize(32);table.setShowGrid(False);table.setFocusPolicy(Qt.FocusPolicy.NoFocus);table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter);return table
    def fill_table(self,table,rows):
        table.setRowCount(len(rows))
        for i,row in enumerate(rows):
            for j,value in enumerate(row):item=QTableWidgetItem(str(value));item.setTextAlignment(Qt.AlignmentFlag.AlignCenter);table.setItem(i,j,item)
    def players_page(self):
        self.header('PLAYERS','PLAYER DIRECTORY / DISCORD MAPPINGS / TOURNAMENT HISTORY')
        records=self.player_records()
        metrics=QWidget();mr=layout_row(metrics,10)
        for heading,value in [('TOTAL PLAYERS',len(records)),
                              ('DISCORD LINKED',sum(bool(rec.get('discord_id')) for rec in records.values())),
                              ('WITH APPEARANCES',sum(bool(rec.get('appearances')) for rec in records.values()))]:
            panel=QFrame();panel.setObjectName('surface')
            panel_col=layout_col(panel,5,(14,12,14,12))
            panel_col.addWidget(label(heading,'muted'))
            metric=label(str(value),'heading');metric.setStyleSheet('font-size:25px;color:#58dc00;font-weight:700;')
            panel_col.addWidget(metric)
            mr.addWidget(panel,1)
        self.cv.addWidget(metrics)
        self.cv.addSpacing(10)
        search=QLineEdit();search.setPlaceholderText('SEARCH PLAYER, ARENA ID, DISCORD ID OR TEAM...')
        self.cv.addWidget(search)
        self.cv.addSpacing(12)
        count=label('','muted');self.cv.addWidget(count)
        table=self.table(['PLAYER','ARENA ID','DISCORD ID','MOST RECENT TEAM','APPEARANCES'])
        self.cv.addWidget(table,1)
        def refresh():
            records=self.player_records();rows=[];ids=[]
            for uid,rec in sorted(records.items(),key=lambda x:x[1].get('name','').lower()):
                team=rec['appearances'][-1][1] if rec['appearances'] else '—'
                row=[rec.get('name',''),uid,rec.get('discord_id','') or 'NOT LINKED',team,len(rec['appearances'])]
                if search.text().lower() in ' '.join(map(str,row)).lower():
                    rows.append(row);ids.append(uid)
            self.fill_table(table,rows);table.setProperty('ids',ids)
            count.setText(f'{len(rows)} / {len(records)} PLAYERS')
        search.textChanged.connect(refresh);refresh()
        def open_profile():
            idx=table.currentRow();ids=table.property('ids') or []
            if idx<0 or idx>=len(ids):return
            uid=ids[idx];rec=self.player_records()[uid]
            d=QDialog(self);d.setWindowTitle(f'Player · {rec.get("name",uid)}');d.resize(570,550);v=layout_col(d,13,(22,22,22,22))
            v.addWidget(label(rec.get('name',uid),'heading'));v.addWidget(label(f'Arena ID: {uid}','muted'))
            v.addWidget(label('Preferred player name'));preferred=QLineEdit(rec.get('name',uid));v.addWidget(preferred)
            v.addWidget(label('Discord user ID'));discord=QLineEdit(rec.get('discord_id',''));v.addWidget(discord)
            v.addWidget(label('Notes'));notes=QTextEdit(rec.get('notes',''));notes.setMaximumHeight(100);v.addWidget(notes)
            v.addWidget(label(f'TOURNAMENT HISTORY  ·  {len(rec["appearances"])} APPEARANCES','subheading'))
            hist=QTextEdit();hist.setReadOnly(True);hist.setPlainText('\n'.join(f'{date}  ·  {tour}  ·  {team}' for tour,team,date in rec['appearances']));v.addWidget(hist)
            def save_profile():
                value=discord.text().strip();new_name=preferred.text().strip()
                if not new_name:QMessageBox.warning(d,'Name required','Enter a preferred player name.');return
                previous_name=rec.get('name',uid)
                old=self.data['players'].get(uid,{})
                history=list(old.get('name_history',[]))
                if new_name!=previous_name and previous_name not in history:history.append(previous_name)
                self.data['players'][uid]={**old,'name':new_name,'name_history':history,'discord_id':value,'notes':notes.toPlainText()}
                if value:self.data['discord_mappings'][uid]=value
                else:self.data['discord_mappings'].pop(uid,None)
                for t in self.data['tournaments']:
                    for team in t['teams']:
                        for p in team['members']:
                            if str(p['arena_id'])==uid:p['discord_id']=value;p['name']=new_name
                self.save();d.accept();self.render()
            footer=QWidget();buttons=layout_row(footer,8);buttons.addStretch();buttons.addWidget(button('CANCEL',d.reject));buttons.addWidget(button('SAVE PROFILE',save_profile,True));v.addWidget(footer);d.exec()
        table.cellDoubleClicked.connect(lambda *_:open_profile())
        footer=QWidget();fr=layout_row(footer,8);fr.addStretch();fr.addWidget(button('VIEW / EDIT PLAYER',open_profile));self.cv.addWidget(footer)
    def teams_page(self):
        self.header('TEAMS','PERMANENT TEAM IDENTITIES / ROSTERS / TRANSFER WINDOWS',
                    ('+ TRANSFER WINDOW',self.new_transfer_window))
        db=self.data.setdefault('teams_db',{})
        toolbar=QWidget();toolbar_row=layout_row(toolbar,10)
        search=QLineEdit();search.setPlaceholderText('SEARCH TEAMS OR PLAYERS...')
        toolbar_row.addWidget(search,1)
        toolbar_row.addWidget(button('MANAGE TRANSFERS',self.manage_transfers))
        self.cv.addWidget(toolbar)
        self.cv.addSpacing(10)
        summary=label(f'{len(db)} REGISTERED TEAMS','muted')
        self.cv.addWidget(summary)
        table=self.table(['TEAM','PERMANENT ID','CURRENT ROSTER','PREVIOUS NAMES'])
        self.cv.addWidget(table,1)
        selected_ids=[]

        def refresh():
            rows=[];selected_ids.clear()
            query=search.text().strip().lower()
            for tid,rec in sorted(db.items(),key=lambda item:item[1].get('name','').lower()):
                roster=[self.data['players'].get(str(uid),{}).get('name',str(uid))
                        for uid in rec.get('roster',[])]
                row=[rec.get('name',''),tid,', '.join(roster),
                     ', '.join(rec.get('names',[])[:-1]) or '—']
                if query and query not in ' '.join(map(str,row)).lower():
                    continue
                rows.append(row);selected_ids.append(tid)
            self.fill_table(table,rows)
            summary.setText(f'{len(rows)} / {len(db)} REGISTERED TEAMS')

        def rename():
            i=table.currentRow()
            if i<0 or i>=len(selected_ids):
                QMessageBox.information(self,'Select team','Select a team to rename first.')
                return
            rec=db[selected_ids[i]]
            name,ok=QInputDialog.getText(self,'Rename team','New team name:',text=rec['name'])
            if ok and name.strip() and name.strip()!=rec['name']:
                rec.setdefault('names',[]).append(name.strip());rec['name']=name.strip()
                rec.setdefault('history',[]).append(
                    {'at':datetime.datetime.now().isoformat(),'action':'rename','name':name.strip()})
                if self.save():self.render()

        search.textChanged.connect(refresh)
        refresh()
        actions=QWidget();ar=layout_row(actions,10)
        ar.addStretch()
        ar.addWidget(button('RENAME SELECTED TEAM',rename))
        self.cv.addWidget(actions)

    def unofficial_teams_page(self):
        self.header('UNOFFICIAL TEAMS','CASUAL TOURNAMENT TEAMS / INFORMATION ONLY')
        self.cv.addWidget(label('Browse casual teams by tournament. Newest tournaments appear first; no official rosters or transfer windows are affected.','muted'))
        self.cv.addSpacing(12)
        search=QLineEdit();search.setPlaceholderText('SEARCH TOURNAMENTS, TEAMS OR PLAYERS...')
        self.cv.addWidget(search)
        self.cv.addSpacing(12)
        summary=label('0 UNOFFICIAL TEAM ENTRIES','muted');self.cv.addWidget(summary)
        tree=QTreeWidget()
        tree.setHeaderLabels(['TOURNAMENT / TEAM','PLAYERS','ROSTER'])
        tree.setRootIsDecorated(True)
        tree.setAlternatingRowColors(True)
        tree.setIndentation(20)
        tree.header().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents)
        tree.header().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents)
        tree.header().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch)
        self.cv.addWidget(tree,1)
        tournaments=sorted(
            (t for t in self.data.get('tournaments',[]) if not t.get('locked',True)),
            key=lambda t: max(t.get('dates') or [t.get('date','')]),
            reverse=True)
        groups=[]
        for tournament in tournaments:
            date=max(tournament.get('dates') or [tournament.get('date','')])
            rows=[]
            for team in tournament.get('teams',[]):
                members=team.get('members',[])
                rows.append((team.get('name',''),str(len(members)),
                             ', '.join(self.display_player_name(p) for p in members)))
            groups.append((tournament.get('name','Unnamed tournament'),date,rows))
        def refresh():
            tree.clear()
            query=search.text().strip().casefold()
            visible=0
            for name,date,rows in groups:
                matching=[row for row in rows if not query or query in name.casefold() or
                          query in ' '.join(row).casefold()]
                if not matching:
                    continue
                heading=QTreeWidgetItem([name+(f'  ·  {date}' if date else ''),str(len(matching))+' teams',''])
                tree.addTopLevelItem(heading)
                for row in matching:
                    heading.addChild(QTreeWidgetItem(list(row)))
                heading.setExpanded(True)
                visible+=len(matching)
            summary.setText(f'{visible} UNOFFICIAL TEAM ENTRIES ACROSS {tree.topLevelItemCount()} TOURNAMENTS')
        search.textChanged.connect(refresh)
        refresh()

    def new_transfer_window(self):
        d=QDialog(self);d.setWindowTitle('Create transfer window');d.resize(540,440)
        v=layout_col(d,12,(24,24,24,24));v.addWidget(label('CREATE TRANSFER WINDOW','heading'))
        v.addWidget(label('Configure when teams can make roster changes.','muted'))
        v.addWidget(label('WINDOW NAME'))
        name=QLineEdit();name.setPlaceholderText('e.g. Season 5 Transfer Window');v.addWidget(name)
        v.addWidget(label('MAXIMUM REPLACEMENTS PER TEAM'))
        limit=QSpinBox();limit.setRange(0,100);limit.setValue(2);v.addWidget(limit)
        v.addWidget(label('Set to 0 for unlimited replacements.','muted'))
        v.addWidget(label('START DATE'));start=QDateEdit(QDate.currentDate());start.setCalendarPopup(True);start.setDisplayFormat('dd-MM-yyyy');v.addWidget(start)
        v.addWidget(label('END DATE'));end=QDateEdit(QDate.currentDate().addDays(7));end.setCalendarPopup(True);end.setDisplayFormat('dd-MM-yyyy');v.addWidget(end)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);b.button(QDialogButtonBox.StandardButton.Ok).setText('CREATE WINDOW');b.button(QDialogButtonBox.StandardButton.Ok).setObjectName('primary');b.accepted.connect(d.accept);b.rejected.connect(d.reject);v.addWidget(b)
        if d.exec()!=QDialog.DialogCode.Accepted:return
        if not name.text().strip() or start.date()>end.date():QMessageBox.warning(self,'Invalid window','Enter a name and valid dates.');return
        self.data.setdefault('transfer_windows',[]).append({'id':str(uuid.uuid4()),'name':name.text().strip(),'limit':limit.value(),'start':start.date().toString('yyyy-MM-dd'),'end':end.date().toString('yyyy-MM-dd'),'open':True,'changes':[]})
        if self.save():self.render()

    def manage_transfers(self):
        windows=self.data.setdefault('transfer_windows',[])
        if not windows:QMessageBox.information(self,'No transfer window','Create a transfer window first.');return
        names=[w['name']+(' (Open)' if w.get('open') else ' (Closed)') for w in windows]
        selected,ok=QInputDialog.getItem(self,'Transfer windows','Select window:',names,len(names)-1,False)
        if not ok:return
        w=windows[names.index(selected)]
        if not w.get('open'):
            if QMessageBox.question(self,'Closed window','Reopen this transfer window?')==QMessageBox.StandardButton.Yes:
                w['open']=True;self.save();self.render()
            return
        choice,ok=QInputDialog.getItem(self,'Transfer window','Action:',['Replace player','Close window'],0,False)
        if not ok:return
        if choice=='Close window':w['open']=False;self.save();self.render();return
        db=self.data.setdefault('teams_db',{})
        if not db:QMessageBox.warning(self,'No teams','Import teams before managing transfers.');return
        teamnames=[rec['name'] for rec in db.values()];name,ok=QInputDialog.getItem(self,'Transfer','Team:',teamnames,0,False)
        if not ok:return
        tid=next(tid for tid,rec in db.items() if rec['name']==name);rec=db[tid]
        roster=rec.get('roster',[])
        if not roster:QMessageBox.warning(self,'Empty roster','No players on this team.');return
        old_names=[self.data['players'].get(str(uid),{}).get('name',str(uid))+f' ({uid})' for uid in roster]
        outgoing,ok=QInputDialog.getItem(self,'Replace player','Outgoing player:',old_names,0,False)
        if not ok:return
        out_id=roster[old_names.index(outgoing)]
        incoming,ok=QInputDialog.getText(self,'Replace player','Incoming Arena ID:')
        if not ok or not incoming.strip():return
        incoming=incoming.strip()
        if incoming==out_id or incoming in roster:QMessageBox.warning(self,'Invalid replacement','Incoming player must not already be on this team.');return
        if any(incoming in other.get('roster',[]) for other in db.values()):QMessageBox.warning(self,'Player already rostered','This player belongs to another permanent roster. Release them first.');return
        if incoming not in self.data['players']:
            pname,ok=QInputDialog.getText(self,'New player','Player display name:')
            if not ok or not pname.strip():return
        else:pname=self.data['players'][incoming].get('name',incoming)
        used=sum(c.get('team_id')==tid for c in w.get('changes',[]))
        override=bool(w['limit'] and used>=w['limit'])
        if override:
            d=QDialog(self);d.setWindowTitle('Transfer limit override');v=layout_col(d,14,(22,22,22,22))
            v.addWidget(label(f'{name} has used {used} / {w["limit"]} permitted changes.','subheading'))
            v.addWidget(label(f'Additional replacement: {outgoing} → {pname} ({incoming})'))
            reason=QLineEdit();reason.setPlaceholderText('Reason for override');v.addWidget(reason)
            ack=QCheckBox('I explicitly authorise exceeding this transfer limit.');v.addWidget(ack)
            actions=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
            actions.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            ack.toggled.connect(lambda x:actions.button(QDialogButtonBox.StandardButton.Ok).setEnabled(x and bool(reason.text().strip())))
            reason.textChanged.connect(lambda x:actions.button(QDialogButtonBox.StandardButton.Ok).setEnabled(ack.isChecked() and bool(x.strip())))
            actions.accepted.connect(d.accept);actions.rejected.connect(d.reject);v.addWidget(actions)
            if d.exec()!=QDialog.DialogCode.Accepted:return
            why=reason.text().strip()
        else:why=''
        self.data['players'].setdefault(incoming,{'name':pname,'discord_id':'','notes':''})
        if self.protected_backup('roster_change') is False:return
        rec['roster']=[incoming if x==out_id else x for x in roster]
        change={'at':datetime.datetime.now().isoformat(),'team_id':tid,'out':out_id,'in':incoming,'override':override,'reason':why}
        w.setdefault('changes',[]).append(change);rec.setdefault('history',[]).append(change)
        if self.save():self.render()

    def tournament_teams(self,t):
        top=QWidget();r=layout_row(top);r.addWidget(label(f'{len(t["teams"])} imported teams','subheading'));r.addStretch();r.addWidget(button('Import teams JSON',self.import_teams,True));self.cv.addWidget(top)
        table=self.table(['Team','Type','Players','Roster']);self.fill_table(table,[[team['name'],'Substitute' if team.get('sub') else 'Main',len(team['members']),', '.join(self.display_player_name(p) for p in team['members'])] for team in t['teams']]);self.cv.addWidget(table,1)
    def import_teams(self):
        path,_=QFileDialog.getOpenFileName(self,'Import tournament export','','JSON files (*.json)')
        if not path:return
        t=self.t()
        try:
            source=json.loads(Path(path).read_text(encoding='utf8'))['teams'][:t['main']+t['subs']]
            if not source:raise ValueError('No teams found')
            old={str(p['arena_id']):p for team in t['teams'] for p in team['members']}
            teams=[];seen=set()
            for i,team in enumerate(source):
                members=[]
                for p in team['members']:
                    uid=str(p['userId'])
                    if uid in seen:raise ValueError(f'Duplicate Arena ID {uid}')
                    seen.add(uid);previous=old.get(uid,{})
                    members.append({'arena_id':uid,'name':self.display_player_name({'arena_id':uid,'name':p['name']}),'imported_name':p['name'],'discord_id':previous.get('discord_id',self.data['discord_mappings'].get(uid,'')),'key':previous.get('key'),'sent':previous.get('sent',False)})
                team_name=team['crewName'].strip()
                tid=('arena:'+str(team['crewId']) if team.get('crewId') is not None else next((k for k,v in self.data.get('teams_db',{}).items() if team_name.lower() in [n.lower() for n in v.get('names',[v.get('name','')])]),'local:'+str(uuid.uuid4()))) if t.get('locked') else 'unofficial:'+str(t['id'])+':'+str(i)
                teams.append({'name':team_name,'team_id':tid,'sub':i>=t['main'],'members':members})
            if t['teams'] and QMessageBox.question(self,'Replace rosters?','Re-importing can change roster assignments. Continue?')!=QMessageBox.StandardButton.Yes:return
            if t.get('locked'):
                conflicts=[]
                for team in teams:
                    rec=self.data.get('teams_db',{}).get(team['team_id'])
                    if rec and rec.get('roster') and set(rec['roster'])!={p['arena_id'] for p in team['members']}:
                        conflicts.append(team['name'])
                if conflicts and QMessageBox.question(self,'Locked roster mismatch',f"Imported roster differs from saved locked roster for: {', '.join(conflicts)}.\n\nApprove tournament-specific roster snapshot? Permanent rosters will NOT be overwritten.")!=QMessageBox.StandardButton.Yes:return
            if DATA.exists() and self.protected_backup('before_team_import') is False:return
            t['teams']=teams;t['teams_imported']=True
            if t.get('locked'):
                for team in teams:
                    tid=team['team_id'];rec=self.data.setdefault('teams_db',{}).get(tid)
                    if not rec:
                        self.data['teams_db'][tid]={'id':tid,'name':team['name'],'names':[team['name']],'roster':[p['arena_id'] for p in team['members']],'history':[]}
                    else:
                        if team['name'] not in rec.setdefault('names',[]):rec['names'].append(team['name']);rec['name']=team['name']
            for team in teams:
                for p in team['members']:
                    self.data['players'].setdefault(p['arena_id'],{'name':p['name'],'discord_id':p['discord_id'],'notes':''})
            changes,review=reconcile_teams(self.data)
            if self.save():
                self.render()
                if review:QMessageBox.warning(self,'Team identity review','Possible duplicate teams need manual review:\n'+'\n'.join(review[:15]))
        except Exception as e:QMessageBox.critical(self,'Import failed',str(e))
    def files_page(self,t):
        self.cv.addWidget(label('Tournament files','subheading'))
        self.cv.addWidget(label('Upload the tournament JSON and Cloudflare TXT after receiving them from an Arena developer.','muted'))
        self.cv.addSpacing(15)
        imports=QWidget();ir=layout_row(imports,12)
        ir.addWidget(button('IMPORT TOURNAMENT EXPORT (.JSON)',self.import_teams,True))
        ir.addWidget(button('IMPORT CLOUDFLARE STREAM KEYS (.TXT)',self.import_keys))
        ir.addStretch();self.cv.addWidget(imports)
        self.cv.addWidget(label(f"Teams imported: {'Yes' if t.get('teams_imported') else 'No'}    ·    Stream keys imported: {'Yes' if t.get('keys_imported') else 'No'}",'muted'))
        self.cv.addStretch()
    def import_keys(self):
        t=self.t()
        if not t['teams']:QMessageBox.warning(self,'Import teams first','Import the tournament JSON before stream keys.');return
        path,_=QFileDialog.getOpenFileName(self,'Import Cloudflare keys','','Text files (*.txt);;All files (*)')
        if not path:return
        try:
            keys=parse_keys(Path(path).read_text(encoding='utf-8-sig'))
            players=[p for team in t['teams'] for p in team['members']]
            if len(keys)<len(players):raise ValueError(f'Only {len(keys)} keys for {len(players)} players')
            if any(p.get('sent') for p in players) and QMessageBox.question(self,'Previously sent DMs','This will reset sent statuses and replace assigned keys. Continue?')!=QMessageBox.StandardButton.Yes:return
            for p,key in zip(players,keys):p['key']=key;p['sent']=False
            t['spares']=keys[len(players):];t['keys_imported']=True
            if not self.save():return
            self.render()
            QMessageBox.information(self,'Keys imported',f'Assigned {len(players)} keys; {len(t["spares"])} spare keys.')
        except Exception as e:QMessageBox.critical(self,'Import failed',str(e))
    def streams(self,t):
        players=[(team,p) for team in t['teams'] for p in team['members']]
        sent=sum(bool(p.get('sent')) for _,p in players)
        self.cv.addWidget(label(f'Stream distribution     {sent} / {len(players)} DMs sent     ·     {len(t.get("spares",[]))} spares','subheading'))
        self.cv.addWidget(label('Select multiple players with Ctrl/Shift or use Select all. Copying a DM does not mark it sent.','muted'))
        table=self.table(['Team','Player','Arena ID','Discord ID','Key','DM status'])
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.fill_table(table,[[team['name']+(' [SUB]' if team.get('sub') else ''),self.display_player_name(p),p['arena_id'],p.get('discord_id',''),'Assigned' if p.get('key') else 'Missing','Sent' if p.get('sent') else 'Pending'] for team,p in players])
        self.cv.addWidget(table,1)
        # Keep the bulk-action toolbar visually separate from the player table.
        self.cv.addSpacing(12)
        actions=QFrame();actions.setObjectName('surface');r=layout_col(actions,8,(12,10,12,10))
        def selected_players():
            return [players[i][1] for i in sorted({index.row() for index in table.selectedIndexes()}) if 0<=i<len(players)]
        def single_player():
            selected=selected_players()
            if len(selected)!=1:
                QMessageBox.information(self,'Select one player','Select exactly one player for this action.')
                return None
            return selected[0]
        def copy_dm():
            p=single_player()
            if not p:return
            if not p.get('key'):
                QMessageBox.warning(self,'Missing key','Import stream keys first.');return
            k=p['key']
            QApplication.clipboard().setText(f"Hi {self.display_player_name(p)},\n\nYour Arena tournament stream details:\n\nStream / publish URL: {k['publish']}\nPreview URL: {k['preview']}\n\nPlease keep your stream key private.")
            QMessageBox.information(self,'Copied','Private DM copied. Confirm sent only after sending it.')
        def bulk_sent(mark):
            selected=selected_players()
            if not selected:
                QMessageBox.information(self,'Select players','Select at least one player first.');return
            eligible=[p for p in selected if p.get('key') and bool(p.get('sent'))!=mark]
            missing=sum(not p.get('key') for p in selected)
            if not eligible:
                QMessageBox.information(self,'Nothing to change',f'No eligible player statuses to update. {missing} selected players have no assigned key.');return
            action='Mark as sent' if mark else 'Mark as not sent'
            message=(f'{action} for {len(eligible)} selected player(s)?\n\n'
                     + ('Only confirm this after actually sending their individual Discord DMs.\n' if mark else 'This will reset their sent confirmations.\n')
                     + (f'\n{missing} player(s) without assigned keys will be skipped.' if missing else ''))
            if QMessageBox.question(self,'Confirm bulk DM status',message,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
            previous=[(p,bool(p.get('sent'))) for p in eligible]
            for p in eligible:p['sent']=mark
            if not self.save():
                for p,old in previous:p['sent']=old
                return
            self.render()
        def discord_id():
            p=single_player()
            if not p:return
            value,ok=QInputDialog.getText(self,'Discord mapping',f'Discord user ID for {self.display_player_name(p)}:',text=p.get('discord_id',''))
            if not ok:return
            uid=str(p['arena_id']);p['discord_id']=value.strip();self.data['players'].setdefault(uid,{'name':p['name'],'notes':''})['discord_id']=value.strip()
            if value.strip():self.data['discord_mappings'][uid]=value.strip()
            else:self.data['discord_mappings'].pop(uid,None)
            self.save();self.render()
        def commands(separator):
            cmds=[f"set_stream_key {p['arena_id']} {p['key']['play']}" for _,p in players if p.get('key')]
            if not cmds:QMessageBox.warning(self,'No keys','Import keys first.');return
            QApplication.clipboard().setText(separator.join(cmds))
            QMessageBox.information(self,'Copied',f'{len(cmds)} admin-only commands copied.')
        for heading,entries in [
            ('SELECTION',[('Select all',table.selectAll),('Clear selection',table.clearSelection)]),
            ('PLAYER ACTIONS',[('Mark selected as sent',lambda:bulk_sent(True)),
                               ('Mark selected as not sent',lambda:bulk_sent(False)),
                               ('Edit Discord ID',discord_id)]),
            ('COPY & EXPORT',[('Copy player DM',copy_dm),
                             ('Copy commands (comma-separated)',lambda:commands(', ')),
                             ('Copy commands (one per line)',lambda:commands('\n'))])
        ]:
            group=QWidget();gr=layout_row(group,8)
            title=label(heading,'muted');title.setMinimumWidth(110);gr.addWidget(title)
            for text,callback in entries:gr.addWidget(button(text,callback))
            gr.addStretch();r.addWidget(group)
        self.cv.addWidget(actions)
    def set_bracket(self):
        t=self.t();value,ok=QInputDialog.getText(self,'Bracket HQ link','Tournament bracket URL:',text=t.get('bracket_url',''))
        if not ok:return
        if value.strip() and not value.strip().startswith(('https://','http://')):QMessageBox.warning(self,'Invalid URL','Use a valid http(s) link.');return
        t['bracket_url']=value.strip();self.save();self.render()
    def results_page(self,t):
        self.cv.addWidget(label('Podium & rewards','subheading'))
        self.cv.addWidget(label('Enter the TOTAL team prize for each placement. Both $ and Gems are supported.','muted'))
        self.cv.addSpacing(14)
        saved=t.get('results',{})
        if not isinstance(saved,dict):
            if saved:
                self.cv.addWidget(label('Legacy results: '+str(saved)[:250],'muted'))
            saved={}
        existing=saved.get('placements',{})
        teams=[(team.get('team_id',team['name']),team['name']) for team in t.get('teams',[]) if not team.get('sub')]
        if not teams:self.cv.addWidget(label('Import tournament teams to enable result entry.','muted'))
        selectors=[]
        for rank,heading in [('1','1st Place'),('2','2nd Place'),('3','3rd Place')]:
            card=QFrame();card.setObjectName('surface');v=layout_col(card,12,(18,16,18,16))
            v.addWidget(label(heading,'subheading'))
            row=QWidget();r=layout_row(row,12)
            team=QComboBox();team.addItem('Select team…','')
            for tid,name in teams:team.addItem(name,tid)
            entry=existing.get(rank,{})
            oldteam=entry.get('team_id',entry.get('team',''))
            ix=team.findData(oldteam)
            if ix<0:ix=team.findText(oldteam)
            if ix>=0:team.setCurrentIndex(ix)
            dollars=QSpinBox();dollars.setRange(0,1000000000);dollars.setPrefix('$  ');dollars.setValue(int(entry.get('money',entry.get('amount',0) if entry.get('currency')=='$' else 0)))
            gems=QSpinBox();gems.setRange(0,1000000000);gems.setSuffix('  Gems');gems.setValue(int(entry.get('gems',entry.get('amount',0) if entry.get('currency')=='Gems' else 0)))
            r.addWidget(team,3);r.addWidget(dollars,2);r.addWidget(gems,2)
            v.addWidget(row);self.cv.addWidget(card);self.cv.addSpacing(10)
            selectors.append((rank,team,dollars,gems))
        def save_results():
            placements={};selected=[]
            for rank,team,dollars,gems in selectors:
                tid=team.currentData()
                if tid:
                    selected.append(tid)
                    placements[rank]={'team_id':tid,'team':team.currentText(),'money':dollars.value(),'gems':gems.value()}
            if len(selected)!=len(set(selected)):
                QMessageBox.warning(self,'Duplicate placement','Each team can occupy only one placement.');return
            if not placements:
                QMessageBox.warning(self,'No placements','Select at least one team.');return
            t['results']={'placements':placements}
            if self.save():self.render();QMessageBox.information(self,'Saved','Podium and rewards saved.')
        footer=QWidget();fr=layout_row(footer,8);fr.addStretch();fr.addWidget(button('SAVE RESULTS',save_results,True));self.cv.addWidget(footer);self.cv.addStretch()

    def bracket_page(self,t):
        self.cv.addWidget(label('Bracket HQ','subheading'))
        self.cv.addWidget(label('View your live bracket without leaving the tournament manager.','muted'))
        row=QWidget();r=layout_row(row)
        r.addWidget(button('Set bracket link',self.set_bracket))
        url=t.get('bracket_url','')
        if url:r.addWidget(button('Open in browser',lambda:webbrowser.open(url)))
        r.addStretch();self.cv.addWidget(row)
        if not url:
            self.cv.addWidget(label('Add your Bracket HQ URL to view the bracket here.','muted'));self.cv.addStretch();return
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView
            view=QWebEngineView();view.setUrl(QUrl(url));self.cv.addWidget(view,1)
            self.cv.addWidget(button('Refresh bracket',view.reload))
        except ImportError:
            self.cv.addWidget(label('Qt WebEngine is unavailable. Use Open in browser instead.','muted'));self.cv.addStretch()

    def update_found(self,info):
        from packaging.version import Version
        try:
            newer=Version(str(info['version']))>Version(VERSION)
        except Exception:
            return
        if newer:
            self.update_info=info
            self.update_button.setText('Update available · '+str(info['version']))
            self.update_button.setObjectName('primary')
            self.update_button.setStyleSheet('background:#83e38b;color:#102016;')
            self.update_button.clicked.disconnect()
            self.update_button.clicked.connect(self.install_update)
            if self.section=='Settings':self.render()

    def check_updates_background(self):
        def worker():
            try:
                from updater import get_latest
                info=get_latest()
                self.update_signals.found.emit(info)
            except Exception:
                pass
        threading.Thread(target=worker,daemon=True).start()

    def install_update(self):
        if self.update_busy:
            return
        info=self.update_info
        if not info:
            QMessageBox.information(self,'No update','No update is currently available.');return
        if not getattr(sys,'frozen',False):
            QMessageBox.warning(self,'Packaged application required','One-click updates are supported in the installed Windows EXE. Source-mode users should update via GitHub.');return
        if QMessageBox.question(self,'Install update',f"Install version {info['version']}?\n\n{info.get('notes','')[:1500]}\n\nThe application will restart. Your database is stored separately and will be preserved.")!=QMessageBox.StandardButton.Yes:return

        self.update_busy=True
        dialog=QDialog(self)
        dialog.setWindowTitle('Updating Tournament Manager')
        dialog.setModal(False)
        dialog.setMinimumWidth(440)
        dialog.setWindowFlag(Qt.WindowType.WindowCloseButtonHint,False)
        v=layout_col(dialog,14,(24,24,24,24))
        title=label('Installing version '+str(info['version']),'subheading')
        v.addWidget(title)
        self.update_status_label=label('Preparing download…','muted')
        v.addWidget(self.update_status_label)
        self.update_progress_bar=QProgressBar()
        self.update_progress_bar.setRange(0,0)
        v.addWidget(self.update_progress_bar)
        self.update_detail_label=label('Please keep the application open until it restarts.','muted')
        v.addWidget(self.update_detail_label)
        self.update_dialog=dialog
        dialog.show()

        def worker():
            try:
                from updater import stage_update
                def progress(stage, received, total):
                    self.update_signals.progress.emit(stage,int(received),int(total or 0))
                package=stage_update(info,BASE,progress=progress)
                self.update_signals.staged.emit(str(package))
            except Exception as exc:
                self.update_signals.failed.emit(str(exc))
        threading.Thread(target=worker,daemon=True).start()

    def update_progress(self,stage,received,total):
        if not self.update_busy or self.update_dialog is None:
            return
        self.update_status_label.setText(stage+'…')
        if stage=='Downloading' and total>0:
            self.update_progress_bar.setRange(0,1000)
            self.update_progress_bar.setValue(min(1000,int(received*1000/total)))
            self.update_detail_label.setText(f'{received/1048576:.1f} MB / {total/1048576:.1f} MB  ·  {received*100//total}%')
        else:
            self.update_progress_bar.setRange(0,0)
            if stage=='Verifying':
                self.update_detail_label.setText('Checking the download and its integrity…')
            elif stage=='Ready':
                self.update_detail_label.setText('Preparing to restart…')

    def update_staged(self,package):
        if not self.update_busy:
            return
        self.update_status_label.setText('Installing and restarting…')
        self.update_detail_label.setText('The application will close and reopen automatically.')
        try:
            app_dir=Path(sys.executable).resolve().parent
            helper=app_dir/'ArenaUpdater.exe'
            if not helper.exists():
                raise FileNotFoundError('ArenaUpdater.exe is missing from the installation')
            import tempfile
            temp_helper=Path(tempfile.mkdtemp(prefix='arena-updater-'))/'ArenaUpdater.exe'
            shutil.copy2(helper,temp_helper)
            subprocess.Popen([str(temp_helper),'--apply',str(package),str(app_dir),str(os.getpid())],
                             cwd=str(temp_helper.parent),
                             creationflags=getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0))
            QApplication.instance().quit()
        except Exception as exc:
            self.update_failed(str(exc))

    def update_failed(self,message):
        self.update_busy=False
        if self.update_dialog is not None:
            self.update_dialog.close()
            self.update_dialog=None
        QMessageBox.critical(self,'Update failed',message+'\n\nYour current installation has not been replaced.')

    def settings_page(self):
        self.header('SETTINGS','APPLICATION / CONFIGURATION')
        def section(title,description,action,callback,primary=False):
            panel=QFrame();panel.setObjectName('surface')
            col=layout_col(panel,12,(18,16,18,16))
            col.addWidget(label(title,'subheading'))
            col.addWidget(label(description,'muted'))
            actions=QWidget();row=layout_row(actions,8)
            row.addWidget(button(action,callback,primary));row.addStretch()
            col.addWidget(actions);self.cv.addWidget(panel)
        section('SOFTWARE UPDATES',f'Installed version: {VERSION}  ·  Updates from GitHub Releases',
                'CHECK FOR UPDATES',self.check_updates_background)
        if self.update_info:
            self.cv.addWidget(button('INSTALL UPDATE '+str(self.update_info['version']),self.install_update,True))
        self.cv.addSpacing(10)
        section('CHECKLIST NOTIFICATIONS','Windows and Discord reminders before deadlines, plus overdue alerts.',
                'CONFIGURE NOTIFICATIONS',self.edit_notification_settings)
        self.cv.addSpacing(10)
        section('BACKUPS & RECOVERY','Rolling backups retain 25 saves. Protected and manual snapshots are preserved.',
                'OPEN BACKUP MANAGER',self.backup_manager)
        self.cv.addSpacing(16)
        info=QFrame();info.setObjectName('surface');ic=layout_col(info,9,(18,16,18,16))
        ic.addWidget(label('DATABASE INFORMATION','subheading'))
        for title,value in [('TOURNAMENTS',len(self.data.get('tournaments',[]))),
                            ('REGISTERED TEAMS',len(self.data.get('teams_db',{}))),
                            ('KNOWN PLAYERS',len(self.player_records()))]:
            line=QWidget();lr=layout_row(line,8);lr.addWidget(label(title,'muted'),1);lr.addWidget(label(str(value)));ic.addWidget(line)
        ic.addWidget(label('DATA FOLDER: '+str(BASE),'muted'))
        self.cv.addWidget(info);self.cv.addStretch()

    def protected_backup(self,reason):
        try:
            if DATA.exists():return snapshot(DATA,BACKUPS,'protected',reason)
        except Exception as e:
            QMessageBox.critical(self,'Safety backup failed',str(e))
            return False
        return None

    def backup_manager(self):
        dlg=QDialog(self);dlg.setWindowTitle('Backup Manager');dlg.resize(790,500)
        v=layout_col(dlg,12,(20,20,20,20))
        v.addWidget(label('Backup Manager','subheading'))
        v.addWidget(label('Protected and manual backups are retained until you remove them outside the app.','muted'))
        table=QTableWidget(0,3);table.setHorizontalHeaderLabels(['Backup','Integrity','Contents'])
        table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch)
        v.addWidget(table,1)
        paths=[]
        def refresh():
            paths.clear();entries=list_snapshots(BACKUPS);table.setRowCount(len(entries))
            for i,(path,status,counts) in enumerate(entries):
                paths.append(path)
                for j,value in enumerate((path.name,status,counts)):
                    item=QTableWidgetItem(value);item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable);table.setItem(i,j,item)
        def selected():
            row=table.currentRow()
            if row<0 or row>=len(paths):
                QMessageBox.information(dlg,'Select backup','Select a backup first.');return None
            return paths[row]
        def create():
            try:
                snapshot(DATA,BACKUPS,'manual','user_requested');refresh()
            except Exception as e:QMessageBox.critical(dlg,'Backup failed',str(e))
        def export():
            source=selected()
            if source is None:return
            try:read_validated(source)
            except Exception as e:QMessageBox.critical(dlg,'Invalid backup',str(e));return
            dest,_=QFileDialog.getSaveFileName(dlg,'Export backup',source.name,'JSON (*.json)')
            if dest:
                try:shutil.copy2(source,dest)
                except Exception as e:QMessageBox.critical(dlg,'Export failed',str(e))
        def recover():
            source=selected()
            if source is None:return
            try:read_validated(source)
            except Exception as e:QMessageBox.critical(dlg,'Invalid backup',str(e));return
            confirm=QMessageBox.question(dlg,'Restore database',f'Restore {source.name}?\n\nThis replaces the current database. A protected pre-restore snapshot will be created first.')
            if confirm!=QMessageBox.StandardButton.Yes:return
            try:
                safety=restore_backup(source,DATA,BACKUPS)
                self.data=load();self.active=None;self.render();refresh()
                QMessageBox.information(dlg,'Restore complete','Database restored successfully.'+(f'\nSafety snapshot: {safety.name}' if safety else ''))
            except Exception as e:QMessageBox.critical(dlg,'Restore failed',str(e))
        row=QWidget();r=layout_row(row,8)
        for name,callback in [('Create manual backup',create),('Export selected',export),('Restore selected',recover),('Refresh',refresh)]:r.addWidget(button(name,callback))
        v.addWidget(row);refresh();dlg.exec()

    def finish(self):
        t=self.t();tasks=[(k,n) for k,n,_ in TASKS if t['qualifiers'] or k not in ('qopen','qclose')]
        remaining=[name for key,name in tasks if not self.task_done(t,key)]
        if remaining and QMessageBox.question(self,'Incomplete tasks',f'{len(remaining)} tasks are incomplete. Finish anyway?')!=QMessageBox.StandardButton.Yes:return
        t['status']='Finished';self.save();self.render()

if __name__=='__main__':
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('TournamentManager.Desktop')
        except (AttributeError, OSError):
            pass
    app=QApplication(sys.argv);app.setStyle('Fusion')
    if ICON_ASSET.exists():app.setWindowIcon(QIcon(str(ICON_ASSET)))
    elif ASSET.exists():app.setWindowIcon(QIcon(str(ASSET)))
    font_path=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))/'assets'/'Rajdhani-SemiBold.ttf'
    if font_path.exists():
        font_id=QFontDatabase.addApplicationFont(str(font_path))
        families=QFontDatabase.applicationFontFamilies(font_id) if font_id>=0 else []
        if families:
            app.setFont(QFont(families[0],11))
    app.setStyleSheet(STYLE)
    try:win=Window()
    except Exception as e:
        QMessageBox.critical(None,'Cannot start Arena Tournament Manager',str(e));sys.exit(1)
    win.show();sys.exit(app.exec())
