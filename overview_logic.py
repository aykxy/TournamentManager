"""Pure, side-effect-free tournament readiness calculations."""
import datetime

TASKS = [('announce','Announce tournament','manual'),('qopen','Announce qualifiers open','manual'),('qclose','Announce qualifiers closed','manual'),('received','Receive stream key document & tournament export from developer','manual'),('files','Upload stream key document & tournament export','auto'),('tickets','Add team players to their team ticket','manual'),('congrats','Send congratulations / acceptance and misc info','manual'),('guide','Send OBS guide in team tickets','manual'),('keys','DM stream keys to players','auto'),('bracket','Create bracket via Bracket HQ','manual'),('games','Create tournament games','manual'),('live','Announce tournament is live','manual'),('results','Record tournament results','manual')]

def active_tasks(t):
    return [(k,n,kind) for k,n,kind in TASKS if t.get('qualifiers') or k not in ('qopen','qclose')]

def task_complete(t,key):
    if key=='files':
        # Legacy imports may contain fully assigned data without import flags.
        teams=t.get('teams') or []
        members=[p for team in teams for p in team.get('members',[])]
        export_present=bool(t.get('teams_imported')) or bool(teams)
        keys_present=bool(t.get('keys_imported')) or (bool(members) and all(p.get('key') for p in members))
        return export_present and keys_present
    if key=='keys':
        members=[p for team in t.get('teams',[]) for p in team.get('members',[])]
        return bool(members) and all(p.get('sent') for p in members)
    if key=='results':
        results=t.get('results',{})
        return bool(results.get('placements')) if isinstance(results,dict) else bool(str(results).strip())
    return bool(t.get('tasks',{}).get(key))

def deadline_status(t,key,now=None):
    """Return deadline state for a task; date/time stored in local ISO format."""
    if task_complete(t,key):return 'complete'
    raw=t.get('task_deadlines',{}).get(key)
    if not raw:return 'none'
    try:due=datetime.datetime.fromisoformat(raw)
    except (TypeError,ValueError):return 'invalid'
    now=now or datetime.datetime.now()
    if due<now:return 'overdue'
    if due<=now+datetime.timedelta(hours=48):return 'due_soon'
    return 'upcoming'

def tournament_date(t):
    values=t.get('dates') or [t.get('date','')]
    dates=[]
    for value in values:
        try: dates.append(datetime.date.fromisoformat(str(value)))
        except (ValueError,TypeError): pass
    return min(dates) if dates else None

def overview(data,today=None):
    today=today or datetime.date.today()
    active=[]
    for t in data.get('tournaments',[]):
        if str(t.get('status','')).casefold()=='finished': continue
        tasks=active_tasks(t)
        pending=[(k,n,kind) for k,n,kind in tasks if not task_complete(t,k)]
        when=tournament_date(t)
        days=(when-today).days if when else None
        warnings=[]
        overdue=[n for k,n,_ in pending if deadline_status(t,k,datetime.datetime.combine(today,datetime.datetime.now().time()))=='overdue']
        due_soon=[n for k,n,_ in pending if deadline_status(t,k,datetime.datetime.combine(today,datetime.datetime.now().time()))=='due_soon']
        if overdue:warnings.append(f'{len(overdue)} checklist deadline(s) overdue')
        if due_soon:warnings.append(f'{len(due_soon)} checklist deadline(s) due within 48 hours')
        if when is None: warnings.append('Tournament date missing or invalid')
        elif days<0: warnings.append(f'{abs(days)} day(s) past scheduled start')
        elif days<=3 and pending: warnings.append(f'{days} day(s) until tournament · {len(pending)} tasks pending')
        if not t.get('teams_imported'):warnings.append('Tournament export not imported')
        if not t.get('keys_imported'):warnings.append('Stream keys not imported')
        if t.get('teams') and not task_complete(t,'keys'):warnings.append('Player stream-key DMs outstanding')
        active.append({'tournament':t,'date':when,'days':days,'completed':len(tasks)-len(pending),'total':len(tasks),'pending':pending,'warnings':warnings})
    active.sort(key=lambda item:(item['date'] is None,item['date'] or datetime.date.max,str(item['tournament'].get('name','')).casefold()))
    return active
