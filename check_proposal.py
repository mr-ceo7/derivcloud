import asyncio
from deriv_api import DerivAPI

async def check_scenario(api, stake, barrier, market, desc):
    print(f"\n--- Testing {desc} ---")
    print(f"Stake: {stake}, Barrier: {barrier}, Market: {market}")
    try:
        proposal = await api.proposal({
            "proposal": 1,
            "amount": stake, 
            "basis": "stake",
            "contract_type": "DIGITOVER", 
            "currency": "USD",
            "duration": 1,
            "duration_unit": "t",
            "symbol": market,
            "barrier": str(barrier)
        })
        print("SUCCESS:", proposal['proposal']['id'])
    except Exception as e:
        print(f"FAILED: {e}")

async def check():
    api = DerivAPI(app_id=1089)
    try:
        # Case 1: The user's exact failing case
        await check_scenario(api, 0.35, 0, "1HZ100V", "Case 1: Stake 0.35, Over 0 (High Win Chance)")
        
        # Case 2: Higher Barrier (Lower Win Chance = Higher Payout)
        await check_scenario(api, 0.35, 5, "1HZ100V", "Case 2: Stake 0.35, Over 5 (Medium Win Chance)")
        
        # Case 3: Different Market
        await check_scenario(api, 0.35, 0, "R_100", "Case 3: Stake 0.35, Over 0, Market R_100")

        # Case 4: Higher Stake
        await check_scenario(api, 0.40, 0, "1HZ100V", "Case 4: Stake 0.40, Over 0")

    finally:
        await api.clear()

asyncio.run(check())
