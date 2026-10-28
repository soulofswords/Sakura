import json
from types import SimpleNamespace
from unittest.mock import Mock,patch

import numpy as np
import pytest

from agent_connections import Connections
from agent_imports import AgentImports
from agent_runtime import AgentRuntime
from agent_voice import transcribe
from telegram_bot import TelegramGateway


def test_skill_import_requires_exact_preview_and_never_executes(tmp_path):
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'));imports=AgentImports(runtime)
    text='---\nname: sample-workflow\ndescription: Demo\n---\nRead the notes and propose a draft.'
    preview=imports.preview('SKILL.md',text)
    assert runtime.skills.list()==[]
    preview['items'][0]['instructions']='Mutated data must not be imported'
    with pytest.raises(ValueError):imports.confirm(preview['id'],False)
    imports.confirm(preview['id'],True)
    assert runtime.skills.get('sample-workflow')['instructions']=='Read the notes and propose a draft.'
    with pytest.raises(ValueError):imports.confirm(preview['id'],True)
    assert not runtime.runs


def test_imported_transcript_never_restores_authority(tmp_path):
    runtime=AgentRuntime(Connections(tmp_path/'connections.json'));imports=AgentImports(runtime)
    preview=imports.preview('history.json',json.dumps({'runs':[{'goal':'Archived sample','status':'running','steps':[{'tool':'shell.run','status':'pending','bindings':{'token':'hidden'},'arguments':{'command':'unsafe data'},'result':{'token':'secret'}}]}]}))
    imports.confirm(preview['id'],True)
    assert runtime.runs=={} and runtime.actions=={}
    result=runtime.history.search('Archived')['results'][0]
    archived=runtime.history.read(result['id'])
    assert archived['status']=='imported' and archived['steps'][0]['status']=='imported'
    assert 'secret' not in json.dumps(archived)
    with pytest.raises(ValueError):imports.preview('config.json','{"permissions": ["*"]}')
    with pytest.raises(ValueError):imports.preview('plugin.zip','contents')


def test_voice_decoding_is_bounded_and_does_not_record():
    recognizer=Mock(return_value='Memo transcript')
    decoded=SimpleNamespace(returncode=0,stdout=np.ones(1600,dtype='<f4').tobytes())
    with patch('agent_voice.shutil.which',return_value='ffmpeg'),patch('agent_voice.subprocess.run',return_value=decoded) as run:
        assert transcribe(b'OggSdemo',recognizer)=='Memo transcript'
        assert run.call_args.kwargs['timeout']==15
        assert '-protocol_whitelist' in run.call_args.args[0]
        assert run.call_args.args[0][-1]=='pipe:1'
        recognizer.assert_called_once()
        decoded.stdout=b'\0'*(121*16000*4)
        with pytest.raises(ValueError,match='two minutes'):transcribe(b'OggSdemo',recognizer)
    with pytest.raises(ValueError):transcribe(b'not audio',recognizer)


def test_telegram_checks_allowlist_and_opt_in_before_voice_download(tmp_path):
    bot=TelegramGateway(tmp_path/'bot.json',handler=lambda text:'Reply '+text)
    update={'message':{'chat':{'id':42},'voice':{'file_id':'abc','duration':1,'file_size':100}}}
    with patch.object(bot,'voice_text',return_value='voice transcript') as voice:
        bot.reply_for(update);voice.assert_not_called()
        bot.chat_ids={42};bot.reply_for(update);voice.assert_not_called()
        bot.voice_enabled=True
        assert bot.reply_for(update)==(42,'Reply voice transcript')
        voice.assert_called_once()
