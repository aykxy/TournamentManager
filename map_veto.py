"""Arena Map Veto: seven-map pool, admin-operated picks, side selection and export."""
import copy
import datetime
import secrets
import uuid
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QGuiApplication, QPainter
from PySide6.QtWidgets import (
    QWidget,QFrame,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QComboBox,QLineEdit,
    QFileDialog,QMessageBox,QScrollArea,QGridLayout,QInputDialog,QDialog,QDialogButtonBox
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
        'tournament_id': tournament_id, 'actions': [], 'sides': {}, 'completed': False
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
    veto['actions'].append({'kind': step['kind'], 'team': step['team'], 'map_id': map_id})
    veto['completed'] = False


def apply_side(veto, map_id, side):
    if side not in ('RED','BLUE'):
        raise ValueError('Choose RED or BLUE')
    if map_id not in {a['map_id'] for a in selected_maps(veto)}:
        raise ValueError('This map has not been picked')
    veto.setdefault('sides', {})[map_id] = side
    veto['completed'] = next_action(veto) is None and pending_side(veto) is None


def undo(veto):
    if veto['actions']:
        action = veto['actions'].pop()
        veto.setdefault('sides', {}).pop(action['map_id'], None)
        # The decider is recalculated after each action; remove obsolete side selection.
        valid = {a['map_id'] for a in selected_maps(veto)}
        veto['sides'] = {k:v for k,v in veto['sides'].items() if k in valid}
        veto['completed'] = False
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
        for name,callback in [('NEW VETO',self.new_page),('MAP POOL',self.pool_page),('VETO HISTORY',self.history_page)]:
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
        directory=Path.home()/'ArenaTournamentManager'/'map_images'
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

    def new_page(self):
        self._clear_body()
        p,v=panel();v.addWidget(label('CREATE MAP VETO'))
        if len(self.data['active_map_ids'])!=7:
            v.addWidget(label('Set exactly seven active maps in MAP POOL before starting a veto.',True))
            v.addWidget(btn('OPEN MAP POOL',self.pool_page))
            self.w.cv.addWidget(p);return
        a=QLineEdit();a.setPlaceholderText('TEAM A')
        b=QLineEdit();b.setPlaceholderText('TEAM B')
        v.addWidget(a);v.addWidget(b)
        fmt=QComboBox();fmt.addItems(['BO1','BO3','BO5']);v.addWidget(label('MATCH FORMAT'));v.addWidget(fmt)
        tournament=QComboBox();tournament.addItem('Unlinked / practice match',None)
        for t in reversed(self.data.get('tournaments',[])):
            tournament.addItem(t['name'],t['id'])
        v.addWidget(label('TOURNAMENT (OPTIONAL)'));v.addWidget(tournament)
        def start():
            ids=set(self.data['active_map_ids'])
            pool=[copy.deepcopy(m) for m in self.data['map_library'] if m['id'] in ids]
            try:record=new_veto(a.text(),b.text(),fmt.currentText(),pool,tournament.currentData())
            except ValueError as exc:
                QMessageBox.warning(self.w,'Cannot create veto',str(exc));return
            self.data['map_vetoes'].append(record)
            if not self.save():
                self.data['map_vetoes'].remove(record);return
            self.current=record['id'];self.veto_page()
        v.addWidget(btn('RANDOMISE FIRST BAN & START',start,True))
        self.w.cv.addWidget(p);self.w.cv.addStretch()

    def history_page(self):
        self._clear_body();self.history_page_content()

    def history_page_content(self):
        p,v=panel();v.addWidget(label('VETO HISTORY'))
        records=list(reversed(self.data['map_vetoes']))
        if not records:v.addWidget(label('No map vetoes recorded yet. Create your first veto to get started.',True))
        for record in records:
            line=QWidget();r=QHBoxLayout(line);r.setContentsMargins(0,0,0,0)
            state='COMPLETED' if record.get('completed') else 'IN PROGRESS'
            r.addWidget(label('  VS  '.join(record['teams'])+'  ·  '+record['format']+'  ·  '+state),1)
            r.addWidget(btn('OPEN',lambda checked=False,vid=record['id']:self.open_veto(vid)))
            v.addWidget(line)
        self.w.cv.addWidget(p);self.w.cv.addStretch()

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
        self.w.cv.addWidget(heading)
        content=QWidget();columns=QHBoxLayout(content);columns.setContentsMargins(0,0,0,0);columns.setSpacing(14)
        left,lv=panel();right,rv=panel()
        columns.addWidget(left,3);columns.addWidget(right,2)
        step=next_action(record)
        side=pending_side(record)
        if step:
            lv.addWidget(label('STEP '+str(step['step'])+'/6  ·  '+record['teams'][step['team']].upper()+' — '+step['kind'].upper()+' A MAP'))
        elif record.get('completed'):
            lv.addWidget(label('VETO COMPLETE — ALL SIDES CONFIRMED'))
        else:
            lv.addWidget(label('MAP VETO COMPLETE — AWAITING SIDE PICKS'))
        grid=QWidget();g=QGridLayout(grid);g.setContentsMargins(0,0,0,0);g.setSpacing(9)
        actions={action['map_id']:action for action in record['actions']}
        decider=selected_maps(record)[-1] if not step else None
        for i,m in enumerate(record['pool']):
            action=actions.get(m['id'])
            status=('BANNED' if action['kind']=='ban' else 'PICKED') if action else ('DECIDER' if decider and decider['map_id']==m['id'] else 'AVAILABLE')
            card=QFrame();card.setObjectName('surface');cv=QVBoxLayout(card);cv.setSpacing(5)
            cv.addWidget(image_label(m.get('preview'),190,105))
            cv.addWidget(label(m['name']))
            colour={'BANNED':'#ff4556','PICKED':'#00d78a','DECIDER':'#00d78a','AVAILABLE':'#bfc1c6'}[status]
            state=label(status);state.setStyleSheet('color:'+colour+';font-weight:bold;')
            cv.addWidget(state)
            if step and status=='AVAILABLE':
                def select(checked=False,mid=m['id']):
                    apply_map(record,mid)
                    if self.save():self.veto_page()
                cv.addWidget(btn(step['kind'].upper(),select,True))
            g.addWidget(card,i//3,i%3)
        lv.addWidget(grid)
        rv.addWidget(label('VETO HISTORY'))
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
        if side:
            owner=side_owner(record,side)
            rv.addWidget(label('SIDE PICK — '+record['teams'][owner].upper()))
            rv.addWidget(label(name_of(record,side['map_id'])+' · Other team gets opposite side.',True))
            map_rec=next(m for m in record['pool'] if m['id']==side['map_id'])
            rv.addWidget(image_label(map_rec.get('spawns'),340,190))
            choices=QWidget();cr=QHBoxLayout(choices);cr.setContentsMargins(0,0,0,0)
            def choose_side(colour):
                apply_side(record,side['map_id'],colour)
                if self.save():self.veto_page()
            cr.addWidget(btn('RED',lambda:choose_side('RED'),True))
            cr.addWidget(btn('BLUE',lambda:choose_side('BLUE'),True))
            rv.addWidget(choices)
        rv.addWidget(label('CONFIRMED SIDES'))
        for action in selected_maps(record):
            chosen=record.get('sides',{}).get(action['map_id'])
            if chosen:
                owner=side_owner(record,action)
                rv.addWidget(label(name_of(record,action['map_id'])+' — '+record['teams'][owner]+': '+chosen))
        rv.addStretch()
        def undo_action():
            if record.get('sides'):
                last=next((a for a in reversed(selected_maps(record)) if a['map_id'] in record['sides']),None)
                if last:
                    record['sides'].pop(last['map_id'],None);record['completed']=False
                    self.save();self.veto_page();return
            if undo(record):self.save();self.veto_page()
        rv.addWidget(btn('UNDO LAST',undo_action))
        rv.addWidget(btn('COPY VETO IMAGE',lambda:self.copy_board(record),True))
        self.w.cv.addWidget(content,1)

    def copy_board(self,record):
        # Render an independent, clean image instead of screenshotting the admin controls.
        board=QWidget()
        board.setStyleSheet('QWidget{background:#242426;color:#e8e8ec;font-family:Rajdhani;} QLabel{color:#e8e8ec;}')
        v=QVBoxLayout(board);v.setContentsMargins(28,24,28,24);v.setSpacing(12)
        heading=QLabel('ARENA  /  MAP VETO  /  '+record['format'])
        heading.setStyleSheet('font-size:25px;font-weight:bold;color:#58dc00;')
        v.addWidget(heading)
        title=QLabel('  VS  '.join(record['teams']));title.setStyleSheet('font-size:23px;font-weight:bold;')
        v.addWidget(title)
        step=next_action(record);side=pending_side(record)
        status='COMPLETE' if record.get('completed') else ('SIDE PICK: '+record['teams'][side_owner(record,side)] if side else ('TURN: '+record['teams'][step['team']]+' '+step['kind'].upper() if step else 'AWAITING SIDES'))
        v.addWidget(QLabel(status))
        for i,action in enumerate(selected_maps(record)):
            m=next(m for m in record['pool'] if m['id']==action['map_id'])
            card=QFrame();card.setStyleSheet('background:#323234;border:1px solid #48484b;')
            row=QHBoxLayout(card)
            preview=image_label(m.get('preview'),180,95);row.addWidget(preview)
            info=QVBoxLayout();name=QLabel(str(i+1)+'.  '+m['name']);name.setStyleSheet('font-size:20px;font-weight:bold;')
            info.addWidget(name)
            info.addWidget(QLabel('DECIDER' if action['kind']=='decider' else 'PICKED BY '+record['teams'][action['team']]))
            owner=side_owner(record,action);choice=record.get('sides',{}).get(action['map_id'])
            if choice:
                opposite='BLUE' if choice=='RED' else 'RED'
                sides=QLabel(record['teams'][owner]+': '+choice+'  |  '+record['teams'][1-owner]+': '+opposite)
                sides.setStyleSheet('font-size:15px;color:#58dc00;')
                info.addWidget(sides)
            else:info.addWidget(QLabel(record['teams'][owner]+' — SIDE PENDING'))
            row.addLayout(info,1);v.addWidget(card)
        banned=', '.join(name_of(record,a['map_id']) for a in record['actions'] if a['kind']=='ban')
        v.addWidget(QLabel('BANNED: '+(banned or 'None yet')))
        v.addWidget(QLabel('FIRST BAN: '+record['teams'][record['first']]))
        board.setFixedWidth(850);board.adjustSize()
        board.resize(850,max(board.sizeHint().height(),230))
        pix=QPixmap(board.size());pix.fill(Qt.GlobalColor.transparent)
        board.render(pix)
        QGuiApplication.clipboard().setPixmap(pix)
        QMessageBox.information(self.w,'Veto image copied','The veto board is on your clipboard. Paste it directly into Discord.')
