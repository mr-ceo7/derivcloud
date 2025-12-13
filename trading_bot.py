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

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)
        self.logs.insert(0, log_entry)
        if len(self.logs) > 50:
            self.logs.pop()

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
        
        if not self.api_token or self.api_token == "YOUR_API_TOKEN":
            self.log("Error: API Token not set.")
            return

        self.is_running = True
        self.log("Bot started.")
        
        # Run event loop in separate thread
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop_bot(self):
        if not self.is_running:
            return
        self.is_running = False
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
            
            # Strategy Check
            if last_digit == self.prediction_digit:
                self.consecutive_counter += 1
            else:
                self.consecutive_counter = 0

            if self.consecutive_counter >= self.consecutive_triggers:
                
                # Send Proposal IMMEDIATELY
                # Using '0' (integer) for barrier and raw dictionary
                req = {
                    "proposal": 1,
                    "amount": self.stake, 
                    "basis": "stake",
                    "contract_type": "DIGITOVER",
                    "currency": self.currency,
                    "duration": self.duration,
                    "duration_unit": "t",
                    "symbol": self.market,
                    "barrier": 0 
                }
                await self.send(req)
                
                # Log after sending to ensure zero latency
                self.log(f"Trigger Reached! Quote: {quote} -> Buying DIGITOVER {self.prediction_digit}")
                self.consecutive_counter = 0 # Reset

        elif msg_type == 'proposal':
            proposal = data['proposal']
            prop_id = proposal['id']
            # Execute Trade
            # Reference Royal_mint.py uses price: 10000 or high number? 
            # We can use proposal['ask_price'] or just a high limit.
            # Using 100 to be safe and allow any execution within reason.
            await self.send({"buy": prop_id, "price": 100}) 

        elif msg_type == 'buy':
            # buy_id = data['buy']['contract_id']
            # self.log(f"Trade Placed! ID: {buy_id}")
            # We wait for proposal_open_contract to see result, but buy response gives contract_id
            pass

        elif msg_type == 'proposal_open_contract':
            # Monitor trade result
            # We need to subscribe to proposal_open_contract? 
            # Usually 'buy' automatically subscribes to the contract updates in most flows, 
            # or we receive 'proposal_open_contract' if we subscribed.
            # The simple 'buy' returns success. We need to know result.
            # Let's rely on 'profit_table' or subscribe to the contract.
            # The easiest way:
            contract = data['proposal_open_contract']
            if contract['is_sold']:
                profit = contract['profit']
                status = "WIN" if profit > 0 else "LOSS"
                self.log(f"{status}! Profit: {profit}")
                
                self.total_profit += profit
                self.total_trades += 1
                if profit > 0: self.wins += 1
                else: self.losses += 1
            else:
                # Trade running...
                pass

        # We need to ensure we get contract updates.
        # When buying, we should subscribe?
        if msg_type == 'buy':
             contract_id = data['buy']['contract_id']
             self.log(f"Trade Placed! ID: {contract_id}")
             # Subscribe to this contract to get the result
             await self.send({"proposal_open_contract": 1, "contract_id": contract_id, "subscribe": 1})

bot = TradingBot()
