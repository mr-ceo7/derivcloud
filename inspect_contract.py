import asyncio
import json
from deriv_api import DerivAPI

async def check():
    api = DerivAPI(app_id=1089)
    try:
        # Check Payout Currencies which often lists min stake
        currencies = await api.website_status()
        print("Website Status (Currencies):", json.dumps(currencies['website_status']['currencies_config']['USD'], indent=2))

        # Get detailed contract info
        contracts = await api.contracts_for({"contracts_for": "1HZ100V"})
        
        # Filter for DIGITOVER
        available = contracts['contracts_for']['available']
        digit_over = next((c for c in available if c['contract_type'] == 'DIGITOVER'), None)
        
        if digit_over:
            print(json.dumps(digit_over, indent=2))
        else:
            print("DIGITOVER not found in available contracts")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await api.clear()

asyncio.run(check())
