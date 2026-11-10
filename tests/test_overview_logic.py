import datetime, unittest
from overview_logic import overview, task_complete

class OverviewTests(unittest.TestCase):
    def test_nearest_first_and_finished_excluded(self):
        ts=[{'id':1,'name':'Later','date':'2026-12-01','status':'Preparing'}, {'id':2,'name':'Soon','date':'2026-11-12','status':'Preparing'}, {'id':3,'name':'Old','date':'2026-11-01','status':'Finished'}]
        self.assertEqual([x['tournament']['id'] for x in overview({'tournaments':ts},datetime.date(2026,11,10))],[2,1])
    def test_qualifier_tasks_optional(self):
        t={'date':'2026-11-12','status':'Preparing','qualifiers':False,'tasks':{}}
        self.assertEqual(overview({'tournaments':[t]},datetime.date(2026,11,10))[0]['total'],11)
    def test_keys_require_explicit_sent_flags(self):
        t={'teams':[{'members':[{'sent':True},{'sent':False}]}]}
        self.assertFalse(task_complete(t,'keys'))
        t['teams'][0]['members'][1]['sent']=True
        self.assertTrue(task_complete(t,'keys'))
    def test_missing_date_warns(self):
        self.assertIn('Tournament date missing or invalid',overview({'tournaments':[{'status':'Preparing'}]})[0]['warnings'])
    def test_completed_tasks(self):
        t={'tasks':{'announce':True},'qualifiers':False}
        self.assertTrue(task_complete(t,'announce'))
        self.assertFalse(task_complete(t,'files'))
if __name__=='__main__':unittest.main()
