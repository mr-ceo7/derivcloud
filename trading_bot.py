import asyncio
import websockets
import json
import logging
import threading
from datetime import datetime

class TradingBot:
    def __init__(self):
        self.api_token = "YOUR_API_TOKEN"
        self.market = "1HZ100V" # Volatility 100 (1s) Index
        self.stake = 0.35
        self.duration = 1
        self.prediction_digit = 0
        self.consecutive_triggers = 1
        self.smart_mode = False # Trade both 0 and 9
        
        self.is_running = False
        self.websocket = None
        self.loop = None
        self.thread = None
        self.currency = "USD"
        self.current_balance = 0.0
        
        # Stats
        self.total_profit = 0.0
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.logs = []
        self.current_digit = None
        self.consecutive_counter = 0
        self.streak_digit = -1
        self.start_time = None
        self.trade_history = []
        self.active_trades = {} # contract_id -> trigger_info
        self.last_trigger = None # Temp store for trigger details

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)
        self.logs.insert(0, log_entry)
        if len(self.logs) > 50:
            self.logs.pop()

    def update_settings(self, token=None, market=None, stake=None, duration=None, prediction=None, consecutive=None, smart_mode=None):
        if token: self.api_token = token
        if market: self.market = market
        if stake: self.stake = float(stake)
        if duration: self.duration = int(duration)
        if prediction: self.prediction_digit = int(prediction)
        if consecutive: self.consecutive_triggers = int(consecutive)
        if smart_mode is not None: self.smart_mode = (str(smart_mode).lower() == 'true')
        self.log(f"Settings updated: Market={self.market}, Stake={self.stake}, Pred={self.prediction_digit}, Consec={self.consecutive_triggers}, Smart={self.smart_mode}")

    def reset_stats(self):
        self.total_profit = 0.0
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.logs = []
        self.trade_history = []
        self.active_trades = {}
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
        
        # Run event loop in separate thread
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop_bot(self):
        if not self.is_running:
            return
        self.is_running = False
        self.start_time = None
        self.log("Bot stopped.")
        # Loop will exit when is_running is False and socket closes

    def _run_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._websocket_logic())

    async def _websocket_logic(self):
        uri = "wss://ws.binaryws.com/websockets/v3?app_id=1089"
        async for websocket in websockets.connect(uri):
            self.websocket = websocket
            try:
                # 1. Authorize
                await self.send({"authorize": self.api_token})
                
                # 2. Subscribe to Ticks
                await self.send({"ticks": self.market, "subscribe": 1})
                
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
        data = json.loads(message)
        
        if 'error' in data:
            self.log(f"Error: {data['error']['message']}")
            return

        msg_type = data.get('msg_type')

        if msg_type == 'authorize':
            self.current_balance = data['authorize']['balance']
            self.currency = data['authorize']['currency']
            self.log(f"Authorized. Balance: {self.current_balance} {self.currency}")

        elif msg_type == 'tick':
            quote = data['tick']['quote']
            quote_str = "{:.2f}".format(quote)
            last_digit = int(quote_str[-1])
            self.current_digit = last_digit
            
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
            
            # Check conditions
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

            if trigger_met:
                
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
                    "barrier": barrier 
                }
                await self.send(req)
                
                # Log after sending
                action = f"Buying {contract_type} {barrier}"
                self.log(f"Trigger! Quote: {quote} (L: {last_digit}) -> {action}")
                self.consecutive_counter = 0 # Reset streak after trade
                self.streak_digit = -1       # Reset logic

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
                
                self.total_profit += profit
                self.total_trades += 1
                if profit > 0: self.wins += 1
                else: self.losses += 1

bot = TradingBot()
