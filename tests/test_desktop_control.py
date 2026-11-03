import ctypes
import unittest
from unittest.mock import Mock, patch

import command_approval
import desktop_control


class TargetTests(unittest.TestCase):
    def tearDown(self):
        desktop_control._target.update({'hwnd': 0, 'point': None})

    def test_marking_the_target_remembers_only_the_window(self):
        user32 = Mock()
        user32.GetForegroundWindow.return_value = 4242
        with patch.object(ctypes, 'windll', Mock(user32=user32)):
            desktop_control.mark_target()
        self.assertEqual(desktop_control._target, {'hwnd': 4242, 'point': None})
        user32.SetCursorPos.assert_not_called()
        user32.GetCursorPos.assert_not_called()

    def test_a_spoken_coordinate_arms_the_guard_on_the_window_under_it(self):
        window, root = Mock(), Mock()
        user32 = Mock()
        user32.WindowFromPoint.return_value = window
        user32.GetAncestor.return_value = root
        with patch.object(ctypes, 'windll', Mock(user32=user32)):
            desktop_control.mark_target('click at 300, 400')
        self.assertEqual(desktop_control._target['point'], {'x': 300, 'y': 400, 'root': root})
        self.assertEqual(user32.GetAncestor.call_args.args[1], desktop_control._GA_ROOT)

    def test_a_label_click_is_never_armed_because_its_screen_is_fresh(self):
        user32 = Mock()
        with patch.object(ctypes, 'windll', Mock(user32=user32)):
            desktop_control.mark_target('click Save')
        self.assertIsNone(desktop_control._target['point'])
        user32.WindowFromPoint.assert_not_called()

    def test_the_first_coordinate_of_a_sequence_is_the_one_armed(self):
        user32 = Mock()
        user32.GetAncestor.return_value = 77
        with patch.object(ctypes, 'windll', Mock(user32=user32)):
            desktop_control.mark_target('click at 12, 34 then type hello')
        self.assertEqual(desktop_control._target['point'], {'x': 12, 'y': 34, 'root': 77})

    def test_clicking_refuses_when_another_window_took_the_point(self):
        desktop_control._target['point'] = {'x': 300, 'y': 400, 'root': 111}
        user32 = Mock()
        user32.WindowFromPoint.return_value = 2
        user32.GetAncestor.return_value = 222
        with patch.object(ctypes, 'windll', Mock(user32=user32)), \
             patch.object(desktop_control, 'screen_size', return_value=(1920, 1080)), \
             patch.object(desktop_control, '_send') as send:
            with self.assertRaises(ValueError) as caught:
                desktop_control.click(300, 400)
        self.assertIn('different window', str(caught.exception))
        send.assert_not_called()

    def test_clicking_still_works_while_the_same_window_holds_the_point(self):
        desktop_control._target['point'] = {'x': 300, 'y': 400, 'root': 111}
        user32 = Mock()
        user32.GetAncestor.return_value = 111
        with patch.object(ctypes, 'windll', Mock(user32=user32)), \
             patch.object(desktop_control, 'screen_size', return_value=(1920, 1080)), \
             patch.object(desktop_control, '_send') as send, \
             patch.object(desktop_control.time, 'sleep'):
            desktop_control.click(300, 400)
        self.assertEqual(len(send.call_args_list), 2)

    def test_a_refused_guard_is_reported_instead_of_raising(self):
        desktop_control._target['point'] = {'x': 300, 'y': 400, 'root': 111}
        with patch.object(desktop_control, 'screen_size', return_value=(1920, 1080)), \
             patch.object(desktop_control, '_root_under', return_value=222), \
             patch.object(desktop_control, '_send') as send:
            result = desktop_control.execute_action('desktop.click', {'x': 300, 'y': 400})
        self.assertFalse(result['ok'])
        self.assertIn('different window', result['reply'])
        send.assert_not_called()

    def test_asking_for_approval_marks_the_target(self):
        with patch.object(desktop_control, 'mark_target') as mark:
            command_approval.propose('click at 8, 9', 'desktop')
        mark.assert_called_once_with('click at 8, 9')

    def test_scrolling_never_moves_the_pointer(self):
        user32 = Mock()
        with patch.object(ctypes, 'windll', Mock(user32=user32)), \
             patch.object(desktop_control, '_send') as send:
            desktop_control._target['hwnd'] = 123
            desktop_control.scroll('down', 2)
        user32.SetCursorPos.assert_not_called()
        events = send.call_args.args
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].mi.mouseData, (-2 * 120) & 0xFFFFFFFF)

    def test_typing_stops_when_another_window_keeps_focus(self):
        user32 = Mock()
        user32.IsWindow.return_value = 1
        user32.GetForegroundWindow.return_value = 999
        desktop_control._target['hwnd'] = 123
        with patch.object(ctypes, 'windll', Mock(user32=user32)), \
             patch.object(desktop_control, '_send') as send, \
             patch.object(desktop_control.time, 'sleep'):
            with self.assertRaises(ValueError):
                desktop_control.type_text('hello')
        send.assert_not_called()

    def test_typing_continues_once_focus_is_returned(self):
        user32 = Mock()
        user32.IsWindow.return_value = 1
        user32.GetForegroundWindow.return_value = 123
        desktop_control._target['hwnd'] = 123
        with patch.object(ctypes, 'windll', Mock(user32=user32)), \
             patch.object(desktop_control, '_send') as send, \
             patch.object(desktop_control.time, 'sleep'):
            desktop_control.type_text('hi')
        user32.SetForegroundWindow.assert_called_once_with(123)
        self.assertEqual(len(send.call_args.args), 4)


class ParseTests(unittest.TestCase):
    def test_clicks_by_label(self):
        for text, label, button, times in (('click save', 'save', 'left', 1),
                                           ('Click the Save button', 'Save', 'left', 1),
                                           ('hey sakura, click on the Save button', 'Save', 'left', 1),
                                           ('click link', 'link', 'left', 1),
                                           ('double click on OK', 'OK', 'left', 2),
                                           ('right click the file', 'file', 'right', 1)):
            with self.subTest(text=text):
                parsed = desktop_control.parse_command(text)
                self.assertEqual(parsed['action'], 'desktop.click_text')
                self.assertEqual(parsed['arguments']['label'], label)
                self.assertEqual(parsed['arguments']['button'], button)
                self.assertEqual(parsed['arguments']['times'], times)

    def test_clicks_by_coordinates(self):
        for text, x, y in (('click at 640, 360', 640, 360), ('click 12 34', 12, 34),
                           ('please click on 1920, 1080', 1920, 1080),
                           ('double click at 8, 9', 8, 9)):
            with self.subTest(text=text):
                parsed = desktop_control.parse_command(text)
                self.assertEqual(parsed['action'], 'desktop.click')
                self.assertEqual({key: parsed['arguments'][key] for key in ('x', 'y')}, {'x': x, 'y': y})

    def test_half_spent_sentences_are_not_control_names(self):
        for text in ('click on the', 'click on it', 'click on that', 'double click on a'):
            with self.subTest(text=text):
                self.assertIsNone(desktop_control.parse_command(text))

    def test_typing_keeps_capitalisation_and_refuses_conversation(self):
        parsed = desktop_control.parse_command('can you type Hello World')
        self.assertEqual(parsed['action'], 'desktop.type')
        self.assertEqual(parsed['arguments']['text'], 'Hello World')
        self.assertIsNone(desktop_control.parse_command('what type of game is this'))

    def test_key_combinations(self):
        self.assertEqual(desktop_control._key_codes('ctrl s'), [0x11, 0x53])
        self.assertEqual(desktop_control._key_codes('shift plus tab'), [0x10, 0x09])
        self.assertEqual(desktop_control.parse_command('press the Enter key')['arguments'], {'combo': 'Enter'})
        self.assertEqual(desktop_control._key_codes('page down'), [0x22])
        self.assertEqual(desktop_control._key_codes('control plus shift plus f5'), [0x11, 0x10, 0x74])
        self.assertEqual(desktop_control.parse_command('press ctrl s')['arguments'], {'combo': 'ctrl s'})
        self.assertIsNone(desktop_control.parse_command('press the wrongness key'))
        self.assertIsNone(desktop_control.parse_command('press ctrl plus alt plus shift plus win plus s'))

    def test_scroll_amounts(self):
        self.assertEqual(desktop_control.parse_command('scroll down')['arguments'], {'direction': 'down', 'amount': 3})
        self.assertEqual(desktop_control.parse_command('scroll up a bit')['arguments']['amount'], 1)
        self.assertEqual(desktop_control.parse_command('scroll down by 9')['arguments']['amount'], 9)

    def test_plain_conversation_is_not_a_desktop_command(self):
        for text in ('hello there', 'click', 'type', 'press the button on the screen', 'scroll sideways'):
            with self.subTest(text=text):
                self.assertIsNone(desktop_control.parse_command(text))

    def test_every_desktop_action_needs_review(self):
        for text in ('click save', 'click at 10, 20', 'type hello', 'press ctrl s', 'scroll down'):
            with self.subTest(text=text):
                self.assertTrue(command_approval.required(text))
        self.assertFalse(command_approval.required('hello there'))
        self.assertTrue(command_approval.required('click save then press enter'))



class ExecutionTests(unittest.TestCase):
    def test_click_typing_and_keys_call_windows_input(self):
        with patch.object(desktop_control, 'click') as click, \
             patch.object(desktop_control, 'type_text') as typing, \
             patch.object(desktop_control, 'press') as press, \
             patch.object(desktop_control, 'scroll') as scroll:
            self.assertTrue(desktop_control.execute_action('desktop.click', {'x': 5, 'y': 6})['ok'])
            self.assertTrue(desktop_control.execute_action('desktop.type', {'text': 'Hello World'})['ok'])
            self.assertTrue(desktop_control.execute_action('desktop.press', {'combo': 'ctrl+s'})['ok'])
            self.assertTrue(desktop_control.execute_action('desktop.scroll', {'direction': 'up', 'amount': 2})['ok'])
            self.assertTrue(desktop_control.execute_action(
                'desktop.click', {'x': 5, 'y': 6, 'button': 'right', 'times': 2})['ok'])
        self.assertEqual(click.call_args_list[0].args, (5, 6, 'left', 1))
        self.assertEqual(click.call_args_list[1].args, (5, 6, 'right', 2))
        typing.assert_called_once_with('Hello World')
        press.assert_called_once_with('ctrl+s')
        scroll.assert_called_once_with('up', 2)

    def test_a_failed_click_is_reported_without_running_anything_else(self):
        with patch.object(desktop_control, 'screen_size', return_value=(100, 100)), \
             patch.object(desktop_control, '_send') as send:
            result = desktop_control.execute_action('desktop.click', {'x': 500, 'y': 500})
        self.assertFalse(result['ok'])
        self.assertIn('outside this screen', result['reply'])
        send.assert_not_called()

    def test_typing_refuses_newlines_and_oversized_text(self):
        with patch.object(desktop_control, '_send'):
            with self.assertRaises(ValueError):
                desktop_control.type_text('two\nlines')
            with self.assertRaises(ValueError):
                desktop_control.type_text('x' * 501)

    def test_click_outside_the_screen_is_refused(self):
        with patch.object(desktop_control, 'screen_size', return_value=(100, 100)), \
             patch.object(desktop_control, '_send') as send:
            with self.assertRaises(ValueError):
                desktop_control.click(500, 500)
        send.assert_not_called()

    def test_only_left_and_right_buttons_are_accepted(self):
        with patch.object(desktop_control, '_send') as send:
            with self.assertRaises(ValueError):
                desktop_control.click(10, 10, 'middle')
        send.assert_not_called()

    def test_typing_stops_when_focus_could_not_be_returned(self):
        with patch.object(desktop_control, '_ensure_target',
                          side_effect=ValueError('I could not return focus to the window you were using.')), \
             patch.object(desktop_control, '_send') as send:
            result = desktop_control.execute_action('desktop.type', {'text': 'hello'})
        self.assertFalse(result['ok'])
        self.assertIn('focus', result['reply'])
        send.assert_not_called()


    def test_press_releases_keys_in_reverse_order(self):
        with patch.object(desktop_control, '_send') as send:
            desktop_control.press('ctrl+s')
        events = send.call_args.args
        self.assertEqual([event.ki.wVk for event in events], [0x11, 0x53, 0x53, 0x11])
        self.assertEqual([event.ki.dwFlags for event in events[-2:]], [0x0002, 0x0002])

    def test_typing_sends_unicode_code_units(self):
        with patch.object(desktop_control, '_send') as send:
            desktop_control.type_text('Hi')
        events = send.call_args.args
        self.assertEqual([event.ki.wScan for event in events], [ord('H'), ord('H'), ord('i'), ord('i')])
        self.assertEqual([event.ki.dwFlags for event in events], [0x0004, 0x0006, 0x0004, 0x0006])


class ScreenClickTests(unittest.TestCase):
    def _shot(self):
        shot = Mock()
        shot.width, shot.height = 1920, 1080
        shot.save = lambda buffer, format: buffer.write(b'png')
        return shot

    def test_clicks_the_centre_of_the_matching_word(self):
        with patch('PIL.ImageGrab.grab', return_value=self._shot()), \
             patch('ocr.engine_name', return_value='windows-ocr'), \
             patch('ocr.locate', return_value=[{'text': 'Save', 'score': 3, 'x': 100, 'y': 50,
                                               'width': 40, 'height': 20}]) as locate, \
             patch.object(desktop_control, 'screen_size', return_value=(1920, 1080)), \
             patch.object(desktop_control, 'click') as click:
            result = desktop_control.execute_action('desktop.click_text', {'label': 'Save'})
        self.assertTrue(result['ok'])
        self.assertIn('Clicked', result['reply'])
        locate.assert_called_once()
        click.assert_called_once_with(120, 60, 'left', 1)

    def test_right_click_is_named_in_the_reply(self):
        with patch('PIL.ImageGrab.grab', return_value=self._shot()), \
             patch('ocr.engine_name', return_value='windows-ocr'), \
             patch('ocr.locate', return_value=[{'text': 'file', 'score': 3, 'x': 10, 'y': 10,
                                               'width': 20, 'height': 10}]), \
             patch.object(desktop_control, 'screen_size', return_value=(1920, 1080)), \
             patch.object(desktop_control, 'click') as click:
            result = desktop_control.execute_action(
                'desktop.click_text', {'label': 'file', 'button': 'right', 'times': 1})
        self.assertIn('Right-clicked', result['reply'])
        click.assert_called_once_with(20, 15, 'right', 1)

    def test_an_impossible_label_is_reported_instead_of_raising(self):
        with patch('PIL.ImageGrab.grab', return_value=self._shot()), \
             patch('ocr.engine_name', return_value='windows-ocr'), \
             patch('ocr.locate', side_effect=ValueError('Use at most six words for a screen label.')), \
             patch.object(desktop_control, 'click') as click:
            result = desktop_control.execute_action('desktop.click_text', {'label': 'one two three four five six seven'})
        self.assertFalse(result['ok'])
        self.assertIn('six words', result['reply'])
        click.assert_not_called()

    def test_reports_when_the_label_is_not_on_screen(self):
        with patch('PIL.ImageGrab.grab', return_value=self._shot()), \
             patch('ocr.engine_name', return_value='windows-ocr'), \
             patch('ocr.locate', return_value=[]), \
             patch.object(desktop_control, 'click') as click:
            result = desktop_control.execute_action('desktop.click_text', {'label': 'Approve'})
        self.assertFalse(result['ok'])
        self.assertIn('could not find', result['reply'])
        click.assert_not_called()

    def test_ambiguous_near_matches_are_refused(self):
        with patch('PIL.ImageGrab.grab', return_value=self._shot()), \
             patch('ocr.engine_name', return_value='windows-ocr'), \
             patch('ocr.locate', return_value=[{'text': "Sakura's", 'score': 2, 'x': 10, 'y': 10, 'width': 20, 'height': 10},
                                               {'text': 'sakura', 'score': 1, 'x': 50, 'y': 10, 'width': 20, 'height': 10}]), \
             patch.object(desktop_control, 'click') as click:
            result = desktop_control.execute_action('desktop.click_text', {'label': 'Sakura'})
        self.assertFalse(result['ok'])
        self.assertIn('More than one thing', result['reply'])
        self.assertIn('Nothing was clicked', result['reply'])
        click.assert_not_called()

    def test_a_single_near_match_still_clicks(self):
        with patch('PIL.ImageGrab.grab', return_value=self._shot()), \
             patch('ocr.engine_name', return_value='windows-ocr'), \
             patch('ocr.locate', return_value=[{'text': "Sakura's", 'score': 2, 'x': 100, 'y': 50,
                                                'width': 40, 'height': 20}]), \
             patch.object(desktop_control, 'screen_size', return_value=(1920, 1080)), \
             patch.object(desktop_control, 'click') as click:
            result = desktop_control.execute_action('desktop.click_text', {'label': 'Sakura'})
        self.assertTrue(result['ok'])
        click.assert_called_once_with(120, 60, 'left', 1)

    def test_reports_when_windows_ocr_is_missing(self):
        with patch('ocr.engine_name', return_value=''), \
             patch.object(desktop_control, 'click') as click:
            result = desktop_control.execute_action('desktop.click_text', {'label': 'Save'})
        self.assertFalse(result['ok'])
        self.assertIn('OCR', result['reply'])
        click.assert_not_called()


class RoutingTests(unittest.TestCase):
    def test_assistant_tools_classifies_and_executes_desktop_actions(self):
        from assistant_tools import classify, execute
        self.assertEqual(classify('click save')[0], 'desktop.click_text')
        with patch('desktop_control.execute_action', return_value={'ok': True, 'reply': 'Clicked.', 'data': {}}) as action:
            result = execute('desktop.click', {'x': 1, 'y': 2})
        self.assertEqual(result['reply'], 'Clicked.')
        action.assert_called_once_with('desktop.click', {'x': 1, 'y': 2})

    def test_voice_typing_keeps_case_and_needs_computer_access(self):
        from assistant_commands import run_command
        with patch('desktop_control.execute_action', return_value={'ok': True, 'reply': 'Typed.', 'data': {}}) as action:
            self.assertEqual(run_command('type Hello World', True), 'Typed.')
            action.assert_called_once_with('desktop.type', {'text': 'Hello World'})
            self.assertIn('computer access', run_command('press ctrl s', False))

    def test_sequences_keep_typed_text_case(self):
        from assistant_commands import normalize
        from assistant_tools import _parse_sequence
        self.assertEqual(normalize('hey sakura, type Hello World'), 'type Hello World')
        plan, error = _parse_sequence(normalize('click save then type Hello World'), True)
        self.assertIsNone(error)
        self.assertEqual(plan[0][1][0], 'desktop.click_text')
        self.assertEqual(plan[0][1][1]['label'], 'save')
        self.assertEqual(plan[1][1], ('desktop.type', {'text': 'Hello World'}))


if __name__ == '__main__':
    unittest.main()
