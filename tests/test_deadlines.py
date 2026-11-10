import unittest,datetime
from overview_logic import deadline_status,overview
class DeadlineTests(unittest.TestCase):
 def test_overdue_and_upcoming(self):
  now=datetime.datetime(2026,11,10,12,0)
  t={'tasks':{},'task_deadlines':{'announce':'2026-11-09T12:00'}}
  self.assertEqual(deadline_status(t,'announce',now),'overdue')
  t['task_deadlines']['announce']='2026-11-11T12:00'
  self.assertEqual(deadline_status(t,'announce',now),'due_soon')
  t['task_deadlines']['announce']='2026-11-20T12:00'
  self.assertEqual(deadline_status(t,'announce',now),'upcoming')
 def test_completed_never_overdue(self):
  t={'tasks':{'announce':True},'task_deadlines':{'announce':'2020-01-01T00:00'}}
  self.assertEqual(deadline_status(t,'announce',datetime.datetime(2026,11,10)),'complete')
 def test_missing_and_invalid(self):
  self.assertEqual(deadline_status({},'announce'),'none')
  self.assertEqual(deadline_status({'task_deadlines':{'announce':'oops'}},'announce'),'invalid')
if __name__=='__main__':unittest.main()
