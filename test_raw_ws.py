import websocket
import json
import ssl
import time
import threading

# Configuration
APP_ID = 1089
TOKEN = "YOUR_TOKEN_HERE" # Will replace with env var or let user run
URL = f"wss://ws.binaryws.com/websockets/v3?app_id={APP_ID}"

def on_message(ws, message):
    data = json.loads(message)
    print(f"Received: {data}")
    
    if "error" in data:
        print(f"ERROR: {data['error']['message']}")
        ws.close()

    if "proposal" in data:
        print(f"SUCCESS: Proposal ID {data['proposal']['id']}")
        ws.close()

def on_open(ws):
    print("Connected. Sending Proposal...")
    req = {
        "proposal": 1,
        "amount": 0.35,
        "basis": "stake",
        "contract_type": "DIGITOVER",
        "currency": "USD",
        "duration": 1,
        "duration_unit": "t",
        "symbol": "1HZ100V",
        "barrier": 0
    }
    ws.send(json.dumps(req))

def on_error(ws, error):
    print(f"Websocket Error: {error}")

def on_close(ws, status, msg):
    print("Closed")

def run():
    ws = websocket.WebSocketApp(URL,
                                on_open=on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

if __name__ == "__main__":
    run()
