import unittest
import datetime as dt
from notifications import due_events,event_key,validate_webhook

class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.now=dt.datetime(2026,11,10,12)
        self.data={'tournaments':[{'id':'abc','name':'Cup','qualifiers':False,'tasks':{},'task_deadlines':{'announce':'2026-11-11T11:00'}}]}
    def test_24h(self):
        events=due_events(self.data,self.now)
        self.assertEqual(events[0]['kind'],'24h')
    def test_overdue(self):
        self.data['tournaments'][0]['task_deadlines']['announce']='2026-11-09T12:00'
        self.assertEqual(due_events(self.data,self.now)[0]['kind'],'overdue')
    def test_completed_not_sent(self):
        self.data['tournaments'][0]['tasks']['announce']=True
        self.assertEqual(due_events(self.data,self.now),[])
    def test_finished_not_sent(self):
        self.data['tournaments'][0]['status']='Finished'
        self.assertEqual(due_events(self.data,self.now),[])
    def test_key_changes_with_deadline(self):
        event=due_events(self.data,self.now)[0]
        self.assertNotEqual(event_key(event,'windows'),event_key(event,'discord'))
    def test_webhook_validation(self):
        self.assertTrue(validate_webhook('https://discord.com/api/webhooks/123/abc'))
        self.assertFalse(validate_webhook('http://discord.com/api/webhooks/123/abc'))
        self.assertFalse(validate_webhook('https://discord.com.evil.com/api/webhooks/123/abc'))
if __name__=='__main__':unittest.main()
