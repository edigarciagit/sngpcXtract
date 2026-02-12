import urllib.request
import json
import time

BASE = "http://localhost:8000"

def verify():
    print("Verifying Pipeline API...")
    
    # Check Server Up
    try:
        urllib.request.urlopen(BASE)
        print("Server is UP.")
    except:
        print("Server is DOWN. Make sure 'python main.py server' is running.")
        return

    # Check Progress Endpoint (Should be IDLE)
    try:
        with urllib.request.urlopen(f"{BASE}/api/progress") as res:
            data = json.loads(res.read().decode())
            print(f"Initial Status: {data.get('state')}")
            if data.get('state') == 'IDLE':
                print("PASS: Orchestrator Idle.")
            else:
                print("WARN: Orchestrator not IDLE.")
    except Exception as e:
        print(f"FAIL: Progress Endpoint ({e})")

    # Check Results Endpoint (Pagination)
    try:
        with urllib.request.urlopen(f"{BASE}/api/results?page=1&size=5") as res:
            data = json.loads(res.read().decode())
            print(f"Results Fetch: OK (Total: {data.get('totalElements')})")
    except Exception as e:
        print(f"FAIL: Results Endpoint ({e})")

if __name__ == "__main__":
    verify()
