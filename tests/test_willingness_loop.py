import unittest
import re

class TestWillingnessLogic(unittest.TestCase):
    def setUp(self):
        # Regex as defined in the server code
        self.t_pattern = re.compile(r"\[THOUGHT\]:(.*?)(\[|$)", re.DOTALL)
        self.w_pattern = re.compile(r"\[WILLINGNESS\]:\s*(\d+)")
        self.c_pattern = re.compile(r"\[CONTENT\]:(.*)", re.DOTALL)

    def parse_reply(self, raw_reply):
        thought = ""
        willingness = 10
        content = raw_reply

        t_match = self.t_pattern.search(raw_reply)
        w_match = self.w_pattern.search(raw_reply)
        c_match = self.c_pattern.search(raw_reply)
        
        if t_match: thought = t_match.group(1).strip()
        if w_match: willingness = int(w_match.group(1))
        if c_match: content = c_match.group(1).strip()
        else:
                if "[THOUGHT]" in raw_reply:
                    pass
                else:
                    content = raw_reply

        if "[SCENE_END]" in content:
            scene_ended = True # Just for logic check
            content = content.replace("[SCENE_END]", "").strip()
        
        return thought, willingness, content

    def test_high_willingness(self):
        reply = """
[THOUGHT]: I am very angry!
[WILLINGNESS]: 9
[CONTENT]: How dare you!
        """
        thought, w, content = self.parse_reply(reply.strip())
        self.assertEqual(w, 9)
        self.assertEqual(content, "How dare you!")
        self.assertTrue("angry" in thought)
        
        # Verify Pass Logic
        is_silence = False
        if "[PASS]" in content or (w < 4 and len(content) < 5):
            is_silence = True
        self.assertFalse(is_silence)

    def test_low_willingness_pass(self):
        reply = """
[THOUGHT]: Boring topic.
[WILLINGNESS]: 2
[CONTENT]: [PASS]
        """
        thought, w, content = self.parse_reply(reply.strip())
        self.assertEqual(w, 2)
        self.assertIn("[PASS]", content)
        
        is_silence = False
        if "[PASS]" in content or (w < 4 and len(content) < 5):
            is_silence = True
        self.assertTrue(is_silence)

    def test_low_willingness_implicit_silence(self):
        # Case where actor sends essentially nothing with low willingness
        reply = """
[THOUGHT]: Nothing to say.
[WILLINGNESS]: 3
[CONTENT]: ...
        """
        thought, w, content = self.parse_reply(reply.strip())
        self.assertEqual(w, 3)
        self.assertEqual(content, "...")
        
        is_silence = False
        if "[PASS]" in content or (w < 4 and len(content) < 5):
            is_silence = True
        self.assertTrue(is_silence)

    def test_cold_field_termination(self):
        active_actors_count = 3
        consecutive_silence_count = 0
        scene_ended = False

        # Turn 1: Silence
        consecutive_silence_count += 1
        if consecutive_silence_count >= active_actors_count: scene_ended = True
        self.assertFalse(scene_ended)

         # Turn 2: Silence
        consecutive_silence_count += 1
        if consecutive_silence_count >= active_actors_count: scene_ended = True
        self.assertFalse(scene_ended)

         # Turn 3: Silence (Threshold Reached)
        consecutive_silence_count += 1
        if consecutive_silence_count >= active_actors_count: scene_ended = True
        self.assertTrue(scene_ended)

    def test_silence_reset(self):
        active_actors_count = 3
        consecutive_silence_count = 2 # almost there
        
        # Turn 3: Speaks!
        consecutive_silence_count = 0
        
        self.assertEqual(consecutive_silence_count, 0)

if __name__ == '__main__':
    unittest.main()
