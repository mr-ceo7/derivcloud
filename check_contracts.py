import asyncio
from deriv_api import DerivAPI

async def check():
    api = DerivAPI(app_id=1089)
    try:
        # Volatility 100 (1s) Index is 1HZ100V
        contracts = await api.contracts_for({"contracts_for": "1HZ100V"})
        
        available = contracts['contracts_for']['available']
        types = set(c['contract_type'] for c in available)
        
        print("Available Contract Types:", types)
        
        if 'DIGITOVER' in types:
            print("SUCCESS: DIGITOVER is valid.")
        else:
            print("WARNING: DIGITOVER not found.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await api.clear()

asyncio.run(check())
