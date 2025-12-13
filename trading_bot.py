import threading
import time
import json
import logging
from datetime import datetime
from deriv_api import DerivAPI
from deriv_api.errors import APIError
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TradingBot:
    def __init__(self):
        self.api_token = None
        self.market = "1HZ100V" # Volatility 100 (1s) Index
        self.stake = 0.35
        self.duration = 1
        self.prediction_digit = 0
        self.consecutive_triggers = 1
        self.is_running = False
        self.api = None
        self.loop = None
        self.thread = None
        
        # Stats
        self.total_profit = 0.0
        self.current_balance = 0.0
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.logs = []
        self.consecutive_counter = 0

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        self.logs.insert(0, entry)
        if len(self.logs) > 50:
            self.logs.pop()
        logging.info(message)

    def update_settings(self, token=None, market=None, stake=None, duration=None, prediction=None, consecutive=None):
        if token: self.api_token = token
        if market: self.market = market
        if stake: self.stake = float(stake)
        if duration: self.duration = int(duration)
        if prediction: self.prediction_digit = int(prediction)
        if consecutive: self.consecutive_triggers = int(consecutive)
        self.log(f"Settings updated: Market={self.market}, Stake={self.stake}, Pred={self.prediction_digit}, Consec={self.consecutive_triggers}")

    def reset_stats(self):
        self.total_profit = 0.0
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.logs = []
        self.log("Stats reset by user.")

    def start_bot(self):
        if self.is_running:
            return
        
        if not self.api_token:
            self.log("Error: API Token not set.")
            return

        self.is_running = True
        self.consecutive_counter = 0
        
        # Run asyncio loop in a separate thread
        self.thread = threading.Thread(target=self._run_loop)
        self.thread.daemon = True
        self.thread.start()
        self.log("Bot started.")

    def stop_bot(self):
        self.is_running = False
        self.log("Bot stopped.")

    def _run_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._trade_logic())

    async def _trade_logic(self):
        try:
            self.api = DerivAPI(app_id=1089) # Public App ID or user provided? Defaulting to generic for now
            
            # Authorize
            authorize = await self.api.authorize(self.api_token)
            if authorize.get('error'):
                self.log(f"Auth Failed: {authorize['error']['message']}")
                self.is_running = False
                return
            
            self.current_balance = authorize['authorize']['balance']
            self.log(f"Authorized. Balance: {self.current_balance}")

            # Subscribe to Ticks
            source_ticks = await self.api.subscribe({'ticks': self.market})
            
            # Bridge RxPY Observable to AsyncIO Queue
            tick_queue = asyncio.Queue()
            
            def on_next(tick):
                # Schedule put into queue on the loop
                asyncio.run_coroutine_threadsafe(tick_queue.put(tick), self.loop)
            
            # Subscribe using RxPY
            source_ticks.subscribe(on_next)
            
            while self.is_running:
                try:
                    # Wait for next tick
                    tick = await tick_queue.get()
                    
                    quote = tick['tick']['quote']
                    # Get last digit
                    # Formatting to ensure we get the true last digit displayed
                    quote_str = "{:.2f}".format(quote) # Most indices are 2 decimals, need to be careful with crypto
                    last_digit = int(quote_str[-1])
                    
                    # Check Strategy
                    if last_digit == self.prediction_digit:
                        self.consecutive_counter += 1
                        # self.log(f"Tick: {quote} (Digit: {last_digit}) | Count: {self.consecutive_counter}/{self.consecutive_triggers}")
                    else:
                        self.consecutive_counter = 0
                        # self.log(f"Tick: {quote} (Digit: {last_digit}) | Reset")

                    if self.consecutive_counter >= self.consecutive_triggers:
                        self.log(f"Trigger Reached! Quote: {quote} -> Buying DIGITOVER {self.prediction_digit}")
                        
                        try:
                            proposal = await self.api.proposal({
                                "proposal": 1,
                                "amount": self.stake,
                                "basis": "stake",
                                "contract_type": "DIGITOVER", 
                                "currency": "USD",
                                "duration": self.duration,
                                "duration_unit": "t",
                                "symbol": self.market,
                                "barrier": str(self.prediction_digit)
                            })
                            
                            if proposal.get('error'):
                                self.log(f"Proposal Error: {proposal['error']['message']}")
                                self.consecutive_counter = 0 # Reset
                                continue

                            buy = await self.api.buy({"buy": proposal['proposal']['id'], "price": self.stake})
                            
                            if buy.get('error'):
                                self.log(f"Buy Error: {buy['error']['message']}")
                            else:
                                contract_id = buy['buy']['contract_id']
                                self.log(f"Trade Placed! ID: {contract_id}")
                                
                                # Wait for result (in a simple way for now, this blocks the tick stream which is GOOD for 1 tick trades)
                                while True:
                                    status = await self.api.proposal_open_contract({'contract_id': contract_id})
                                    contract = status['proposal_open_contract']
                                    is_sold = contract.get('is_sold')
                                    
                                    if is_sold:
                                        profit = float(contract.get('profit', 0))
                                        self.total_profit += profit
                                        self.total_trades += 1
                                        if profit > 0:
                                            self.wins += 1
                                            self.log(f"WIN! Profit: +${profit}")
                                        else:
                                            self.losses += 1
                                            self.log(f"LOSS. Profit: ${profit}")
                                        
                                        # Update Balance
                                        balance_data = await self.api.balance()
                                        self.current_balance = balance_data['balance']['balance']
                                        break
                                    await asyncio.sleep(0.5)

                        except Exception as e:
                            self.log(f"Trade Exception: {e}")
                        
                        # Reset counter after trade
                        self.consecutive_counter = 0

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.log(f"Loop Error: {e}")
                    await asyncio.sleep(1)
            
        except Exception as e:
            self.log(f"Critical Bot Error: {e}")
            self.is_running = False

bot = TradingBot()
