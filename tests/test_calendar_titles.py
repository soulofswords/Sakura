import unittest
from calendar_chat import event_title
class CalendarTitles(unittest.TestCase):
 def test_only_event_not_command(self):
  for text,expected in [
   ('i have a interview . so add that to the calendar it would be from 11:30 am to 2 pm','interview'),
   ('hello make a schedule for my interview at 11:30 am','interview'),
   ('i have an interview with infosys at 11:30 am','interview with infosys'),
   ('there is a meeting with mohit at 2 pm','meeting with mohit'),
   ('reminder on mohit birthday','mohit birthday')]:
   with self.subTest(text=text):self.assertEqual(event_title(text),expected)
