import asyncio
from deriv_api import DerivAPI

async def check():
    api = DerivAPI(app_id=1089)
    try:
        # Construct exact payload that worked in test_raw_ws.py
        req = {
            "proposal": 1,
            "amount": 0.35, # Float
            "basis": "stake",
            "contract_type": "DIGITOVER",
            "currency": "USD",
            "duration": 1,
            "duration_unit": "t",
            "symbol": "1HZ100V",
            "barrier": 0 # Integer
        }
        
        # Use low-level send if available (it is in python-deriv-api)
        # Note: deriv_api.send usually returns the response directly
        response = await api.send(req)
        
        print("Response:", response)
        if 'error' in response:
             print("FAILED:", response['error']['message'])
        else:
             print("SUCCESS: ID", response['proposal']['id'])

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await api.clear()

asyncio.run(check())
