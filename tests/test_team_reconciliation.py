import unittest
from team_reconciliation import reconcile_teams

class TeamReconciliationTests(unittest.TestCase):
    def sample(self):
        return {'teams_db':{
            'local:old':{'id':'local:old','name':'MUD','names':['MUD'],'roster':['1','2','3'],'history':[{'action':'rename'}]},
            'arena:42':{'id':'arena:42','name':'MUD','names':['MUD'],'roster':['1','2','4'],'history':[]}},
            'tournaments':[{'teams':[{'name':'MUD','team_id':'local:old','members':[{'arena_id':'1'}]}]}]}
    def test_merge_proven_duplicate(self):
        d=self.sample();changed,review=reconcile_teams(d)
        self.assertGreater(changed,0);self.assertFalse(review)
        self.assertNotIn('local:old',d['teams_db'])
        self.assertEqual(d['tournaments'][0]['teams'][0]['team_id'],'arena:42')
        self.assertEqual(d['teams_db']['arena:42']['roster'],['1','2','4'])
        self.assertEqual(d['teams_db']['arena:42']['history'][-1]['previous_record']['history'],[{'action':'rename'}])
    def test_same_name_different_roster_does_not_merge(self):
        d=self.sample();d['teams_db']['local:old']['roster']=['8','9','10']
        _,review=reconcile_teams(d)
        self.assertIn('local:old',d['teams_db']);self.assertTrue(review)
    def test_ambiguous_multiple_arena_ids_does_not_merge(self):
        d=self.sample();d['teams_db']['arena:43']={'id':'arena:43','name':'MUD','names':['MUD'],'roster':['1','2','3'],'history':[]}
        _,review=reconcile_teams(d)
        self.assertIn('local:old',d['teams_db']);self.assertTrue(review)
    def test_crew_id_authoritative(self):
        d={'teams_db':{},'tournaments':[{'teams':[{'name':'LOL','crewId':99,'members':[{'arena_id':'5'}]}]}]}
        reconcile_teams(d)
        self.assertIn('arena:99',d['teams_db']);self.assertEqual(d['tournaments'][0]['teams'][0]['team_id'],'arena:99')
    def test_unlocked_tournament_never_registers_team(self):
        d={'teams_db':{},'tournaments':[{'locked':False,'teams':[{'name':'FUN','team_id':'arena:99','members':[{'arena_id':'5'}]}]}]}
        changed,review=reconcile_teams(d)
        self.assertEqual(changed,0)
        self.assertEqual(review,[])
        self.assertEqual(d['teams_db'],{})

    def test_locked_tournament_still_registers_team(self):
        d={'teams_db':{},'tournaments':[{'locked':True,'teams':[{'name':'COMP','team_id':'arena:99','members':[{'arena_id':'5'}]}]}]}
        reconcile_teams(d)
        self.assertIn('arena:99',d['teams_db'])

    def test_idempotent(self):
        d=self.sample();reconcile_teams(d);self.assertEqual(reconcile_teams(d)[0],0)

if __name__=='__main__':unittest.main()
