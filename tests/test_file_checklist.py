import unittest
from overview_logic import task_complete

class FileChecklistTests(unittest.TestCase):
    def test_flags_after_both_imports(self):
        t={'teams_imported':True,'keys_imported':True}
        self.assertTrue(task_complete(t,'files'))
    def test_only_one_import(self):
        self.assertFalse(task_complete({'teams_imported':True,'keys_imported':False},'files'))
        self.assertFalse(task_complete({'teams_imported':False,'keys_imported':True},'files'))
    def test_legacy_import_without_flags(self):
        t={'teams':[{'members':[{'arena_id':'1','key':'secret'}]}]}
        self.assertTrue(task_complete(t,'files'))
    def test_legacy_missing_key(self):
        t={'teams':[{'members':[{'arena_id':'1','key':None}]}]}
        self.assertFalse(task_complete(t,'files'))

if __name__=='__main__':unittest.main()
