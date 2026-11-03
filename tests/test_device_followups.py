import unittest
from unittest.mock import Mock,patch
from assistant_tools import DeviceContext,device_followup


class DeviceFollowupTests(unittest.TestCase):
    def test_polite_phrases_and_custom_name(self):
        for phrase in ['can u make it 50 percent','please make it 50 percent',
                       'could you please set it to 50','okay, make it 50 directly',
                       'hey Sakura, can you make it 50 percent for me']:
            self.assertEqual(device_followup(phrase,'volume'),'set volume to 50',phrase)
        self.assertEqual(device_followup('hey Annie, please set it to 40','brightness','Annie'),'set brightness to 40')

    def test_the_reported_volume_session_resolves_every_turn(self):
        # The live transcript: each of these used to fall through to the language model.
        context=DeviceContext()
        self.assertEqual(context.resolve('Hey, Sakura, can you increase the volume to 50 percent?','desktop'),
                         'increase the volume to 50 percent')
        self.assertEqual(context.resolve('Now, Decrease it to 20%','desktop'),'set volume to 20')
        self.assertIsNone(context.resolve('decrase','desktop'))
        self.assertEqual(context.resolve('22','desktop'),'set volume to 22')
        self.assertEqual(context.resolve('It is 50% currently. Decrease it.','desktop'),'volume down')
        self.assertEqual(context.resolve('raise it','desktop'),'volume up')
        # A number only aims at the setting while that setting is the live subject.
        plain=DeviceContext()
        self.assertIsNone(plain.resolve('22','desktop'))
        plain.resolve('volume','desktop')
        self.assertEqual(plain.resolve('22 percent','desktop'),'set volume to 22')
        self.assertIsNone(plain.resolve('what is 22 plus 8?','desktop'))
        with self.assertRaisesRegex(ValueError,'name the setting'):plain.resolve('make it 30','desktop')

    def test_named_requests_are_normalized_for_both_gate_and_runner(self):
        from command_approval import required
        context=DeviceContext()
        normalized=context.resolve('hey Annie, can u set the volume to 50 percent','desktop','Annie')
        self.assertEqual(normalized,'set the volume to 50 percent')
        self.assertTrue(required(normalized))

    def test_channels_are_independent_and_unknown_target_asks(self):
        context=DeviceContext()
        context.resolve('increase volume','desktop')
        context.resolve('brightness up','phone')
        self.assertEqual(context.resolve('please make it 50 percent','desktop'),'set volume to 50')
        self.assertEqual(context.resolve('can u make it 40 percent','phone'),'set brightness to 40')
        with self.assertRaisesRegex(ValueError,'name the setting'):
            context.resolve('make it 50 percent','ai-vtuber')

    def test_expiry_and_topic_changes_remove_context(self):
        clock=Mock(return_value=100)
        context=DeviceContext(clock=clock)
        context.resolve('volume','desktop')
        clock.return_value=219
        self.assertEqual(context.resolve('make it 40','desktop'),'set volume to 40')
        clock.return_value=339
        with self.assertRaisesRegex(ValueError,'name the setting'):context.resolve('make it 50','desktop')
        context.resolve('brightness','desktop')
        context.resolve('tell me about this movie','desktop')
        with self.assertRaisesRegex(ValueError,'name the setting'):context.resolve('make it 50','desktop')
        context.resolve('the audio in this movie is lovely','desktop')
        with self.assertRaisesRegex(ValueError,'name the setting'):context.resolve('make it 50','desktop')

    def test_out_of_range_is_not_sent_to_generation(self):
        context=DeviceContext();context.resolve('volume','desktop')
        with self.assertRaisesRegex(ValueError,'0 to 100'):context.resolve('please make it 101 percent','desktop')
        context.resolve('brightness','desktop')
        with self.assertRaisesRegex(ValueError,'brightness'):context.resolve('make it 101 percent','desktop')


class DeviceRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_followups_review_then_execute_only_the_approved_action(self):
        import app as server
        from command_approval import consume
        context=DeviceContext()
        cfg={'computer_control_enabled':True,'phone_system_access_enabled':True,
             'conversation_mode':'teacher','response_restriction_level':'off','assistant_name':'Sakura'}
        with patch.object(server.app.state,'device_context',context,create=True),patch.object(server,'get_settings',return_value=cfg),patch.object(server,'llm',Mock()),patch('hardware_details.answer',return_value=None),patch('teacher_agent_chat.teacher_agent_chat.handle',return_value=None),patch('assistant_tools.execute',return_value={'ok':True,'reply':'Volume set to 50 percent.','data':{}}) as execute:
            first=await server.chat({'text':'can u increase the volume a bit'})
            self.assertIn('command_approval',first);consume(first['command_approval'],False)
            for phrase in ['can u make it 50 percent','please make it 50 percent']:
                reply=await server.chat({'text':phrase})
                self.assertIn('set volume to 50',reply['reply']);execute.assert_not_called()
                consume(reply['command_approval'],False)
            phone=await server.chat({'text':'make it 50 percent','phone':True})
            self.assertNotIn('command_approval',phone);self.assertIn('name the setting',phone['reply'])
            bad=await server.chat({'text':'make it 101 percent'})
            self.assertNotIn('command_approval',bad);self.assertIn('0 to 100',bad['reply'])
            pending=await server.chat({'text':'make it 50 percent'})
            result=await server.decide_companion_command({'id':pending['command_approval'],'approved':True})
            self.assertEqual(result['reply'],'Volume set to 50 percent.')
            execute.assert_called_once_with('audio.volume',{'action':'set','value':50})

    async def test_background_observation_does_not_replace_target(self):
        import app as server
        context=DeviceContext();context.resolve('volume','desktop')
        cfg={'computer_control_enabled':True,'response_restriction_level':'strict'}
        with patch.object(server.app.state,'device_context',context,create=True),patch.object(server,'get_settings',return_value=cfg),patch.object(server,'llm',None),patch('hardware_details.answer',return_value=None),patch('teacher_agent_chat.teacher_agent_chat.handle',return_value=None),patch.object(server,'_strict_reply',return_value={'reply':'[QUIET]'}):
            await server.chat({'text':'brightness up','screen_reaction':True})
        self.assertEqual(context.resolve('make it 50','desktop'),'set volume to 50')
