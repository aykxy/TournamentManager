import json
import tempfile
import unittest
from pathlib import Path
from backup_manager import atomic_write, snapshot, restore, read_validated, list_snapshots

class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.db=self.base/'tournaments.json'
        self.backups=self.base/'backups'
        self.original={'tournaments':[{'id':1,'name':'Test'}],'players':{'1':{'name':'Trips'}},'teams_db':{}}
        atomic_write(self.db,self.original)

    def test_restore_preserves_original_and_creates_safety_snapshot(self):
        saved=snapshot(self.db,self.backups,'protected','before_edit')
        updated={**self.original,'players':{'1':{'name':'Changed'}}}
        atomic_write(self.db,updated)
        safety=restore(saved,self.db,self.backups)
        self.assertEqual(read_validated(self.db),self.original)
        self.assertEqual(read_validated(safety),updated)

    def test_invalid_backup_does_not_modify_database(self):
        bad=self.base/'invalid.json';bad.write_text('{invalid',encoding='utf-8')
        with self.assertRaises(Exception):restore(bad,self.db,self.backups)
        self.assertEqual(read_validated(self.db),self.original)

    def test_rolling_retention_does_not_delete_protected(self):
        protected=snapshot(self.db,self.backups,'protected','keep')
        for _ in range(4):snapshot(self.db,self.backups,'rolling','test',keep_rolling=2)
        self.assertTrue(protected.exists())
        self.assertEqual(len(list(self.backups.glob('rolling_*.json'))),2)

    def test_invalid_payload_rejected_before_write(self):
        with self.assertRaises(ValueError):atomic_write(self.db,{'tournaments':[]})
        self.assertEqual(read_validated(self.db),self.original)

if __name__=='__main__':unittest.main()
