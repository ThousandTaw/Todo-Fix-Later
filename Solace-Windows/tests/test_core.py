import copy
from datetime import date
import json
import tempfile
import unittest
from unittest.mock import patch
from core import AccountStore, SolaceState, adult_age, streak, next_challenge
from emotion_model import LocalEmotionModel

class SolaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = AccountStore(self.temp.name)
        self.state = SolaceState(self.store)
        self.state.terms_accepted = True
        self.state.authenticate('tester', 'safe-password-123', 22, 'safe-password-123')
    def complete(self):
        self.state.begin('challenge')
        return self.state.finish('Good', 'Private reflection', [True, True, True])
    def test_consent(self):
        with self.assertRaises(ValueError): SolaceState(self.store).authenticate('tester', 'safe-password-123')
    def test_age(self):
        for age in ['17', '-1', 'abc', '18.5']:
            with self.assertRaises(ValueError): adult_age(age)
        self.assertEqual(adult_age('18'), 18)
        with self.assertRaises(ValueError): self.state.profile('', '17', '', '')
        self.assertEqual(self.state.data['profile']['age'], 22)
    def test_encryption_and_login(self):
        self.complete()
        raw = self.store.path('tester').read_text()
        self.assertNotIn('Private reflection', raw)
        self.assertNotIn('safe-password-123', raw)
        with self.assertRaises(ValueError): self.store.login('tester', 'wrong-password')
        self.assertEqual(self.store.login('TESTER', 'safe-password-123')[1]['entries'][0]['note'], 'Private reflection')
    def test_tampering(self):
        p = self.store.path('tester'); r = json.loads(p.read_text()); token = r['token']
        r['token'] = token[:30] + ('A' if token[30] != 'A' else 'B') + token[31:]
        p.write_text(json.dumps(r))
        with self.assertRaises(ValueError): self.store.login('tester', 'safe-password-123')
    def test_challenge_guards(self):
        self.state.begin('challenge')
        with self.assertRaises(ValueError): self.state.finish('Good', '', [False, True, True])
        self.state.finish('Good', '', [True, True, True])
        with self.assertRaises(ValueError): self.state.finish('Good', '', [True, True, True])
    def test_next_challenge(self):
        name = next_challenge(self.state.data, 'Okay')['name']
        self.complete(); self.state.no_new_friend()
        self.assertNotEqual(next_challenge(self.state.data, 'Okay')['name'], name)
        self.complete()
        self.assertEqual(streak(self.state.data['entries']), 1)
    def test_streak(self):
        rows = [{'date': '2026-10-08'}, {'date': '2026-10-09'}, {'date': '2026-10-09'}]
        self.assertEqual(streak(rows, date(2026, 10, 10)), 2)
        self.assertEqual(streak(rows, date(2026, 10, 11)), 0)
    def test_followup_recovery(self):
        entry = self.complete()
        reopened = SolaceState(self.store); reopened.terms_accepted = True
        reopened.authenticate('tester', 'safe-password-123')
        self.assertEqual(reopened.pending_entry, entry['id'])
        reopened.friend('Ari', 'Art', create=True, from_challenge=True)
        self.assertTrue(reopened.data['entries'][0]['made_friend'])
        self.assertIsNone(reopened.pending_entry)
    def test_circles(self):
        self.state.friend('Ari', 'Music circle'); ident = self.state.data['friends'][0]['id']
        self.state.circle('Band', 'Music circle')
        self.assertEqual(self.state.data['friends'][0]['circle'], 'Band')
        self.state.edit_friend(ident, circle='Family', trusted=True)
        self.assertTrue(self.state.data['friends'][0]['trusted'])
        self.state.remove_circle('Family')
        self.assertEqual(self.state.data['friends'], [])
    def test_password(self):
        self.state.vault = self.store.password(self.state.vault, self.state.data, 'safe-password-123', 'new-password-456')
        with self.assertRaises(ValueError): self.store.login('tester', 'safe-password-123')
        self.store.login('tester', 'new-password-456')
    def test_delete_account(self):
        self.store.delete(self.state.vault)
        self.assertFalse(self.store.path('tester').exists())
    def test_failed_save(self):
        previous = copy.deepcopy(self.state.data)
        with patch.object(self.store, 'save', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.state.circle('Not saved')
        self.assertEqual(self.state.data, previous)
        self.assertEqual(self.store.login('tester', 'safe-password-123')[1], previous)
    def test_no_friend_and_delete(self):
        entry = self.complete(); self.state.no_new_friend()
        self.assertFalse(self.state.data['entries'][0]['made_friend'])
        self.state.delete_entry(entry['id'])
        self.assertEqual(streak(self.state.data['entries']), 0)
    def test_model_and_account_isolation(self):
        model = LocalEmotionModel()
        self.assertEqual(model.predict('happy joyful excited')['emotion'], 'Happy')
        self.assertIsNone(model.predict('zxqv 12345')['emotion'])
        self.store.create('another', 'other-password-123', 25); self.complete()
        self.assertEqual(self.store.login('another', 'other-password-123')[1]['entries'], [])

if __name__ == '__main__': unittest.main()
