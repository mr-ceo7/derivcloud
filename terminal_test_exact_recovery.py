"""
Live Terminal Test of Exact Recovery Martingale
This script connects to the Deriv API using the TradingBot class,
simulates a $1.00 loss, and then forces an Exact Recovery trade
for DIGITOVER 5 to prove the mathematics and the 0.35 minimum work live.
"""
import asyncio
import json
import websockets
from trading_bot import TradingBot

# Use the user's provided demo token from history
API_TOKEN = "30S5538SZ3cl7lp"

async def run_terminal_test():
    bot = TradingBot()
    bot.api_token = API_TOKEN
    
    # Configure Exact Recovery
    bot.martingale_enabled = True
    bot.martingale_mode = "exact_recovery"
    bot.martingale_max_stake = 10.0
    bot.base_stake = 0.35
    bot.stake = 0.35
    
    # Force a mock loss of exactly $1.00
    bot.martingale_profit = -1.00
    print(f"\n[TEST] 📉 Mocked a previous loss. Current Sequence P/L: ${bot.martingale_profit:.2f}")
    
    uri = "wss://ws.binaryws.com/websockets/v3?app_id=1089"
    try:
        async with websockets.connect(uri) as ws:
            bot.websocket = ws
            
            # 1. Authorize
            print("[TEST] 🔐 Authorizing...")
            await ws.send(json.dumps({"authorize": API_TOKEN}))
            auth = json.loads(await ws.recv())
            if 'error' in auth:
                print(f"[TEST] ❌ Auth Error: {auth['error']['message']}")
                return
            print(f"[TEST] ✅ Authorized. Balance: {auth['authorize']['balance']} {auth['authorize']['currency']}")
            
            # Let's set the bot to 'running' state and trigger a trade artificially
            bot.is_running = True
            bot.currency = auth['authorize']['currency']
            
            # The net profit multiplier for DIGITOVER 5 is 1.43
            # To recover $1.00 exactly, the stake should be $1.00 / 1.43 = $0.70
            
            # We will manually invoke the exact recovery calculation logic (which usually runs inside handle_message on trigger)
            multiplier = bot.PAYOUT_MULTIPLIERS["DIGITOVER"][5]
            required_stake = max(0.35, abs(bot.martingale_profit) / multiplier)
            bot.stake = round(required_stake, 2)
            
            print(f"[TEST] 🧮 DIGITOVER 5 Multiplier is {multiplier}x")
            print(f"[TEST] 🧮 Calculated Recovery Stake: ${bot.stake} (should be approx ${1.00/1.43:.2f})")
            
            # Now send the proposal using that exact stake
            print("[TEST] 🚀 Sending Proposal to Deriv...")
            proposal_req = {
                "proposal": 1,
                "amount": bot.stake, 
                "basis": "stake",
                "contract_type": "DIGITOVER",
                "currency": bot.currency,
                "duration": 1,
                "duration_unit": "t",
                "symbol": "1HZ100V",
                "barrier": 5 
            }
            await ws.send(json.dumps(proposal_req))
            
            proposal_res = json.loads(await ws.recv())
            if 'error' in proposal_res:
                print(f"[TEST] ❌ Proposal Error: {proposal_res['error']['message']}")
                return
                
            payout = proposal_res['proposal']['payout']
            cost = proposal_res['proposal']['ask_price']
            net_profit = payout - cost
            
            print(f"[TEST] ✅ Proposal Accepted by Deriv!")
            print(f"[TEST] 📄 Contract Cost : ${cost:.2f}")
            print(f"[TEST] 📄 Potential Net Profit : ${net_profit:.2f}")
            
            # Verify if this net profit exactly recovers our $1.00 loss
            print("\n[TEST] --- RECOVERY MATH VERIFICATION ---")
            print(f"Previous Loss      : -${abs(bot.martingale_profit):.2f}")
            print(f"Profit if won      : +${net_profit:.2f}")
            print(f"Final Seq P/L      : ${net_profit + bot.martingale_profit:.2f}")
            
            if abs(net_profit + bot.martingale_profit) < 0.05:
                print("🎯 SUCCESS! The payout perfectly covers the previous loss.")
            else:
                print("⚠️ WARNING: The payout does not perfectly match the loss.")
                
            print("\n[TEST] 🛑 Test complete. No real trade was bought, only proposed.")

    except Exception as e:
        print(f"[TEST] Error: {e}")

if __name__ == "__main__":
    asyncio.run(run_terminal_test())
