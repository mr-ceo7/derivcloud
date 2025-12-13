import asyncio
from deriv_api import DerivAPI

async def check_scenario(api, contract_type, barrier, duration, stake, desc):
    print(f"\n--- Testing {desc} ---")
    try:
        proposal = await api.proposal({
            "proposal": 1,
            "amount": stake,
            "basis": "stake",
            "contract_type": contract_type,
            "currency": "USD",
            "duration": duration,
            "duration_unit": "t",
            "symbol": "1HZ100V",
            "barrier": str(barrier)
        })
        print(f"SUCCESS: ID {proposal['proposal']['id']}")
        return True
    except Exception as e:
        print(f"FAILED: {e}")
        return False

async def check():
    api = DerivAPI(app_id=1089)
    try:
        # Case 1: The current failing case
        await check_scenario(api, "DIGITOVER", 0, 1, 0.35, "DIGITOVER 0 | 1 Tick | 0.35")
        
        # Case 2: Using the DIGITDIFF workaround
        await check_scenario(api, "DIGITDIFF", 0, 1, 0.35, "DIGITDIFF 0 | 1 Tick | 0.35")
        
        # Case 3: Increasing Duration (Does 1t require higher stake?)
        await check_scenario(api, "DIGITOVER", 0, 5, 0.35, "DIGITOVER 0 | 5 Ticks | 0.35")
        
        # Case 4: Increasing Stake slightly
        await check_scenario(api, "DIGITOVER", 0, 1, 0.36, "DIGITOVER 0 | 1 Tick | 0.36")

    finally:
        await api.clear()

asyncio.run(check())
