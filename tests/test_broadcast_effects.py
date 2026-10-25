import unittest
from unittest.mock import patch
import broadcast_effects
from assistant_commands import run_command
from assistant_tools import capabilities,classify
from broadcast_effects import classify as effect_classify

CONNECTION={'id':'d49dc0227f6d41feaa44e654e3e98f7f','name':'Nvidia Broadcast','transport':'http','url':'http://127.0.0.1:18100/gateway'}
SCHEMA={'type':'object','properties':{'effects':{'type':'array'}},'required':['effects']}
# The ids NVIDIA Broadcast itself publishes as settable.
DISCOVERED=[{'name':'set_effects','description':'','inputSchema':SCHEMA},
            {'name':'submit_file_processing','description':'','inputSchema':SCHEMA}]

def recorder(calls,discover=None,reply=None):
    def mcp_request(config,operation,**kwargs):
        calls.append((operation,kwargs.get('tool'),kwargs.get('arguments'),kwargs.get('schema_hash')))
        if operation=='discover':return discover if discover is not None else list(DISCOVERED)
        return reply or {'is_error':False,'content':[{'type':'text','text':'applied'}],'output_truncated':False}
    return mcp_request

def one(text):
    request=effect_classify(text)
    assert request and request['changes'],text
    return request['changes'][0]

class VoiceMatching(unittest.TestCase):
 def test_effect_phrases_map_to_allowlisted_effects(self):
  for text,expected in [('blur my background',('background_blur',True,{})),
      ('put studio voice on',('studio_voice',True,{})),
      ('turn off background blur',('background_blur',False,{})),
      ('turn background blur off',('background_blur',False,{})),
      ('set background blur to 60%',('background_blur',True,{'strength':0.6})),
      ('remove my background',('background_remove',True,{})),
      ('enable eye contact',('eye_contact',True,{})),
      ('stop eye contact',('eye_contact',False,{})),
      ('noise removal on',('noise_removal',True,{})),
      ('turn off noise cancellation',('noise_removal',False,{})),
      ('remove echo from my speakers',('speaker_echo_removal',True,{})),
      ('studio voice warm',('studio_voice',True,{'micProfile':'warm'})),
      ('video noise removal off',('video_noise_removal',False,{}))]:
   with self.subTest(text=text):
    change=one(text)
    self.assertEqual((change['effect'],change['enabled'],change['params']),expected)
 def test_questions_and_ordinary_talk_are_not_effect_commands(self):
  for text in ['why is my background blurry','how do I enable eye contact','what does studio voice do',
      'tell me about noise removal','the background blur looks bad today','set volume to 30%','open youtube','pc status']:
   with self.subTest(text=text):self.assertIsNone(effect_classify(text))
 def test_a_sequence_is_left_to_the_workflow_splitter(self):
  self.assertIsNone(effect_classify('blur my background then set volume to 30%'))
 def test_only_an_off_switch_is_offered_for_background_replacement(self):
  self.assertEqual(effect_classify('replace my background'),{'changes':[],'needs_asset':'background_replace'})
  self.assertEqual(one('turn off background replacement'),{'effect':'background_replace','enabled':False,'params':{}})
 def test_strength_bounds_are_rejected_before_the_network(self):
  with self.assertRaises(ValueError):effect_classify('set background blur to 101%')
  with self.assertRaises(ValueError):effect_classify('set eye contact to 40%')
 def test_the_voice_surface_is_exactly_the_curated_effects(self):
  self.assertEqual(set(broadcast_effects.EFFECTS),{
   'background_blur','background_remove','background_replace','vignette','eye_contact','auto_frame',
   'video_noise_removal','virtual_key_light','studio_voice','noise_removal','room_echo_removal',
   'speaker_noise_removal','speaker_echo_removal'})
  for spec in broadcast_effects.EFFECTS.values():
   self.assertIn(spec['pct'],(None,'strength','zoom'))

class EffectExecution(unittest.TestCase):
 def test_permission_gate_blocks_before_any_mcp_call(self):
  calls=[]
  with patch.object(broadcast_effects,'_connection',return_value=CONNECTION),patch('agent_connections.mcp_request',recorder(calls)):
   self.assertIn('Enable',run_command('blur my background',False))
  self.assertEqual(calls,[])
 def test_call_batches_effects_with_a_fresh_schema_hash(self):
  from agent_runtime import digest
  calls=[]
  with patch.object(broadcast_effects,'_connection',return_value=CONNECTION),patch('agent_connections.mcp_request',recorder(calls)):
   reply=run_command('blur my background',True)
  self.assertEqual('Background blur is on.',reply)
  self.assertEqual([step[0] for step in calls],['discover','call'])
  operation,tool,arguments,schema_hash=calls[1]
  self.assertEqual(tool,'set_effects')
  self.assertEqual(arguments,{'effects':[{'effectId':'background_blur','enabled':True}]})
  self.assertEqual(schema_hash,digest(SCHEMA),'the guard needs the hash of the schema just discovered')
 def test_strength_and_profile_are_sent_as_bounded_params(self):
  calls=[]
  with patch.object(broadcast_effects,'_connection',return_value=CONNECTION),patch('agent_connections.mcp_request',recorder(calls)):
   self.assertEqual('Vignette is on at 30 percent.',run_command('set vignette to 30%',True))
   self.assertEqual('Studio voice is on with the warm profile.',run_command('studio voice warm',True))
  self.assertEqual(calls[1][2],{'effects':[{'effectId':'vignette','enabled':True,'params':{'strength':0.3}}]})
  self.assertEqual(calls[3][2],{'effects':[{'effectId':'studio_voice','enabled':True,'params':{'micProfile':'warm'}}]})
 def test_missing_connection_is_reported_without_a_call(self):
  calls=[]
  with patch.object(broadcast_effects,'_connection',return_value=None),patch('agent_connections.mcp_request',recorder(calls)):
   reply=run_command('blur my background',True)
  self.assertIn('MCP connections',reply);self.assertEqual(calls,[])
 def test_unreachable_server_and_refused_change_never_claim_success(self):
  with patch.object(broadcast_effects,'_connection',return_value=CONNECTION),patch('agent_connections.mcp_request',side_effect=OSError('connection refused')):
   self.assertIn('not reachable',run_command('blur my background',True))
  refused={'is_error':True,'content':[{'type':'text','text':'NVIDIA Broadcast is not running'}],'output_truncated':False}
  with patch.object(broadcast_effects,'_connection',return_value=CONNECTION),patch('agent_connections.mcp_request',recorder([],reply=refused)):
   reply=run_command('blur my background',True)
  self.assertIn('refused',reply);self.assertNotIn('is on',reply)
 def test_only_allowlisted_effects_and_params_reach_the_tool(self):
  calls=[]
  for changes,message in [([{'effect':'submit_file_processing','enabled':True}],'allowed to change'),
      ([{'effect':'background_blur','enabled':True,'params':{'imagePath':'C:\\Users\\gaura\\x.png'}}],'does not take'),
      ([{'effect':'background_blur','enabled':True,'params':{'strength':7}}],'between 0 and 100')]:
   with self.subTest(message=message):
    with patch.object(broadcast_effects,'_connection',return_value=CONNECTION),patch('agent_connections.mcp_request',recorder(calls)):
     self.assertIn(message,broadcast_effects.apply(changes)['reply'])
   self.assertNotIn('call',[step[0] for step in calls],'a rejected change must never reach set_effects')
 def test_a_connection_without_set_effects_is_not_used_for_anything_else(self):
  calls=[]
  audio_only=[{'name':'get_broadcast_state','description':'','inputSchema':SCHEMA}]
  with patch.object(broadcast_effects,'_connection',return_value=CONNECTION),patch('agent_connections.mcp_request',recorder(calls,discover=audio_only)):
   self.assertIn('does not offer',run_command('blur my background',True))
  self.assertEqual([step[0] for step in calls],['discover'])
 def test_effects_join_a_workflow_after_the_volume_step(self):
  calls=[]
  with patch.object(broadcast_effects,'_connection',return_value=CONNECTION),patch('agent_connections.mcp_request',recorder(calls)),patch('system_tools.volume',return_value={'percent':30,'muted':False}):
   reply=run_command('blur my background then set volume to 30%',True)
  self.assertIn('Background blur is on.',reply);self.assertIn('30 percent',reply)
  self.assertEqual(calls[1][2],{'effects':[{'effectId':'background_blur','enabled':True}]})
 def test_replacement_request_asks_for_the_path_instead_of_guessing_one(self):
  calls=[]
  with patch.object(broadcast_effects,'_connection',return_value=CONNECTION),patch('agent_connections.mcp_request',recorder(calls)):
   reply=run_command('replace my background',True)
  self.assertIn('file path',reply);self.assertEqual(calls,[])

class ToolRouting(unittest.TestCase):
 def test_assistant_tools_routes_the_new_action(self):
  self.assertEqual(classify('blur my background')[0],'broadcast.effects')
  self.assertEqual(classify('pc status')[0],'system.status')
 def test_capability_list_advertises_the_curated_surface(self):
  entry=next(item for item in capabilities() if item['id']=='broadcast.effects')
  self.assertEqual(entry['permission'],'computer_access')
  self.assertIn('blur my background',entry['examples'])

if __name__=='__main__':unittest.main()
