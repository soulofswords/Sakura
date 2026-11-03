"""Speaking a voice name has to land on that voice, and only when the sentence was about voices."""
import unittest
from unittest.mock import patch

import spoken_voice
from assistant_tools import classify, handle_command
from spoken_voice import request, resolve, selectable, summary

_WINDOWS = [{'id': 'system_en_zira', 'name': 'Microsoft Zira Desktop', 'voice': 'system', 'backend': 'system',
             'gender': 'Female', 'language': 'English', 'rate': '+0%', 'pitch': '+0Hz',
             'desc': 'Offline · Female · en-US · installed Windows voice'}]


class FakeTTS:
    selected_preset_id = 'kokoro_af_heart'

    def set_voice_preset(self, preset_id, pitch=None, rate=None):
        self.selected_preset_id = preset_id
        self.applied = (preset_id, pitch, rate)


class NameTests(unittest.TestCase):
    def setUp(self):
        self.saved = spoken_voice._windows
        spoken_voice._windows = _WINDOWS

    def tearDown(self):
        spoken_voice._windows = self.saved

    def test_a_name_and_its_legacy_spellings_land_on_one_voice(self):
        self.assertEqual(resolve('Bella')['id'], 'kokoro_af_bella')
        self.assertEqual(resolve('the voice Nicole')['id'], 'kokoro_af_nicole')
        self.assertEqual(resolve('en-US-AvaNeural')['id'], 'kokoro_af_heart')
        self.assertEqual(resolve('sakura_ava')['id'], 'kokoro_af_heart')
        self.assertEqual(resolve('Sakura heart')['id'], 'kokoro_af_heart')

    def test_an_installed_windows_voice_is_reachable_by_its_own_name(self):
        self.assertEqual(resolve('Zira')['id'], 'system_en_zira')
        self.assertEqual(resolve('the Zira voice')['id'], 'system_en_zira')

    def test_a_name_inside_another_word_is_not_a_match(self):
        # “eric” is buried in “american”, which is a whole group of voices, not one of them.
        with self.assertRaisesRegex(ValueError, 'several'):
            resolve('american')

    def test_a_description_that_fits_many_voices_is_asked_about(self):
        with self.assertRaisesRegex(ValueError, 'Name one of them'):
            resolve('male')

    def test_an_unknown_voice_is_admitted(self):
        with self.assertRaisesRegex(ValueError, 'no voice called'):
            resolve('Zoe')
        with self.assertRaisesRegex(ValueError, 'no voice called'):
            resolve('mickey')

    def test_only_a_real_single_name_is_returned(self):
        self.assertEqual(len(selectable()), len(spoken_voice.VOICE_PRESETS) + 1)
        self.assertEqual(len({record['id'] for record in selectable()}), len(selectable()))


class SentenceTests(unittest.TestCase):
    def setUp(self):
        self.saved = spoken_voice._windows
        spoken_voice._windows = _WINDOWS

    def tearDown(self):
        spoken_voice._windows = self.saved

    def test_voice_requests_are_claimed(self):
        self.assertEqual(request('switch to Bella'), {'label': 'bella'})
        self.assertEqual(request('Change your voice to Nicole.'), {'label': 'nicole'})
        self.assertEqual(request('use the British voice'), {'label': 'british'})
        self.assertEqual(request('talk like Fenrir'), {'label': 'fenrir'})
        self.assertEqual(request('switch to Zira'), {'label': 'zira'})

    def test_a_question_about_voices_asks_for_the_list(self):
        for text in ['what voices do I have', 'list voices', 'show me the available voices', 'voice options']:
            self.assertEqual(request(text), {'show': True}, text)

    def test_requests_about_anything_else_stay_free(self):
        for text in ['switch to dark theme', 'use calculator', 'open youtube', 'set the volume to 30',
                     'switch to the playlist', 'change the channel to sports', 'talk like a pirate']:
            self.assertIsNone(request(text), text)

    def test_the_resolver_is_used_before_a_command_is_claimed(self):
        spoken_voice._windows = []
        self.assertIsNone(request('switch to zira'))
        spoken_voice._windows = _WINDOWS
        self.assertEqual(request('switch to zira'), {'label': 'zira'})


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.saved = spoken_voice._windows
        spoken_voice._windows = _WINDOWS

    def tearDown(self):
        spoken_voice._windows = self.saved

    def test_classification_carries_the_spoken_label(self):
        self.assertEqual(classify('switch to bella'), ('audio.voice', {'label': 'bella'}))
        self.assertEqual(classify('what voices do I have'), ('audio.voices', {}))

    def test_my_own_voice_needs_no_computer_access(self):
        with patch('app.switch_voice', return_value={'ok': True, 'reply': "Okay, I'll use Bella."}) as switch:
            self.assertEqual(handle_command('switch to bella', False), "Okay, I'll use Bella.")
            switch.assert_called_once_with('kokoro_af_bella')

    def test_an_unknown_voice_is_never_applied(self):
        with patch('app.switch_voice') as switch:
            # Naming a voice that does not exist gets an answer; an unrelated “switch to …” is left alone.
            self.assertIn('no voice called', handle_command('switch to my Zoe voice', False))
            self.assertIsNone(handle_command('switch to zoe', False))
            switch.assert_not_called()

    def test_the_voice_list_answers_without_touching_the_speaker(self):
        with patch('app.switch_voice') as switch:
            reply = handle_command('what voices do I have', False)
            self.assertIn('Bella', reply)
            self.assertIn('switch to', reply)
            switch.assert_not_called()

    def test_an_ambiguous_name_is_reported_as_a_question(self):
        self.assertIn('Name one of them', handle_command('switch to male', False))


class ApplyTests(unittest.TestCase):
    def test_a_resolved_voice_is_saved_and_handed_to_the_speaker(self):
        import app
        tts = FakeTTS()
        with patch('app.save_settings', return_value={'tts_pitch': '+2Hz', 'tts_rate': '+5%'}) as save, \
             patch('app.tts', tts), patch('app.llm') as llm, \
             patch('rvc_manager.stop_rvc_service') as stop:
            result = app.switch_voice('kokoro_bm_george')
        save.assert_called_once_with({'selected_voice': 'kokoro_bm_george'})
        self.assertEqual(tts.applied, ('kokoro_bm_george', '+2Hz', '+5%'))
        self.assertEqual(llm.reply_language, 'English')
        self.assertIn('George', result['reply'])
        stop.assert_called_once()

    def test_a_hindi_voice_changes_the_reply_language_too(self):
        import app
        with patch('app.save_settings', return_value={}), patch('app.tts', FakeTTS()), patch('app.llm') as llm, \
             patch('rvc_manager.stop_rvc_service'):
            result = app.switch_voice('kokoro_hf_alpha_hindi')
        self.assertEqual(llm.reply_language, 'Hindi')
        self.assertIn('Hindi', result['reply'])

    def test_an_imported_rvc_voice_stays_on_the_settings_page(self):
        import app
        with patch('app.save_settings') as save, patch('app.tts', FakeTTS()):
            with self.assertRaisesRegex(ValueError, 'Settings'):
                app.switch_voice('rvc_custom')
        save.assert_not_called()

    def test_a_windows_voice_that_went_missing_is_refused(self):
        import app
        with patch('system_speech.system_voice_presets', return_value=_WINDOWS), \
             patch('app.save_settings') as save, patch('app.tts', FakeTTS()):
            with self.assertRaisesRegex(ValueError, 'no longer installed'):
                app.switch_voice('system_en_nobody')
        save.assert_not_called()
        self.assertEqual(FakeTTS.selected_preset_id, 'kokoro_af_heart')

    def test_an_installed_windows_voice_applies(self):
        import app
        tts = FakeTTS()
        with patch('system_speech.system_voice_presets', return_value=_WINDOWS), \
             patch('app.save_settings', return_value={}), patch('app.tts', tts), patch('app.llm'), \
             patch('rvc_manager.stop_rvc_service'):
            result = app.switch_voice('system_en_zira')
        self.assertEqual(tts.applied[0], 'system_en_zira')
        self.assertIn('Microsoft Zira Desktop', result['reply'])


class CatalogueTests(unittest.TestCase):
    def test_the_summary_names_real_voices_and_how_to_pick_one(self):
        text = summary(_WINDOWS)
        self.assertIn('Bella', text)
        self.assertIn('switch to', text)
        self.assertNotIn('kokoro_', text)


if __name__ == '__main__':
    unittest.main()
