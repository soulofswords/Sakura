import unittest
from llm import LLM

class ContextTests(unittest.TestCase):
    def test_small_context_reserves_reply_and_retains_latest_user(self):
        messages=[{'role':'system','content':'You are Sakura. '+('Long personality. '*400)}]
        messages += [{'role': 'user' if i%2==0 else 'assistant', 'content':'Earlier dialogue. '*100} for i in range(20)]
        messages += [{'role':'user','content':'hello'}, {'role':'system','content':'Reply in English only. Your current name is Myra.'}]
        original=[dict(m) for m in messages]
        fitted=LLM._fit_local_messages(messages,2048,128)
        self.assertEqual(fitted[-1],{'role':'user','content':'hello'})
        self.assertEqual(fitted[0]['role'],'system')
        self.assertIn('Your current name is Myra.',fitted[0]['content'])
        self.assertLess(sum(len(m['content'].encode())/3+16 for m in fitted),1664)
        self.assertEqual(messages,original)

    def test_images_and_large_context_personality_preserved(self):
        messages=[{'role':'system','content':'Full authored personality'}, {'role':'user','content':'What is visible?', 'images':['image-data']}]
        fitted=LLM._fit_local_messages(messages,4096,160)
        self.assertEqual(fitted,messages)

if __name__=='__main__': unittest.main()
