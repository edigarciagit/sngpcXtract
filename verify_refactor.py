import urllib.request
import json
import time

BASE_URL = "http://localhost:8000"
API_URL = f"{BASE_URL}/api/proxy?code=832670"

def test_endpoints():
    print("Verifying Refactored Server...")
    
    # 1. Test Frontend Serve
    try:
        print(f"GET {BASE_URL} (Frontend)...", end=" ")
        with urllib.request.urlopen(BASE_URL) as response:
            if response.status == 200:
                content = response.read().decode('utf-8')
                if "<title>Consulta Medicamentos ANVISA</title>" in content:
                    print("OK")
                else:
                    print("FAIL (Content mismatch)")
            else:
                print(f"FAIL ({response.status})")
    except Exception as e:
        print(f"FAIL ({e})")

    # 2. Test API Proxy (Real Selenium fetch)
    try:
        print(f"GET {API_URL} (API Proxy)...", end=" ")
        # This might take a few seconds due to Selenium startup
        start = time.time()
        with urllib.request.urlopen(API_URL) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                if "nomeComercial" in data or "produto" in data:
                    print(f"OK ({time.time()-start:.1f}s)")
                else:
                    print("FAIL (Invalid JSON structure)")
            else:
                print(f"FAIL ({response.status})")
    except Exception as e:
        print(f"FAIL ({e})")

if __name__ == "__main__":
    test_endpoints()
