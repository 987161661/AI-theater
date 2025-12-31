import unittest
from core.state.performance_blackboard import PerformanceBlackboard

class TestPerformanceBlackboard(unittest.TestCase):
    def setUp(self):
        self.bb = PerformanceBlackboard()

    def test_add_and_retrieve_dialogue(self):
        # Test adding structured dialogue
        self.bb.add_dialogue("UserA", "Hello World")
        self.bb.add_dialogue("UserB", "Hi there")

        # Test structured retrieval
        struct_hist = self.bb.get_recent_dialogue_struct(2)
        self.assertEqual(len(struct_hist), 2)
        self.assertEqual(struct_hist[0]['speaker'], "UserA")
        self.assertEqual(struct_hist[0]['content'], "Hello World")

        # Test string retrieval (compatibility)
        str_hist = self.bb.get_recent_dialogue(2)
        expected_str = "UserA: Hello World\nUserB: Hi there"
        self.assertEqual(str_hist, expected_str)

    def test_limit(self):
        for i in range(10):
            self.bb.add_dialogue(f"User{i}", f"Message {i}")
        
        recent = self.bb.get_recent_dialogue_struct(3)
        self.assertEqual(len(recent), 3)
        self.assertEqual(recent[-1]['content'], "Message 9")

if __name__ == '__main__':
    unittest.main()
