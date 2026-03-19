import re

with open('trading_bot.py', 'r') as f:
    content = f.read()

# 1. Add GlobalTickManager
global_tick_manager_code = """
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
        # We use a completely independent app_id to sidestep any overlapping limits if needed,
        # but 69330 is the user's requested app_id.
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
                                'quote_str': quote_str,
                                'digit': last_digit,
                                'quote': quote
                            })
                            if len(self.market_history[market]) > 100:
                                self.market_history[market].pop(0)

                            # Dispatch to all registered bots
                            for bot in list(self.subscribers):
                                if bot.is_running and bot.market == market and bot.loop:
                                    asyncio.run_coroutine_threadsafe(
                                        bot.process_tick(epoch, quote, quote_str, last_digit), 
                                        bot.loop
                                    )

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

        bot.consecutive_counter = streak
        bot.streak_digit = streak_digit
        bot.range_consecutive_counter = range_counter

global_tick_manager = GlobalTickManager()
global_tick_manager.start()

class TradingBot:
"""

content = content.replace("class TradingBot:\n", global_tick_manager_code, 1)

# 2. Extract tick logic safely
tick_start_str = "        elif msg_type == 'tick':"
prop_start_str = "        elif msg_type == 'proposal':"

start_idx = content.find(tick_start_str)
end_idx = content.find(prop_start_str)

tick_block = content[start_idx:end_idx]

# Replace inside `handle_message`
new_tick_dispatch = """        elif msg_type == 'tick':
            # For testing purposes only
            tick_epoch = data['tick'].get('epoch')
            quote = data['tick']['quote']
            pip_size = data['tick'].get('pip_size', 2)
            quote_str = f"{{:.{pip_size}f}}".format(quote)
            last_digit = int(quote_str[-1])
            await self.process_tick(tick_epoch, quote, quote_str, last_digit)

"""
content = content[:start_idx] + new_tick_dispatch + content[end_idx:]

# Now reconstruct the `process_tick` function from `tick_block`
# Look for where the real logic begins in `tick_block`:
#    tick_epoch = ...
#    ...
#    self.current_quote = quote_str
#    (Logic starts after this)

logic_start_str = "self.current_quote = quote_str"
logic_idx = tick_block.find(logic_start_str)
logic_part = tick_block[logic_idx + len(logic_start_str):]
# strip leading newlines to find exact indentation
logic_part = logic_part.lstrip('\\r\\n')

# Dedent exact 4 spaces because it goes from `elif:` (8 spaces) to `def:` (4 spaces) -> inside is 8 spaces... wait!
# `elif msg_type == 'tick':` is at 8 spaces.
# The code *inside* `elif:` is at 12 spaces!
# We want to put it inside `async def process_tick:` which is at 4 spaces.
# So the code inside `process_tick:` needs to be at 8 spaces.
# Thus we dedent the logic part by 4 spaces.

lines = logic_part.split('\\n')
dedented = []
for line in lines:
    if line.startswith('    '):  # remove exactly 4 spaces
        dedented.append(line[4:])
    else:
        dedented.append(line)

new_process_tick = """
    async def process_tick(self, epoch, quote, quote_str, last_digit):
        tick_epoch = epoch
        
        # Skip duplicate ticks
        if tick_epoch and tick_epoch == self.last_tick_epoch:
            return
        self.last_tick_epoch = tick_epoch
        
        self.current_digit = last_digit
        self.current_quote = quote_str

""" + "\\n".join(dedented) + "\\n"

# Insert `process_tick` before `handle_message`
handle_msg_idx = content.find("    async def handle_message(self, message):")
content = content[:handle_msg_idx] + new_process_tick + content[handle_msg_idx:]


# 3. Simple static replaces
content = content.replace(
'''        # Run event loop in separate thread
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()''',
'''        self.loop = asyncio.new_event_loop()
        global_tick_manager.register_bot(self)
        global_tick_manager.calculate_streak(self)
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()'''
)

content = content.replace(
'''        self.log("Bot stopped.")''',
'''        self.log("Bot stopped.")
        global_tick_manager.unregister_bot(self)'''
)

content = content.replace(
'''    def _run_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._websocket_logic())''',
'''    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._websocket_logic())'''
)

content = content.replace(
'''                # 2. Subscribe to Ticks
                await self.send({"ticks": self.market, "subscribe": 1})''',
'''                # 2. Subscribe to Ticks (Handled globally by GlobalTickManager)'''
)

content = content.replace(
'''        if market: self.market = market''',
'''        if market:
            self.market = market
            if self.is_running:
                global_tick_manager.subscribe_market(market)
                global_tick_manager.calculate_streak(self)'''
)

# Fix testing compat: make sure process_tick has await if it needs it 
# `await self.send(req)` is inside the inner logic, so `process_tick` MUST be `async def`, which I made it.

with open('trading_bot_new.py', 'w') as f:
    f.write(content)
