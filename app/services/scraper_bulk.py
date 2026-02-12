import json
import random
import time
import urllib.parse
from app.core.driver import WebDriverFactory

class BulkScraper:
    def __init__(self):
        self.output_file = "data/bulk_products.json"
        self.base_url = "https://consultas.anvisa.gov.br/api/consulta/medicamento/produtos/"
        self.default_params = {
            "column": "",
            "count": "20",
            "filter[checkNotificado]": "false",
            "filter[checkRegistrado]": "true",
            "filter[prescricoes]": "536,537,538,539,27414,540",
            "filter[situacaoRegistro]": "V",
            "filter[tarjas]": "2,3,4",
            "order": "asc",
            "page": "1"
        }

    def get_url(self, page, params):
        p = params.copy()
        p["page"] = str(page)
        return f"{self.base_url}?{urllib.parse.urlencode(p)}"

    def run(self):
        print(f"Starting Bulk Code Extraction to {self.output_file}...", flush=True)
        
        all_codes = []
        page = 1
        total_elements = None
        fetched_count = 0
        items_since_renew = 0
        
        driver = WebDriverFactory.create_driver(headless=True)
        
        try:
            print("Priming session...", flush=True)
            driver.get("https://consultas.anvisa.gov.br/")
            time.sleep(5) 
            
            while True:
                # Session Renewal
                if items_since_renew >= 1000:
                    print(f"Renewing session after {items_since_renew} items...", flush=True)
                    driver.quit()
                    time.sleep(2)
                    driver = WebDriverFactory.create_driver(headless=True)
                    driver.get("https://consultas.anvisa.gov.br/")
                    time.sleep(5)
                    items_since_renew = 0
                
                current_url = self.get_url(page, self.default_params)
                print(f"Fetching page {page}...", flush=True)
                
                fetch_script = f"""
                    var callback = arguments[arguments.length - 1];
                    fetch('{current_url}', {{
                        method: 'GET',
                        headers: {{
                            'Accept': 'application/json',
                            'Authorization': 'Guest',
                            'X-Requested-With': 'XMLHttpRequest'
                        }}
                    }})
                    .then(response => response.text())
                    .then(text => callback(text))
                    .catch(err => callback('ERROR: ' + err));
                """
                
                content = driver.execute_async_script(fetch_script)
                
                if content.startswith("ERROR:"):
                    print(f"Fetch failed on page {page}: {content}")
                    break

                try:
                    data = json.loads(content)
                    
                    if "error" in data:
                        print(f"Stop: API Error: {data.get('error')}")
                        break
                    
                    if total_elements is None:
                        total_elements = data.get("totalElements", 0)
                        print(f"Total Elements: {total_elements}")
                        if total_elements == 0:
                            break

                    items = data.get("content", [])
                    if not items:
                        break
                    
                    for item in items:
                        # Extract ONLY codigoProduto as requested
                        prod_info = item.get("produto", {})
                        code = prod_info.get("codigo")
                        if code:
                            all_codes.append({"codigoProduto": code})
                    
                    count = len(items)
                    fetched_count += count
                    items_since_renew += count
                    
                    print(f"Page {page} done. Total Codes: {len(all_codes)}/{total_elements}", flush=True)
                    
                    if fetched_count >= total_elements:
                        break
                    
                    page += 1
                    time.sleep(random.uniform(1.0, 2.0))
                    
                except json.JSONDecodeError:
                    print(f"JSON Error on page {page}")
                    break
                    
        except Exception as e:
            print(f"Scraper crashed: {e}")
            
        finally:
            if driver:
                driver.quit()
            
            if all_codes:
                with open(self.output_file, 'w', encoding='utf-8') as f:
                    json.dump(all_codes, f, indent=2, ensure_ascii=False)
                print(f"Saved {len(all_codes)} codes to {self.output_file}")
        
        return len(all_codes)
