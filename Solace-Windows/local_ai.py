"""Local Ollama chat adapter. No extra Python package or cloud API key required."""
import json
import os
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

MODEL = os.environ.get('SOLACE_MODEL', 'llama3.2')
ENDPOINT = 'http://127.0.0.1:11434/api/chat'
SYSTEM_PROMPT = '''You are Solace, a supportive wellbeing companion for adults.
Respond warmly and concisely in the user's language. Listen before suggesting;
ask at most one thoughtful question. Offer gentle, optional, realistic next steps.
Do not claim to be a psychologist, diagnose conditions, or prescribe treatment.
If someone describes immediate danger or intent to harm themselves, encourage
contacting local emergency services and a trusted person who can stay with them.
Do not claim to contact anyone. Respect uncertainty and the user's choices.'''

class LocalAIError(RuntimeError):
    pass

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise LocalAIError('The local AI service redirected the request. Check your Ollama installation.')

def build_messages(history):
    """Keep recent chat only; never send profile, passwords, circles or saved notes."""
    recent = []
    remaining = 10000
    for speaker, text in reversed(history[-12:]):
        text = str(text)[:2000]
        if len(text) > remaining: break
        remaining -= len(text)
        recent.append({'role': 'user' if speaker == 'You' else 'assistant', 'content': text})
    recent.reverse()
    return [{'role': 'system', 'content': SYSTEM_PROMPT}] + recent

def chat(history):
    if MODEL not in {'llama3.2', 'llama3.2:latest', 'llama3.2:3b', 'llama3.2:1b'}:
        raise LocalAIError('Set SOLACE_MODEL to llama3.2, llama3.2:3b or llama3.2:1b.')
    request = Request(ENDPOINT, data=json.dumps({
        'model': MODEL, 'messages': build_messages(history), 'stream': False,
        'keep_alive': '5m', 'options': {'temperature': 0.65, 'num_predict': 300, 'num_ctx': 4096}
    }).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
    # Explicitly bypass system proxies, and never follow redirects off localhost.
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=180) as response:
            raw = response.read(1_000_001)
        if len(raw) > 1_000_000: raise LocalAIError('The AI response was too large. Try a shorter message.')
        result = json.loads(raw)
        content = result.get('message', {}).get('content', '')
        if not isinstance(content, str) or not content.strip():
            raise LocalAIError('The model returned no reply. Try again.')
        return content.strip()
    except HTTPError as exc:
        if exc.code == 404:
            raise LocalAIError(f'Model not found. Run: ollama pull {MODEL}') from None
        raise LocalAIError(f'Ollama returned HTTP {exc.code}. Check Ollama, then try again.') from None
    except (socket.timeout, TimeoutError):
        raise LocalAIError('The model took too long. Try again, or use llama3.2:1b on a slower laptop.') from None
    except URLError:
        raise LocalAIError('Cannot connect to Ollama. Open Ollama from the Windows Start menu, then retry.') from None
    except (ValueError, AttributeError, TypeError):
        raise LocalAIError('Ollama returned an unexpected response. Restart Ollama and try again.') from None

if __name__ == '__main__':
    print('Connecting to local Ollama with', MODEL)
    try: print(chat([('You', 'Say hello in one short sentence.')]))
    except LocalAIError as exc: raise SystemExit(str(exc))
