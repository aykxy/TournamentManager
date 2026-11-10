"""Checklist notification scheduling and Discord delivery (no external dependencies)."""
import datetime as dt
import json
import urllib.parse
import urllib.request


def due_events(data, now=None):
    from overview_logic import active_tasks, task_complete
    now = now or dt.datetime.now()
    events = []
    for tournament in data.get('tournaments', []):
        if str(tournament.get('status', '')).casefold() == 'finished':
            continue
        for key, name, _ in active_tasks(tournament):
            if task_complete(tournament, key):
                continue
            raw = tournament.get('task_deadlines', {}).get(key)
            if not raw:
                continue
            try:
                due = dt.datetime.fromisoformat(raw)
                if due.tzinfo:
                    due = due.astimezone().replace(tzinfo=None)
            except (ValueError, TypeError):
                continue
            kind = None
            if now >= due:
                kind = 'overdue'
            elif now >= due - dt.timedelta(hours=24):
                kind = '24h'
            if kind:
                events.append({'id': str(tournament.get('id', '')), 'tournament': tournament.get('name', 'Tournament'),
                               'task': key, 'label': name, 'due': due.isoformat(timespec='minutes'), 'kind': kind})
    return events


def event_key(event, channel):
    return '|'.join((event['id'], event['task'], event['due'], event['kind'], channel))


def validate_webhook(url):
    parsed = urllib.parse.urlparse(url)
    return (parsed.scheme == 'https' and parsed.hostname in ('discord.com', 'discordapp.com')
            and parsed.path.startswith('/api/webhooks/') and not parsed.username and not parsed.password
            and not parsed.fragment)


def send_discord(url, event):
    if not validate_webhook(url):
        raise ValueError('Use a Discord webhook URL from discord.com/api/webhooks/')
    state = 'OVERDUE' if event['kind'] == 'overdue' else 'Due within 24 hours'
    # Discord mentions are disabled and user-supplied names are plain text.
    message = f"**Arena Tournament Manager — {state}**\nTournament: {event['tournament']}\nTask: {event['label']}\nDue (PC local time): {event['due'].replace('T', ' ')}"
    payload = json.dumps({'content': message[:1900], 'allowed_mentions': {'parse': []}}).encode('utf-8')
    request = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json', 'User-Agent': 'ArenaTournamentManager/2.14'}, method='POST')
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status not in (200, 204):
            raise RuntimeError(f'Discord returned HTTP {response.status}')
