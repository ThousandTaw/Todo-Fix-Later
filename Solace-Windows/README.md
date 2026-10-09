# Solace — redesigned Python desktop app

A redesigned desktop interface built with CustomTkinter: rounded controls, a fixed sidebar, a two-column overview, a calmer color palette, a wider mood chart, and a circle card grid. Existing local accounts use the same storage and remain available after updating.

## Update from the first version

Extract the new ZIP to a fresh folder. Double-click `run.bat` in its `Solace-Windows` folder; it installs the new UI dependency automatically. Log in with your existing local username and password. Account data is stored outside the source folder, so there is no need to copy it.

If you use the previously created environment at `%USERPROFILE%\solace-venv`, open a terminal in the new folder and run:

```powershell
& "$env:USERPROFILE\solace-venv\Scripts\python.exe" -m pip install -r requirements.txt
& "$env:USERPROFILE\solace-venv\Scripts\python.exe" app.py
```

## Connect Llama 3.2 through Ollama

This version already connects the Companion screen to Ollama at `http://127.0.0.1:11434/api/chat`. It uses Python's standard library; no `pip install ollama` or API key is needed. Install/open Ollama for Windows from https://ollama.com/download/windows if necessary.

1. Open Ollama from the Windows Start menu. It normally runs in the background.
2. In PowerShell run `ollama list`. The default model used by this app is `llama3.2` (the `llama3.2:latest` tag works with that name).
3. If the model is missing, run `ollama pull llama3.2` once. Downloading requires internet; local inference with the downloaded model works offline.
4. Extract this updated ZIP into a fresh folder, then open its `Solace-Windows` folder. Keep any separately modified source files in your old folder.
5. Double-click `run.bat`, log in, open Companion and send a message.

If Ollama is not running, open it from Start, or run `ollama serve` in a separate terminal. A port-in-use message usually means a server is already running; do not start another one.

Optional connection test from the project folder, using your existing virtual environment:

```powershell
& "$env:USERPROFILE\solace-venv\Scripts\python.exe" local_ai.py
```

For a different supported installed tag, set `SOLACE_MODEL` to `llama3.2:3b` or `llama3.2:1b`. For example, after downloading that model:

```powershell
$env:SOLACE_MODEL = "llama3.2:1b"
& "$env:USERPROFILE\solace-venv\Scripts\python.exe" app.py
```

The initial greeting is authored; subsequent replies come from Llama. Recent messages from the active conversation provide context. Profile, credentials, circles and saved reflections are not sent to Ollama. No cloud fallback is used. Generation runs in a background thread; Tk updates happen on its main thread. Leaving a session or logging out discards its pending reply. On connection failure the typed message is restored for retry.

The model must be installed on the same computer as this app. If you use LM Studio or a GGUF file directly instead of Ollama, this adapter must be changed for that runtime.

## Run on your laptop

1. Install **Python 3.11 or newer** from https://www.python.org/downloads/windows/. Keep pip and Tcl/Tk enabled.
2. Extract the ZIP completely. Open **Solace-Windows**.
3. Double-click **run.bat**. The first launch creates a virtual environment and installs the encryption dependency; that first install requires internet. Later launches work offline.
4. Accept all three terms acknowledgements and create a local account. You must be at least 18.

This is Python source, not a prebuilt EXE. Do not launch from inside the ZIP.

## Run using VS Code

Open the extracted Solace-Windows folder in VS Code. Install Microsoft's Python and Python Debugger extensions. Open Terminal → New Terminal:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

If `py` is unavailable, use `python` for the first command. No PowerShell activation script is needed.

For F5 debugging: Ctrl+Shift+P → Python: Select Interpreter → `.venv\Scripts\python.exe`, then F5 → Run Solace. Check Tkinter with `py -3 -m tkinter` if no window opens.

## Features and conversion

- Original Solace logo, navy desktop layout, sidebar navigation and glowing hover/focus buttons.
- Required terms before login, encrypted local accounts, age 18+ gate, optional profile name/personality/interests. No diagnosis or family/friend-count questionnaire.
- Five emotion faces, colorful spectrum, emotion-colored progress bars labelled with the chosen emotion.
- Local Llama companion conversations, 15 mood-based challenges, completion feedback, daily streak and next-challenge/done-for-today choice.
- Friend question after each challenge; choose/create a circle. Unanswered follow-ups resume after login.
- Create/rename/remove circles; add/remove/move friends; trusted support contacts. Need support opens circles.
- View/delete reflections, edit profile, toggle glow, change password, logout and account deletion.

The uploaded Java backend's small **offline Naive Bayes emotion classifier** is ported to `emotion_model.py`. On Overview, choose Explore my feeling, then enter text and request a suggestion. The model's guess is applied only after your confirmation.

The backend has six labels; the frontend has five spectrum categories. The explicit prototype mapping is Happy → Great, Calm → Good, Anxious → Anxious, Sad/Lonely → Low, Angry → Anxious. It is not a clinical interpretation. The training examples are tiny and English-only; guesses can be wrong or unavailable.

The redesigned Companion screen calls `local_ai.chat()` from `app.py`, using your installed Ollama Llama 3.2 model. No model weights are included in this ZIP. The original `SolaceState.reply()` helper remains available for the old UI but is not used by the redesigned Companion. AI responses can be inaccurate; Solace is a wellbeing companion, not a psychologist. The authored challenges rotate through three per mood, then repeat. Bar heights are category ordering, not clinical scores. Age is self-reported; terms are prototype copy.

## Local data

Accounts are in `%LOCALAPPDATA%\Solace\accounts` on Windows, outside the source folder. On other systems the default is `~/.local/share/Solace/accounts`. Fernet encrypts/authenticates each account record using a PBKDF2-SHA256 password-derived key. Passwords are not saved as plaintext. Conversation messages remain in memory; saved reflection notes persist.

There is no cloud sync or password recovery. Deleting account files removes the data. This prototype has not undergone a production security audit. Run one instance per account at a time; concurrent-instance merging is not implemented. Existing Android vault files are not imported.

## Source files

| File | Purpose |
| --- | --- |
| app.py | Redesigned desktop UI and entry point |
| legacy_ui.py | Shared onboarding, challenge and account flows inherited by the redesigned UI |
| core.py | Accounts, encryption, sessions, circles and streaks |
| emotion_model.py | Java classifier port |
| local_ai.py | Local Ollama adapter, system prompt and connection test |
| assets/challenges.json | Fifteen authored challenges |
| assets/solace_logo.png | Original logo |
| run.bat | Windows setup/launch |
| .vscode/ | VS Code debugger settings |
| tests/test_core.py | Behavioral tests |

## Validation

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Python syntax and 21 automated tests were checked. Seven new tests cover mocked Ollama responses, transport failures, history limits and session isolation; the original 14 cover: age/consent, encrypted storage, tamper rejection, password changes, isolation, completion guards, streaks, follow-up recovery, circle operations and save-failure handling. The redesigned desktop pages were previously rendered in a Linux virtual display and the challenge → reflection → friend → circle flow was exercised. The new AI transport was tested with mocked responses; live Ollama/Llama inference and native Windows rendering still need verification on your laptop.

References: [Ollama chat API](https://docs.ollama.com/api/chat), [Ollama on Windows](https://docs.ollama.com/windows), [Tkinter](https://docs.python.org/3/library/tkinter.html), [Fernet](https://cryptography.io/en/stable/fernet/).

## Logo update

The sidebar uses the exact uploaded blue heart-and-hands logo. A multi-size `assets/solace.ico` supplies the Windows window icon. The original PNG is preserved. Close the old app before opening this version.
