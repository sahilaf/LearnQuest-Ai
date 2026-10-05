"""Tests for the live voice tutor's context (services/live_tutor.py).

The live model gets one system instruction instead of a message list, so the
whole tutor context has to survive being folded into it. No network, no DB.
"""

from __future__ import annotations

import unittest
import uuid
from unittest.mock import patch

from app.services import live_tutor

USER = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _context(*history):
    return [
        {"role": "system", "content": "You are LearnQuest. Weak topics: recursion."},
        {"role": "system", "content": "Prior conversation summary (long-term memory): floats."},
        *history,
    ]


class TestLiveInstruction(unittest.TestCase):
    def _build(self, messages):
        with patch.object(live_tutor, "database_is_configured", return_value=False), patch.object(
            live_tutor, "build_tutor_context", return_value=messages
        ):
            return live_tutor.build_live_instruction(USER, None)

    def test_carries_profile_summary_and_spoken_rules(self) -> None:
        text = self._build(_context())
        self.assertIn("Weak topics: recursion", text)
        self.assertIn("long-term memory): floats", text)
        self.assertIn("LIVE SPOKEN conversation", text)

    def test_earlier_turns_are_included_in_order(self) -> None:
        text = self._build(_context(
            {"role": "user", "content": "What is 0.1 + 0.2?"},
            {"role": "assistant", "content": "Slightly more than 0.3."},
        ))
        self.assertIn("Student: What is 0.1 + 0.2?\nTutor: Slightly more than 0.3.", text)
        self.assertIn("do not greet the student again", text)

    def test_long_history_keeps_the_most_recent_turns(self) -> None:
        old = {"role": "user", "content": "OLDEST " + "x" * live_tutor.MAX_HISTORY_CHARS}
        new = {"role": "assistant", "content": "NEWEST"}
        text = self._build(_context(old, new))
        self.assertIn("NEWEST", text)
        self.assertNotIn("OLDEST", text)

    def test_no_history_means_no_history_section(self) -> None:
        self.assertNotIn("Earlier in this conversation", self._build(_context()))


class TestSaveTurn(unittest.TestCase):
    def test_nothing_to_save_touches_no_database(self) -> None:
        with patch.object(live_tutor, "get_session_factory") as factory:
            live_tutor.save_turn(uuid.uuid4(), "  ", "")
            live_tutor.save_turn(None, "hello", "hi")
        factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
