"""Conservative, deterministic team identity migration. No name-only auto merges."""
from copy import deepcopy


def members_of(team):
    return {str(p.get('arena_id', p.get('userId'))) for p in team.get('members', []) if p.get('arena_id', p.get('userId')) not in (None, '')}


def _names(rec):
    return {str(x).strip().casefold() for x in [rec.get('name', ''), *rec.get('names', [])] if str(x).strip()}


def reconcile_teams(data):
    """Mutate data only for proven identity matches; return (changes, review_items).

    An arena:ID is authoritative. A local record can be migrated only if it
    shares >=2 players and >=50% of the smaller roster with exactly one Arena
    identity, and has a matching name history. Existing arena IDs never merge.
    """
    db = data.setdefault('teams_db', {})
    changes = 0
    review = []
    for tournament in data.get('tournaments', []):
        if not tournament.get('locked', True):
            continue  # Casual tournament teams never create permanent identities.
        for team in tournament.get('teams', []):
            name = str(team.get('name', '')).strip()
            if not name:
                continue
            raw_id = team.get('team_id')
            arena_id = team.get('crewId')
            target = ('arena:' + str(arena_id)) if arena_id not in (None, '') else (str(raw_id) if str(raw_id or '').startswith('arena:') else None)
            if not target:
                # No verified ID: do not merge by name. Keep existing local link.
                if raw_id and str(raw_id) in db:
                    continue
                review.append(f'{name}: no Arena crew ID')
                continue
            if team.get('team_id') != target:
                team['team_id'] = target
                changes += 1
            if target not in db:
                db[target] = {'id': target, 'name': name, 'names': [name], 'roster': sorted(members_of(team)), 'history': []}
                changes += 1
    # Match local duplicates against authoritative arena records, conservatively.
    arena = {tid: rec for tid, rec in db.items() if tid.startswith('arena:')}
    for local_id, local in list(db.items()):
        if not local_id.startswith('local:'):
            continue
        local_roster = {str(x) for x in local.get('roster', [])}
        candidates = []
        for arena_id, rec in arena.items():
            arena_roster = {str(x) for x in rec.get('roster', [])}
            overlap = len(local_roster & arena_roster)
            if (_names(local) & _names(rec) and overlap >= 2 and
                    overlap / max(1, min(len(local_roster), len(arena_roster))) >= 0.5):
                candidates.append(arena_id)
        if len(candidates) != 1:
            if candidates or any(_names(local) & _names(rec) for rec in arena.values()):
                review.append(f"{local.get('name', local_id)} ({local_id}): needs manual review")
            continue
        target = candidates[0]
        rec = db[target]
        # Don't overwrite the authoritative roster or name; preserve history.
        rec['names'] = list(dict.fromkeys([*rec.get('names', []), *local.get('names', []), local.get('name', '')]))
        rec.setdefault('history', []).append({'action': 'local_id_reconciled', 'previous_id': local_id, 'previous_record': deepcopy(local)})
        for t in data.get('tournaments', []):
            if not t.get('locked', True):
                continue
            for team in t.get('teams', []):
                if team.get('team_id') == local_id:
                    team['team_id'] = target
        del db[local_id]
        changes += 1
    return changes, sorted(set(review))
