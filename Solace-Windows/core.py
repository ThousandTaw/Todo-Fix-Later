"""Solace's local account storage and wellbeing session state; no UI dependencies."""
from __future__ import annotations
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
from cryptography.fernet import Fernet, InvalidToken

MOODS = {'Low': '#D6E3F3', 'Anxious': '#E0D7ED', 'Okay': '#E9DEF4', 'Good': '#FAE5B9', 'Great': '#F6D3C5'}
TERMS_VERSION = 'Solace-Windows-2026-10-10-local-ai'
TERMS = [
    ('Companion limits', 'Solace supports reflection and small self-care activities. It is not therapy, diagnosis, treatment or emergency care. The companion generates responses with a local AI model. Responses can be inaccurate.'),
    ('Adults only', 'You must be 18 or older to use Solace. Age is required. Your name, personality and interests are optional.'),
    ('Local privacy', 'Saved account data is encrypted on this computer. There is no cloud sync or password recovery. Removing the account files permanently removes your saved information.'),
    ('Your choices', 'You may stop an activity or delete your account. For immediate danger, seek local emergency or in-person support. These are prototype terms.')]

def asset_path(name):
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)) / 'assets' / name

CHALLENGES = json.loads(asset_path('challenges.json').read_text(encoding='utf-8'))

def adult_age(raw):
    try: age = int(str(raw).strip())
    except ValueError: raise ValueError('Enter a whole number for your age.') from None
    if not 18 <= age <= 120: raise ValueError('You must be 18 or older to use Solace (age range 18–120).')
    return age

def new_data(age):
    return {'profile': {'name': '', 'age': adult_age(age), 'personality': 'Prefer not to say', 'interests': ''},
            'entries': [], 'circles': ['Music circle', 'School circle', 'Family'], 'friends': [],
            'glow': True, 'accepted_terms': TERMS_VERSION, 'accepted_at': datetime.now(timezone.utc).isoformat()}

def streak(entries, today=None):
    today = today or date.today()
    days = {e['date'] for e in entries}
    day = today if today.isoformat() in days else today - timedelta(days=1)
    count = 0
    while day.isoformat() in days:
        count += 1
        day -= timedelta(days=1)
    return count

def next_challenge(data, mood):
    if mood not in MOODS: raise ValueError('Choose a valid emotion.')
    completed = sum(e['type'] == 'challenge' and e['before'] == mood for e in data['entries'])
    return copy.deepcopy(CHALLENGES[mood][completed % len(CHALLENGES[mood])])

class AccountStore:
    """One authenticated, encrypted JSON file per local account. Atomic writes."""
    def __init__(self, directory=None):
        if directory is None:
            directory = Path(os.environ.get('LOCALAPPDATA', Path.home() / '.local' / 'share')) / 'Solace' / 'accounts'
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def normalize(username):
        user = username.strip().lower()
        if not re.fullmatch(r'[a-z0-9_]{3,30}', user):
            raise ValueError('Username must contain 3–30 letters, numbers or underscores.')
        return user

    def path(self, username):
        user = self.normalize(username)
        return self.directory / (hashlib.sha256(user.encode()).hexdigest() + '.json')

    @staticmethod
    def key(password, salt):
        return base64.urlsafe_b64encode(hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 600_000, dklen=32))

    @staticmethod
    def check_password(password):
        if len(password) < 10: raise ValueError('Choose a password with at least 10 characters.')
        if len(password) > 1024: raise ValueError('Use a password of 1024 characters or fewer.')

    def create(self, username, password, age):
        username = self.normalize(username)
        self.check_password(password)
        data = new_data(age)
        if self.path(username).exists(): raise ValueError('That username already exists on this computer. Log in instead.')
        salt = os.urandom(16)
        vault = {'username': username, 'salt': salt, 'key': self.key(password, salt)}
        self.save(vault, data)
        return vault, data

    def login(self, username, password):
        username = self.normalize(username)
        if len(password) > 1024: raise ValueError('Username or password is incorrect.')
        try:
            record = json.loads(self.path(username).read_text(encoding='utf-8'))
            salt = base64.b64decode(record['salt'], validate=True)
            key = self.key(password, salt)
            data = json.loads(Fernet(key).decrypt(record['token'].encode('ascii')))
        except (FileNotFoundError, InvalidToken, ValueError, KeyError):
            raise ValueError('Username or password is incorrect, or the account file is damaged.') from None
        adult_age(data['profile']['age'])
        return {'username': username, 'salt': salt, 'key': key}, data

    def save(self, vault, data):
        record = {'version': 1, 'salt': base64.b64encode(vault['salt']).decode('ascii'),
                  'token': Fernet(vault['key']).encrypt(json.dumps(data, ensure_ascii=False).encode('utf-8')).decode('ascii')}
        fd, tmp = tempfile.mkstemp(dir=self.directory, prefix='.solace-', suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(record, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path(vault['username']))
        finally:
            if os.path.exists(tmp): os.unlink(tmp)

    def password(self, vault, data, old, new):
        self.check_password(new)
        self.login(vault['username'], old)
        salt = os.urandom(16)
        updated = {'username': vault['username'], 'salt': salt, 'key': self.key(new, salt)}
        self.save(updated, data)
        return updated

    def delete(self, vault):
        self.path(vault['username']).unlink()

class SolaceState:
    def __init__(self, store=None):
        self.store = store or AccountStore()
        self.vault = None
        self.data = None
        self.terms_accepted = False
        self.mood = 'Okay'
        self.session = None
        self.pending_entry = None
        self.messages = []

    def require_account(self):
        if self.vault is None or not self.terms_accepted: raise ValueError('Accept the terms and log in first.')
        adult_age(self.data['profile']['age'])

    def authenticate(self, username, password, age=None, confirm=None):
        if not self.terms_accepted: raise ValueError('Answer all terms acknowledgements first.')
        if age is not None:
            if password != confirm: raise ValueError('Your passwords do not match.')
            vault, data = self.store.create(username, password, age)
        else: vault, data = self.store.login(username, password)
        data['accepted_terms'] = TERMS_VERSION
        data['accepted_at'] = datetime.now(timezone.utc).isoformat()
        self.store.save(vault, data)
        self.vault, self.data = vault, data
        pending = [e for e in data['entries'] if e['type'] == 'challenge' and e['made_friend'] is None]
        self.pending_entry = pending[-1]['id'] if pending else None

    def commit(self, data):
        self.require_account()
        self.store.save(self.vault, data)
        self.data = data

    def profile(self, name, age, personality, interests):
        updated = copy.deepcopy(self.data)
        updated['profile'] = {'name': name.strip()[:60], 'age': adult_age(age), 'personality': personality[:60], 'interests': interests.strip()[:500]}
        self.commit(updated)

    def begin(self, kind):
        self.require_account()
        if kind not in ('challenge', 'consult'): raise ValueError('Unknown session type.')
        self.session = {'type': kind, 'before': self.mood}
        if kind == 'challenge': self.session['challenge'] = next_challenge(self.data, self.mood)
        self.messages = [('Solace', {'Low': 'We can take this slowly. What has been on your mind?',
            'Anxious': 'What is taking up space in your thoughts?', 'Okay': 'What would you like to make room for?',
            'Good': 'What helped you feel this way?', 'Great': 'What brought you this good feeling?'}[self.mood])]
        return self.session

    def reply(self, text):
        self.require_account()
        if not self.session or self.session['type'] != 'consult': raise ValueError('Start a conversation first.')
        text = text.strip()[:1500]
        if not text: return
        if re.search(r'suicid|kill myself|hurt myself|end my life', text, re.I):
            response = 'Thank you for sharing this. If you may act on these feelings or are in immediate danger, contact local emergency services or go to the nearest emergency department. If possible, reach out to someone you trust who can stay with you. Solace cannot provide crisis care.'
        else:
            responses = ['Thank you for putting that into words. What feels most important for you to be heard about?',
                'What would support you right now: space, reassurance, rest or connection?',
                'What small next step would feel manageable for the next few minutes?']
            response = responses[sum(who == 'You' for who, _ in self.messages) % len(responses)]
        # Integration point: replace response selection with an on-device model.
        self.messages += [('You', text), ('Solace', response)]

    def finish(self, after, note, checks=None):
        self.require_account()
        if not self.session: raise ValueError('This session has already been saved.')
        if after not in MOODS: raise ValueError('Choose an emotion.')
        challenge = self.session.get('challenge')
        if challenge and (not checks or len(checks) != len(challenge['steps']) or not all(checks)):
            raise ValueError('Complete each challenge step before finishing.')
        entry = {'id': uuid4().hex, 'date': date.today().isoformat(), 'type': self.session['type'],
                 'before': self.session['before'], 'after': after, 'note': note.strip()[:1500],
                 'challenge_name': challenge['name'] if challenge else '', 'made_friend': None, 'friend_id': ''}
        updated = copy.deepcopy(self.data)
        updated['entries'].append(entry)
        self.commit(updated)
        self.session = None
        self.pending_entry = entry['id'] if challenge else None
        self.messages = []
        return entry

    def circle(self, name, old=None):
        self.require_account()
        clean = name.strip()[:60]
        if not clean: raise ValueError('Enter a circle name.')
        if any(c.lower() == clean.lower() and c != old for c in self.data['circles']): raise ValueError('That circle already exists.')
        updated = copy.deepcopy(self.data)
        if old is None: updated['circles'].append(clean)
        else:
            if old not in updated['circles']: raise ValueError('Circle not found.')
            updated['circles'] = [clean if c == old else c for c in updated['circles']]
            for person in updated['friends']:
                if person['circle'] == old: person['circle'] = clean
        self.commit(updated)

    def remove_circle(self, name):
        updated = copy.deepcopy(self.data)
        updated['circles'].remove(name)
        updated['friends'] = [p for p in updated['friends'] if p['circle'] != name]
        self.commit(updated)

    def friend(self, name, circle, create=False, from_challenge=False):
        self.require_account()
        name, circle = name.strip()[:80], circle.strip()[:60]
        if not name or not circle: raise ValueError('Enter a name and choose a circle.')
        updated = copy.deepcopy(self.data)
        match = next((c for c in updated['circles'] if c.lower() == circle.lower()), None)
        if match: circle = match
        elif create: updated['circles'].append(circle)
        else: raise ValueError('Choose an existing circle or create a new one.')
        person = {'id': uuid4().hex, 'name': name, 'circle': circle, 'trusted': False}
        updated['friends'].append(person)
        if from_challenge:
            if not self.pending_entry: raise ValueError('No challenge is waiting for this answer.')
            entry = next(e for e in updated['entries'] if e['id'] == self.pending_entry)
            entry['made_friend'], entry['friend_id'] = True, person['id']
        self.commit(updated)
        if from_challenge: self.pending_entry = None

    def no_new_friend(self):
        if not self.pending_entry: return
        updated = copy.deepcopy(self.data)
        next(e for e in updated['entries'] if e['id'] == self.pending_entry)['made_friend'] = False
        self.commit(updated)
        self.pending_entry = None

    def remove_friend(self, ident):
        updated = copy.deepcopy(self.data)
        updated['friends'] = [p for p in updated['friends'] if p['id'] != ident]
        self.commit(updated)

    def edit_friend(self, ident, circle=None, trusted=None):
        self.require_account()
        updated = copy.deepcopy(self.data)
        person = next(p for p in updated['friends'] if p['id'] == ident)
        if circle is not None:
            if circle not in updated['circles']: raise ValueError('Choose an existing circle.')
            person['circle'] = circle
        if trusted is not None: person['trusted'] = bool(trusted)
        self.commit(updated)

    def delete_entry(self, ident):
        self.require_account()
        updated = copy.deepcopy(self.data)
        updated['entries'] = [e for e in updated['entries'] if e['id'] != ident]
        self.commit(updated)

    def logout(self):
        self.vault = self.data = self.session = self.pending_entry = None
        self.messages = []
        self.mood = 'Okay'
