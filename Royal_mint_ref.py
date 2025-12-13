
"""
Royal_mint.py

A trading bot module for the Royal Mint application.

Author: Qassim Musa 
Product of GALVANIY TECHNOLOGIES: All rights reserved
Contact:galvanytech@gmail.com
Tell   :0746957502
socials:@it.exper7(mr.ceo)
Version: 1.0
"""



from pickle import FALSE
import websocket
import json
import os
import threading
import logging
from dotenv import load_dotenv
import time
import sys


# Load environment variables from a .env file
load_dotenv()

# Configure logging for better debugging and monitoring
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("trading_bot.log"), logging.StreamHandler()])
logger = logging.getLogger(__name__)

# WebSocket URL for Deriv API
url = "wss://ws.binaryws.com/websockets/v3?app_id=1089"

# Tokens for Demo and Real accounts
api_tokens = {
    "demo": os.getenv("DERIV_DEMO_TOKEN"),  # Demo account token from environment
    "real": os.getenv("DERIV_REAL_TOKEN")   # Real account token from environment
}

if not api_tokens["demo"]:
    logger.warning("Demo account token is missing.")
if not api_tokens["real"]:
    logger.warning("Real account token is missing.")

# Globals for managing state
current_mode = "demo"      # Initial mode is demo
authorized = False         # Tracks if the account is authorized
balance = 0.0              # Tracks the account balance
new_balance = 0.0
profit = 0.0               # Tracks the account profits/losses
trade_log = []             # Log for trade history
lock = threading.Lock()    # Lock for thread-safe operations
trading_active = True     # Tracks if trading is active
digit_probabilities = {str(i): 0 for i in range(10)}  # Tracks digit probabilities
probability_threshold = 9.8  # 10% threshold for digits 9 and 0
recovery_amount = 0.0  # Additional stake to recover losses
stake = 1.0  # Current stake amount
initial_stake = 1.0
loss_occurred = False  # Tracks if a loss occurred
market_list = ["R_10", "R_25", "R_50", "R_75", "R_100"]  # Predefined market list
current_market_index = 0  # Tracks the current market index
loss_count = 0.0
counter = 0
checkd = 0
check_count = 0
safety0 = True
safety9 = True
trade_occured = False
# User-configurable parameters
user_market = "R_10"  # Default market      
user_tick = 1          # Default tick duration
decimall = 3
manual = True
automatic = False
buy1=0
#Trade types
OVER_UNDER = True
EVEN_ODD = FALSE
MATCH_DIFFER =False

def change_trade_type(change="over"):
    global OVER_UNDER,EVEN_ODD,MATCH_DIFFER

    if change=="over":
        OVER_UNDER = True
        EVEN_ODD = FALSE
        MATCH_DIFFER =False
    elif change=="even":
        EVEN_ODD = True
        OVER_UNDER = False
        MATCH_DIFFER =False
    elif change=="match":
        MATCH_DIFFER =True
        OVER_UNDER = False
        EVEN_ODD = FALSE
    else:
        print("warning wrong value passed to change trade type")

def buy():
    global buy1
    buy1=1
    
prediction=0

def set_prediction(num):
    global prediction
    prediction=num
    print(f"prediction updated to {prediction}")

# Control flags
ws_thread = None
ws_app = None
running = False
stop_event = threading.Event()


balance_callback = None
tick_callback = None
market_callback = None
stake_callback = None
duration_callback = None
probability_callback = None
acc_status_callback = None

def set_balance_callback(callback):
    global balance_callback
    balance_callback = callback

def set_tick_callback(callback):
    global tick_callback
    tick_callback= callback

def set_market_callback(callback):
    global market_callback
    market_callback = callback

def set_stake_callback(callback):
    global stake_callback
    stake_callback = callback

def set_duration_callback(callback):
    global duration_callback
    duration_callback = callback

def set_probability_callback(callback):
    global probability_callback
    probability_callback = callback

def set_acc_status_callback(callback):
    global acc_status_callback
    acc_status_callback = callback



def notify_balance_update(balance):
    global balance_callback
    if balance_callback:
        balance_callback(balance)  # Notify the front end

def notify_tick_update(price):
    global tick_callback
    if tick_callback:
        tick_callback(price)  # Notify the front end

def notify_market_update(market):
    global market_callback
    if market_callback:
        market_callback(market)  # Notify the front end


def notify_stake_update(stake):
    global stake_callback
    if stake_callback:
        stake_callback(stake)  # Notify the front end


def notify_duration_update(duration):
    global duration_callback
    if duration_callback:
        duration_callback(duration)  # Notify the front end


def notify_probability_update(probabilities):
    global probability_callback
    if probability_callback:
        probability_callback(probabilities)  # Notify the front end


def notify_acc_status_update(status):
    global acc_status_callback
    if acc_status_callback:
        acc_status_callback(status)  # Notify the front end







def send_heartbeat(ws):
    def ping():
        while not stop_event.is_set():
            if ws.sock and ws.sock.connected:
                try:
                    ws.send(json.dumps({"ping": 1}))  # Send a ping message
                except Exception as e:
                    logger.error("Failed to send heartbeat ping: %s", e)
            stop_event.wait(20)  # Wait for 20 seconds before sending the next ping
    threading.Thread(target=ping, daemon=True).start()
   


 
def Manual_Mode(ws,message):
    global buy1,OVER_UNDER,EVEN_ODD,MATCH_DIFFER,probability_active,user_market,tick,decimall,contract_type, trade_occured,  authorized, balance, trading_active, digit_probabilities, loss_occurred, stake, profit , loss_count, counter, checkd,check_count
    print("WELCOME TO MANUAL MODE",OVER_UNDER)
    
    if buy1==1:   
        Trade(ws,"DIGITOVER")
        buy1=0
    try:
        data = json.loads(message)  # Parse the JSON message

        
        # Handle account authorization response
        if "authorize" in data:
            if "balance" in data["authorize"]:
                with lock:
                    balance = data["authorize"]["balance"]  # Update balance
                    notify_balance_update(balance)
                    authorized = True  # Mark as authorized
                logger.info("Logged into %s account! Balance: %s", current_mode.upper(), balance)
                request_balance(ws)
                request_ticks(ws)  # Request tick data after authorization
                request_digit_analysis(ws)
                
            else:
                logger.error("Authorization failed!")

        # Handle error messages
        elif "error" in data:
            logger.error("Error: %s", data["error"]["message"])

        # Handle digit analysis data
        elif "history" in data:
            # while True:
            ticks = data["history"]["prices"]
            digit_counts = {str(i): 0 for i in range(10)}
            for tick in ticks:
                
                last_digit = str(tick).split(".")[-1]
                lenth = len(last_digit)
                if lenth < decimall:
                    last_digit = "0"
                    digit_counts[last_digit] += 1
                else:
                    last_digit = str(tick)[-1]
                    digit_counts[last_digit] += 1

            total_ticks = len(ticks)
            digit_probabilities = analyze_digit_probabilities(ticks)
            # verify_probabilities(ws,list(digit_probabilities.values()))
            # logger.info("Digit probabilities: %s", digit_probabilities)
            notify_probability_update(digit_probabilities)
          

        # Handle tick data
        elif "tick" in data:
            
            tick = data["tick"]["quote"]
            notify_tick_update(tick)
            last_digit = str(tick).split(".")[-1]
            lenth = len(last_digit)
            if lenth < 4:
                last_digit = 0
                
            else:
                last_digit = int(str(data["tick"]["quote"])[-1])  # Get the last digit of the tick
                
            logger.info("Last digit of the tick: %d", last_digit)
            request_digit_analysis(ws)
           
            
        # Handle trade proposal responses
        elif "proposal" in data:
            proposal = data.get("proposal", {})
            if proposal:
                logger.info("Proposal received: %s", proposal)
                proposal_id = proposal.get("id")
                if proposal_id:
                    logger.info("Executing trade with proposal ID: %s", proposal_id)
                    execute_trade(ws, proposal_id)
        

        # Handle successful trade execution
        elif "balance" in data:
            with lock:
                new_balance = data["balance"]["balance"]
                notify_balance_update(balance)
            logger.info("Updated balance: %s", new_balance)


            if new_balance < balance  and counter > 1:
                logger.info("LOSS!!!!!!!! %f", new_balance - balance)
                profit += new_balance - balance
                balance = new_balance
                notify_balance_update(balance)
            elif new_balance == balance:
                logger.info("no trade occured")
                
            else:
                logger.info("WIN PROFIT: %f", new_balance - balance)
                profit += new_balance - balance
                balance = new_balance
                notify_balance_update(balance)
                    

            with lock:
                trading_active = False  # Reset trading state here
                

    except Exception as e:
        logger.exception("Error handling message: %s", e)
    

def Auto_Mode(ws, message):
    global user_market,tick,decimall,contract_type, trade_occured, safety9,safety0, authorized, balance, trading_active, digit_probabilities, loss_occurred, stake, profit , loss_count, counter, checkd,check_count
    try:
        data = json.loads(message)  # Parse the JSON message


        # Handle account authorization response
        if "authorize" in data:
            if "balance" in data["authorize"]:
                with lock:
                    balance = data["authorize"]["balance"]  # Update balance
                    notify_balance_update(balance)
                    authorized = True  # Mark as authorized
                logger.info("Logged into %s account! Balance: %s", current_mode.upper(), balance)
                request_balance(ws)
                request_ticks(ws)  # Request tick data after authorization
                request_digit_analysis(ws)  # Request digit analysis
            else:
                logger.error("Authorization failed!")

        # Handle error messages
        elif "error" in data:
            logger.error("Error: %s", data["error"]["message"])

        # Handle digit analysis data
        elif "history" in data:
            # while True:
            ticks = data["history"]["prices"]
            digit_counts = {str(i): 0 for i in range(10)}
            for tick in ticks:
                
                last_digit = str(tick).split(".")[-1]
                lenth = len(last_digit)
                if lenth < decimall:
                    last_digit = "0"
                    digit_counts[last_digit] += 1
                else:
                    last_digit = str(tick)[-1]
                    digit_counts[last_digit] += 1

            total_ticks = len(ticks)
            digit_probabilities = analyze_digit_probabilities(ticks)
            verify_probabilities(ws,list(digit_probabilities.values()))
            logger.info("Digit probabilities: %s", digit_probabilities)
            notify_probability_update(digit_probabilities)
            

            # Check probabilities for digits 9 and 0
            if digit_probabilities["9"] > probability_threshold or digit_probabilities["0"] > probability_threshold: 
                if digit_probabilities["9"] > probability_threshold:
                    logger.warning("Digits 9 exceed the threshold or are most frequent. Current probabilities: %s",
                    digit_probabilities["9"])
                    logger.info("OVER 0 SAFE")
                    safety0 = True
                else:
                    logger.warning("Digits 0 exceed the threshold or are most frequent. Current probabilities: %s",digit_probabilities["0"])
                    logger.info("UNDER 9 SAFE")    
                    safety9 = True
                if digit_probabilities["9"] > probability_threshold and digit_probabilities["0"] > probability_threshold:
                    logger.warning("BAD MARKET CONDITIONS")
                    logger.info("Switching market automatically...")
                    safety0 = False
                    safety9 = False
                    trading_active = True
                    time.sleep(0.5)
                    auto_switch_market(ws)  # Switch to the next market

            else:
                trading_active = False
                safety9 = True
                safety0 = True
                # break
                print("found a good market" , user_market )
                

        # Handle tick data
        elif "tick" in data:
            
            tick = data["tick"]["quote"]
            notify_tick_update(tick)
            last_digit = str(tick).split(".")[-1]
            lenth = len(last_digit)
            if lenth < 4:
                last_digit = 0
                
            else:
                last_digit = int(str(data["tick"]["quote"])[-1])  # Get the last digit of the tick
                
            logger.info("Last digit of the tick: %d", last_digit)
        
            if (last_digit == 9 or last_digit == 0) and (safety0 or safety9):
                logger.info(f"Last digit is {last_digit}. Waiting for confirmation...")
                time.sleep(1)  # Wait for 1 second
                # Request the latest tick again
                request_ticks(ws)
                
                tick = data["tick"]["quote"]
                
                last_digit = str(tick).split(".")[-1]
                lenth = len(last_digit)
                if lenth < decimall:
                    last_digit = 0
                
                else:
                    last_digit = int(str(data["tick"]["quote"])[-1])  # Get the last digit of the tick
        # Afterwaiting, if the digit is still 9, trade
            if (last_digit == 9 or last_digit == 0 )and (safety9 or safety0):
                logger.info(f"Last digit is confirmed to be {last_digit}. Initiating trade...")
                if trade_occured and ((contract_type == "DIGITUNDER" and last_digit == 9) or (contract_type == "DIGITOVER" and last_digit ==0)):
                    recovery(ws, contract_type, last_digit)
                else:
                    trade_occured = False
            else:
                contract_type = ""
            # break
            
                 
            # Trade logic: OVER 0 when last digit is 0, UNDER 9 when last digit is 9
            if not trading_active and ((last_digit == 0 or last_digit == 9 )and( safety0 or safety9)):
                with lock:
                    trading_active = True  # Prevent multiple trades simultaneously

                contract_type = "DIGITOVER" if last_digit == 0 else "DIGITUNDER"
                barrier = 0 if last_digit == 0 else 9

                logger.info("Condition met for trading. Initiating trade...")
                notify_market_update(user_market)
                request_digits_proposal(ws, user_market, stake, user_tick, contract_type, barrier,last_digit)

        # Handle trade proposal responses
        elif "proposal" in data:
            proposal = data.get("proposal", {})
            if proposal:
                logger.info("Proposal received: %s", proposal)
                proposal_id = proposal.get("id")
                if proposal_id:
                    logger.info("Executing trade with proposal ID: %s", proposal_id)
                    execute_trade(ws, proposal_id)
                    
                    # time.sleep(5)
                    # request_balance(ws)
                    trade_occured = True
                    request_digit_analysis(ws)


        

        # Handle successful trade execution
        elif "balance" in data:
            with lock:
                new_balance = data["balance"]["balance"]
                notify_balance_update(balance)
            logger.info("Updated balance: %s", new_balance)


            if new_balance < balance  and counter > 1:
                logger.info("LOSS!!!!!!!! %f", new_balance - balance)
                # consucutive_check = True
                # check_count += 1
                loss_count += new_balance - balance
                profit += new_balance - balance
                logger.info("RECOVERING.......")
                loss_occurred = True
                #if current_stake <= 2:
                stake += recovery_amount
                balance = new_balance
                notify_balance_update(balance)
            elif new_balance == balance:
                logger.info("no trade occured")
                

            
            else:
                if loss_count < 0 and  loss_count  != 0:
                    logger.info("we won but still recovering previous loss")
                    #if current_stake <= 2:
                    stake += recovery_amount
                    profit += new_balance - balance
                    loss_count += profit
                    loss_occurred = False
                    balance = new_balance
                    notify_balance_update(balance)
                    
                else:
                    logger.info("WIN PROFIT: %f", new_balance - balance)
                    loss_count = 0.0
                    profit += new_balance - balance
                    stake = initial_stake
                    loss_occurred = False
                    balance = new_balance
                    notify_balance_update(balance)
                    

            with lock:
                trading_active = False  # Reset trading state here

    except Exception as e:
        logger.exception("Error handling message: %s", e)


def recovery(ws, contract_type , lastdigitt):
    print("RECOVERING........////////")
    sstake = 11
    request_digits_proposal(ws, user_market, sstake, user_tick, contract_type, digit=lastdigitt,last_digit=9)

def verify_probabilities(ws,probabilities):
    logger.info("verifying........prob")
    global decimall, trading_active

    for value in probabilities:
        if value < 1 or value > 12.9:
            print(f"Value {value} is out of range!")
            print("Recalculating probabilities......")
    
            trading_active = True
            decimall += 1
            request_digit_analysis(ws)
            return decimall 
        else:
            trading_active = False
    if decimall > 10:
        decimall = 1
        return decimall 


def analyze_digit_probabilities(ticks):
    """Calculate the probabilities of each digit (0–9) from tick data."""
    digit_counts = {str(i): 0 for i in range(10)}
    for tick in ticks:
        
        last_digit = str(tick).split(".")[-1]
        lenth = len(last_digit)
        if lenth < decimall:
            last_digit = "0"
            digit_counts[last_digit] += 1
        else:
            last_digit = str(tick)[-1]
            digit_counts[last_digit] += 1
    total_ticks = len(ticks)
    return {k: (v / total_ticks) * 100 for k, v in digit_counts.items()}


def request_balance(ws):
    """Send a request to get the current account balance."""
    balance_request = {
        "balance": 1,  # The specific API key for balance request
        "subscribe": 1  # No need to subscribe; a one-time request
    }
    ws.send(json.dumps(balance_request))
    logger.info("Balance request sent.")



def on_error(ws, error):
    logger.error("WebSocket error: %s", error)


def on_close(ws, close_status_code, close_msg):
    logger.warning("Connection closed (Code: %s, Message: %s)", close_status_code, close_msg)
    if running:
        logger.info("Attempting to reconnect...")
        reconnect()


def on_open(ws):
    logger.info("WebSocket connection opened.")
    authorize_account(ws)
    send_heartbeat(ws)


def reconnect():
    global ws_thread, ws_app
    if ws_app:
        ws_app.close()
    if ws_thread and ws_thread.is_alive():
        ws_thread.join()
    connect_and_authorize()


def authorize_account(ws):
    global api_tokens, current_mode
    token = api_tokens.get(current_mode)
    if not token:
        logger.error("API token for %s mode is missing or invalid.", current_mode.upper())
        ws.close()  # Close the WebSocket to prevent further invalid requests
        return

    logger.info("Authorizing %s account...", current_mode.upper())
    auth_request = {
        "authorize": token
    }
    ws.send(json.dumps(auth_request))  # Send the authorization request


active_subscriptions = set()  # Tracks active subscriptions

def request_ticks(ws):
    global active_subscriptions

    if user_market in active_subscriptions:
        logger.info("Already subscribed to market: %s. Skipping subscription.", user_market)
        return

    logger.info("Requesting tick stream for market %s...", user_market)
    tick_request = {
        "ticks": user_market,  # Track ticks for the user-selected market
        "subscribe": 1  # Subscribe to updates
    }
    ws.send(json.dumps(tick_request))
    active_subscriptions.add(user_market)




def request_digit_analysis(ws):
    """Request digit analysis for the current market."""
    logger.info("Requesting digit analysis for market %s...", user_market)
    analysis_request = {
        "ticks_history": user_market,
        "end": "latest",
        "count": 1000,  # Check the last 1000 ticks
        "style": "ticks"
    }
    ws.send(json.dumps(analysis_request))


def request_digits_proposal(ws, market, stake, duration, contract_type, digit,last_digit):
    logger.info("Requesting proposal for %s on digit %s...", contract_type, digit)
    print(contract_type,digit,last_digit)
    
    proposal_request = {
        "proposal": 1,
        "amount": stake,
        "basis": "stake",
        "contract_type": contract_type.upper(),
        "currency": "USD",
        "duration": duration,
        "duration_unit": "t",  # Tick duration
        "symbol": market,
        "barrier": digit  # Always trade OVER 0
    }
    ws.send(json.dumps(proposal_request))  # Send the proposal request


def Trade(ws,contype="DIGITOVER"):
    if OVER_UNDER:
        request_digits_proposal(ws,user_market,stake,user_tick,contype,prediction,None)
    elif EVEN_ODD:
        request_digits_proposal(ws,user_market,stake,user_tick,contype,prediction)
    elif MATCH_DIFFER:
        request_digits_proposal(ws,user_market,stake,user_tick,contype,prediction)
    else:
        print("!!!!!!!!!!!!TRADE ERRO!!!!!!!!!!!!")

def auto_switch_market(ws):
    """Automatically switch to the next market in the list."""
    global current_market_index, user_market, trading_active, active_subscriptions

    # Clear active subscriptions
    active_subscriptions.clear()
    # Unsubscribe from the current market
    unsubscribe_request = {"forget_all": "ticks"}  # Forget all tick subscriptions
    ws.send(json.dumps(unsubscribe_request))
    logger.info("Unsubscribed from the current market: %s", user_market)

    time.sleep(1)  # Give time for the unsubscribe request to process

    # Switch to the next market
    current_market_index = (current_market_index + 1) % len(market_list)
    user_market = market_list[current_market_index]

    logger.info("Switching to the next market: %s", user_market)

    # Request new ticks and digit analysis for the updated market
    trading_active = False  # Ensure trading is paused during the switch
    request_ticks(ws)
    request_digit_analysis(ws)



def set_market_list():
    global market_list
    new_list = input("Enter a comma-separated list of markets (e.g., R_10,R_25,R_50): ").strip()
    if new_list:
        market_list = [market.strip().upper() for market in new_list.split(",")]
        logger.info("Updated market list: %s", market_list)
    else:
        logger.error("Market list cannot be empty.")



def execute_trade(ws, proposal_id):
    logger.info("Executing trade with proposal ID: %s", proposal_id)
    buy_request = {
        "buy": proposal_id,
        "price": 10000  # Set maximum acceptable price in cents
    }
    ws.send(json.dumps(buy_request))  # Send the buy request


def connect_and_authorize(state="manual"):
    global ws_thread, ws_app, running,manual,automatic,on_messagee
    stop_bot()
    if state=="manual":
        on_messagee=Manual_Mode
        automatic=False
    elif state=='auto':
        on_messagee=Auto_Mode
        manual=False
    else:
        logger.warning("bot is not in either manual or auto!!!!!!!!!!!!!!!!")
        stop_bot()
        return

    
    ws_app = websocket.WebSocketApp(
        url,
        on_open=on_open,
        on_message=on_messagee,
        on_error=on_error,
        on_close=on_close
    )

    ws_thread = threading.Thread(target=ws_app.run_forever, daemon=True)
    ws_thread.start()
    running = True
    logger.info("WebSocket thread started.")


def stop_bot():
    global running,active_subscriptions
    if running and ws_app:
        logger.info("Stopping the bot...")
        active_subscriptions.clear()
        stop_event.set()
        ws_app.close()
        if ws_thread:
            ws_thread.join()
        running = False
        logger.info("Bot stopped.")
    else:
        logger.info("Bot is not running.")


def start_bot():
    global stop_event
    if not running:
        logger.info("Starting the bot...")
        stop_event.clear()
        connect_and_authorize()
    else:
        logger.info("Bot is already running.")


def switch_account(choice):
    global current_mode, authorized, balance, trading_active, profit
    with lock:
        if choice == "Demo":
            current_mode = "demo"
        else:
            current_mode = "real"
        authorized = False
        #balance = 0.0
        #profit = 0.0
        trading_active = False
        trade_log.clear()
    logger.info("Switched account mode to %s.", current_mode.upper())
    if running:
        reconnect()


def set_stake(value):
    global initial_stake , stake
    try:
        new_stake = float(value)
        if new_stake <= 0:
            raise ValueError("Stake must be positive.")
        with lock:
            initial_stake = new_stake
            stake = new_stake
        logger.info("Stake updated to %.2f", initial_stake)
    except ValueError as e:
        logger.error("Invalid stake value: %s", e)


def set_market(new_market):
    global user_market
    # new_market = input("Enter the new market symbol (e.g., R_100): ").strip().upper()
    new_market=new_market
    if "10" in new_market:
        new_market="R_10"
    elif "25" in new_market:
        new_market="R_25"
    elif "50" in new_market:
        new_market="R_50"
    elif "75" in new_market:
        new_market="R_75"
    elif "100" in new_market:
        new_market="R_100"
    else:
        print("invalid market sekection!!!!!")
        return
    if new_market:
        with lock:
            user_market = new_market
        logger.info("Market updated to %s", user_market)
        if running and authorized:
            request_ticks(ws_app)
    else:
        logger.error("Market symbol cannot be empty.")


def set_tick(value):
    global user_tick
    try:
        new_tick = int(value)
        if new_tick <= 0:
            raise ValueError("Tick duration must be positive.")
        with lock:
            user_tick = new_tick
        logger.info("Tick duration updated to %d", user_tick)
    except ValueError as e:
        logger.error("Invalid tick duration: %s", e)


def show_trade_log():
    with lock:
        if trade_log:
            print("\n----- Trade Log -----")
            for trade in trade_log:
                print(f"Contract ID: {trade['contract_id']}, Profit: {trade['profit']:.2f}")
            print("---------------------\n")
        else:
            print("\nNo trades have been executed yet.\n")


def print_menu():
    menu = """
    ===== $$ROYAL MINT$$ =====
    1. Start Bot
    2. Stop Bot
    3. Switch Account (Demo/Real)
    4. Set Stake
    5. Set Market
    6. Set Tick
    7. Show Settings
    8. Show Trade Log
    9. Set Recovery Amount
    10. Edit Market List
    11. Exit
    =========================================
    """
    print(menu)


def set_recovery_amount():
    global recovery_amount
    try:
        new_recovery = float(input("Enter the new recovery amount (e.g., 0.5): ").strip())
        if new_recovery < 0:
            raise ValueError("Recovery amount must be non-negative.")
        with lock:
            recovery_amount = new_recovery
        logger.info("Recovery amount updated to %.2f", recovery_amount)
    except ValueError as e:
        logger.error("Invalid recovery amount: %s", e)



def show_settings():
    with lock:
        print(f"""
    ----- Current Settings -----
    Account Mode : {current_mode.upper()}
    Authorized    : {authorized}
    Balance       : {balance}
    Profit        : {profit:.2f}
    Market        : {user_market}
    Stake         : {initial_stake}
    Tick Duration : {user_tick}
    Trading Active: {trading_active}
    Bot Running   : {running}
    Recovery_amoun: {recovery_amount}
    ------------------------------
    """)


def menu_loop():
    while True:
        print_menu()
        choice = input("Enter your choice (1-11): ").strip()
        if choice == '1':
            start_bot()
        elif choice == '2':
            stop_bot()
        elif choice == '3':
            switch_account()
        elif choice == '4':
            set_stake()
        elif choice == '5':
            set_market()
        elif choice == '6':
            set_tick()
        elif choice == '7':
            show_settings()
        elif choice == '8':
            show_trade_log()
        elif choice == '9':
            set_recovery_amount()
        elif choice == '10':
            set_market_list()
        elif choice == '11':
            logger.info("Exiting the bot...")
            stop_bot()
            sys.exit(0)
        else:
            logger.warning("Invalid choice. Please enter a number between 1 and 12.")
        time.sleep(1)  # Small delay to improve user experience




if __name__ == "__main__":
    logger.info("$$WELCOME TO THE ROYAL MINT$$")
    

    # Start the user menu in the main thread
    menu_thread = threading.Thread(target=menu_loop, daemon=True)
    menu_thread.start()

    # Keep the main thread alive while the menu is running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt detected. Exiting...")
        stop_bot()
        sys.exit(0)
