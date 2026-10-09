"""Solace Desktop — redesigned native Python interface."""
import copy
import queue
import threading
import local_ai
import sys
from datetime import date
import tkinter as tk
from tkinter import messagebox, simpledialog
import customtkinter as ctk
from legacy_ui import SolaceApp as BaseApp
from core import MOODS, streak, next_challenge

BG = '#0B1120'
SIDE = '#0E1729'
PANEL = '#131F33'
INNER = '#17263E'
LINE = '#263851'
TEXT = '#F0F5FF'
MUTED = '#93A7C3'
CYAN = '#9CCFFF'
ACCENT = '#83BDF8'
FONT = 'Segoe UI' if sys.platform == 'win32' else 'DejaVu Sans'

class SolaceApp(BaseApp):
    def __init__(self):
        self.ai_busy = False
        self.ai_results = queue.Queue()
        self.ai_failure = None
        ctk.set_appearance_mode('dark')
        ctk.set_default_color_theme('blue')
        super().__init__()
        self.title('Solace')
        self.geometry('1280x850')
        self.minsize(1024, 700)
        self.configure(bg=BG)

    def color(self, parent):
        try:
            value = parent.cget('fg_color')
            if isinstance(value, tuple): value = value[1]
            if value != 'transparent': return value
        except (ValueError, tk.TclError): pass
        try: return parent.cget('bg')
        except (ValueError, tk.TclError): return PANEL

    def label(self, parent, text, size=11, color=TEXT, bold=False, pady=(0, 8)):
        widget = tk.Label(parent, text=text, bg=self.color(parent), fg=color,
            font=(FONT, size, 'bold' if bold else 'normal'), anchor='w', justify='left')
        widget.pack(fill='x', pady=pady)
        widget.bind('<Configure>', lambda e: widget.configure(wraplength=max(100, e.width - 4)))
        return widget

    def button(self, parent, text, action, secondary=False, enabled=True):
        normal = INNER if secondary else ACCENT
        button = ctk.CTkButton(parent, text=text, command=self.safe(action), height=43,
            corner_radius=11, fg_color=normal, hover_color='#263F60' if secondary else '#ACD6FF',
            text_color=TEXT if secondary else '#0C2139', text_color_disabled='#657C9A',
            border_width=1 if secondary else 0, border_color=LINE,
            font=(FONT, 14, 'bold'), anchor='center', state='normal' if enabled else 'disabled')
        button.pack(fill='x', pady=(5, 8))
        glow = not self.state_model.data or self.state_model.data.get('glow', True)
        button.configure(hover=glow)
        button.bind('<FocusIn>', lambda _e: button.configure(border_width=2, border_color=CYAN))
        button.bind('<FocusOut>', lambda _e: button.configure(border_width=1 if secondary else 0, border_color=LINE))
        button.bind('<Return>', lambda _e: button.invoke())
        # CTk's canvas-based buttons need an explicit keyboard focus target.
        button._canvas.configure(takefocus=1)
        return button

    def card(self, parent=None):
        parent = parent or self.body
        outer = ctk.CTkFrame(parent, fg_color=PANEL, border_width=1, border_color=LINE, corner_radius=18)
        outer.pack(fill='x', pady=(0, 18))
        inner = tk.Frame(outer, bg=PANEL)
        inner.pack(fill='both', expand=True, padx=23, pady=21)
        return inner

    def title_block(self, eyebrow, title, subtitle=''):
        self.label(self.body, eyebrow.upper(), 9, CYAN, True, (0, 9))
        self.label(self.body, title, 27, TEXT, True, (0, 9))
        if subtitle: self.label(self.body, subtitle, 11, MUTED, pady=(0, 25))

    def field(self, parent, title, value='', secret=False, multiline=False):
        self.label(parent, title, 10, MUTED, pady=(8, 7))
        if multiline:
            field = ctk.CTkTextbox(parent, height=105, corner_radius=10, border_width=1,
                border_color=LINE, fg_color=BG, text_color=TEXT, font=(FONT, 14), wrap='word')
            field.insert('1.0', value)
        else:
            field = ctk.CTkEntry(parent, height=43, corner_radius=10, border_width=1,
                border_color=LINE, fg_color=BG, text_color=TEXT, font=(FONT, 14), show='•' if secret else '')
            field.insert(0, str(value))
        field.pack(fill='x', pady=(0, 9))
        return field

    def select(self, parent, title, options, current=''):
        self.label(parent, title, 10, MUTED, pady=(8, 7))
        value = tk.StringVar(value=current or (options[0] if options else ''))
        combo = ctk.CTkComboBox(parent, variable=value, values=options, state='readonly',
            height=43, corner_radius=10, fg_color=BG, border_color=LINE, button_color=LINE,
            button_hover_color='#385473', text_color=TEXT, dropdown_fg_color=INNER,
            dropdown_hover_color='#284464', font=(FONT, 14))
        combo.pack(fill='x', pady=(0, 9))
        return value, combo

    def check(self, parent, text, var, command=None):
        row = tk.Frame(parent, bg=self.color(parent))
        row.pack(fill='x', pady=8)
        checkbox = ctk.CTkCheckBox(row, text='', variable=var, command=command, width=26,
            checkbox_width=21, checkbox_height=21, corner_radius=6, border_width=1,
            border_color='#456080', fg_color=ACCENT, checkmark_color=BG, hover_color='#456080')
        checkbox.pack(side='left', anchor='n', pady=4)
        label = tk.Label(row, text=text, bg=self.color(parent), fg=TEXT, justify='left', anchor='w', font=(FONT, 11))
        label.pack(side='left', fill='x', expand=True, padx=(10, 0))
        label.bind('<Configure>', lambda e: label.configure(wraplength=max(100, e.width - 3)))
        label.bind('<Button-1>', lambda _e: checkbox.toggle())
        return checkbox

    def show(self, page):
        if page not in ('terms', 'login'): self.state_model.require_account()
        if self.state_model.pending_entry and page not in ('friend_question', 'friend_form', 'success'): page = 'friend_question'
        self.page = page
        for widget in self.winfo_children(): widget.destroy()
        logged = bool(self.state_model.vault)
        if not logged: self.ai_failure = None
        shell = tk.Frame(self, bg=BG)
        shell.pack(fill='both', expand=True)
        sidebar = tk.Frame(shell, bg=SIDE, width=222)
        sidebar.pack(side='left', fill='y')
        sidebar.pack_propagate(False)
        brand = tk.Frame(sidebar, bg=SIDE)
        brand.pack(fill='x', padx=24, pady=(32, 28))
        if self.logo: tk.Label(brand, image=self.logo, bg=SIDE).pack(side='left', padx=(0, 10))
        tk.Label(brand, text='solace', bg=SIDE, fg=TEXT, font=(FONT, 24, 'bold')).pack(side='left')
        nav = tk.Frame(sidebar, bg=SIDE)
        nav.pack(fill='x', padx=15)
        self.label(nav, '   YOUR SPACE', 8, MUTED, True, (0, 15))
        icons = {'home': '⌂', 'companion': '◇', 'challenge': '✧', 'progress': '▥', 'circles': '◎', 'settings': '⚙'}
        if logged:
            for name, target in [('Overview', 'home'), ('Companion', 'companion'), ('Challenges', 'challenge'), ('Your progress', 'progress'), ('Your circles', 'circles')]:
                active = page == target
                b = ctk.CTkButton(nav, text=f'  {icons[target]}    {name}', height=45, corner_radius=11, anchor='w',
                    font=(FONT, 14, 'bold' if active else 'normal'), fg_color='#203A59' if active else 'transparent',
                    hover_color='#192C45', text_color=CYAN if active else MUTED,
                    command=self.safe(lambda p=target: self.navigate(p)), state='disabled' if self.state_model.pending_entry else 'normal')
                b.pack(fill='x', pady=4)
            bottom = tk.Frame(sidebar, bg=SIDE)
            bottom.pack(side='bottom', fill='x', padx=18, pady=22)
            self.button(bottom, 'Settings', lambda: self.show('settings'), secondary=True, enabled=not bool(self.state_model.pending_entry))
            self.label(bottom, self.state_model.data['profile']['name'] or self.state_model.vault['username'], 11, TEXT, True, (14, 3))
            self.label(bottom, 'Your personal space', 9, MUTED)
            support = ctk.CTkFrame(sidebar, fg_color='#172B43', corner_radius=14)
            support.pack(side='bottom', fill='x', padx=18, pady=12)
            support_inner = tk.Frame(support, bg='#172B43')
            support_inner.pack(fill='x', padx=14, pady=14)
            self.label(support_inner, 'You’re not on your own.', 10, TEXT, True)
            self.label(support_inner, 'A familiar person can help.', 9, MUTED)
            self.button(support_inner, 'Find your circle  →', lambda: self.show('circles'), secondary=True, enabled=not bool(self.state_model.pending_entry))
        else:
            self.label(nav, 'A quieter place\nto check in.', 20, TEXT, True)
            self.label(nav, 'Small steps.\nAt your own pace.', 11, MUTED, pady=(12, 10))
            self.label(sidebar, '   MADE FOR YOUR EVERYDAY', 8, MUTED)
        main = tk.Frame(shell, bg=BG)
        main.pack(side='left', fill='both', expand=True)
        top = tk.Frame(main, bg=BG, height=69)
        top.pack(fill='x', padx=32)
        top.pack_propagate(False)
        names = {'home':'Overview','companion':'Companion','challenge':'Challenges','progress':'Your progress','circles':'Your circles','settings':'Settings','terms':'Welcome','login':'Your account'}
        tk.Label(top, text='Your space   /   '+names.get(page, page.replace('_',' ').title()), font=(FONT, 10), bg=BG, fg=MUTED).pack(side='left')
        tk.Label(top, text=date.today().strftime('%a, %d %b'), font=(FONT, 10), bg=BG, fg=MUTED).pack(side='right')
        tk.Frame(main, bg=LINE, height=1).pack(fill='x')
        scroll = ctk.CTkScrollableFrame(main, corner_radius=0, fg_color=BG, scrollbar_button_color=LINE,
            scrollbar_button_hover_color='#456080')
        scroll.pack(fill='both', expand=True)
        self.canvas = scroll._parent_canvas
        self.body = tk.Frame(scroll, bg=BG, padx=26, pady=25)
        self.body.pack(fill='both', expand=True)
        # Profile/onboarding forms have a readable line length on wide monitors.
        if page in ('terms','login','profile','password','feedback','friend_question','friend_form','success','privacy'):
            shell_body = self.body
            self.body = tk.Frame(shell_body, bg=BG, width=720)
            self.body.pack(fill='x', padx=32)
        getattr(self, 'page_'+page)()
        self.label(self.body, 'YOUR PACE. YOUR SPACE.                                      solace', 8, MUTED, pady=(22, 10))
        self.canvas.yview_moveto(0)

    def wheel(self, event):
        # CustomTkinter owns wheel scrolling and textbox routing.
        pass

    def mood_picker(self, parent, current, on_select):
        row = tk.Frame(parent, bg=self.color(parent))
        row.pack(fill='x', pady=(14, 13))
        buttons = {}
        for i, (mood, color) in enumerate(MOODS.items()):
            row.columnconfigure(i, weight=1, uniform='moods')
            cell = tk.Frame(row, bg=self.color(parent))
            cell.grid(row=0, column=i, sticky='nsew', padx=4)
            face = tk.Canvas(cell, height=57, width=58, bg=self.color(parent), highlightthickness=0)
            face.pack()
            face.create_oval(8, 3, 50, 45, fill=color, outline='')
            for x in [20,35]: face.create_oval(x,17,x+3,20,fill=BG,outline='')
            if mood == 'Low': points=[19,34,29,27,39,34]
            elif mood == 'Anxious': points=[19,30,24,27,33,33,39,30]
            elif mood == 'Okay': points=[20,30,38,30]
            else: points=[19,26,29,37,39,26]
            face.create_line(*points, fill=BG, width=2, smooth=True)
            def choose(value=mood):
                for name,b in buttons.items(): b.configure(fg_color='#284665' if name==value else INNER, border_color=CYAN if name==value else LINE)
                on_select(value)
            b=ctk.CTkButton(cell,text=mood,height=35,corner_radius=9,font=(FONT,12),text_color=TEXT,
                fg_color='#284665' if mood==current else INNER,hover_color='#284665',border_width=1,
                border_color=CYAN if mood==current else LINE,command=choose,width=60)
            b.pack(fill='x'); buttons[mood]=b
            face.bind('<Button-1>',lambda _e,f=choose:f())
        spectrum=tk.Canvas(parent,height=5,bg=self.color(parent),highlightthickness=0)
        spectrum.pack(fill='x',pady=(0,14))
        def draw(e):
            spectrum.delete('all')
            stops=['#719DE6','#AD91D6','#D7A8CE','#E6C68B','#91C6AD']
            for i,color in enumerate(stops): spectrum.create_rectangle(i*e.width/5,0,(i+1)*e.width/5,5,fill=color,outline='')
        spectrum.bind('<Configure>',draw)

    def page_home(self):
        data=self.state_model.data
        name=data['profile']['name'] or 'there'
        self.title_block('A moment for yourself',f'Welcome back, {name}.','How you feel matters. Let’s make a little room for it today.')
        grid=tk.Frame(self.body,bg=BG); grid.pack(fill='x')
        grid.columnconfigure(0,weight=3,uniform='top');grid.columnconfigure(1,weight=2,uniform='top')
        left=tk.Frame(grid,bg=BG);left.grid(row=0,column=0,sticky='nsew',padx=(0,16))
        right=tk.Frame(grid,bg=BG);right.grid(row=0,column=1,sticky='nsew')
        panel=self.card(left)
        self.label(panel,'DAILY CHECK-IN',9,CYAN,True)
        self.label(panel,'How are you feeling?',21,TEXT,True)
        self.label(panel,'There’s no right or wrong answer.',10,MUTED)
        self.mood_picker(panel,self.state_model.mood,lambda value:setattr(self.state_model,'mood',value))
        self.button(panel,'Talk it through  →',lambda:self.start('consult'))
        self.button(panel,'Try a small challenge',lambda:self.start('challenge'),secondary=True)
        panel=self.card(right)
        self.label(panel,'YOUR CONSISTENCY',9,CYAN,True)
        self.label(panel,str(streak(data['entries'])),38,TEXT,True,pady=(2,0))
        self.label(panel,'day streak',13,MUTED)
        self.label(panel,'One small act of care is enough.',10,MUTED,pady=(8,12))
        self.label(panel,f'{len(data["entries"])} sessions completed',10,TEXT)
        self.label(panel,f'{len(data["circles"])} circles to come back to',10,TEXT)
        self.button(panel,'View your progress  →',lambda:self.show('progress'),secondary=True)
        panel=self.card()
        self.label(panel,'YOUR EMOTIONAL RHYTHM',9,CYAN,True)
        self.label(panel,'A little perspective.',19,TEXT,True)
        self.rhythm(panel)
        bottom=tk.Frame(self.body,bg=BG);bottom.pack(fill='x')
        bottom.columnconfigure(0,weight=1,uniform='bottom');bottom.columnconfigure(1,weight=1,uniform='bottom')
        one=tk.Frame(bottom,bg=BG);one.grid(row=0,column=0,sticky='nsew',padx=(0,16))
        two=tk.Frame(bottom,bg=BG);two.grid(row=0,column=1,sticky='nsew')
        panel=self.card(one)
        self.label(panel,'FIND THE WORDS',9,CYAN,True)
        self.label(panel,'Not sure how you feel?',16,TEXT,True)
        self.label(panel,'Describe your day and explore a suggested emotion.',10,MUTED)
        self.button(panel,'Explore my feeling  →',lambda:self.show('emotion'),secondary=True)
        panel=self.card(two)
        self.label(panel,'YOUR PEOPLE',9,CYAN,True)
        self.label(panel,'Connection starts small.',16,TEXT,True)
        self.label(panel,'Keep the people who matter within reach.',10,MUTED)
        self.button(panel,'Open your circles  →',lambda:self.show('circles'),secondary=True)

    def page_emotion(self):
        self.title_block('Find the words','What’s on your mind?','An optional local suggestion. You decide what fits.')
        panel=self.card();note=self.field(panel,'A few words about today',multiline=True)
        def suggest():
            result=self.emotion_model.predict(note.get('1.0','end-1c'))
            if not result['emotion']:
                messagebox.showinfo('Your feeling','No suggestion for these words. You can choose your feeling on Overview.',parent=self);return
            if messagebox.askyesno('Does this fit?',f'The local model suggests {result["emotion"]}. Use {result["mood"]} on your emotion spectrum? You can change it anytime.',parent=self):
                self.state_model.mood=result['mood'];self.show('home')
        self.button(panel,'Suggest an emotion',suggest)
        self.button(panel,'Back to overview',lambda:self.show('home'),secondary=True)
        self.label(panel,'This small model can be wrong. Its suggestion is not a diagnosis.',9,MUTED)

    def rhythm(self,parent):
        entries=self.state_model.data['entries'][-7:]
        canvas=tk.Canvas(parent,height=205,bg=self.color(parent),highlightthickness=0)
        canvas.pack(fill='x',pady=(8,0))
        def draw(e):
            canvas.delete('all');w=e.width
            for y in [35,85,135]:canvas.create_line(12,y,w-12,y,fill='#21334C',dash=(3,6))
            if not entries:
                canvas.create_text(w/2,76,text='Your story starts with one check-in.',fill=TEXT,font=(FONT,13,'bold'))
                canvas.create_text(w/2,105,text='Complete a conversation or challenge to see your rhythm.',fill=MUTED,font=(FONT,10));return
            space=(w-24)/max(7,len(entries))
            for i,entry in enumerate(entries):
                mood=entry['after']; x=12+space*(i+.5);h=35+list(MOODS).index(mood)*25
                canvas.create_line(x,152-h,x,152,fill=MOODS[mood],width=min(32,space*.4),capstyle='round')
                canvas.create_text(x,177,text=mood,fill=TEXT,font=(FONT,10))
                canvas.create_text(x,196,text=entry['date'][5:],fill=MUTED,font=(FONT,8))
        canvas.bind('<Configure>',draw)
        self.label(parent,'Last 7 sessions · Your emotions, not a clinical score.',9,MUTED)

    def page_companion(self):
        self.title_block('A listening space','Room for your thoughts.','Take your time. You don’t have to have it all figured out.')
        panel=self.card()
        for who,text in self.state_model.messages:
            outer=ctk.CTkFrame(panel,fg_color=INNER if who=='Solace' else '#234260',corner_radius=14)
            outer.pack(fill='x',padx=(0,85) if who=='Solace' else (85,0),pady=7)
            inner=tk.Frame(outer,bg=INNER if who=='Solace' else '#234260');inner.pack(fill='x',padx=18,pady=15)
            self.label(inner,who.upper(),8,CYAN,True)
            self.label(inner,text,11)
        failed = self.ai_failure if self.ai_failure and self.ai_failure[0] is self.state_model.session else None
        if self.ai_busy:
            self.label(panel,'Thinking locally… The first reply may take a little longer.',10,CYAN)
        if failed:
            self.label(panel,failed[2],10,'#F0B5B5')
        prompt=self.field(panel,'Your message',failed[1] if failed else '',multiline=True)
        def send():
            value=prompt.get('1.0','end-1c').strip()
            if not value or self.ai_busy: return
            if len(value)>1500: raise ValueError('Please use 1500 characters or fewer per message.')
            self.state_model.require_account()
            session=self.state_model.session
            if not session or session['type']!='consult': return
            self.state_model.messages.append(('You',value))
            history=list(self.state_model.messages)
            self.ai_busy=True
            self.ai_failure=None
            self.show('companion')
            self.after_idle(lambda:self.canvas.yview_moveto(1))
            def generate():
                try: self.ai_results.put((session,value,local_ai.chat(history),None))
                except Exception as exc:
                    error=str(exc) if isinstance(exc,local_ai.LocalAIError) else 'The local AI request failed. Check Ollama and retry.'
                    self.ai_results.put((session,value,None,error))
            threading.Thread(target=generate,daemon=True).start()
            self.after(150,self.poll_ai)
        actions=tk.Frame(panel,bg=PANEL);actions.pack(fill='x')
        left=tk.Frame(actions,bg=PANEL);left.pack(side='left',fill='x',expand=True,padx=(0,12))
        right=tk.Frame(actions,bg=PANEL);right.pack(side='left',fill='x',expand=True)
        self.button(left,'Thinking…' if self.ai_busy else 'Send message  →',send,enabled=not self.ai_busy)
        self.button(right,'Finish & reflect',self.open_feedback,secondary=True,enabled=not self.ai_busy)
        prompt.bind('<Control-Return>',lambda _e:self.safe(send)() or 'break')
        self.label(panel,'Ctrl + Enter to send · '+local_ai.MODEL+' · Runs on your computer',9,MUTED)
        prompt.focus_set()

    def poll_ai(self):
        # This method runs on Tk's main thread. Workers only write to the queue.
        try:
            session,value,response,error=self.ai_results.get_nowait()
        except queue.Empty:
            self.after(150,self.poll_ai)
            return
        self.ai_busy=False
        if self.state_model.vault and self.state_model.session is session:
            if error:
                if self.state_model.messages and self.state_model.messages[-1]==('You',value):
                    self.state_model.messages.pop()
                self.ai_failure=(session,value,error)
            else:
                self.state_model.messages.append(('Solace',response))
                self.ai_failure=None
        else:
            # Ignore replies from an abandoned activity or a logged-out account.
            self.ai_failure=None
        if self.page=='companion' and self.state_model.vault:
            self.show('companion')
            self.after_idle(lambda:self.canvas.yview_moveto(1))

    def page_circles(self):
        self.title_block('Your people','Good company. Your circles.','A place for the people you want to stay connected with.')
        toolbar=tk.Frame(self.body,bg=BG);toolbar.pack(fill='x',pady=(0,16))
        left=tk.Frame(toolbar,bg=BG);left.pack(side='left',fill='x',expand=True,padx=(0,14))
        right=tk.Frame(toolbar,bg=BG);right.pack(side='left',fill='x',expand=True)
        self.button(left,'+  Add a connection',lambda:self.show('add_connection'))
        def create():
            name=simpledialog.askstring('New circle','Circle name:',parent=self)
            if name is not None:self.state_model.circle(name);self.show('circles')
        self.button(right,'+  Create a circle',create,secondary=True)
        grid=tk.Frame(self.body,bg=BG);grid.pack(fill='x')
        for col in range(2):grid.columnconfigure(col,weight=1,uniform='circles')
        for idx,circle in enumerate(self.state_model.data['circles']):
            cell=tk.Frame(grid,bg=BG);cell.grid(row=idx//2,column=idx%2,sticky='nsew',padx=(0,14) if idx%2==0 else 0)
            panel=self.card(cell);people=[p for p in self.state_model.data['friends'] if p['circle']==circle]
            self.label(panel,'◎',23,CYAN)
            self.label(panel,circle,18,TEXT,True)
            self.label(panel,f'{len(people)} connections',10,MUTED)
            if not people:self.label(panel,'A little room for new connections.',10,MUTED,pady=(12,20))
            for person in people:
                self.button(panel,('★  ' if person.get('trusted') else '○  ')+person['name']+'   ›',lambda p=person:self.open_person(p),secondary=True)
            def rename(c=circle):
                name=simpledialog.askstring('Rename circle','Circle name:',initialvalue=c,parent=self)
                if name is not None:self.state_model.circle(name,c);self.show('circles')
            def remove(c=circle):
                if messagebox.askyesno('Remove circle?',f'Remove {c} and its saved connections?',parent=self):self.state_model.remove_circle(c);self.show('circles')
            row=tk.Frame(panel,bg=PANEL);row.pack(fill='x',pady=(8,0))
            for title,fn in [('Rename',rename),('Remove',remove)]:
                ctk.CTkButton(row,text=title,width=85,height=30,fg_color='transparent',hover_color=INNER,text_color=MUTED,command=self.safe(fn)).pack(side='left',padx=(0,10))
        self.label(self.body,'Select a connection to move, remove or mark them as a trusted support contact.',10,MUTED)

    def page_add_connection(self):
        self.title_block('Keep the connection','Add someone to your circle.','Your circles are private. Adding someone does not send a message.')
        self.friend_fields(self.card())
        self.button(self.body,'Back to circles',lambda:self.show('circles'),secondary=True)

    def open_person(self,person):
        self.person_id=person['id'];self.show('person')

    def page_person(self):
        person=next(p for p in self.state_model.data['friends'] if p['id']==self.person_id)
        self.title_block('Your connections',person['name'],'A familiar person, a little closer.')
        panel=self.card();circle,_=self.select(panel,'Circle',self.state_model.data['circles'],person['circle'])
        trusted=tk.BooleanVar(value=person.get('trusted',False));self.check(panel,'Mark as a trusted person for support',trusted)
        def save():self.state_model.edit_friend(person['id'],circle=circle.get(),trusted=trusted.get());self.show('circles')
        self.button(panel,'Save connection',save)
        def remove():
            if messagebox.askyesno('Remove connection?',f'Remove {person["name"]}?',parent=self):self.state_model.remove_friend(person['id']);self.show('circles')
        self.button(panel,'Remove connection',remove,secondary=True)
        self.button(panel,'Back to circles',lambda:self.show('circles'),secondary=True)

    def page_settings(self):
        self.title_block('Make it yours','Your space, your way.','A few preferences to help you feel at home.')
        panel=self.card();self.label(panel,'Your account',18,TEXT,True)
        self.label(panel,self.state_model.data['profile']['name'] or self.state_model.vault['username'],13)
        self.label(panel,'@'+self.state_model.vault['username'],10,MUTED)
        row=tk.Frame(panel,bg=PANEL);row.pack(fill='x')
        for text,target in [('Edit profile','profile'),('Change password','password')]:
            box=tk.Frame(row,bg=PANEL);box.pack(side='left',fill='x',expand=True,padx=(0,12))
            self.button(box,text,lambda p=target:self.show(p),secondary=True)
        panel=self.card();self.label(panel,'Appearance',18,TEXT,True)
        glow=tk.BooleanVar(value=self.state_model.data['glow'])
        def save_glow():
            updated=copy.deepcopy(self.state_model.data);updated['glow']=glow.get();self.state_model.commit(updated)
        self.check(panel,'Illuminate buttons on hover',glow,self.safe(save_glow))
        self.label(panel,'The emotion spectrum keeps its own colors. The rest of your space stays calm.',10,MUTED)
        panel=self.card();self.label(panel,'Privacy & support',18,TEXT,True)
        self.button(panel,'Terms and local privacy  →',lambda:self.show('privacy'),secondary=True)
        self.button(panel,'Find support in your circles  →',lambda:self.show('circles'),secondary=True)
        self.button(panel,'Log out',self.logout,secondary=True)
        def delete():
            if messagebox.askyesno('Delete account?','Permanently delete this local account, reflections and circles?',parent=self):
                self.state_model.store.delete(self.state_model.vault);self.state_model.logout();self.last_entry=None;self.login_mode='register';self.show('login')
        ctk.CTkButton(panel,text='Delete local account',fg_color='transparent',hover_color=INNER,text_color=MUTED,command=self.safe(delete)).pack(anchor='w',pady=(14,0))

if __name__=='__main__':
    if sys.platform == 'win32':
        import ctypes
        try: ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Solace.Desktop')
        except (AttributeError, OSError): pass
    SolaceApp().mainloop()
