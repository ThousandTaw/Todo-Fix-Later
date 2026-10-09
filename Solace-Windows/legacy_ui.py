"""Native Solace desktop UI. Run with: python app.py"""
from __future__ import annotations
import copy
import ctypes
from datetime import date
import json
from pathlib import Path
import tkinter as tk
import os
from PIL import Image, ImageTk
from tkinter import ttk, messagebox, simpledialog
from emotion_model import LocalEmotionModel
from core import AccountStore, SolaceState, MOODS, TERMS, asset_path, streak, next_challenge

BG = '#09172B'
PANEL = '#142640'
DEEP = '#102037'
LINE = '#29415E'
CYAN = '#8ED5FF'
TEXT = '#EAF2FF'
MUTED = '#A7BAD3'
BLUE = '#347FD7'

class SolaceApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Solace • Your private space')
        self.geometry('1120x800')
        self.minsize(840, 620)
        self.configure(bg=BG)
        self.state_model = SolaceState()
        self.emotion_model = LocalEmotionModel()
        self.page = ''
        self.login_mode = 'register' if not list(self.state_model.store.directory.glob('*.json')) else 'login'
        self.checks = []
        self.challenge_note = ''
        self.last_entry = None
        self.feedback_mood = 'Okay'
        self.logo = None
        try:
            with Image.open(asset_path('solace_logo.png')) as artwork:
                self._window_icon = ImageTk.PhotoImage(artwork.resize((256, 256), Image.Resampling.LANCZOS), master=self)
                self.logo = ImageTk.PhotoImage(artwork.resize((54, 54), Image.Resampling.LANCZOS), master=self)
            self.iconphoto(True, self._window_icon)
            if os.name == 'nt':
                self.iconbitmap(str(asset_path('solace.ico')))
        except (tk.TclError, OSError): pass
        self._styles()
        self.protocol('WM_DELETE_WINDOW', self.close_app)
        self.bind_all('<MouseWheel>', self.wheel)
        self.show('terms')

    def _styles(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('TCombobox', fieldbackground=DEEP, background=LINE, foreground=TEXT,
                        arrowcolor=CYAN, bordercolor=LINE, padding=8)
        style.map('TCombobox', fieldbackground=[('readonly', DEEP)], foreground=[('readonly', TEXT)], selectbackground=[('readonly', DEEP)], selectforeground=[('readonly', TEXT)])
        style.configure('Vertical.TScrollbar', background=LINE, troughcolor=BG, bordercolor=BG, arrowcolor=MUTED)
        self.option_add('*TCombobox*Listbox.background', DEEP)
        self.option_add('*TCombobox*Listbox.foreground', TEXT)
        self.option_add('*TCombobox*Listbox.selectBackground', BLUE)

    def safe(self, fn):
        def call():
            try: return fn()
            except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
                messagebox.showerror('Solace', str(exc), parent=self)
        return call

    def label(self, parent, text, size=11, color=TEXT, bold=False, pady=(0, 8)):
        widget = tk.Label(parent, text=text, bg=parent.cget('bg'), fg=color, font=('Segoe UI', size, 'bold' if bold else 'normal'),
                          anchor='w', justify='left', wraplength=650)
        widget.pack(fill='x', pady=pady)
        # Reflow text for the actual content width, including when resizing Windows.
        widget.bind('<Configure>', lambda e: widget.configure(wraplength=max(100, e.width - 4)))
        return widget

    def button(self, parent, text, action, secondary=False, enabled=True):
        normal = DEEP if secondary else BLUE
        button = tk.Button(parent, text=text, command=self.safe(action), bg=normal, fg=TEXT,
            activebackground='#438AD8', activeforeground=TEXT, disabledforeground='#667C96',
            font=('Segoe UI', 11, 'bold'), relief='flat', bd=0, cursor='hand2', padx=18, pady=11,
            highlightthickness=1, highlightbackground=LINE if secondary else '#6BA9EF', highlightcolor=CYAN,
            state='normal' if enabled else 'disabled', takefocus=True)
        button.pack(fill='x', pady=(4, 8))
        def glow(_event=None):
            data = self.state_model.data
            if str(button.cget('state')) != 'disabled' and (not data or data['glow']):
                button.configure(bg='#23557E' if secondary else '#4B9DF2', highlightbackground='#9CEBFF', highlightthickness=2)
        def restore(_event=None):
            button.configure(bg=normal, highlightbackground=LINE if secondary else '#6BA9EF', highlightthickness=1)
        button.bind('<Enter>', glow)
        button.bind('<Leave>', restore)
        button.bind('<FocusIn>', glow)
        button.bind('<FocusOut>', restore)
        button.bind('<Return>', lambda _e: button.invoke())
        return button

    def card(self, parent=None):
        parent = parent or self.body
        border = tk.Frame(parent, bg=LINE, padx=1, pady=1)
        border.pack(fill='x', pady=(0, 18))
        frame = tk.Frame(border, bg=PANEL, padx=22, pady=20)
        frame.pack(fill='both', expand=True)
        return frame

    def title_block(self, eyebrow, title, subtitle=''):
        self.label(self.body, eyebrow.upper(), 10, CYAN, True, (0, 10))
        self.label(self.body, title, 27, TEXT, True)
        if subtitle: self.label(self.body, subtitle, 11, MUTED, pady=(0, 24))

    def field(self, parent, title, value='', secret=False, multiline=False):
        self.label(parent, title, 10, MUTED, pady=(6, 5))
        if multiline:
            field = tk.Text(parent, height=4, wrap='word', undo=True, bg=DEEP, fg=TEXT, insertbackground=CYAN,
                            font=('Segoe UI', 11), relief='flat', padx=10, pady=10, highlightthickness=1,
                            highlightbackground=LINE, highlightcolor=CYAN)
            field.insert('1.0', value)
        else:
            field = tk.Entry(parent, bg=DEEP, fg=TEXT, insertbackground=CYAN, font=('Segoe UI', 12),
                             relief='flat', show='•' if secret else '', highlightthickness=1,
                             highlightbackground=LINE, highlightcolor=CYAN)
            field.insert(0, str(value))
        field.pack(fill='x', ipady=8 if not multiline else 0, pady=(0, 8))
        return field

    def select(self, parent, title, options, current=''):
        self.label(parent, title, 10, MUTED, pady=(6, 5))
        value = tk.StringVar(value=current or (options[0] if options else ''))
        combo = ttk.Combobox(parent, textvariable=value, values=options, state='readonly', font=('Segoe UI', 11))
        combo.pack(fill='x', pady=(0, 10))
        return value, combo

    def check(self, parent, text, var, command=None):
        checkbox = tk.Checkbutton(parent, text=text, variable=var, command=command, bg=parent.cget('bg'), fg=TEXT,
            selectcolor=DEEP, activebackground=parent.cget('bg'), activeforeground=CYAN,
            font=('Segoe UI', 11), wraplength=600, justify='left', anchor='w', padx=8, pady=8)
        checkbox.pack(fill='x', pady=4)
        checkbox.bind('<Configure>', lambda e: checkbox.configure(wraplength=max(100, e.width - 42)))
        return checkbox

    def wheel(self, event):
        if event.widget.winfo_toplevel() != self: return
        if isinstance(event.widget, (tk.Text, ttk.Combobox)): return
        if hasattr(self, 'canvas') and self.canvas.winfo_exists():
            self.canvas.yview_scroll(-int(event.delta / 120), 'units')

    def show(self, page):
        if page not in ('terms', 'login'):
            self.state_model.require_account()
        if self.state_model.pending_entry and page not in ('friend_question', 'friend_form', 'success'):
            page = 'friend_question'
        self.page = page
        for widget in self.winfo_children(): widget.destroy()
        shell = tk.Frame(self, bg=BG)
        shell.pack(fill='both', expand=True)
        sidebar = tk.Frame(shell, bg=DEEP, width=205, padx=18, pady=25)
        sidebar.pack(side='left', fill='y')
        sidebar.pack_propagate(False)
        if self.logo: tk.Label(sidebar, image=self.logo, bg=DEEP).pack(anchor='w', pady=(0, 12))
        self.label(sidebar, 'solace.', 26, TEXT, True)
        self.label(sidebar, 'A little space for you.', 10, MUTED, pady=(0, 28))
        if self.state_model.vault:
            for name, target in [('Today', 'home'), ('Companion', 'companion'), ('Challenges', 'challenge'), ('Progress', 'progress'), ('Your circles', 'circles'), ('Settings', 'settings')]:
                selected = target == page
                b = self.button(sidebar, ('•  ' if selected else '') + name, lambda p=target: self.navigate(p), secondary=not selected,
                                enabled=not bool(self.state_model.pending_entry))
                b.configure(anchor='w')
            footer = tk.Frame(sidebar, bg=DEEP)
            footer.pack(side='bottom', fill='x')
            self.label(footer, '@' + self.state_model.vault['username'], 10, MUTED)
            self.button(footer, 'Need support?', lambda: self.navigate('circles'), secondary=True, enabled=not bool(self.state_model.pending_entry))
        else:
            self.label(sidebar, 'YOUR WELLBEING\nYOUR CHOICE', 10, CYAN, True)
            self.label(sidebar, 'Take this at your pace.', 10, MUTED)
        main = tk.Frame(shell, bg=BG)
        main.pack(side='left', fill='both', expand=True)
        scrollbar = ttk.Scrollbar(main, orient='vertical')
        scrollbar.pack(side='right', fill='y')
        self.canvas = tk.Canvas(main, bg=BG, highlightthickness=0, yscrollcommand=scrollbar.set)
        self.canvas.pack(side='left', fill='both', expand=True)
        scrollbar.configure(command=self.canvas.yview)
        self.body = tk.Frame(self.canvas, bg=BG, padx=32, pady=30)
        window = self.canvas.create_window(0, 0, anchor='nw', window=self.body)
        self.body.bind('<Configure>', lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        def resize(e):
            self.canvas.itemconfigure(window, width=e.width)
            self.body.configure(padx=max(24, (e.width - 790) // 2))
        self.canvas.bind('<Configure>', resize)
        getattr(self, 'page_' + page)()
        if self.state_model.vault:
            self.label(self.body, 'A companion for reflection. Not professional or emergency care.', 9, MUTED, pady=(12, 5))
        self.canvas.yview_moveto(0)

    def navigate(self, target):
        if target in ('challenge', 'companion'):
            kind = 'challenge' if target == 'challenge' else 'consult'
            if not self.state_model.session or self.state_model.session['type'] != kind:
                if self.state_model.session and not messagebox.askyesno('Switch activity?', 'Leave this unfinished activity and start another?', parent=self): return
                self.state_model.begin(kind)
                self.challenge_note = ''
                self.checks = [False] * len(self.state_model.session.get('challenge', {}).get('steps', []))
        self.show(target)

    def start(self, kind):
        if self.state_model.session and not messagebox.askyesno('Start again?', 'Replace the unfinished activity with a new session?', parent=self): return
        self.state_model.begin(kind)
        self.challenge_note = ''
        self.checks = [False] * len(self.state_model.session.get('challenge', {}).get('steps', []))
        self.show('challenge' if kind == 'challenge' else 'companion')

    def page_terms(self):
        self.title_block('01 / Before we begin', 'Your wellbeing. Your choice.', 'Read and answer each statement before entering your private space.')
        panel = self.card()
        self.label(panel, 'Terms & informed consent', 17, bold=True)
        self.terms_copy(panel)
        answers = [tk.BooleanVar(value=False) for _ in range(3)]
        texts = ['I understand the companion’s limits and that it cannot provide professional or emergency care.',
                 'I understand local storage and that a forgotten password cannot be recovered.',
                 'I agree to these prototype terms and choose to continue.']
        def update(): proceed.configure(state='normal' if all(v.get() for v in answers) else 'disabled')
        for text, var in zip(texts, answers): self.check(panel, text, var, update)
        def accept():
            if all(v.get() for v in answers):
                self.state_model.terms_accepted = True
                self.show('login')
        proceed = self.button(panel, 'Agree & continue', accept, enabled=False)
        self.label(panel, 'You can close the application without accepting.', 10, MUTED)

    def terms_copy(self, parent):
        for title, text in TERMS:
            self.label(parent, title, 11, bold=True, pady=(12, 5))
            self.label(parent, text, 10, MUTED)

    def page_login(self):
        register = self.login_mode == 'register'
        self.title_block('02 / Your private space', 'A space of your own.' if register else 'Welcome back.', 'A local account. No email needed.')
        panel = self.card()
        self.button(panel, 'Switch to log in' if register else 'Create a new account', self.toggle_login, secondary=True)
        user = self.field(panel, 'Username')
        self.label(panel, '3–30 letters, numbers or underscores.', 9, MUTED)
        age = self.field(panel, 'Age (18 or older)') if register else None
        password = self.field(panel, 'Password (at least 10 characters)', secret=True)
        confirm = self.field(panel, 'Confirm password', secret=True) if register else None
        def authenticate():
            self.state_model.authenticate(user.get(), password.get(), age.get() if age else None, confirm.get() if confirm else None)
            self.show('profile' if register else 'home')
        self.button(panel, 'Create my account' if register else 'Unlock my space', authenticate)
        password.bind('<Return>', lambda _e: self.safe(authenticate)() if not register else None)
        self.label(panel, 'Keep your password safe. There is no reset link or cloud account.', 10, MUTED)
        self.button(panel, 'Review terms', lambda: self.show('terms'), secondary=True)
        user.focus_set()

    def toggle_login(self):
        self.login_mode = 'login' if self.login_mode == 'register' else 'register'
        self.show('login')

    def page_profile(self):
        self.title_block('Make this space yours', 'A little about you.', 'Your age is required. Everything else is optional.')
        panel = self.card()
        profile = self.state_model.data['profile']
        name = self.field(panel, 'Name or nickname (optional)', profile['name'])
        age = self.field(panel, 'Age (18 or older)', profile['age'])
        personality, _ = self.select(panel, 'How do you describe yourself? (optional)', ['Prefer not to say', 'Introvert', 'Extrovert', 'Ambivert', 'INTJ', 'INFP', 'Other'], profile['personality'])
        interests = self.field(panel, 'Interests (optional)', profile['interests'])
        def save():
            self.state_model.profile(name.get(), age.get(), personality.get(), interests.get())
            self.show('home')
        self.button(panel, 'Save my profile', save)
        self.button(panel, 'Keep current profile', lambda: self.show('home'), secondary=True)

    def mood_picker(self, parent, current, on_select):
        row = tk.Frame(parent, bg=parent.cget('bg'))
        row.pack(fill='x', pady=(6, 12))
        buttons = {}
        for i, (mood, color) in enumerate(MOODS.items()):
            row.columnconfigure(i, weight=1)
            box = tk.Frame(row, bg=row.cget('bg'), padx=3)
            box.grid(row=0, column=i, sticky='nsew')
            face = tk.Canvas(box, height=54, width=60, bg=row.cget('bg'), highlightthickness=0)
            face.pack()
            face.create_oval(8, 4, 52, 48, fill=color, outline=color)
            face.create_oval(20, 19, 23, 22, fill=BG, outline=BG)
            face.create_oval(37, 19, 40, 22, fill=BG, outline=BG)
            if mood == 'Low': face.create_line(21, 36, 30, 30, 39, 36, smooth=True, fill=BG, width=2)
            elif mood == 'Anxious': face.create_line(21, 32, 27, 29, 33, 35, 39, 32, smooth=True, fill=BG, width=2)
            elif mood == 'Okay': face.create_line(21, 32, 39, 32, fill=BG, width=2)
            else: face.create_line(21, 29, 30, 39, 39, 29, smooth=True, fill=BG, width=2)
            def choose(value=mood):
                for name, b in buttons.items(): b.configure(bg='#254A69' if name == value else DEEP, highlightbackground=CYAN if name == value else LINE)
                on_select(value)
            btn = tk.Button(box, text=mood, command=choose, bg='#254A69' if mood == current else DEEP, fg=TEXT,
                            activebackground='#254A69', activeforeground=TEXT, relief='flat', font=('Segoe UI', 10),
                            pady=8, highlightthickness=1, highlightbackground=CYAN if mood == current else LINE)
            btn.pack(fill='x')
            face.bind('<Button-1>', lambda _e, f=choose: f())
            buttons[mood] = btn
        spectrum = tk.Canvas(parent, height=10, bg=parent.cget('bg'), highlightthickness=0)
        spectrum.pack(fill='x', pady=(0, 15))
        def draw(e):
            spectrum.delete('all')
            stops = ['#6A94FF', '#AC84E8', '#F294B4', '#F6CE7B', '#8CD4B1']
            rgb = [tuple(int(h[i:i+2], 16) for i in (1, 3, 5)) for h in stops]
            for x in range(e.width):
                t = x / max(1, e.width - 1) * 4
                idx = min(3, int(t)); f = t - idx
                color = '#' + ''.join(f'{round(a+(b-a)*f):02x}' for a, b in zip(rgb[idx], rgb[idx+1]))
                spectrum.create_line(x, 0, x, 10, fill=color)
        spectrum.bind('<Configure>', draw)

    def page_home(self):
        name = self.state_model.data['profile']['name'] or 'you'
        self.title_block(date.today().strftime('%A, %B %d'), f'A little space for {name}.', 'No perfect answers. Just a moment to check in with yourself.')
        panel = self.card()
        self.label(panel, 'How are you feeling today?', 19, bold=True)
        self.label(panel, 'Choose the emotion closest to how you feel.', 10, MUTED)
        self.mood_picker(panel, self.state_model.mood, lambda v: setattr(self.state_model, 'mood', v))
        self.label(panel, 'Want help naming the feeling? (optional)', 11, bold=True)
        mood_note = self.field(panel, 'Describe how you feel', multiline=True)
        def suggest():
            result = self.emotion_model.predict(mood_note.get('1.0', 'end-1c'))
            if not result['emotion']:
                messagebox.showinfo('Emotion suggestion', 'The small local model has no suggestion for those words. Choose the emotion that fits you.', parent=self)
                return
            if messagebox.askyesno('Confirm emotion suggestion',
                f"The local demo model suggests {result['emotion']}. The closest available spectrum category is {result['mood']}.\n\nUse {result['mood']} for this check-in? This guess can be wrong; it is not a diagnosis.", parent=self):
                self.state_model.mood = result['mood']
                self.show('home')
        self.button(panel, 'Suggest an emotion locally', suggest, secondary=True)
        self.label(panel, 'What would feel right for you?', 13, bold=True)
        self.button(panel, 'Talk it through  →', lambda: self.start('consult'))
        self.label(panel, 'A place to put your thoughts into words.', 10, MUTED)
        self.button(panel, 'Take a small challenge  →', lambda: self.start('challenge'), secondary=True)
        self.streak_card()
        panel = self.card()
        self.label(panel, 'Your emotional rhythm', 17, bold=True)
        self.rhythm(panel)
        self.button(panel, 'See your reflections', lambda: self.show('progress'), secondary=True)
        panel = self.card()
        self.label(panel, 'Connection can be a small step.', 17, bold=True)
        self.label(panel, 'Need support? Choose someone you trust in your circles.', 10, MUTED)
        self.button(panel, 'Visit your circles', lambda: self.show('circles'), secondary=True)

    def streak_card(self):
        panel = self.card()
        days = streak(self.state_model.data['entries'])
        self.label(panel, f'{days} day streak', 20, CYAN, True)
        self.label(panel, 'A day counts when you complete a conversation or challenge. Extra sessions still count as one day.', 10, MUTED)

    def rhythm(self, parent):
        entries = self.state_model.data['entries'][-7:]
        if not entries:
            self.label(parent, 'Your first completed session will appear here.', 11, MUTED)
            return
        canvas = tk.Canvas(parent, height=235, bg=PANEL, highlightthickness=0)
        canvas.pack(fill='x')
        def draw(e):
            canvas.delete('all')
            spacing = e.width / len(entries)
            canvas.create_line(0, 180, e.width, 180, fill=LINE)
            for i, entry in enumerate(entries):
                mood = entry['after']; x = spacing * (i + .5)
                height = 48 + list(MOODS).index(mood) * 24
                width = min(45, spacing * .55)
                canvas.create_rectangle(x-width/2, 180-height, x+width/2, 180, fill=MOODS[mood], outline='')
                canvas.create_text(x, 199, text=mood, fill=TEXT, font=('Segoe UI', 10))
                canvas.create_text(x, 219, text=entry['date'][5:], fill=MUTED, font=('Segoe UI', 9))
        canvas.bind('<Configure>', draw)
        self.label(parent, 'Recent completed sessions • Colors match your chosen emotion. Bar heights show mood categories, not a clinical score.', 9, MUTED)

    def page_companion(self):
        self.title_block('Room for your thoughts', 'Let’s talk it through.', 'You can take your time. What feels most important today?')
        panel = self.card()
        for who, text in self.state_model.messages:
            bubble = tk.Frame(panel, bg=DEEP if who == 'Solace' else '#1D3B5D', padx=16, pady=13)
            bubble.pack(fill='x', padx=(0, 30) if who == 'Solace' else (30, 0), pady=7)
            self.label(bubble, who, 10, CYAN, True)
            self.label(bubble, text, 11)
        prompt = self.field(panel, 'Your message', multiline=True)
        def send():
            value = prompt.get('1.0', 'end-1c')
            if value.strip():
                self.state_model.reply(value)
                self.show('companion')
                self.after_idle(lambda: self.canvas.yview_moveto(1))
        self.button(panel, 'Send message', send)
        prompt.bind('<Control-Return>', lambda _e: self.safe(send)() or 'break')
        self.button(panel, 'Finish & reflect', self.open_feedback, secondary=True)
        self.label(panel, 'This frontend uses sample responses. Connect an on-device model in core.py to enable real AI.', 9, MUTED)
        prompt.focus_set()

    def page_challenge(self):
        challenge = self.state_model.session['challenge']
        self.title_block('Small steps / ' + self.state_model.session['before'], challenge['name'], challenge['desc'])
        panel = self.card()
        self.label(panel, challenge['time'] + ' • Go at your own pace', 10, CYAN, True)
        variables = [tk.BooleanVar(value=v) for v in self.checks]
        note = None
        def update():
            self.checks = [v.get() for v in variables]
            complete.configure(state='normal' if all(self.checks) else 'disabled')
        for i, (step, var) in enumerate(zip(challenge['steps'], variables), 1): self.check(panel, f'{i}.  {step}', var, update)
        note = self.field(panel, 'A thought to keep (optional)', self.challenge_note, multiline=True)
        def finish():
            self.challenge_note = note.get('1.0', 'end-1c')
            self.open_feedback()
        complete = self.button(panel, 'Finished — reflect on it', finish, enabled=all(self.checks))
        self.button(panel, 'Pause and return to today', lambda: self.show('home'), secondary=True)
        self.label(panel, 'You can stop whenever you need to. An unfinished challenge does not add a streak day.', 10, MUTED)

    def open_feedback(self):
        if not self.state_model.session: raise ValueError('Start an activity first.')
        if self.state_model.session['type'] == 'challenge' and not all(self.checks): raise ValueError('Check each completed step first.')
        self.feedback_mood = self.state_model.session['before']
        self.show('feedback')

    def page_feedback(self):
        self.title_block('Notice this moment', 'How do you feel now?', 'Any answer is welcome. A different emotion is not required.')
        panel = self.card()
        self.mood_picker(panel, self.feedback_mood, lambda v: setattr(self, 'feedback_mood', v))
        note = self.field(panel, 'Your reflection (optional)', self.challenge_note if self.state_model.session['type'] == 'challenge' else '', multiline=True)
        def save():
            self.last_entry = self.state_model.finish(self.feedback_mood, note.get('1.0', 'end-1c'), self.checks)
            self.show('friend_question' if self.last_entry['type'] == 'challenge' else 'success')
        self.button(panel, 'Save my reflection', save)
        self.button(panel, 'Back to activity', lambda: self.show('challenge' if self.state_model.session['type'] == 'challenge' else 'companion'), secondary=True)

    def page_friend_question(self):
        self.title_block('A new connection?', 'Did you gain a friend?', 'If your challenge led to a new connection, you can add them to a circle.')
        panel = self.card()
        self.button(panel, 'Yes — add them to a circle', lambda: self.show('friend_form'))
        def no():
            self.state_model.no_new_friend()
            self.show('success')
        self.button(panel, 'Not this time', no, secondary=True)
        self.label(panel, 'Making a friend is optional. Your completed challenge already counts.', 10, MUTED)

    def page_friend_form(self):
        self.title_block('Keep the connection', 'Add your new friend.', 'Choose a circle that feels right, or create a new one.')
        panel = self.card()
        self.friend_fields(panel, True)
        self.button(panel, 'Back', lambda: self.show('friend_question'), secondary=True)

    def friend_fields(self, panel, from_challenge=False):
        name = self.field(panel, 'Friend’s name')
        marker = '+ Create a new circle'
        options = self.state_model.data['circles'] + [marker]
        circle, _ = self.select(panel, 'Circle', options)
        new_circle = self.field(panel, 'New circle name (only if creating one)')
        def save():
            creating = circle.get() == marker
            self.state_model.friend(name.get(), new_circle.get() if creating else circle.get(), creating, from_challenge)
            self.show('success' if from_challenge else 'circles')
        self.button(panel, 'Save connection', save)

    def page_success(self):
        self.title_block('You showed up', 'A step worth keeping.', 'Your reflection is saved. You can rest here or try another small step.')
        self.streak_card()
        panel = self.card()
        recent = self.last_entry or (self.state_model.data['entries'][-1] if self.state_model.data['entries'] else None)
        mood = recent['before'] if recent else self.state_model.mood
        challenge = next_challenge(self.state_model.data, mood)
        self.label(panel, 'YOUR NEXT CHALLENGE IS READY', 10, CYAN, True)
        self.label(panel, challenge['name'], 20, bold=True)
        self.label(panel, challenge['desc'], 11, MUTED)
        def start_next():
            self.state_model.mood = mood
            self.start('challenge')
        self.button(panel, 'Start next challenge', start_next)
        self.button(panel, 'I’m done for today', lambda: self.show('home'), secondary=True)

    def page_progress(self):
        self.title_block('Your own pace', 'Small steps, over time.', 'Progress is showing up, whatever your mood looks like.')
        self.streak_card()
        panel = self.card()
        self.label(panel, 'Your emotional rhythm', 18, bold=True)
        self.rhythm(panel)
        self.label(self.body, 'Your reflections', 18, bold=True)
        entries = self.state_model.data['entries']
        if not entries: self.label(self.body, 'Your story starts with one check-in.', 11, MUTED)
        for entry in reversed(entries):
            panel = self.card()
            self.label(panel, entry['challenge_name'] if entry['type'] == 'challenge' else 'Conversation', 15, bold=True)
            self.label(panel, entry['date'] + '  •  Before: ' + entry['before'] + '  →  After: ' + entry['after'], 10, CYAN)
            if entry['note']: self.label(panel, entry['note'], 11)
            if entry['made_friend']: self.label(panel, 'A new connection was added to your circles.', 10, MUTED)
            def delete_entry(ident=entry['id']):
                if messagebox.askyesno('Delete reflection?', 'Permanently delete this session and reflection? The streak will be recalculated.', parent=self):
                    self.state_model.delete_entry(ident)
                    self.show('progress')
            self.button(panel, 'Delete reflection', delete_entry, secondary=True)

    def page_circles(self):
        self.title_block('People who matter', 'Your circles.', 'Reach out to someone you trust. Solace keeps a list; it does not contact people automatically.')
        panel = self.card()
        def create():
            name = simpledialog.askstring('New circle', 'Circle name:', parent=self)
            if name is not None:
                self.state_model.circle(name)
                self.show('circles')
        self.button(panel, '+ Create a circle', create)
        self.label(panel, 'Add a connection', 15, bold=True)
        self.friend_fields(panel)
        for circle in self.state_model.data['circles']:
            panel = self.card()
            people = [p for p in self.state_model.data['friends'] if p['circle'] == circle]
            self.label(panel, circle, 18, bold=True)
            self.label(panel, f'{len(people)} connections', 10, MUTED)
            if any(p.get('trusted') for p in people): self.label(panel, '★ = someone you have marked as trusted for support', 9, CYAN)
            for person in people:
                row = tk.Frame(panel, bg=PANEL)
                row.pack(fill='x', pady=4)
                tk.Label(row, text=('★ ' if person.get('trusted') else '') + person['name'], bg=PANEL, fg=TEXT, font=('Segoe UI', 11), anchor='w', wraplength=400).pack(side='left', fill='x', expand=True)
                def remove(p=person):
                    if messagebox.askyesno('Remove connection?', f'Remove {p["name"]} from this circle?', parent=self):
                        self.state_model.remove_friend(p['id'])
                        self.show('circles')
                tk.Button(row, text='Remove', bg=DEEP, fg=MUTED, activebackground=LINE, activeforeground=TEXT, relief='flat', padx=10, pady=5, command=self.safe(remove)).pack(side='right')
                trusted = tk.BooleanVar(value=person.get('trusted', False))
                def toggle_trust(p=person, var=trusted):
                    self.state_model.edit_friend(p['id'], trusted=var.get())
                self.check(panel, 'Trusted support contact: ' + person['name'], trusted, self.safe(toggle_trust))
                move_to, _ = self.select(panel, 'Move ' + person['name'] + ' to circle', self.state_model.data['circles'], person['circle'])
                def move(p=person, target=move_to):
                    self.state_model.edit_friend(p['id'], circle=target.get())
                    self.show('circles')
                self.button(panel, 'Move connection', move, secondary=True)
            if not people: self.label(panel, 'No connections here yet.', 10, MUTED)
            def rename(c=circle):
                name = simpledialog.askstring('Rename circle', 'Circle name:', initialvalue=c, parent=self)
                if name is not None:
                    self.state_model.circle(name, c)
                    self.show('circles')
            def delete(c=circle):
                if messagebox.askyesno('Remove circle?', f'Remove {c} and all its saved connections? This cannot be undone.', parent=self):
                    self.state_model.remove_circle(c)
                    self.show('circles')
            self.button(panel, 'Rename circle', rename, secondary=True)
            self.button(panel, 'Remove circle', delete, secondary=True)

    def page_settings(self):
        self.title_block('Make room for you', 'Your settings.', 'Your profile, your preferences, your pace.')
        panel = self.card()
        self.label(panel, self.state_model.data['profile']['name'] or 'Your account', 20, bold=True)
        self.label(panel, '@' + self.state_model.vault['username'], 10, MUTED)
        self.button(panel, 'Edit profile', lambda: self.show('profile'), secondary=True)
        self.button(panel, 'Change password', lambda: self.show('password'), secondary=True)
        glow = tk.BooleanVar(value=self.state_model.data['glow'])
        def set_glow():
            updated = copy.deepcopy(self.state_model.data)
            updated['glow'] = glow.get()
            try: self.state_model.commit(updated)
            except Exception:
                glow.set(not glow.get())
                raise
        self.check(panel, 'Buttons glow on hover and keyboard focus', glow, self.safe(set_glow))
        self.button(panel, 'Terms & privacy', lambda: self.show('privacy'), secondary=True)
        self.button(panel, 'Need support? Visit your circles', lambda: self.show('circles'), secondary=True)
        self.button(panel, 'Log out', self.logout, secondary=True)
        def delete():
            if messagebox.askyesno('Delete local account?', 'Permanently remove your account, reflections and circles from this computer? There is no undo.', parent=self):
                self.state_model.store.delete(self.state_model.vault)
                self.state_model.logout()
                self.last_entry = None
                self.login_mode = 'register'
                self.show('login')
        self.button(panel, 'Delete local account', delete, secondary=True)

    def page_password(self):
        self.title_block('Protect your space', 'Change your password.', 'Use at least 10 characters. There is no password recovery.')
        panel = self.card()
        old = self.field(panel, 'Current password', secret=True)
        new = self.field(panel, 'New password', secret=True)
        confirm = self.field(panel, 'Confirm new password', secret=True)
        def update():
            if new.get() != confirm.get(): raise ValueError('New passwords do not match.')
            self.state_model.vault = self.state_model.store.password(self.state_model.vault, self.state_model.data, old.get(), new.get())
            messagebox.showinfo('Solace', 'Password updated.', parent=self)
            self.show('settings')
        self.button(panel, 'Update password', update)
        self.button(panel, 'Cancel', lambda: self.show('settings'), secondary=True)

    def page_privacy(self):
        self.title_block('Your choices', 'Terms & privacy.', 'Review the acknowledgements for this version of Solace.')
        panel = self.card()
        self.terms_copy(panel)
        self.label(panel, 'Saved profile, reflections and circles are encrypted in your Windows user’s local application-data folder. The encryption key is derived from your password; passwords are not saved as plaintext. Conversations stay in memory until you finish or leave the application. This prototype has not undergone a production security audit.', 10, MUTED)
        self.label(panel, 'Accepted: ' + self.state_model.data['accepted_at'], 9, MUTED)
        self.label(panel, 'Version: ' + self.state_model.data['accepted_terms'], 9, MUTED)
        self.button(panel, 'Back to settings', lambda: self.show('settings'), secondary=True)

    def logout(self):
        if self.state_model.session and not messagebox.askyesno('Log out?', 'Discard the unfinished activity and log out?', parent=self): return
        self.state_model.logout()
        self.last_entry = None
        self.checks = []
        self.challenge_note = ''
        self.login_mode = 'login'
        self.show('login')

    def close_app(self):
        if self.state_model.session and not messagebox.askyesno('Close Solace?', 'This activity is unfinished. Close without saving it?', parent=self): return
        self.destroy()


def main():
    try:
        # Improve sharpness on Windows high-DPI displays, before creating Tk.
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError): pass
    SolaceApp().mainloop()

if __name__ == '__main__':
    main()
