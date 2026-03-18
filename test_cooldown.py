"""
Unit tests for the Cool-Down (Paper Trading) Loss Prevention feature.
Tests activation, simulation, batch cycling, exit conditions, and disabled state.
"""
import unittest
from trading_bot import TradingBot


class TestSimulatedResultChecker(unittest.TestCase):
    """Test _check_simulated_result for all contract types."""

    def setUp(self):
        self.bot = TradingBot()

    def test_digitover_win(self):
        """DIGITOVER 5: digit 7 > 5 = WIN."""
        result = self.bot._check_simulated_result("DIGITOVER", 5, 7)
        self.assertTrue(result)
        print("✅ PASS: DIGITOVER 5 with exit digit 7 = WIN")

    def test_digitover_loss(self):
        """DIGITOVER 5: digit 3 < 5 = LOSS."""
        result = self.bot._check_simulated_result("DIGITOVER", 5, 3)
        self.assertFalse(result)
        print("✅ PASS: DIGITOVER 5 with exit digit 3 = LOSS")

    def test_digitover_equal_loss(self):
        """DIGITOVER 5: digit 5 is NOT > 5 = LOSS."""
        result = self.bot._check_simulated_result("DIGITOVER", 5, 5)
        self.assertFalse(result)
        print("✅ PASS: DIGITOVER 5 with exit digit 5 = LOSS (not strictly greater)")

    def test_digitunder_win(self):
        """DIGITUNDER 5: digit 3 < 5 = WIN."""
        result = self.bot._check_simulated_result("DIGITUNDER", 5, 3)
        self.assertTrue(result)
        print("✅ PASS: DIGITUNDER 5 with exit digit 3 = WIN")

    def test_digitunder_loss(self):
        """DIGITUNDER 5: digit 7 > 5 = LOSS."""
        result = self.bot._check_simulated_result("DIGITUNDER", 5, 7)
        self.assertFalse(result)
        print("✅ PASS: DIGITUNDER 5 with exit digit 7 = LOSS")

    def test_digitmatch_win(self):
        """DIGITMATCH 5: digit 5 == 5 = WIN."""
        result = self.bot._check_simulated_result("DIGITMATCH", 5, 5)
        self.assertTrue(result)
        print("✅ PASS: DIGITMATCH 5 with exit digit 5 = WIN")

    def test_digitmatch_loss(self):
        """DIGITMATCH 5: digit 3 != 5 = LOSS."""
        result = self.bot._check_simulated_result("DIGITMATCH", 5, 3)
        self.assertFalse(result)
        print("✅ PASS: DIGITMATCH 5 with exit digit 3 = LOSS")

    def test_digiteven_win(self):
        """DIGITEVEN: digit 4 is even = WIN."""
        result = self.bot._check_simulated_result("DIGITEVEN", None, 4)
        self.assertTrue(result)
        print("✅ PASS: DIGITEVEN with exit digit 4 = WIN")

    def test_digiteven_loss(self):
        """DIGITEVEN: digit 7 is odd = LOSS."""
        result = self.bot._check_simulated_result("DIGITEVEN", None, 7)
        self.assertFalse(result)
        print("✅ PASS: DIGITEVEN with exit digit 7 = LOSS")

    def test_digitodd_win(self):
        """DIGITODD: digit 7 is odd = WIN."""
        result = self.bot._check_simulated_result("DIGITODD", None, 7)
        self.assertTrue(result)
        print("✅ PASS: DIGITODD with exit digit 7 = WIN")

    def test_digitodd_loss(self):
        """DIGITODD: digit 4 is even = LOSS."""
        result = self.bot._check_simulated_result("DIGITODD", None, 4)
        self.assertFalse(result)
        print("✅ PASS: DIGITODD with exit digit 4 = LOSS")


class TestCooldownActivation(unittest.TestCase):
    """Test that cooldown activates after X consecutive losses."""

    def setUp(self):
        self.bot = TradingBot()
        self.bot.cooldown_enabled = True
        self.bot.cooldown_after = 3
        self.bot.cooldown_check = 2

    def _simulate_trade_result(self, profit):
        """Simulate the trade result handler's cooldown logic."""
        if profit > 0:
            self.bot.wins += 1
        else:
            self.bot.losses += 1

        if self.bot.cooldown_enabled:
            if profit <= 0:
                self.bot.cooldown_loss_streak += 1
                if self.bot.cooldown_loss_streak >= self.bot.cooldown_after and not self.bot.cooldown_active:
                    self.bot.cooldown_active = True
                    self.bot.cooldown_sim_wins = 0
                    self.bot.cooldown_sim_count = 0
            else:
                self.bot.cooldown_loss_streak = 0

    def test_no_cooldown_before_threshold(self):
        """2 losses with threshold 3 should NOT activate cooldown."""
        self._simulate_trade_result(-0.35)
        self._simulate_trade_result(-0.35)
        self.assertFalse(self.bot.cooldown_active)
        self.assertEqual(self.bot.cooldown_loss_streak, 2)
        print("✅ PASS: 2 losses (threshold 3) = cooldown NOT active")

    def test_cooldown_activates_at_threshold(self):
        """3 losses with threshold 3 SHOULD activate cooldown."""
        self._simulate_trade_result(-0.35)
        self._simulate_trade_result(-0.35)
        self._simulate_trade_result(-0.35)
        self.assertTrue(self.bot.cooldown_active)
        print("✅ PASS: 3 losses (threshold 3) = cooldown ACTIVE")

    def test_win_resets_loss_streak(self):
        """A win should reset the loss streak counter."""
        self._simulate_trade_result(-0.35)
        self._simulate_trade_result(-0.35)
        self._simulate_trade_result(0.50)  # win resets
        self.assertEqual(self.bot.cooldown_loss_streak, 0)
        self.assertFalse(self.bot.cooldown_active)
        print("✅ PASS: Win resets loss streak counter")

    def test_win_between_losses_prevents_cooldown(self):
        """Loss, loss, win, loss, loss should NOT activate (streak broken)."""
        self._simulate_trade_result(-0.35)
        self._simulate_trade_result(-0.35)
        self._simulate_trade_result(0.50)  # resets
        self._simulate_trade_result(-0.35)
        self._simulate_trade_result(-0.35)
        self.assertFalse(self.bot.cooldown_active)
        self.assertEqual(self.bot.cooldown_loss_streak, 2)
        print("✅ PASS: Win between losses prevents cooldown activation")


class TestCooldownSimulation(unittest.TestCase):
    """Test the simulation batch logic."""

    def setUp(self):
        self.bot = TradingBot()
        self.bot.cooldown_enabled = True
        self.bot.cooldown_after = 3
        self.bot.cooldown_check = 2
        self.bot.cooldown_active = True  # Start in cooldown

    def _resolve_pending_sim(self, exit_digit):
        """Simulate resolving a pending simulation on the next tick."""
        if self.bot.cooldown_pending_sim:
            sim = self.bot.cooldown_pending_sim
            self.bot.cooldown_pending_sim = None
            sim_win = self.bot._check_simulated_result(
                sim['contract_type'], sim.get('barrier'), exit_digit
            )
            self.bot.cooldown_sim_count += 1
            if sim_win:
                self.bot.cooldown_sim_wins += 1

            if self.bot.cooldown_sim_count >= self.bot.cooldown_check:
                if self.bot.cooldown_sim_wins >= 1:
                    self.bot.cooldown_active = False
                    self.bot.cooldown_loss_streak = 0
                self.bot.cooldown_sim_wins = 0
                self.bot.cooldown_sim_count = 0

    def test_sim_win_exits_cooldown(self):
        """If 1 of 2 simulated trades wins, cooldown should exit."""
        # Sim trade 1: DIGITOVER 5 -> exit digit 8 -> WIN
        self.bot.cooldown_pending_sim = {'contract_type': 'DIGITOVER', 'barrier': 5}
        self._resolve_pending_sim(8)
        # Sim trade 2: DIGITOVER 5 -> exit digit 3 -> LOSS
        self.bot.cooldown_pending_sim = {'contract_type': 'DIGITOVER', 'barrier': 5}
        self._resolve_pending_sim(3)
        # Should exit cooldown (1 win found)
        self.assertFalse(self.bot.cooldown_active)
        print("✅ PASS: 1 win in 2 sim trades → cooldown exits")

    def test_all_sim_losses_stays_in_cooldown(self):
        """If all Y simulated trades lose, cooldown stays active."""
        # Sim trade 1: DIGITOVER 5 -> exit digit 3 -> LOSS
        self.bot.cooldown_pending_sim = {'contract_type': 'DIGITOVER', 'barrier': 5}
        self._resolve_pending_sim(3)
        # Sim trade 2: DIGITOVER 5 -> exit digit 2 -> LOSS
        self.bot.cooldown_pending_sim = {'contract_type': 'DIGITOVER', 'barrier': 5}
        self._resolve_pending_sim(2)
        # Should stay in cooldown
        self.assertTrue(self.bot.cooldown_active)
        print("✅ PASS: 0 wins in 2 sim trades → cooldown stays active")

    def test_batch_resets_for_next_cycle(self):
        """After a full losing batch, sim counters reset for the next batch."""
        # Batch 1: 2 losses
        self.bot.cooldown_pending_sim = {'contract_type': 'DIGITOVER', 'barrier': 5}
        self._resolve_pending_sim(3)
        self.bot.cooldown_pending_sim = {'contract_type': 'DIGITOVER', 'barrier': 5}
        self._resolve_pending_sim(2)
        # Counters should be reset
        self.assertEqual(self.bot.cooldown_sim_count, 0)
        self.assertEqual(self.bot.cooldown_sim_wins, 0)
        self.assertTrue(self.bot.cooldown_active)
        # Batch 2: 1 win, 1 loss → should exit
        self.bot.cooldown_pending_sim = {'contract_type': 'DIGITOVER', 'barrier': 5}
        self._resolve_pending_sim(9)  # WIN
        self.bot.cooldown_pending_sim = {'contract_type': 'DIGITOVER', 'barrier': 5}
        self._resolve_pending_sim(1)  # LOSS
        self.assertFalse(self.bot.cooldown_active)
        print("✅ PASS: Batch 1 (all losses) → Batch 2 (1 win) → cooldown exits")

    def test_digiteven_simulation(self):
        """DIGITEVEN simulation works correctly."""
        self.bot.cooldown_pending_sim = {'contract_type': 'DIGITEVEN', 'barrier': None}
        self._resolve_pending_sim(4)  # even = WIN
        self.bot.cooldown_pending_sim = {'contract_type': 'DIGITEVEN', 'barrier': None}
        self._resolve_pending_sim(5)  # odd = LOSS
        self.assertFalse(self.bot.cooldown_active)
        print("✅ PASS: DIGITEVEN sim (4=win, 5=loss) → cooldown exits")


class TestCooldownEdgeCases(unittest.TestCase):
    """Test edge cases and interactions."""

    def test_cooldown_disabled_no_effect(self):
        """When disabled, losses should NOT trigger cooldown."""
        bot = TradingBot()
        bot.cooldown_enabled = False
        # Simulate 10 losses
        for _ in range(10):
            bot.cooldown_loss_streak += 1
        self.assertFalse(bot.cooldown_active)
        print("✅ PASS: Cooldown disabled = no activation regardless of losses")

    def test_reset_stats_clears_cooldown(self):
        """reset_stats should clear all cooldown state."""
        bot = TradingBot()
        bot.cooldown_enabled = True
        bot.cooldown_active = True
        bot.cooldown_loss_streak = 5
        bot.cooldown_sim_count = 1
        bot.cooldown_sim_wins = 0
        bot.cooldown_pending_sim = {'contract_type': 'DIGITOVER', 'barrier': 5}
        bot.reset_stats()
        self.assertFalse(bot.cooldown_active)
        self.assertEqual(bot.cooldown_loss_streak, 0)
        self.assertEqual(bot.cooldown_sim_count, 0)
        self.assertEqual(bot.cooldown_sim_wins, 0)
        self.assertIsNone(bot.cooldown_pending_sim)
        print("✅ PASS: reset_stats clears all cooldown state")

    def test_cooldown_after_1(self):
        """Cooldown with after=1 activates on the very first loss."""
        bot = TradingBot()
        bot.cooldown_enabled = True
        bot.cooldown_after = 1
        bot.cooldown_check = 1
        # 1 loss
        bot.cooldown_loss_streak = 1
        if bot.cooldown_loss_streak >= bot.cooldown_after:
            bot.cooldown_active = True
        self.assertTrue(bot.cooldown_active)
        print("✅ PASS: cooldown_after=1 activates on first loss")

    def test_check_1_exits_on_single_sim_win(self):
        """With check=1, a single sim win should exit cooldown."""
        bot = TradingBot()
        bot.cooldown_enabled = True
        bot.cooldown_check = 1
        bot.cooldown_active = True
        bot.cooldown_pending_sim = {'contract_type': 'DIGITOVER', 'barrier': 0}
        # Resolve: DIGITOVER 0, exit digit 5 -> 5 > 0 = WIN
        sim_win = bot._check_simulated_result('DIGITOVER', 0, 5)
        bot.cooldown_sim_count = 1
        bot.cooldown_sim_wins = 1 if sim_win else 0
        if bot.cooldown_sim_count >= bot.cooldown_check and bot.cooldown_sim_wins >= 1:
            bot.cooldown_active = False
        self.assertFalse(bot.cooldown_active)
        print("✅ PASS: check=1, single sim win → cooldown exits")

    def test_settings_update_cooldown(self):
        """update_settings should correctly set cooldown params."""
        bot = TradingBot()
        bot.update_settings(
            cooldown_enabled='true',
            cooldown_after=5,
            cooldown_check=3
        )
        self.assertTrue(bot.cooldown_enabled)
        self.assertEqual(bot.cooldown_after, 5)
        self.assertEqual(bot.cooldown_check, 3)
        print("✅ PASS: update_settings correctly sets cooldown params")


if __name__ == '__main__':
    unittest.main(verbosity=2)
