import ast
import json
from pathlib import Path
import queue
import types
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
import local_ai

class LocalAITests(unittest.TestCase):
    def test_history_and_budget(self):
        messages=local_ai.build_messages([('You','hello'),('Solace','welcome'),('You','worried')])
        self.assertEqual([m['role'] for m in messages],['system','user','assistant','user'])
        long=local_ai.build_messages([('You','x'*1500)]*40)
        self.assertLessEqual(sum(len(m['content']) for m in long[1:]),10000)
    @patch('local_ai.build_opener')
    def test_success(self,factory):
        factory.return_value.open.return_value.__enter__.return_value.read.return_value=b'{"message":{"content":"A gentle response."}}'
        self.assertEqual(local_ai.chat([('You','Hello')]),'A gentle response.')
        request=factory.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url,'http://127.0.0.1:11434/api/chat')
        self.assertFalse(json.loads(request.data)['stream'])
    @patch('local_ai.build_opener')
    def test_service_and_model_errors(self,factory):
        factory.return_value.open.side_effect=URLError('refused')
        with self.assertRaisesRegex(local_ai.LocalAIError,'Open Ollama'):local_ai.chat([('You','hi')])
        factory.return_value.open.side_effect=HTTPError(local_ai.ENDPOINT,404,'missing',{},None)
        with self.assertRaisesRegex(local_ai.LocalAIError,'ollama pull'):local_ai.chat([('You','hi')])
    @patch('local_ai.build_opener')
    def test_invalid_response(self,factory):
        for raw in [b'{}',b'not json',b'[]']:
            factory.return_value.open.return_value.__enter__.return_value.read.return_value=raw
            with self.assertRaises(local_ai.LocalAIError):local_ai.chat([('You','hi')])
    def test_cloud_model_rejected(self):
        with patch('local_ai.MODEL','cloud-model'):
            with self.assertRaises(local_ai.LocalAIError):local_ai.chat([('You','hi')])
    def poller(self):
        tree=ast.parse((Path(__file__).resolve().parents[1]/'app.py').read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='SolaceApp')
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='poll_ai')
        module=ast.Module(body=[method],type_ignores=[]);ast.fix_missing_locations(module)
        scope={'queue':queue};exec(compile(module,'poll_ai','exec'),scope)
        return scope['poll_ai']
    def test_old_session_reply_discarded(self):
        old={'type':'consult'};current={'type':'consult'}
        obj=types.SimpleNamespace(ai_results=queue.Queue(),ai_busy=True,ai_failure=None,page='home',state_model=types.SimpleNamespace(vault={'username':'new'},session=current,messages=[]))
        obj.ai_results.put((old,'private text','old reply',None));self.poller()(obj)
        self.assertEqual(obj.state_model.messages,[])
        self.assertFalse(obj.ai_busy)
    def test_failed_send_restores_draft(self):
        session={'type':'consult'}
        obj=types.SimpleNamespace(ai_results=queue.Queue(),ai_busy=True,ai_failure=None,page='home',state_model=types.SimpleNamespace(vault={'username':'test'},session=session,messages=[('You','hello')]))
        obj.ai_results.put((session,'hello',None,'Cannot connect'));self.poller()(obj)
        self.assertEqual(obj.state_model.messages,[])
        self.assertEqual(obj.ai_failure,(session,'hello','Cannot connect'))

if __name__=='__main__':unittest.main()
