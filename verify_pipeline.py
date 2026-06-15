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
    except Exception as e:
        print(f"Server is DOWN. Make sure 'python main.py server' is running. Error: {e}")
        return

    # 1. Check Progress Endpoint (Should be IDLE)
    try:
        with urllib.request.urlopen(f"{BASE}/api/progress") as res:
            data = json.loads(res.read().decode('utf-8'))
            print(f"Initial Status: {data.get('state')}")
            if data.get('state') == 'IDLE':
                print("PASS: Orchestrator Idle.")
            else:
                print("WARN: Orchestrator not IDLE.")
    except Exception as e:
        print(f"FAIL: Progress Endpoint ({e})")

    # 2. Check Results Endpoint (Pagination)
    ms_code = None
    try:
        with urllib.request.urlopen(f"{BASE}/api/results?page=1&size=5") as res:
            data = json.loads(res.read().decode('utf-8'))
            total_elements = data.get('totalElements')
            print(f"Results Fetch: OK (Total: {total_elements})")
            content = data.get('content', [])
            if content:
                ms_code = content[0].get('numero_registro')
                print(f"PASS: Successfully retrieved a sample MS code '{ms_code}' for subsequent testing.")
            else:
                print("WARN: No items in content to fetch MS code from.")
    except Exception as e:
        print(f"FAIL: Results Endpoint ({e})")

    # 3. Check MS Lookup Endpoint (with DCB enrichment)
    if ms_code:
        try:
            with urllib.request.urlopen(f"{BASE}/api/ms/{ms_code}") as res:
                data = json.loads(res.read().decode('utf-8'))
                print(f"MS Lookup for {ms_code}: OK (Found {len(data)} presentations)")
                
                # Check DCB enrichment
                has_dcb = any('dcb_list' in item for item in data)
                if has_dcb:
                    print("PASS: Presentations are enriched with DCB list data.")
                    # Let's inspect the first presentation's DCB info
                    dcb_list = data[0].get('dcb_list', [])
                    print(f"  Sample DCB List for '{data[0].get('apresentacao')}': {dcb_list}")
                else:
                    print("FAIL: Presentations are missing DCB data.")
        except Exception as e:
            print(f"FAIL: MS Lookup Endpoint ({e})")
    else:
        print("SKIP: MS Lookup Endpoint check (no MS code available).")

    # 4. Check Swagger Documentation Endpoint (/api-docs)
    try:
        with urllib.request.urlopen(f"{BASE}/api-docs") as res:
            content = res.read().decode('utf-8')
            if "SwaggerUIBundle" in content or "<div id=\"swagger-ui\">" in content:
                print("PASS: Swagger UI Documentation Endpoint is functional.")
            else:
                print("FAIL: Swagger UI is missing expected markers.")
    except Exception as e:
        print(f"FAIL: Swagger Documentation Endpoint ({e})")

    # 5. Check OpenAPI JSON Endpoint (/frontend/openapi.json)
    try:
        with urllib.request.urlopen(f"{BASE}/frontend/openapi.json") as res:
            data = json.loads(res.read().decode('utf-8'))
            if data.get('openapi'):
                print(f"PASS: OpenAPI Specification Endpoint is functional (OpenAPI Version: {data.get('openapi')}).")
            else:
                print("FAIL: openapi.json is missing 'openapi' root field.")
    except Exception as e:
        print(f"FAIL: OpenAPI JSON Endpoint ({e})")

if __name__ == "__main__":
    verify()

