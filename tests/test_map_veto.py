"""Map veto rules: seven maps, alternating bans, picks and side ownership."""
import unittest
from unittest.mock import patch
from map_veto import new_veto, next_action, apply_map, apply_side, selected_maps, side_owner, pending_side, undo

POOL=[{'id':str(i),'name':'Map '+str(i),'preview':'','spawns':''} for i in range(7)]

class VetoTests(unittest.TestCase):
    def create(self,fmt):
        with patch('map_veto.secrets.randbelow',return_value=0):
            return new_veto('Alpha','Bravo',fmt,POOL)

    def test_seven_maps_required(self):
        with self.assertRaises(ValueError):new_veto('A','B','BO1',POOL[:6])

    def test_random_first_ban_persisted(self):
        v=self.create('BO1')
        self.assertEqual(v['first'],0)
        self.assertEqual(next_action(v)['team'],0)

    def test_bo1_decider_side(self):
        v=self.create('BO1')
        for i in range(6):apply_map(v,str(i))
        self.assertIsNone(next_action(v))
        decider=selected_maps(v)[0]
        self.assertEqual(decider['map_id'],'6')
        self.assertEqual(side_owner(v,decider),0) # Bravo made final ban, Alpha chooses side.
        apply_side(v,'6','RED')
        self.assertTrue(v['completed'])

    def test_bo3_picked_map_side(self):
        v=self.create('BO3')
        for i in range(4):apply_map(v,str(i))
        picks=selected_maps(v)
        self.assertEqual([a['map_id'] for a in picks],['2','3'])
        self.assertEqual([side_owner(v,a) for a in picks],[1,0])
        apply_side(v,'2','BLUE');apply_side(v,'3','RED')
        apply_map(v,'4');apply_map(v,'5')
        self.assertEqual(side_owner(v,selected_maps(v)[-1]),0)
        self.assertFalse(v['completed'])
        apply_side(v,'6','BLUE')
        self.assertTrue(v['completed'])

    def test_bo5_four_picks(self):
        v=self.create('BO5')
        for i in range(6):apply_map(v,str(i))
        picks=selected_maps(v)
        self.assertEqual(len(picks),5)
        self.assertEqual([side_owner(v,a) for a in picks],[1,0,1,0,0])

    def test_undo_reverts_last_action_chronologically(self):
        v=self.create('BO3')
        for i in range(3):apply_map(v,str(i))
        apply_side(v,'2','RED')
        self.assertTrue(undo(v))
        self.assertEqual(len(v['actions']),3)  # Side selection was the latest action.
        self.assertNotIn('2',v['sides'])
        self.assertTrue(undo(v))
        self.assertEqual(len(v['actions']),2)  # Now undo the preceding map pick.

    def test_undo_interleaved_side_and_map_actions(self):
        v=self.create('BO3')
        for i in range(3):apply_map(v,str(i))
        apply_side(v,'2','RED')
        apply_map(v,'3')
        self.assertTrue(undo(v))  # Last action was the fourth map.
        self.assertEqual(len(v['actions']),3)
        self.assertEqual(v['sides']['2'],'RED')  # Earlier side choice is preserved.
        self.assertTrue(undo(v))
        self.assertNotIn('2',v['sides'])
        self.assertEqual(len(v['actions']),3)

    def test_undo_restores_previous_side_choice(self):
        v=self.create('BO3')
        for i in range(3):apply_map(v,str(i))
        apply_side(v,'2','RED')
        apply_side(v,'2','BLUE')
        self.assertTrue(undo(v))
        self.assertEqual(v['sides']['2'],'RED')

if __name__=='__main__':unittest.main()
