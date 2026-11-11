"""Arena Map Veto: seven-map pool, admin-operated picks, side selection and export."""
import copy
import datetime
import secrets
import uuid
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QGuiApplication, QPainter, QColor, QFont, QLinearGradient
from PySide6.QtWidgets import (
    QWidget,QFrame,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QComboBox,QLineEdit,
    QFileDialog,QMessageBox,QScrollArea,QGridLayout,QInputDialog,QDialog,QDialogButtonBox,QTreeWidget,QTreeWidgetItem,QHeaderView,QGraphicsBlurEffect
)

SEQUENCES = {
    'BO1': ('ban','ban','ban','ban','ban','ban'),
    'BO3': ('ban','ban','pick','pick','ban','ban'),
    'BO5': ('ban','ban','pick','pick','pick','pick'),
}
RED = '#ee6767'
BLUE = '#6cb7ff'
GREEN = '#58dc00'


def new_veto(team_a, team_b, fmt, pool, tournament_id=None):
    if fmt not in SEQUENCES:
        raise ValueError('Unsupported format')
    if len(pool) != 7 or len({m['id'] for m in pool}) != 7:
        raise ValueError('Exactly seven different maps are required')
    if not team_a.strip() or not team_b.strip() or team_a.strip().casefold() == team_b.strip().casefold():
        raise ValueError('Enter two different team names')
    return {
        'id': str(uuid.uuid4()), 'created': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'teams': [team_a.strip(), team_b.strip()], 'format': fmt,
        'first': secrets.randbelow(2), 'pool': copy.deepcopy(pool),
        'tournament_id': tournament_id, 'actions': [], 'sides': {}, 'completed': False, 'event_log': []
    }


def remaining(veto):
    used = {a['map_id'] for a in veto['actions']}
    return [m for m in veto['pool'] if m['id'] not in used]


def sequence(veto):
    return SEQUENCES[veto['format']]


def next_action(veto):
    idx = len(veto['actions'])
    if idx >= len(sequence(veto)):
        return None
    return {'kind': sequence(veto)[idx], 'team': (veto['first'] + idx) % 2, 'step': idx + 1}


def selected_maps(veto):
    picks = [a for a in veto['actions'] if a['kind'] == 'pick']
    if next_action(veto) is None:
        leftover = remaining(veto)
        if len(leftover) == 1:
            last_ban = next((a for a in reversed(veto['actions']) if a['kind'] == 'ban'), None)
            # The captain who did not make the final ban chooses the decider side.
            decider_owner = 1 - last_ban['team'] if last_ban else 1 - veto['first']
            picks.append({'kind': 'decider', 'map_id': leftover[0]['id'], 'team': None, 'side_owner': decider_owner})
    return picks


def side_owner(veto, action):
    if action['kind'] == 'decider':
        return action['side_owner']
    return 1 - action['team']


def pending_side(veto):
    for action in selected_maps(veto):
        if action['map_id'] not in veto.get('sides', {}):
            return action
    return None


def apply_map(veto, map_id):
    step = next_action(veto)
    if step is None:
        raise ValueError('All map actions are complete')
    if map_id not in {m['id'] for m in remaining(veto)}:
        raise ValueError('Map is not available')
    veto.setdefault('event_log',[]).append({'kind':'map','map_id':map_id})
    veto['actions'].append({'kind': step['kind'], 'team': step['team'], 'map_id': map_id})
    veto['completed'] = False


def apply_side(veto, map_id, side):
    if side not in ('RED','BLUE'):
        raise ValueError('Choose RED or BLUE')
    if map_id not in {a['map_id'] for a in selected_maps(veto)}:
        raise ValueError('This map has not been picked')
    veto.setdefault('event_log',[]).append({'kind':'side','map_id':map_id,'previous':veto.get('sides',{}).get(map_id)})
    veto.setdefault('sides', {})[map_id] = side
    veto['completed'] = next_action(veto) is None and pending_side(veto) is None


def undo(veto):
    log=veto.get('event_log')
    if log:
        event=log.pop()
        if event['kind']=='side':
            previous=event.get('previous')
            if previous is None:veto.setdefault('sides',{}).pop(event['map_id'],None)
            else:veto.setdefault('sides',{})[event['map_id']]=previous
        else:
            if not veto['actions'] or veto['actions'][-1]['map_id']!=event['map_id']:
                log.append(event);return False
            veto['actions'].pop()
            valid={a['map_id'] for a in selected_maps(veto)}
            veto['sides']={k:v for k,v in veto.get('sides',{}).items() if k in valid}
        veto['completed']=next_action(veto) is None and pending_side(veto) is None
        return True
    if veto['actions']:
        action=veto['actions'].pop()
        veto.setdefault('sides',{}).pop(action['map_id'],None)
        valid={a['map_id'] for a in selected_maps(veto)}
        veto['sides']={k:v for k,v in veto['sides'].items() if k in valid}
        veto['completed']=False
        return True
    return False


def name_of(veto, map_id):
    return next((m['name'] for m in veto['pool'] if m['id'] == map_id), 'Unknown map')


def layout_col(parent, gap=10):
    l=QVBoxLayout(parent);l.setContentsMargins(0,0,0,0);l.setSpacing(gap);return l


def label(text, muted=False):
    w=QLabel(str(text));w.setWordWrap(True)
    if muted:w.setObjectName('muted')
    return w


def section_heading(title):
    heading=label(title)
    heading.setStyleSheet('font-size:19px;font-weight:700;color:#f4f4f6;')
    return heading


def btn(text, callback, primary=False):
    w=QPushButton(text)
    if primary:w.setObjectName('primary')
    w.clicked.connect(callback)
    return w


def panel():
    w=QFrame();w.setObjectName('surface');v=QVBoxLayout(w);v.setContentsMargins(17,16,17,16);v.setSpacing(12)
    return w,v


def image_label(path, width=330, height=185):
    w=QLabel();w.setAlignment(Qt.AlignmentFlag.AlignCenter);w.setMinimumHeight(height)
    w.setStyleSheet('background:#28282b;border:1px solid #47474a;color:#9b9ba3;')
    if path and Path(path).is_file():
        pix=QPixmap(path)
        if not pix.isNull():
            w.setPixmap(pix.scaled(width,height,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
            return w
    w.setText('MAP IMAGE NOT UPLOADED')
    return w


class MapStatusCard(QFrame):
    """Draw a subtle coloured glow inward from every edge for selected maps."""
    def __init__(self,status,parent=None):
        super().__init__(parent)
        self.status=status
        self.setObjectName('surface')

    def paintEvent(self,event):
        super().paintEvent(event)
        if self.status not in ('BANNED','PICKED','DECIDER'):
            return
        colour=QColor('#ff4556' if self.status=='BANNED' else '#00d78a')
        painter=QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width,height=self.width(),self.height()
        depth=min(38,width//4,height//4)
        if depth<=0:return
        for x1,y1,x2,y2,area in (
            (0,0,depth,0,(0,0,depth,height)),
            (width,0,width-depth,0,(width-depth,0,depth,height)),
            (0,0,0,depth,(0,0,width,depth)),
            (0,height,0,height-depth,(0,height-depth,width,depth)),
        ):
            gradient=QLinearGradient(x1,y1,x2,y2)
            outer=QColor(colour);outer.setAlpha(105)
            inner=QColor(colour);inner.setAlpha(0)
            gradient.setColorAt(0,outer);gradient.setColorAt(1,inner)
            painter.fillRect(*area,gradient)
        painter.end()


class VetoPage:
    def __init__(self, window):
        self.w=window
        self.data=window.data
        self.data.setdefault('map_library',[])
        self.data.setdefault('active_map_ids',[])
        self.data.setdefault('map_vetoes',[])
        self.current=None

    def render(self):
        self.w.header('MAP VETO','SEVEN-MAP ROTATION / ADMIN CONTROLLED BANS & SIDE PICKS')
        tabs=QWidget();row=QHBoxLayout(tabs);row.setContentsMargins(0,0,0,0)
        for name,callback in [('NEW VETO',lambda checked=False:self.new_page()),('MAP POOL',self.pool_page),('VETO HISTORY',self.history_page)]:
            row.addWidget(btn(name,callback))
        row.addStretch();self.w.cv.addWidget(tabs);self.w.cv.addSpacing(13)
        self.history_page_content()

    def _clear_body(self):
        self.w.clear()
        self.w.header('MAP VETO','SEVEN-MAP ROTATION / ADMIN CONTROLLED BANS & SIDE PICKS')
        tabs=QWidget();row=QHBoxLayout(tabs);row.setContentsMargins(0,0,0,0)
        for name,callback in [('NEW VETO',self.new_page),('MAP POOL',self.pool_page),('VETO HISTORY',self.history_page)]:
            row.addWidget(btn(name,callback))
        row.addStretch();self.w.cv.addWidget(tabs);self.w.cv.addSpacing(13)

    def save(self):
        return self.w.save()

    def _assets(self):
        from pathlib import Path
        directory=Path(getattr(self.w,'assets_directory',Path.home()/'ArenaTournamentManager'/'map_images'))
        directory.mkdir(parents=True,exist_ok=True)
        return directory

    def _import_image(self):
        import shutil
        path,_=QFileDialog.getOpenFileName(self.w,'Choose map image','','Images (*.png *.jpg *.jpeg *.webp)')
        if not path:return None
        dest=self._assets()/(str(uuid.uuid4())+Path(path).suffix.lower())
        shutil.copy2(path,dest)
        return str(dest)

    def pool_page(self):
        self._clear_body()
        library=self.data['map_library'];active=self.data['active_map_ids']
        p,v=panel();v.addWidget(label('ACTIVE MAP ROTATION — '+str(len(active))+'/7'))
        v.addWidget(label('Only seven active maps can be used for new vetoes. Previous vetoes retain their original map pool.',True))
        if not library:v.addWidget(label('No maps added yet. Add your FiveM maps below.',True))
        for m in library:
            line=QWidget();r=QHBoxLayout(line);r.setContentsMargins(0,0,0,0)
            r.addWidget(label(('●  ' if m['id'] in active else '○  ')+m['name']),1)
            def toggle(checked=False,mid=m['id']):
                if mid in active:active.remove(mid)
                elif len(active)<7:active.append(mid)
                else:
                    QMessageBox.warning(self.w,'Seven-map limit','Deactivate a map before activating another.');return
                self.save();self.pool_page()
            r.addWidget(btn('DEACTIVATE' if m['id'] in active else 'ACTIVATE',toggle))
            def rename(checked=False,rec=m):
                value,ok=QInputDialog.getText(self.w,'Rename map','Map name:',text=rec['name'])
                if ok and value.strip():
                    rec['name']=value.strip();self.save();self.pool_page()
            r.addWidget(btn('RENAME',rename))
            def upload(which,rec):
                path=self._import_image()
                if path:rec[which]=path;self.save();self.pool_page()
            r.addWidget(btn('MAP IMAGE',lambda checked=False,rec=m:upload('preview',rec)))
            r.addWidget(btn('SPAWNS',lambda checked=False,rec=m:upload('spawns',rec)))
            v.addWidget(line)
        self.w.cv.addWidget(p)
        add=QWidget();r=QHBoxLayout(add);r.setContentsMargins(0,0,0,0)
        name=QLineEdit();name.setPlaceholderText('NEW MAP NAME');r.addWidget(name,1)
        def add_map():
            value=name.text().strip()
            if not value:return
            if any(m['name'].casefold()==value.casefold() for m in library):
                QMessageBox.warning(self.w,'Duplicate map','That map already exists.');return
            rec={'id':str(uuid.uuid4()),'name':value,'preview':'','spawns':''}
            library.append(rec)
            if len(active)<7:active.append(rec['id'])
            self.save();self.pool_page()
        r.addWidget(btn('+ ADD MAP',add_map,True))
        self.w.cv.addWidget(add)
        self.w.cv.addWidget(label('Map and combined RED/BLUE spawn images can be uploaded at any time.',True))
        self.w.cv.addStretch()

    def new_page(self,preselected_tournament_id=None):
        self._clear_body()
        p,v=panel();v.addWidget(label('CREATE MAP VETO'))
        if len(self.data['active_map_ids'])!=7:
            v.addWidget(label('Set exactly seven active maps in MAP POOL before starting a veto.',True))
            v.addWidget(btn('OPEN MAP POOL',self.pool_page))
            self.w.cv.addWidget(p);return
        a=QComboBox();a.setEditable(True);a.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        b=QComboBox();b.setEditable(True);b.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        v.addWidget(label('TEAM A'));v.addWidget(a)
        v.addWidget(label('TEAM B'));v.addWidget(b)
        fmt=QComboBox();fmt.addItems(['BO1','BO3','BO5']);v.addWidget(label('MATCH FORMAT'));v.addWidget(fmt)
        tournament=QComboBox()
        tournament.setMinimumWidth(360)
        tournament.addItem('No tournament — standalone veto',None)
        # The tournament database is shared with the main Tournaments page.
        # Distinguish official (locked-roster) events from casual ones explicitly.
        tournaments=list(reversed(self.data.get('tournaments',[])))
        official=[t for t in tournaments if t.get('locked',True)]
        casual=[t for t in tournaments if not t.get('locked',True)]
        for title,events in (('OFFICIAL TOURNAMENTS',official),('OTHER TOURNAMENTS',casual)):
            if not events:continue
            tournament.insertSeparator(tournament.count())
            for t in events:
                tournament.addItem(title.split(' ')[0]+'  ·  '+str(t.get('name','Unnamed tournament')),t['id'])
        if not getattr(self.w,'standalone',False):
            v.addWidget(label('TOURNAMENT (OPTIONAL)'))
            v.addWidget(tournament)
            v.addWidget(label('Choose tournament teams or enter names manually.',True))
        def update_teams():
            tid=tournament.currentData()
            selected=next((t for t in tournaments if str(t['id'])==str(tid)),None)
            names=list(dict.fromkeys(str(team.get('name','')).strip() for team in selected.get('teams',[]) if team.get('name'))) if selected else []
            for combo in (a,b):
                previous=combo.currentText()
                combo.blockSignals(True)
                combo.clear()
                combo.addItems(names)
                combo.setCurrentText(previous if previous in names else '')
                combo.blockSignals(False)
        tournament.currentIndexChanged.connect(lambda *_:update_teams())
        if preselected_tournament_id is not None:
            idx=tournament.findData(preselected_tournament_id)
            if idx>=0:tournament.setCurrentIndex(idx)
        update_teams()
        def start():
            ids=set(self.data['active_map_ids'])
            pool=[copy.deepcopy(m) for m in self.data['map_library'] if m['id'] in ids]
            try:record=new_veto(a.currentText(),b.currentText(),fmt.currentText(),pool,tournament.currentData())
            except ValueError as exc:
                QMessageBox.warning(self.w,'Cannot create veto',str(exc));return
            self.data['map_vetoes'].append(record)
            if not self.save():
                self.data['map_vetoes'].remove(record);return
            self.current=record['id'];self._coin_flip(record)
        v.addWidget(btn('RANDOMISE FIRST BAN & START',start,True))
        self.w.cv.addWidget(p);self.w.cv.addStretch()

    def _coin_flip(self,record):
        dialog=QDialog(self.w)
        dialog.setWindowTitle('First ban draw')
        dialog.setModal(True)
        dialog.setMinimumSize(530,300)
        dialog.setStyleSheet('QDialog{background:#181b1d;}')
        layout=QVBoxLayout(dialog)
        layout.setContentsMargins(28,25,28,25)
        layout.setSpacing(16)
        eyebrow=label('RANDOM FIRST BAN DRAW')
        eyebrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        eyebrow.setStyleSheet('font-size:15px;font-weight:700;color:#a9b5ae;letter-spacing:2px;')
        layout.addWidget(eyebrow)
        result=label('VS')
        result.setAlignment(Qt.AlignmentFlag.AlignCenter)
        result.setStyleSheet('font-size:38px;font-weight:900;color:#f5f7f5;padding:24px;'
                             'background:#242c29;border:2px solid #4a6656;border-radius:12px;')
        layout.addWidget(result,1)
        # A subtle blur during the rapid name changes suggests movement;
        # it eases away as the draw slows, leaving the winner crisp.
        motion_blur=QGraphicsBlurEffect(result)
        motion_blur.setBlurHints(QGraphicsBlurEffect.BlurHint.AnimationHint)
        motion_blur.setBlurRadius(0)
        result.setGraphicsEffect(motion_blur)
        caption=label('SELECTING WHICH TEAM BANS FIRST')
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        caption.setStyleSheet('font-size:16px;font-weight:700;color:#aab7ad;')
        layout.addWidget(caption)
        continue_button=btn('CONTINUE TO MAP VETO',dialog.accept,True)
        continue_button.setMinimumHeight(44)
        continue_button.setVisible(False)
        layout.addWidget(continue_button)
        frames={'n':0}
        # Deliberately slow down the reveal instead of rapidly flickering text.
        intervals=[100,110,120,135,155,180,215,260,320,390,480,600]
        def animate():
            index=frames['n']
            if index>=len(intervals):
                motion_blur.setBlurRadius(0)
                result.setText(record['teams'][record['first']].upper())
                result.setStyleSheet('font-size:40px;font-weight:900;color:#a8ff86;padding:24px;'
                                     'background:#1e3529;border:2px solid #58dc00;border-radius:12px;')
                eyebrow.setText('FIRST BAN WINNER')
                caption.setText('THIS TEAM WILL BAN THE FIRST MAP')
                QTimer.singleShot(3000,lambda:continue_button.setVisible(True))
                return
            motion_blur.setBlurRadius(max(0,4.5-index*0.42))
            result.setText(record['teams'][index%2].upper())
            frames['n']+=1
            QTimer.singleShot(intervals[index],animate)
        QTimer.singleShot(200,animate)
        dialog.exec()
        self.veto_page()

    def history_page(self):
        self._clear_body();self.history_page_content()

    def history_page_content(self):
        p,v=panel()
        v.addWidget(section_heading('VETO HISTORY'))
        v.addWidget(label('Browse previous staff vetoes.' if getattr(self.w,'standalone',False) else 'Browse vetoes by tournament. Unlinked matches are shown separately.',True))
        records=list(reversed(self.data['map_vetoes']))
        if not records:
            v.addWidget(label('No map vetoes recorded yet. Create your first veto to get started.',True))
            self.w.cv.addWidget(p);self.w.cv.addStretch();return
        tree=QTreeWidget()
        tree.setHeaderLabels(['MATCH','FORMAT','STATUS','ACTIONS'] if getattr(self.w,'standalone',False) else ['TOURNAMENT / MATCH','FORMAT','STATUS','ACTIONS'])
        tree.setRootIsDecorated(True)
        tree.setAlternatingRowColors(False)
        tree.setIndentation(20)
        tree.setStyleSheet('QTreeWidget{background:#323234;alternate-background-color:#323234;'
                           'color:#e8e8ec;border:1px solid #4a4a4f;}'
                           'QTreeWidget::item{background:#323234;color:#e8e8ec;min-height:38px;}'
                           'QTreeWidget::item:selected{background:#3a4b31;color:#ffffff;}'
                           'QHeaderView::section{background:#29292b;color:#e8e8ec;'
                           'border:0;border-bottom:1px solid #4a4a4f;padding:8px;}')
        tree.header().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        tree.header().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents)
        tree.header().setSectionResizeMode(2,QHeaderView.ResizeMode.ResizeToContents)
        tree.header().setSectionResizeMode(3,QHeaderView.ResizeMode.ResizeToContents)
        groups={}
        tournaments={str(t['id']):t for t in self.data.get('tournaments',[])}
        for record in records:
            tid=record.get('tournament_id')
            t=tournaments.get(str(tid)) if tid is not None else None
            key=str(tid) if t else '__unlinked__'
            groups.setdefault(key,[]).append(record)
        for t in reversed(self.data.get('tournaments',[])):
            key=str(t['id'])
            if key not in groups:continue
            kind='OFFICIAL' if t.get('locked',True) else 'UNOFFICIAL'
            group=QTreeWidgetItem([kind+' · '+t.get('name','Unnamed tournament'),
                                   '',str(len(groups[key]))+' VETOES',''])
            tree.addTopLevelItem(group)
            for record in groups[key]:
                self._veto_history_row(tree,group,record)
            group.setExpanded(True)
        if '__unlinked__' in groups:
            group=QTreeWidgetItem(['STAFF MATCHES' if getattr(self.w,'standalone',False) else 'UNLINKED / PRACTICE MATCHES','',
                                   str(len(groups['__unlinked__']))+' VETOES',''])
            tree.addTopLevelItem(group)
            for record in groups['__unlinked__']:
                self._veto_history_row(tree,group,record)
            group.setExpanded(True)
        v.addWidget(tree)
        self.w.cv.addWidget(p);self.w.cv.addStretch()

    def _veto_history_row(self,tree,parent,record):
        state='COMPLETED' if record.get('completed') else 'IN PROGRESS'
        row=QTreeWidgetItem(['  VS  '.join(record['teams']),record['format'],state,''])
        parent.addChild(row)
        controls=QWidget()
        buttons=QHBoxLayout(controls)
        buttons.setContentsMargins(4,2,4,2)
        buttons.setSpacing(7)
        buttons.addWidget(btn('OPEN',lambda checked=False,vid=record['id']:self.open_veto(vid)))
        buttons.addWidget(btn('DELETE',lambda checked=False,vid=record['id']:self.delete_veto(vid)))
        tree.setItemWidget(row,3,controls)

    def delete_veto(self,vid):
        record=next((v for v in self.data['map_vetoes'] if v['id']==vid),None)
        if not record:return
        title='  VS  '.join(record['teams'])+' ('+record['format']+')'
        answer=QMessageBox.question(
            self.w,'Delete map veto',
            'Permanently delete this map veto?\\n\\n'+title+
            '\\n\\nAll recorded bans, picks and side selections for this veto will be removed. '
            'This cannot be undone from Veto History.',
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer!=QMessageBox.StandardButton.Yes:return
        # Protect the complete database before destructive changes.
        if self.w.protected_backup('delete_map_veto') is False:return
        previous=list(self.data['map_vetoes'])
        self.data['map_vetoes']=[v for v in previous if v['id']!=vid]
        if not self.save():
            self.data['map_vetoes']=previous
            return
        if self.current==vid:self.current=None
        self.history_page()

    def open_veto(self,vid):
        self.current=vid;self.veto_page()

    def _current(self):
        return next((v for v in self.data['map_vetoes'] if v['id']==self.current),None)

    def veto_page(self):
        record=self._current()
        if not record:self.history_page();return
        self._clear_body()
        heading,hv=panel()
        hv.addWidget(label('  VS  '.join(record['teams'])+'  |  '+record['format']))
        hv.addWidget(label('FIRST BAN: '+record['teams'][record['first']]+' (randomly selected)',True))
        tournament=QComboBox()
        tournament.addItem('UNLINKED / PRACTICE MATCH',None)
        for t in reversed(self.data.get('tournaments',[])):
            tournament.addItem(('OFFICIAL' if t.get('locked',True) else 'UNOFFICIAL')+
                               ' · '+t.get('name','Unnamed tournament'),t['id'])
        idx=tournament.findData(record.get('tournament_id'))
        if idx>=0:tournament.setCurrentIndex(idx)
        def relink(index):
            previous=record.get('tournament_id')
            record['tournament_id']=tournament.itemData(index)
            if not self.save():
                record['tournament_id']=previous
                tournament.blockSignals(True)
                tournament.setCurrentIndex(tournament.findData(previous))
                tournament.blockSignals(False)
        tournament.currentIndexChanged.connect(relink)
        if not getattr(self.w,'standalone',False):
            hv.addWidget(label('LINKED TOURNAMENT'))
            hv.addWidget(tournament)
        self.w.cv.addWidget(heading)
        content=QWidget();columns=QHBoxLayout(content);columns.setContentsMargins(0,0,0,0);columns.setSpacing(14)
        left,lv=panel();right,rv=panel()
        columns.addWidget(left,3);columns.addWidget(right,2)
        step=next_action(record)
        pending_sides=[action for action in selected_maps(record) if action['map_id'] not in record.get('sides',{})]
        if step:
            turn=QFrame()
            turn.setStyleSheet('QFrame{background:#203127;border:2px solid #58dc00;border-radius:10px;}'
                               'QLabel{border:none;background:transparent;}')
            turn_layout=QVBoxLayout(turn)
            turn_layout.setContentsMargins(18,14,18,14)
            who=label(record['teams'][step['team']].upper())
            who.setStyleSheet('font-size:30px;font-weight:900;color:#b2ff91;')
            turn_layout.addWidget(who)
            instruction=label('NEXT MAP ACTION  ·  '+step['kind'].upper()+' A MAP  ·  STEP '+str(step['step'])+'/6')
            instruction.setStyleSheet('font-size:17px;font-weight:800;color:#f2f7f2;')
            turn_layout.addWidget(instruction)
            lv.addWidget(turn)
        elif record.get('completed'):
            lv.addWidget(section_heading('VETO COMPLETE — ALL SIDES CONFIRMED'))
        else:
            lv.addWidget(section_heading('MAP VETO COMPLETE — AWAITING SIDE PICKS'))
        count=len(record['actions'])
        chosen=len(record.get('sides',{}))
        total={'BO1':1,'BO3':3,'BO5':5}[record['format']]
        lv.addWidget(label('MAP ACTIONS: '+str(count)+'/6  ·  SIDES CONFIRMED: '+
                           str(chosen)+'/'+str(total),True))
        grid=QWidget();g=QGridLayout(grid);g.setContentsMargins(0,0,0,0);g.setSpacing(9)
        actions={action['map_id']:action for action in record['actions']}
        decider=selected_maps(record)[-1] if not step else None
        for i,m in enumerate(record['pool']):
            action=actions.get(m['id'])
            status=('BANNED' if action['kind']=='ban' else 'PICKED') if action else ('DECIDER' if decider and decider['map_id']==m['id'] else 'AVAILABLE')
            card=MapStatusCard(status);cv=QVBoxLayout(card);cv.setSpacing(5)
            cv.addWidget(image_label(m.get('preview'),190,105))
            cv.addWidget(label(m['name']))
            colour={'BANNED':'#ff4556','PICKED':'#00d78a','DECIDER':'#00d78a','AVAILABLE':'#bfc1c6'}[status]
            state=label(status);state.setStyleSheet('color:'+colour+';font-weight:bold;')
            cv.addWidget(state)
            if step and status=='AVAILABLE':
                def select(checked=False,mid=m['id']):
                    chosen_map=name_of(record,mid)
                    choice=QMessageBox.question(self.w,'Confirm '+step['kind'].upper(),
                        record['teams'][step['team']]+' — '+step['kind'].upper()+' '+chosen_map+'?')
                    if choice!=QMessageBox.StandardButton.Yes:return
                    apply_map(record,mid)
                    if self.save():self.veto_page()
                cv.addWidget(btn(step['kind'].upper(),select,True))
            g.addWidget(card,i//3,i%3)
        lv.addWidget(grid)
        if step and pending_sides:
            rv.addWidget(label('BOTH ACTIONS ARE OPEN — '+record['teams'][step['team']].upper()+
                               ' CAN '+step['kind'].upper()+' THE NEXT MAP WHILE SIDE PICKS ARE DECIDED.'))
        rv.addWidget(section_heading('VETO HISTORY'))
        for i,action in enumerate(record['actions']):
            word='banned' if action['kind']=='ban' else 'picked'
            item=label(str(i+1)+'. '+record['teams'][action['team']]+' '+word+' '+name_of(record,action['map_id']))
            item.setStyleSheet('color:' + ('#ff4556' if word=='banned' else '#00d78a')+';')
            rv.addWidget(item)
        if not step:
            dec=selected_maps(record)[-1]
            item=label('7. System picked '+name_of(record,dec['map_id']))
            item.setStyleSheet('color:#00d78a;')
            rv.addWidget(item)
        if pending_sides:
            rv.addWidget(section_heading('SIDE PICKS — CAN BE DONE ALONGSIDE BANS / PICKS'))
        for side_action in pending_sides:
            owner=side_owner(record,side_action)
            side_banner=QFrame()
            side_banner.setStyleSheet('QFrame{background:#233143;border:2px solid #6cb7ff;border-radius:10px;}'
                                      'QLabel{border:none;background:transparent;}')
            side_layout=QVBoxLayout(side_banner)
            side_layout.setContentsMargins(14,12,14,12)
            side_title=label('SIDE PICK — '+record['teams'][owner].upper())
            side_title.setStyleSheet('font-size:24px;font-weight:900;color:#a8d8ff;')
            side_layout.addWidget(side_title)
            side_hint=label('CHOOSE SIDES FOR '+name_of(record,side_action['map_id']).upper())
            side_hint.setStyleSheet('font-size:16px;font-weight:800;color:#f2f7f2;')
            side_layout.addWidget(side_hint)
            rv.addWidget(side_banner)
            rv.addWidget(label('The other team gets the opposite side. You can continue map bans/picks at any time.',True))
            map_rec=next(m for m in record['pool'] if m['id']==side_action['map_id'])
            rv.addWidget(image_label(map_rec.get('spawns'),340,155))
            choices=QWidget();cr=QHBoxLayout(choices);cr.setContentsMargins(0,0,0,0)
            def choose_side(colour,mid=side_action['map_id']):
                apply_side(record,mid,colour)
                if self.save():self.veto_page()
            cr.addWidget(btn('RED',lambda checked=False,mid=side_action['map_id']:choose_side('RED',mid),True))
            cr.addWidget(btn('BLUE',lambda checked=False,mid=side_action['map_id']:choose_side('BLUE',mid),True))
            rv.addWidget(choices)
        # Once side picking is finished, show confirmed assignments in place
        # of the now-irrelevant pending side panel, not below its old position.
        if record.get('completed'):
            rv.addWidget(section_heading('CONFIRMED SIDES — FINAL'))
        else:
            rv.addWidget(section_heading('CONFIRMED SIDES'))
        for action in selected_maps(record):
            chosen=record.get('sides',{}).get(action['map_id'])
            if chosen:
                owner=side_owner(record,action)
                opposite='BLUE' if chosen=='RED' else 'RED'
                rv.addWidget(label(name_of(record,action['map_id'])+' — '+
                                   record['teams'][owner]+': '+chosen+'  |  '+
                                   record['teams'][1-owner]+': '+opposite))
        rv.addStretch()
        def undo_action():
            if undo(record):
                if self.save():self.veto_page()
        rv.addWidget(btn('UNDO LAST',undo_action))
        rv.addWidget(btn('COPY VETO IMAGE',lambda:self.copy_board(record),True))
        self.w.cv.addWidget(content,1)

    def copy_board(self,record):
        """Copy a player-facing veto board: all seven maps, history and pending side."""
        from PySide6.QtCore import QRect, QRectF
        width,height=1200,850
        pix=QPixmap(width,height)
        pix.fill(QColor('#242426'))
        painter=QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        def rect(x,y,w,h,fill):
            painter.fillRect(QRect(x,y,w,h),QColor(fill))
        def text(x,y,w,h,value,size=16,colour='#e8e8ec',bold=False):
            font=QFont('Rajdhani',size)
            font.setBold(bold)
            painter.setFont(font)
            painter.setPen(QColor(colour))
            painter.drawText(QRect(x,y,w,h),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,
                             str(value))
        def picture(path,x,y,w,h):
            rect(x,y,w,h,'#28282b')
            if path and Path(path).is_file():
                source=QPixmap(path)
                if not source.isNull():
                    scaled=source.scaled(w,h,Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation)
                    painter.drawPixmap(x+(w-scaled.width())//2,y+(h-scaled.height())//2,scaled)
                    return
            text(x+10,y+10,w-20,h-20,'IMAGE PENDING',12,'#88888f')
        text(28,14,1144,38,'ARENA  /  MAP VETO  /  '+record['format'],22,GREEN,True)
        text(28,55,1144,43,'  VS  '.join(record['teams']),25,'#ffffff',True)
        step=next_action(record)
        side=pending_side(record)
        if step:
            status=record['teams'][step['team']]+' — '+step['kind'].upper()+' A MAP'
        elif record.get('completed'):
            status='VETO COMPLETE'
        else:
            status='MAP SELECTION COMPLETE — AWAITING SIDES'
        rect(28,110,1144,45,'#394630')
        text(42,114,1116,36,'CURRENT TURN: '+status,17,GREEN,True)
        rect(28,170,745,642,'#323234')
        rect(789,170,383,642,'#323234')
        text(44,178,712,32,'ALL SEVEN MAPS',19,'#ffffff',True)
        text(805,178,349,32,'VETO HISTORY',19,'#ffffff',True)
        actions={action['map_id']:action for action in record['actions']}
        picks=selected_maps(record)
        decider=next((a for a in picks if a['kind']=='decider'),None)
        for i,m in enumerate(record['pool']):
            col,row=i%3,i//3
            x=44+col*240;y=221+row*188
            rect(x,y,228,175,'#29292c')
            picture(m.get('preview'),x+8,y+8,212,113)
            action=actions.get(m['id'])
            state=('BANNED' if action['kind']=='ban' else 'PICKED') if action else (
                'DECIDER' if decider and decider['map_id']==m['id'] else 'AVAILABLE')
            colour={'BANNED':'#ff4556','PICKED':'#00d78a','DECIDER':'#00d78a',
                    'AVAILABLE':'#e8e8ec'}[state]
            if state in ('BANNED','PICKED','DECIDER'):
                glow=QColor(colour)
                for x1,y1,x2,y2,area in (
                    (x,y,x+26,y,(x,y,26,175)),
                    (x+228,y,x+202,y,(x+202,y,26,175)),
                    (x,y,x,y+26,(x,y,228,26)),
                    (x,y+175,x,y+149,(x,y+149,228,26)),
                ):
                    gradient=QLinearGradient(x1,y1,x2,y2)
                    outer=QColor(glow);outer.setAlpha(125)
                    inner=QColor(glow);inner.setAlpha(0)
                    gradient.setColorAt(0,outer);gradient.setColorAt(1,inner)
                    painter.fillRect(QRect(*area),gradient)
            text(x+9,y+122,210,27,m['name'],15,'#ffffff',True)
            text(x+9,y+149,210,21,state,12,colour,True)
        for i,action in enumerate(record['actions']):
            colour='#ff4556' if action['kind']=='ban' else '#00d78a'
            line=f"{i+1}. {record['teams'][action['team']]} {action['kind']} {name_of(record,action['map_id'])}"
            text(805,216+i*31,353,29,line,13,colour)
        if decider:
            text(805,216+len(record['actions'])*31,353,29,
                 '7. System picked '+name_of(record,decider['map_id']),13,'#00d78a')
        side_y=450
        rect(800,side_y,361,2,'#4a4a4e')
        if side:
            owner=side_owner(record,side)
            text(805,side_y+10,349,31,'SIDE CHOICE: '+record['teams'][owner],17,GREEN,True)
            text(805,side_y+43,349,25,name_of(record,side['map_id'])+' — RED or BLUE?',14,'#ffffff')
            map_rec=next(m for m in record['pool'] if m['id']==side['map_id'])
            picture(map_rec.get('spawns'),805,side_y+75,350,155)
            text(805,side_y+237,350,26,'Other team receives the opposite side',12,'#aaaaaf')
            confirmed_y=side_y+274
        else:
            # No empty side-choice panel: show the confirmed side assignments here.
            confirmed_y=side_y+10
        text(805,confirmed_y,350,28,
             'CONFIRMED SIDES — FINAL' if record.get('completed') else 'CONFIRMED SIDES',
             16,'#ffffff',True)
        for i,action in enumerate(a for a in picks if a['map_id'] in record.get('sides',{})):
            owner=side_owner(record,action)
            chosen=record['sides'][action['map_id']]
            opposite='BLUE' if chosen=='RED' else 'RED'
            text(805,confirmed_y+32+i*34,350,31,
                 name_of(record,action['map_id'])+': '+record['teams'][owner]+' '+chosen+
                 ' / '+record['teams'][1-owner]+' '+opposite,12,GREEN)
        painter.end()
        QGuiApplication.clipboard().setPixmap(pix)
        QMessageBox.information(self.w,'Veto image copied',
                                'The full seven-map board, action history and side selection are on your clipboard. Paste into Discord.')
