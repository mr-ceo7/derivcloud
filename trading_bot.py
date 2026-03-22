import asyncio
import websockets
import json
import logging
import threading
import time
from datetime import datetime

class GlobalTickManager:
    def __init__(self):
        self.market_history = {} # market -> list of dicts
        self.subscriptions = set()
        self.websocket = None
        self.is_running = False
        self.loop = None
        self.thread = None
        self.subscribers = [] # list of Bot instances

    def start(self):
        if self.is_running: return
        self.is_running = True
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.is_running = False

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._websocket_logic())

    async def _websocket_logic(self):
        uri = "wss://ws.binaryws.com/websockets/v3?app_id=69330"
        async for websocket in websockets.connect(uri):
            self.websocket = websocket
            try:
                for market in list(self.subscriptions):
                    await self.websocket.send(json.dumps({"ticks": market, "subscribe": 1}))

                async for message in websocket:
                    if not self.is_running: break
                    data = json.loads(message)
                    if 'error' in data:
                        logging.error(f"TickManager Error: {data['error']['message']}")
                        continue

                    if data.get('msg_type') == 'tick':
                        tick = data['tick']
                        market = tick['symbol']
                        epoch = tick['epoch']
                        quote = tick['quote']
                        pip_size = tick.get('pip_size', 2)
                        quote_str = f"{{:.{pip_size}f}}".format(quote)
                        last_digit = int(quote_str[-1])
                        
                        if market not in self.market_history:
                            self.market_history[market] = []
                        
                        if not self.market_history[market] or self.market_history[market][-1]['epoch'] != epoch:
                            self.market_history[market].append({
                                'epoch': epoch,
                                'digit': last_digit
                            })
                            if len(self.market_history[market]) > 100:
                                self.market_history[market].pop(0)

                            for bot in list(self.subscribers):
                                if bot.is_running and bot.market == market and bot.loop:
                                    try:
                                        asyncio.run_coroutine_threadsafe(
                                            bot.handle_message(message), 
                                            bot.loop
                                        )
                                    except Exception as dispatch_err:
                                        logging.error(f"TickManager dispatch error for {getattr(bot, 'account_id', '?')}: {dispatch_err}")

            except websockets.ConnectionClosed:
                continue
            except Exception as e:
                if not self.is_running: break
                await asyncio.sleep(5)

    def subscribe_market(self, market):
        if market not in self.subscriptions:
            self.subscriptions.add(market)
            if self.websocket and self.is_running and self.loop:
                asyncio.run_coroutine_threadsafe(
                    self.websocket.send(json.dumps({"ticks": market, "subscribe": 1})),
                    self.loop
                )

    def register_bot(self, bot):
        if bot not in self.subscribers:
            self.subscribers.append(bot)
            self.subscribe_market(bot.market)

    def unregister_bot(self, bot):
        if bot in self.subscribers:
            self.subscribers.remove(bot)

    def calculate_streak(self, bot):
        history = self.market_history.get(bot.market, [])
        streak = 0
        streak_digit = -1
        range_counter = 0

        for tick in history:
            digit = tick['digit']
            if digit == streak_digit:
                streak += 1
            else:
                streak = 1
                streak_digit = digit

            if bot.strategy == "range_threshold":
                if bot.range_direction == "below" and digit < bot.range_barrier:
                    range_counter += 1
                elif bot.range_direction == "above" and digit > bot.range_barrier:
                    range_counter += 1
                else:
                    range_counter = 0

            # Simulate the reset that happens when the bot actually places a trade!
            if bot.strategy == "range_threshold":
                if range_counter >= bot.consecutive_triggers:
                    range_counter = 0
                    streak = 0
                    streak_digit = -1
            elif bot.strategy == "digit_streak":
                if bot.smart_mode:
                    if streak >= bot.consecutive_triggers and (streak_digit == 0 or streak_digit == 9):
                        streak = 0
                        streak_digit = -1
                else:
                    if streak >= bot.consecutive_triggers and streak_digit == bot.prediction_digit:
                        streak = 0
                        streak_digit = -1

        bot.consecutive_counter = streak
        bot.streak_digit = streak_digit
        bot.range_consecutive_counter = range_counter

global_tick_manager = GlobalTickManager()
global_tick_manager.start()

class TradingBot:
    # Net Profit Multipliers for $1 stake (approximate, based on probability - margin)
    PAYOUT_MULTIPLIERS = {
        "DIGITOVER": {0: 0.09, 1: 0.23, 2: 0.40, 3: 0.64, 4: 0.96, 5: 1.43, 6: 2.21, 7: 3.86, 8: 7.93},
        "DIGITUNDER": {1: 7.93, 2: 3.86, 3: 2.21, 4: 1.43, 5: 0.96, 6: 0.64, 7: 0.40, 8: 0.23, 9: 0.09},
        "DIGITMATCH": {0: 8.50, 1: 8.50, 2: 8.50, 3: 8.50, 4: 8.50, 5: 8.50, 6: 8.50, 7: 8.50, 8: 8.50, 9: 8.50},
        "DIGITEVEN": {None: 0.94},
        "DIGITODD": {None: 0.94}
    }

    def __init__(self):
        self.api_token = "YOUR_API_TOKEN"
        self.market = "1HZ100V" # Volatility 100 (1s) Index
        self.stake = 0.35
        self.duration = 1
        self.prediction_digit = 0
        self.consecutive_triggers = 1
        self.smart_mode = False # Trade both 0 and 9
        self.take_profit = 0.0  # Target profit to stop bot (0 = disabled)
        
        # Strategy selection: "digit_streak", "range_threshold", or "trio_coverage"
        self.strategy = "digit_streak"
        
        # Range Threshold settings
        self.range_barrier = 5
        self.range_direction = "below"  # "below" or "above"
        self.range_consecutive_counter = 0
        
        # Trio Coverage settings
        self.trio_role = "over_5"    # "over_5", "under_5", "match_5"
        self.trio_trigger = "every_tick"  # "every_tick" or "on_digit_5"
        self.trio_digit = 5  # Prediction digit for trio (0-9)
        
        # Even/Odd Duo settings
        self.duo_role = "even"          # "even" or "odd"
        self.duo_trigger = "every_tick"  # "every_tick" or "on_digit"
        self.duo_trigger_digit = 5       # Digit that triggers (0-9)
        self.duo_switch_enabled = False
        self.duo_switch_after = 3        # Switch after N consecutive losses
        self.duo_consecutive_losses = 0  # Current consecutive loss count
        
        # Cool-Down (Paper Trading) settings
        self.cooldown_enabled = False
        self.cooldown_after = 3          # X: Enter cooldown after X consecutive losses
        self.cooldown_check = 2          # Y: Simulate Y trades before resuming
        self.cooldown_active = False     # Whether currently in cooldown mode
        self.cooldown_pending_sim = None # Pending simulated trade awaiting next tick
        self.cooldown_sim_wins = 0       # Wins in current simulation batch
        self.cooldown_sim_count = 0      # Trades checked in current simulation batch
        self.cooldown_loss_streak = 0    # Current consecutive real-trade loss count
        
        # Martingale Recovery settings
        self.martingale_enabled = False
        self.martingale_mode = "multiply"  # "multiply" or "additive"
        self.martingale_multiplier = 2.0
        self.martingale_increment = 0.35
        self.martingale_max_stake = 10.0
        self.base_stake = self.stake  # Original stake to reset to
        self.martingale_profit = 0.0  # Cumulative profit for current sequence
        
        self.is_running = False
        self.websocket = None
        self.loop = None
        self.thread = None
        self.currency = "USD"
        self.current_balance = 0.0
        self.account_id = None
        
        # Stats
        self.total_profit = 0.0
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.logs = []
        self.current_digit = None
        self.current_quote = None
        self.consecutive_counter = 0
        self.streak_digit = -1
        self.start_time = None
        self.trade_history = []
        self.active_trades = {} # contract_id -> trigger_info
        self.last_trigger = None # Temp store for trigger details
        self.last_tick_epoch = None  # Track last processed tick to skip duplicates
        self.waiting_for_result = False  # Prevent re-triggering while trade is pending
        self.waiting_since = None          # Timestamp when waiting_for_result was set True

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)
        self.logs.insert(0, log_entry)
        if len(self.logs) > 50:
            self.logs.pop()

    def update_settings(self, token=None, market=None, stake=None, duration=None, prediction=None, consecutive=None, smart_mode=None, take_profit=None, strategy=None, range_barrier=None, range_direction=None, martingale_enabled=None, martingale_mode=None, martingale_multiplier=None, martingale_increment=None, martingale_max_stake=None, trio_role=None, trio_trigger=None, trio_digit=None, duo_role=None, duo_trigger=None, duo_trigger_digit=None, duo_switch_enabled=None, duo_switch_after=None, cooldown_enabled=None, cooldown_after=None, cooldown_check=None):
        if token: self.api_token = token
        if market:
            self.market = market
            if self.is_running:
                global_tick_manager.subscribe_market(market)
                global_tick_manager.calculate_streak(self)
        if stake:
            self.stake = float(stake)
            self.base_stake = float(stake)
        if duration: self.duration = int(duration)
        if prediction is not None: self.prediction_digit = int(prediction)
        if consecutive: self.consecutive_triggers = int(consecutive)
        if smart_mode is not None: self.smart_mode = (str(smart_mode).lower() == 'true')
        if take_profit is not None: self.take_profit = float(take_profit)
        if strategy: self.strategy = strategy
        if range_barrier is not None: self.range_barrier = int(range_barrier)
        if range_direction: self.range_direction = range_direction
        if martingale_enabled is not None: self.martingale_enabled = (str(martingale_enabled).lower() == 'true')
        if martingale_mode: self.martingale_mode = martingale_mode
        if martingale_multiplier is not None: self.martingale_multiplier = float(martingale_multiplier)
        if martingale_increment is not None: self.martingale_increment = float(martingale_increment)
        if martingale_max_stake is not None: self.martingale_max_stake = float(martingale_max_stake)
        if trio_role: self.trio_role = trio_role
        if trio_trigger: self.trio_trigger = trio_trigger
        if trio_digit is not None: self.trio_digit = int(trio_digit)
        if duo_role: self.duo_role = duo_role
        if duo_trigger: self.duo_trigger = duo_trigger
        if duo_trigger_digit is not None: self.duo_trigger_digit = int(duo_trigger_digit)
        if duo_switch_enabled is not None: self.duo_switch_enabled = (str(duo_switch_enabled).lower() == 'true')
        if duo_switch_after is not None: self.duo_switch_after = int(duo_switch_after)
        if cooldown_enabled is not None: self.cooldown_enabled = (str(cooldown_enabled).lower() == 'true')
        if cooldown_after is not None: self.cooldown_after = int(cooldown_after)
        if cooldown_check is not None: self.cooldown_check = int(cooldown_check)
        self.log(f"Settings updated: Strategy={self.strategy}, Stake={self.stake}, Martingale={'ON' if self.martingale_enabled else 'OFF'}")

    def reset_stats(self):
        self.total_profit = 0.0
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.logs = []
        self.trade_history = []
        self.active_trades = {}
        self.range_consecutive_counter = 0
        self.last_tick_epoch = None
        self.waiting_for_result = False
        self.waiting_since = None
        self.stake = self.base_stake  # Reset stake to base
        self.martingale_profit = 0.0
        self.cooldown_active = False
        self.cooldown_pending_sim = None
        self.cooldown_sim_wins = 0
        self.cooldown_sim_count = 0
        self.cooldown_loss_streak = 0
        self.log("Stats reset by user.")

    def start_bot(self):
        if self.is_running:
            return
        
        if not self.api_token or self.api_token == "YOUR_API_TOKEN":
            self.log("Error: API Token not set.")
            return

        self.is_running = True
        self.start_time = datetime.now()
        self.log("Bot started.")
        
        self.loop = asyncio.new_event_loop()
        global_tick_manager.register_bot(self)
        global_tick_manager.calculate_streak(self)
        
        # Run event loop in separate thread
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop_bot(self):
        if not self.is_running:
            return
        self.is_running = False
        self.start_time = None
        self.log("Bot stopped.")
        global_tick_manager.unregister_bot(self)
        # Loop will exit when is_running is False and socket closes

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._websocket_logic())

    async def _websocket_logic(self):
        uri = "wss://ws.binaryws.com/websockets/v3?app_id=69330"
        async for websocket in websockets.connect(uri):
            self.websocket = websocket
            try:
                # 1. Authorize
                await self.send({"authorize": self.api_token})
                
                # 2. Subscribe to Ticks (Handled globally directly now)
                
                # 3. Message Loop
                async for message in websocket:
                    if not self.is_running:
                        break
                    await self.handle_message(message)
                    
            except websockets.ConnectionClosed:
                self.log("Connection closed. Reconnecting...")
                continue
            except Exception as e:
                self.log(f"Error: {e}")
                if not self.is_running:
                    break
                await asyncio.sleep(5)

    async def send(self, data):
        if self.websocket:
            await self.websocket.send(json.dumps(data))

    async def handle_message(self, message):
      try:
        data = json.loads(message)
        
        if 'error' in data:
            err_msg = data['error']['message']
            err_code = data['error'].get('code')
            self.log(f"Error: {err_msg}")
            
            if err_code in ['RateLimit', 'TooManyRequests']:
                self.log("Rate limit hit. Retrying in 5s...")
                async def _retry():
                    await asyncio.sleep(5)
                    await self.send({"authorize": self.api_token})
                asyncio.create_task(_retry())
                
            return

        msg_type = data.get('msg_type')

        if msg_type == 'authorize':
            self.current_balance = data['authorize']['balance']
            self.currency = data['authorize']['currency']
            self.log(f"Authorized. Balance: {self.current_balance} {self.currency}")
            
            # Now that we are fully authorized, subscribe to live balance updates
            asyncio.create_task(self.send({"balance": 1, "subscribe": 1}))
            
            # ── Reconnection Recovery: re-subscribe to in-flight contracts ──
            if self.active_trades:
                for cid in list(self.active_trades.keys()):
                    asyncio.create_task(self.send({"proposal_open_contract": 1, "contract_id": cid, "subscribe": 1}))
                self.log(f"♻️ Re-subscribed to {len(self.active_trades)} open contract(s) after reconnect")
            elif self.waiting_for_result:
                # Proposal/buy was in progress but lost — no contract to track
                self.waiting_for_result = False
                self.waiting_since = None
                self.log("⚠️ Cleared stale waiting_for_result (no active contracts after reconnect)")

        elif msg_type == 'balance':
            self.current_balance = data['balance']['balance']
            self.currency = data['balance']['currency']
            self.log(f"💰 Live Balance Update: {self.current_balance} {self.currency}")

        elif msg_type == 'tick':
            tick_epoch = data['tick'].get('epoch')
            
            # Skip duplicate ticks (same epoch = same tick rebroadcast)
            if tick_epoch and tick_epoch == self.last_tick_epoch:
                return
            self.last_tick_epoch = tick_epoch
            
            # ── Safety Timeout: unblock if waiting_for_result stuck > 30s ──
            if self.waiting_for_result and self.waiting_since:
                if time.time() - self.waiting_since > 30:
                    self.log("⚠️ Trade timeout! No result in 30s. Unblocking bot.")
                    self.waiting_for_result = False
                    self.waiting_since = None
            
            quote = data['tick']['quote']
            pip_size = data['tick'].get('pip_size', 2)
            quote_str = f"{{:.{pip_size}f}}".format(quote)
            last_digit = int(quote_str[-1])
            self.current_digit = last_digit
            self.current_quote = quote_str
            
            # ── Resolve Pending Cool-Down Simulation ──
            if self.cooldown_pending_sim:
                sim = self.cooldown_pending_sim
                self.cooldown_pending_sim = None
                sim_win = self._check_simulated_result(sim['contract_type'], sim.get('barrier'), last_digit)
                self.cooldown_sim_count += 1
                if sim_win:
                    self.cooldown_sim_wins += 1
                self.log(f"🔍 Sim trade {self.cooldown_sim_count}/{self.cooldown_check}: {sim['contract_type']} → {'WIN' if sim_win else 'LOSS'} (digit={last_digit})")
                
                if self.cooldown_sim_count >= self.cooldown_check:
                    if self.cooldown_sim_wins >= 1:
                        # At least 1 win → exit cooldown
                        self.cooldown_active = False
                        self.cooldown_loss_streak = 0
                        self.log(f"✅ Cool-down ended! {self.cooldown_sim_wins}/{self.cooldown_sim_count} sim wins. Resuming real trades.")
                    else:
                        self.log(f"❌ All {self.cooldown_check} sim trades lost. Checking next batch...")
                    # Reset batch counters for next round
                    self.cooldown_sim_wins = 0
                    self.cooldown_sim_count = 0
            
            # Generic Streak Tracking
            if self.current_digit == self.prediction_digit: # Manual Mode Match
                 pass # Logic handled below? 
                 
            # Better Approach: fast streak tracking
            if not hasattr(self, 'streak_digit'): self.streak_digit = -1
            
            if last_digit == self.streak_digit:
                self.consecutive_counter += 1
            else:
                self.consecutive_counter = 1
                self.streak_digit = last_digit

            # Trigger Logic
            trigger_met = False
            contract_type = "DIGITOVER"
            barrier = 0
            
            if self.strategy == "digit_streak":
                # ── STRATEGY 1: Digit Streak ──
                # 1. Manual Target
                if not self.smart_mode and last_digit == self.prediction_digit and self.consecutive_counter >= self.consecutive_triggers:
                    trigger_met = True
                    barrier = last_digit
                    if last_digit == 9:
                        contract_type = "DIGITUNDER"
                        barrier = 9
                    else:
                        contract_type = "DIGITOVER"
                
                # 2. Smart Mode (Any 0 or 9 streak)
                elif self.smart_mode and self.consecutive_counter >= self.consecutive_triggers:
                    if last_digit == 0:
                        trigger_met = True
                        contract_type = "DIGITOVER"
                        barrier = 0
                    elif last_digit == 9:
                        trigger_met = True
                        contract_type = "DIGITUNDER"
                        barrier = 9

            elif self.strategy == "range_threshold":
                # ── STRATEGY 2: Range Threshold ──
                if self.range_direction == "below":
                    # Count consecutive ticks where last digit < barrier
                    if last_digit < self.range_barrier:
                        self.range_consecutive_counter += 1
                    else:
                        self.range_consecutive_counter = 0
                    
                    if self.range_consecutive_counter >= self.consecutive_triggers:
                        trigger_met = True
                        contract_type = "DIGITOVER"
                        barrier = self.range_barrier
                
                elif self.range_direction == "above":
                    # Count consecutive ticks where last digit > barrier
                    if last_digit > self.range_barrier:
                        self.range_consecutive_counter += 1
                    else:
                        self.range_consecutive_counter = 0
                    
                    if self.range_consecutive_counter >= self.consecutive_triggers:
                        trigger_met = True
                        contract_type = "DIGITUNDER"
                        barrier = self.range_barrier

            elif self.strategy == "trio_coverage":
                # ── STRATEGY 3: Trio Coverage (Digit Hedge) ──
                should_trigger = False
                if self.trio_trigger == "every_tick":
                    should_trigger = True
                elif self.trio_trigger == "on_digit_5" and last_digit == self.trio_digit:
                    should_trigger = True
                
                if should_trigger:
                    trigger_met = True
                    if self.trio_role == "over_5":
                        contract_type = "DIGITOVER"
                        barrier = self.trio_digit
                    elif self.trio_role == "under_5":
                        contract_type = "DIGITUNDER"
                        barrier = self.trio_digit
                    elif self.trio_role == "match_5":
                        contract_type = "DIGITMATCH"
                        barrier = self.trio_digit

            elif self.strategy == "duo_coverage":
                # ── STRATEGY 4: Even/Odd Duo ──
                should_trigger = False
                if self.duo_trigger == "every_tick":
                    should_trigger = True
                elif self.duo_trigger == "on_digit" and last_digit == self.duo_trigger_digit:
                    should_trigger = True
                
                if should_trigger:
                    trigger_met = True
                    if self.duo_role == "even":
                        contract_type = "DIGITEVEN"
                    else:
                        contract_type = "DIGITODD"
                    barrier = None  # DIGITEVEN/DIGITODD don't use barrier

            if trigger_met and not self.waiting_for_result:
                
                # ── Cool-Down: Simulate instead of real trade ──
                if self.cooldown_enabled and self.cooldown_active:
                    if not self.cooldown_pending_sim:
                        self.cooldown_pending_sim = {
                            'contract_type': contract_type,
                            'barrier': barrier
                        }
                        self.log(f"⏸️ Cool-down active: simulating {contract_type} (not placing real trade)")
                    # Skip the real trade entirely
                    self.consecutive_counter = 0
                    self.streak_digit = -1
                    self.range_consecutive_counter = 0
                    return
                
                self.waiting_for_result = True  # Block until this trade resolves
                self.waiting_since = time.time()
                
                # --- APPLY EXACT RECOVERY MARTINGALE ---
                if self.martingale_enabled and self.martingale_mode == "exact_recovery" and self.martingale_profit < 0:
                    try:
                        mult_map = self.PAYOUT_MULTIPLIERS.get(contract_type, {})
                        multiplier = mult_map.get(barrier) or mult_map.get(None)
                        if not multiplier:
                            raise KeyError(f"No multiplier for {contract_type} {barrier}")
                        # Calculate exact stake needed to recover loss, minimum $0.35
                        required_stake = max(0.35, abs(self.martingale_profit) / multiplier)
                        
                        # Apply safety cap
                        if required_stake > self.martingale_max_stake:
                            self.stake = self.martingale_max_stake
                            self.log(f"⚠️ Exact Recovery hit max cap! Calculated: ${required_stake:.2f}, Capped at: ${self.martingale_max_stake}")
                        else:
                            self.stake = round(required_stake, 2)
                            self.log(f"📈 Exact Recovery: Calculated ${self.stake} to recover ${abs(self.martingale_profit):.2f}")
                    except KeyError:
                        self.log(f"Error: No multiplier found for {contract_type} {barrier}, using base stake.")
                        self.stake = self.base_stake

                # Capture Trigger Details BEFORE sending
                self.last_trigger = {
                    'entry_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'entry_quote': quote,
                    'entry_digit': last_digit,
                    'contract_type': contract_type,
                    'barrier': barrier
                }

                # Send Proposal IMMEDIATELY
                req = {
                    "proposal": 1,
                    "amount": self.stake, 
                    "basis": "stake",
                    "contract_type": contract_type,
                    "currency": self.currency,
                    "duration": self.duration,
                    "duration_unit": "t",
                    "symbol": self.market,
                }
                if barrier is not None:
                    req["barrier"] = barrier
                await self.send(req)
                
                # Log after sending
                action = f"Buying {contract_type} {barrier}"
                self.log(f"Trigger! Quote: {quote} (L: {last_digit}) -> {action}")
                self.consecutive_counter = 0 # Reset streak after trade
                self.streak_digit = -1       # Reset logic
                self.range_consecutive_counter = 0  # Reset range counter

        elif msg_type == 'proposal':
            proposal = data['proposal']
            prop_id = proposal['id']
            # Execute Trade
            # Reference Royal_mint.py uses price: 10000 or high number? 
            # We can use proposal['ask_price'] or just a high limit.
            # Using 100 to be safe and allow any execution within reason.
            await self.send({"buy": prop_id, "price": 100}) 

        elif msg_type == 'buy':
             contract_id = data['buy']['contract_id']
             # Link this contract to the latest trigger info (from the immediate previous tick cycle)
             if self.last_trigger:
                 self.active_trades[contract_id] = self.last_trigger
                 self.last_trigger = None # Clear it
             else:
                 self.log(f"Warning: Buy confirmed but no trigger data found!")

             self.log(f"Trade Placed! ID: {contract_id}. Waiting for result...")
             # Keep waiting_for_result = True until the contract settles
             # This prevents the bot from firing new trades while the current one is open
             # Subscribe to this contract to get the result
             await self.send({"proposal_open_contract": 1, "contract_id": contract_id, "subscribe": 1})

        elif msg_type == 'proposal_open_contract':
            contract = data['proposal_open_contract']
            if contract['is_sold']:
                contract_id = contract['contract_id']
                profit = contract['profit']
                status = "WIN" if profit > 0 else "LOSS"
                
                # Get Entry Details
                trigger_info = self.active_trades.get(contract_id, {})
                entry_time = trigger_info.get('entry_time', 'N/A')
                entry_quote = trigger_info.get('entry_quote', 'N/A')
                entry_digit = trigger_info.get('entry_digit', 'N/A')
                ctype = trigger_info.get('contract_type', 'DIGIT?')
                
                # Get Exit Details
                exit_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S") # Approximation, or use contract['sell_time']
                exit_quote = contract.get('exit_tick_display_value', 'N/A')
                exit_digit = 'N/A'
                if exit_quote != 'N/A':
                    exit_digit = str(exit_quote)[-1]
                
                # Detailed Log
                # "Time | Type | Entry: Q=... L=... | Exit: Q=... L=... | Profit: ..."
                detailed_msg = (f"{status}! {ctype}. Entry: {entry_quote} (L:{entry_digit}). "
                                f"Exit: {exit_quote} (L:{exit_digit}). Profit: {profit}")
                
                self.log(detailed_msg)
                
                # Save Record
                record = {
                    "Contract ID": contract_id,
                    "Type": ctype,
                    "Entry Time": entry_time,
                    "Entry Quote": entry_quote,
                    "Entry Digit": entry_digit,
                    "Exit Time": exit_time,
                    "Exit Quote": exit_quote,
                    "Exit Digit": exit_digit,
                    "Status": status,
                    "Profit": profit
                }
                self.trade_history.append(record)
                
                # Clean up active trades
                if contract_id in self.active_trades:
                    del self.active_trades[contract_id]
                
                # NOW allow new triggers — only after the contract fully settles
                self.waiting_for_result = False
                self.waiting_since = None
                
                self.total_profit += profit
                self.total_trades += 1
                if profit > 0: self.wins += 1
                else: self.losses += 1
                
                # Cool-down: track consecutive real-trade losses
                if self.cooldown_enabled:
                    if profit <= 0:
                        self.cooldown_loss_streak += 1
                        if self.cooldown_loss_streak >= self.cooldown_after and not self.cooldown_active:
                            self.cooldown_active = True
                            self.cooldown_sim_wins = 0
                            self.cooldown_sim_count = 0
                            self.log(f"🛑 Cool-down activated! {self.cooldown_loss_streak} consecutive losses. Switching to paper trading.")
                    else:
                        self.cooldown_loss_streak = 0
                
                # Auto-switch for duo_coverage
                if self.strategy == "duo_coverage" and self.duo_switch_enabled:
                    if profit <= 0:
                        self.duo_consecutive_losses += 1
                        if self.duo_consecutive_losses >= self.duo_switch_after:
                            old_role = self.duo_role
                            self.duo_role = "odd" if self.duo_role == "even" else "even"
                            self.duo_consecutive_losses = 0
                            self.log(f"🔄 Auto-switch! {old_role.upper()} → {self.duo_role.upper()} after {self.duo_switch_after} consecutive losses")
                    else:
                        self.duo_consecutive_losses = 0
                
                # Apply martingale recovery
                if self.martingale_enabled:
                    self._apply_martingale(profit)
                
                # Check Take Profit
                if self.take_profit > 0 and self.total_profit >= self.take_profit:
                    self.log(f"🎯 TAKE PROFIT REACHED: ${self.total_profit:.2f} >= ${self.take_profit:.2f}. Auto-stopping bot.")
                    self.stop_bot()

      except Exception as e:
        self.log(f"⚠️ handle_message error: {e}")

    def _apply_martingale(self, profit):
        """Adjust stake based on martingale recovery logic."""
        self.martingale_profit += profit
        
        if self.martingale_profit > 0:
            # Sequence recovered — reset
            self.stake = self.base_stake
            self.martingale_profit = 0.0
            self.log(f"♻️ Martingale RESET. Stake back to {self.base_stake}")
        else:
            # Still in loss — increase stake (unless exact_recovery, which calculates at trigger time)
            if self.martingale_mode == "multiply":
                self.stake = self.stake * self.martingale_multiplier
            elif self.martingale_mode == "additive":
                self.stake = self.stake + self.martingale_increment
            elif self.martingale_mode == "exact_recovery":
                # Exact recovery calculates dynamically per trade based on payout multiplier.
                # So we just update the profit above and don't change the stake here.
                # The stake will stay at the last traded value until the next trigger occurs.
                self.log(f"📉 Sequence P/L: {round(self.martingale_profit, 2)}. Exact recovery will calculate on next trigger.")
                return
            
            # Apply safety cap (only needed here for multiply/additive)
            if self.stake > self.martingale_max_stake:
                self.stake = self.martingale_max_stake
                self.log(f"⚠️ Martingale hit max stake cap: {self.martingale_max_stake}")
            
            self.stake = round(self.stake, 2)
            self.log(f"📈 Martingale: Stake adjusted to {self.stake} (seq P/L: {round(self.martingale_profit, 2)})")

    def _check_simulated_result(self, contract_type, barrier, exit_digit):
        """Check if a simulated trade would have won based on the exit tick digit."""
        if contract_type == "DIGITOVER":
            return exit_digit > barrier
        elif contract_type == "DIGITUNDER":
            return exit_digit < barrier
        elif contract_type == "DIGITMATCH":
            return exit_digit == barrier
        elif contract_type == "DIGITEVEN":
            return exit_digit % 2 == 0
        elif contract_type == "DIGITODD":
            return exit_digit % 2 != 0
        return False


class BotManager:
    """Manages multiple TradingBot instances, one per Deriv account."""

    BROADCASTER_TIMEOUT = 30  # seconds before marking a broadcaster as offline

    def __init__(self):
        self.bots = {}  # account_id -> TradingBot
        self.broadcasters = {}  # bot_id -> {data dict + last_seen timestamp}

    def add_account(self, token):
        """Create a new TradingBot for the given token.
        
        We do a quick async authorize call to get the account_id and balance,
        then store the bot keyed by account_id.
        Returns (account_id, balance, currency) or raises an error.
        """
        async def _authorize(token):
            uri = "wss://ws.binaryws.com/websockets/v3?app_id=69330"
            for attempt in range(3):
                try:
                    async with websockets.connect(uri) as ws:
                        await ws.send(json.dumps({"authorize": token}))
                        res = json.loads(await ws.recv())
                        if 'error' in res:
                            if res['error'].get('code') == 'RateLimit' and attempt < 2:
                                await asyncio.sleep(2)
                                continue
                            raise ValueError(res['error']['message'])
                        return res['authorize']
                except Exception as e:
                    if attempt < 2:
                        await asyncio.sleep(2)
                        continue
                    raise ValueError(str(e))

        loop = asyncio.new_event_loop()
        try:
            auth = loop.run_until_complete(_authorize(token))
        finally:
            loop.close()

        account_id = auth['loginid']
        balance = auth['balance']
        currency = auth['currency']

        if account_id in self.bots:
            raise ValueError(f"Account {account_id} is already added.")

        bot = TradingBot()
        bot.api_token = token
        bot.current_balance = balance
        bot.currency = currency
        bot.account_id = account_id
        self.bots[account_id] = bot
        bot.log(f"Account {account_id} added. Balance: {balance} {currency}")
        return account_id, balance, currency

    def remove_account(self, account_id):
        """Stop and remove a bot by account_id."""
        if account_id not in self.bots:
            raise ValueError(f"Account {account_id} not found.")
        bot = self.bots[account_id]
        if bot.is_running:
            bot.stop_bot()
        del self.bots[account_id]

    def get_account(self, account_id):
        """Get a specific bot instance."""
        if account_id not in self.bots:
            raise ValueError(f"Account {account_id} not found.")
        return self.bots[account_id]

    def get_all_statuses(self):
        """Return a list of status dicts for every bot (local + broadcasters)."""
        statuses = []
        for account_id, bot in self.bots.items():
            runtime = "00:00:00"
            if bot.is_running and bot.start_time:
                delta = datetime.now() - bot.start_time
                seconds = int(delta.total_seconds())
                h = seconds // 3600
                m = (seconds % 3600) // 60
                s = seconds % 60
                runtime = f"{h:02d}:{m:02d}:{s:02d}"

            statuses.append({
                'account_id': account_id,
                'is_running': bot.is_running,
                'is_broadcaster': False,
                'running_time': runtime,
                'balance': bot.current_balance,
                'currency': bot.currency,
                'profit': round(bot.total_profit, 2),
                'wins': bot.wins,
                'losses': bot.losses,
                'total_trades': bot.total_trades,
                'logs': bot.logs,
                'current_digit': bot.current_digit,
                'current_quote': bot.current_quote,
                'settings': {
                    'market': bot.market,
                    'stake': bot.base_stake,
                    'duration': bot.duration,
                    'prediction': bot.prediction_digit,
                    'consecutive': bot.consecutive_triggers,
                    'smart_mode': bot.smart_mode,
                    'take_profit': bot.take_profit,
                    'token_set': bot.api_token != "YOUR_API_TOKEN",
                    'strategy': bot.strategy,
                    'range_barrier': bot.range_barrier,
                    'range_direction': bot.range_direction,
                    'martingale_enabled': bot.martingale_enabled,
                    'martingale_mode': bot.martingale_mode,
                    'martingale_multiplier': bot.martingale_multiplier,
                    'martingale_increment': bot.martingale_increment,
                    'martingale_max_stake': bot.martingale_max_stake,
                    'current_stake': bot.stake,
                    'martingale_profit': round(bot.martingale_profit, 2),
                    'trio_role': bot.trio_role,
                    'trio_trigger': bot.trio_trigger,
                    'trio_digit': bot.trio_digit,
                    'duo_role': bot.duo_role,
                    'duo_trigger': bot.duo_trigger,
                    'duo_trigger_digit': bot.duo_trigger_digit,
                    'duo_switch_enabled': bot.duo_switch_enabled,
                    'duo_switch_after': bot.duo_switch_after,
                    'duo_consecutive_losses': bot.duo_consecutive_losses,
                    'cooldown_enabled': bot.cooldown_enabled,
                    'cooldown_after': bot.cooldown_after,
                    'cooldown_check': bot.cooldown_check,
                    'cooldown_active': bot.cooldown_active,
                    'cooldown_loss_streak': bot.cooldown_loss_streak
                }
            })

        # Append broadcaster bots
        now = time.time()
        for bot_id, bdata in list(self.broadcasters.items()):
            age = now - bdata.get('last_seen', 0)
            
            # If broadcaster hasn't been seen for 60 seconds, remove it completely
            if age > 60:
                del self.broadcasters[bot_id]
                continue
                
            is_online = age < self.BROADCASTER_TIMEOUT

            statuses.append({
                'account_id': bdata.get('bot_id', bot_id),
                'is_running': is_online and bdata.get('is_running', False),
                'is_broadcaster': True,
                'broadcaster_source': bdata.get('source', 'unknown'),
                'broadcaster_name': bdata.get('bot_name', bot_id),
                'running_time': bdata.get('running_time', '00:00:00'),
                'balance': bdata.get('balance', 0.0),
                'currency': bdata.get('currency', 'USD'),
                'profit': round(bdata.get('profit', 0.0), 2),
                'wins': bdata.get('wins', 0),
                'losses': bdata.get('losses', 0),
                'total_trades': bdata.get('total_trades', 0),
                'logs': bdata.get('logs', []),
                'current_digit': bdata.get('current_digit', None),
                'current_quote': bdata.get('current_quote', None),
                'settings': {
                    'market': bdata.get('market', 'N/A'),
                    'stake': bdata.get('current_stake', 0.35),
                    'duration': bdata.get('duration', 1),
                    'prediction': 0,
                    'consecutive': 1,
                    'smart_mode': False,
                    'take_profit': 0,
                    'token_set': True,
                    'strategy': bdata.get('strategy', 'N/A'),
                    'range_barrier': 5,
                    'range_direction': 'below',
                    'martingale_enabled': False,
                    'martingale_mode': 'multiply',
                    'martingale_multiplier': 2.0,
                    'martingale_increment': 0.35,
                    'martingale_max_stake': 10.0,
                    'current_stake': bdata.get('current_stake', 0.35),
                    'martingale_profit': 0.0,
                    'trio_role': 'over_5',
                    'trio_trigger': 'every_tick',
                    'trio_digit': 5,
                    'duo_role': 'even',
                    'duo_trigger': 'every_tick',
                    'duo_trigger_digit': 5,
                    'duo_switch_enabled': False,
                    'duo_switch_after': 3,
                    'duo_consecutive_losses': 0,
                    'cooldown_enabled': False,
                    'cooldown_after': 3,
                    'cooldown_check': 2,
                    'cooldown_active': False,
                    'cooldown_loss_streak': 0
                }
            })

        return statuses

    def update_broadcaster(self, data):
        """Upsert a broadcaster bot's status data."""
        bot_id = data.get('bot_id')
        if not bot_id:
            raise ValueError("bot_id is required")
        data['last_seen'] = time.time()
        self.broadcasters[bot_id] = data

    def total_profit(self):
        """Sum of profits across all bots (local + broadcasters)."""
        local = sum(b.total_profit for b in self.bots.values())
        broadcast = sum(b.get('profit', 0.0) for b in self.broadcasters.values())
        return round(local + broadcast, 2)

    def active_count(self):
        """Number of currently running bots (local + online broadcasters)."""
        local = sum(1 for b in self.bots.values() if b.is_running)
        now = time.time()
        broadcast = sum(
            1 for b in self.broadcasters.values()
            if b.get('is_running', False) and (now - b.get('last_seen', 0)) < self.BROADCASTER_TIMEOUT
        )
        return local + broadcast


manager = BotManager()

