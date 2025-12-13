import asyncio
from deriv_api import DerivAPI

async def check_stake(api, stake):
    print(f"\n--- Testing Stake {stake} ---")
    try:
        proposal = await api.proposal({
            "proposal": 1,
            "amount": stake,
            "basis": "stake",
            "contract_type": "DIGITOVER",
            "currency": "USD",
            "duration": 1,
            "duration_unit": "t",
            "symbol": "1HZ100V",
            "barrier": 0  # Testing Integer
        })
        print(f"SUCCESS: ID {proposal['proposal']['id']}")
        return True
    except Exception as e:
        print(f"FAILED: {e}")
        return False

async def check():
    api = DerivAPI(app_id=1089)
    try:
        # Check 0.35
        await check_stake(api, 0.35)
        
    finally:
        await api.clear()

asyncio.run(check())
