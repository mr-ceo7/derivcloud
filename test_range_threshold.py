"""
Unit tests for the Range Threshold strategy.
Tests that the bot strictly obeys the consecutive trigger logic:
- Only fires after X consecutive ticks below/above the barrier
- Resets counter when a tick breaks the streak
- Resets counter after a trade is placed
"""
import unittest
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio
import json
from trading_bot import TradingBot


class TestRangeThresholdBelow(unittest.TestCase):
    """Test Range Threshold strategy with direction='below'"""

    def setUp(self):
        self.bot = TradingBot()
        self.bot.strategy = "range_threshold"
        self.bot.range_barrier = 5
        self.bot.range_direction = "below"
        self.bot.consecutive_triggers = 3
        self.bot.api_token = "test_token"
        self.bot.is_running = True
        self.bot.currency = "USD"
        # Mock websocket to capture sent messages
        self.bot.websocket = AsyncMock()
        self.sent_messages = []

        async def capture_send(data):
            self.sent_messages.append(json.loads(data))

        self.bot.websocket.send = capture_send

    def _make_tick(self, quote_value):
        """Helper: create a tick message with a specific last digit."""
        return json.dumps({
            "msg_type": "tick",
            "tick": {"quote": quote_value}
        })

    def _run(self, coro):
        """Run async coroutine synchronously."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_fires_after_3_consecutive_below(self):
        """Should fire DIGITOVER after 3 consecutive digits below barrier."""
        self.sent_messages.clear()

        # Tick 1: digit 3 (< 5), counter -> 1, no trade
        self._run(self.bot.handle_message(self._make_tick(100.03)))
        self.assertEqual(len(self.sent_messages), 0, "Should NOT trade after 1 tick")

        # Tick 2: digit 1 (< 5), counter -> 2, no trade
        self._run(self.bot.handle_message(self._make_tick(100.01)))
        self.assertEqual(len(self.sent_messages), 0, "Should NOT trade after 2 ticks")

        # Tick 3: digit 2 (< 5), counter -> 3, TRADE!
        self._run(self.bot.handle_message(self._make_tick(100.02)))
        self.assertEqual(len(self.sent_messages), 1, "Should trade after 3 consecutive ticks below barrier")
        proposal = self.sent_messages[0]
        self.assertEqual(proposal["contract_type"], "DIGITOVER")
        self.assertEqual(proposal["barrier"], 5)
        print("✅ PASS: Fires DIGITOVER 5 after 3 consecutive digits below 5")

    def test_resets_on_break(self):
        """Counter should reset when a digit >= barrier appears."""
        self.sent_messages.clear()

        # 2 below, then 1 above (breaks streak)
        self._run(self.bot.handle_message(self._make_tick(100.03)))  # digit 3, counter 1
        self._run(self.bot.handle_message(self._make_tick(100.01)))  # digit 1, counter 2
        self._run(self.bot.handle_message(self._make_tick(100.07)))  # digit 7 (>= 5), counter RESET to 0
        self.assertEqual(len(self.sent_messages), 0, "Should NOT trade — streak broken")

        # Now 2 more below — only 2, not 3 yet
        self._run(self.bot.handle_message(self._make_tick(100.04)))  # digit 4, counter 1
        self._run(self.bot.handle_message(self._make_tick(100.02)))  # digit 2, counter 2
        self.assertEqual(len(self.sent_messages), 0, "Should NOT trade — only 2 after reset")

        # 3rd below — NOW it should fire
        self._run(self.bot.handle_message(self._make_tick(100.00)))  # digit 0, counter 3
        self.assertEqual(len(self.sent_messages), 1, "Should trade after fresh 3-tick streak")
        print("✅ PASS: Counter properly resets when streak is broken")

    def test_resets_after_trade(self):
        """Counter should reset after a trade, requiring a fresh streak."""
        self.sent_messages.clear()

        # Trigger first trade (3 consecutive below)
        self._run(self.bot.handle_message(self._make_tick(100.01)))  # counter 1
        self._run(self.bot.handle_message(self._make_tick(100.02)))  # counter 2
        self._run(self.bot.handle_message(self._make_tick(100.03)))  # counter 3 -> TRADE
        self.assertEqual(len(self.sent_messages), 1, "First trade should fire")
        self.assertTrue(self.bot.waiting_for_result, "Should be waiting for result")

        # Simulate the buy confirmation that resets waiting_for_result
        # (In reality, Deriv sends proposal response then buy response)
        buy_msg = json.dumps({
            "msg_type": "buy",
            "buy": {"contract_id": "test_123"}
        })
        self._run(self.bot.handle_message(buy_msg))
        self.assertFalse(self.bot.waiting_for_result, "Buy confirmation should clear waiting flag")

        # Now 3 more below — should trigger again
        self._run(self.bot.handle_message(self._make_tick(100.04)))  # counter 1
        self._run(self.bot.handle_message(self._make_tick(100.01)))  # counter 2
        self._run(self.bot.handle_message(self._make_tick(100.02)))  # counter 3 -> TRADE
        # Expected 3 total: trade1 proposal + proposal_open_contract subscribe + trade2 proposal
        proposals_sent = [m for m in self.sent_messages if 'proposal' in m and m.get('proposal') == 1]
        self.assertEqual(len(proposals_sent), 2, "Should have 2 trade proposals total")
        print("✅ PASS: Counter resets after trade, needs fresh 3-tick streak")

    def test_no_trade_on_exact_barrier(self):
        """Digit equal to barrier should NOT count as 'below'."""
        self.sent_messages.clear()

        self._run(self.bot.handle_message(self._make_tick(100.03)))  # digit 3, counter 1
        self._run(self.bot.handle_message(self._make_tick(100.05)))  # digit 5 (== barrier, NOT below), counter RESET
        self._run(self.bot.handle_message(self._make_tick(100.02)))  # digit 2, counter 1
        self.assertEqual(len(self.sent_messages), 0, "Digit == barrier should break the streak")
        print("✅ PASS: Digit equal to barrier does NOT count as below")


class TestRangeThresholdAbove(unittest.TestCase):
    """Test Range Threshold strategy with direction='above'"""

    def setUp(self):
        self.bot = TradingBot()
        self.bot.strategy = "range_threshold"
        self.bot.range_barrier = 5
        self.bot.range_direction = "above"
        self.bot.consecutive_triggers = 3
        self.bot.api_token = "test_token"
        self.bot.is_running = True
        self.bot.currency = "USD"
        self.bot.websocket = AsyncMock()
        self.sent_messages = []

        async def capture_send(data):
            self.sent_messages.append(json.loads(data))

        self.bot.websocket.send = capture_send

    def _make_tick(self, quote_value):
        return json.dumps({
            "msg_type": "tick",
            "tick": {"quote": quote_value}
        })

    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_fires_after_3_consecutive_above(self):
        """Should fire DIGITUNDER after 3 consecutive digits above barrier."""
        self.sent_messages.clear()

        self._run(self.bot.handle_message(self._make_tick(100.07)))  # digit 7, counter 1
        self._run(self.bot.handle_message(self._make_tick(100.08)))  # digit 8, counter 2
        self._run(self.bot.handle_message(self._make_tick(100.09)))  # digit 9, counter 3 -> TRADE
        self.assertEqual(len(self.sent_messages), 1)
        proposal = self.sent_messages[0]
        self.assertEqual(proposal["contract_type"], "DIGITUNDER")
        self.assertEqual(proposal["barrier"], 5)
        print("✅ PASS: Fires DIGITUNDER 5 after 3 consecutive digits above 5")

    def test_resets_on_break_above(self):
        """Counter resets when digit <= barrier appears."""
        self.sent_messages.clear()

        self._run(self.bot.handle_message(self._make_tick(100.08)))  # counter 1
        self._run(self.bot.handle_message(self._make_tick(100.06)))  # counter 2
        self._run(self.bot.handle_message(self._make_tick(100.03)))  # digit 3 (<= 5), RESET
        self._run(self.bot.handle_message(self._make_tick(100.07)))  # counter 1
        self._run(self.bot.handle_message(self._make_tick(100.09)))  # counter 2
        self.assertEqual(len(self.sent_messages), 0, "Should NOT trade — streak broken")
        print("✅ PASS: Counter resets when digit <= barrier (above mode)")

    def test_no_trade_on_exact_barrier_above(self):
        """Digit equal to barrier should NOT count as 'above'."""
        self.sent_messages.clear()

        self._run(self.bot.handle_message(self._make_tick(100.07)))  # counter 1
        self._run(self.bot.handle_message(self._make_tick(100.05)))  # digit 5 (== barrier), RESET
        self._run(self.bot.handle_message(self._make_tick(100.08)))  # counter 1
        self.assertEqual(len(self.sent_messages), 0, "Digit == barrier should break the streak")
        print("✅ PASS: Digit equal to barrier does NOT count as above")


class TestDigitStreakUnchanged(unittest.TestCase):
    """Ensure the original Digit Streak strategy still works correctly."""

    def setUp(self):
        self.bot = TradingBot()
        self.bot.strategy = "digit_streak"
        self.bot.prediction_digit = 0
        self.bot.consecutive_triggers = 2
        self.bot.smart_mode = False
        self.bot.api_token = "test_token"
        self.bot.is_running = True
        self.bot.currency = "USD"
        self.bot.websocket = AsyncMock()
        self.sent_messages = []

        async def capture_send(data):
            self.sent_messages.append(json.loads(data))

        self.bot.websocket.send = capture_send

    def _make_tick(self, quote_value):
        return json.dumps({
            "msg_type": "tick",
            "tick": {"quote": quote_value}
        })

    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_digit_streak_still_works(self):
        """Original strategy should fire after 2 consecutive 0s."""
        self.sent_messages.clear()

        self._run(self.bot.handle_message(self._make_tick(100.00)))  # digit 0, streak 1
        self.assertEqual(len(self.sent_messages), 0)

        self._run(self.bot.handle_message(self._make_tick(100.10)))  # digit 0, streak 2 -> TRADE
        self.assertEqual(len(self.sent_messages), 1)
        self.assertEqual(self.sent_messages[0]["contract_type"], "DIGITOVER")
        print("✅ PASS: Original Digit Streak strategy is unaffected")


if __name__ == '__main__':
    unittest.main(verbosity=2)
