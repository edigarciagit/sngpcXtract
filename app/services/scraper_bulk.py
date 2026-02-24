import json
import random
import time
import urllib.parse
from app.core.driver import WebDriverFactory
from app.core.logger import get_logger

logger = get_logger("scraper_bulk")

class BulkScraper:
    def __init__(self):
        self.output_file = "data/bulk_products.json"
        self.base_url = "https://consultas.anvisa.gov.br/api/consulta/medicamento/produtos/"
        self.default_params = {
            "column": "",
            "count": "20",
            "filter[situacaoRegistro]": "C,V",
            "order": "asc",
            "page": "1"
        }
        self.max_retries = 3

    def get_url(self, page, params):
        p = params.copy()
        p["page"] = str(page)
        return f"{self.base_url}?{urllib.parse.urlencode(p)}"

    def run(self, on_count_callback=None):
        logger.info(f"Starting Bulk Code Extraction to {self.output_file}...")
        
        all_codes = []
        page = 1
        total_elements = None
        fetched_count = 0
        items_since_renew = 0
        
        driver = WebDriverFactory.create_driver(headless=True)
        
        try:
            logger.info("Priming session with Anvisa URL...")
            driver.get("https://consultas.anvisa.gov.br/")
            time.sleep(5) 
            
            while True:
                # Session Renewal
                if items_since_renew >= 1000:
                    logger.info(f"Renewing session after {items_since_renew} items...")
                    driver.quit()
                    time.sleep(2)
                    driver = WebDriverFactory.create_driver(headless=True)
                    driver.get("https://consultas.anvisa.gov.br/")
                    time.sleep(5)
                    items_since_renew = 0
                
                current_url = self.get_url(page, self.default_params)
                
                # Fetch page with retry logic
                content = None
                for attempt in range(self.max_retries):
                    try:
                        logger.info(f"Fetching page {page} (Attempt {attempt + 1})...")
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
                            .then(response => {{
                                if (!response.ok) throw new Error('HTTP Status ' + response.status);
                                return response.text();
                            }})
                            .then(text => callback(text))
                            .catch(err => callback('ERROR: ' + err.message));
                        """
                        
                        content = driver.execute_async_script(fetch_script)
                        
                        if content.startswith("ERROR:"):
                            raise Exception(content)
                        
                        # If we reached here, fetch was successful
                        break
                    except Exception as e:
                        wait = (attempt + 1) * 2 + random.uniform(0.5, 1.5)
                        logger.warning(f"Fetch failed on page {page}: {e}. Retrying in {wait:.1f}s...")
                        if attempt < self.max_retries - 1:
                            time.sleep(wait)
                        else:
                            logger.error(f"Max retries reached for page {page}. Aborting bulk extraction.")
                            return len(all_codes)

                try:
                    data = json.loads(content)
                    
                    if "error" in data:
                        logger.warning(f"Stop: API Error: {data.get('error')}")
                        break
                    
                    if total_elements is None:
                        total_elements = data.get("totalElements", 0)
                        logger.info(f"Total Elements to fetch: {total_elements}")
                        
                        if on_count_callback:
                            if not on_count_callback(total_elements):
                                logger.info("Extraction cancelled by user via callback.")
                                return 0

                        if total_elements == 0:
                            break

                    items = data.get("content", [])
                    if not items:
                        break
                    
                    for item in items:
                        prod_info = item.get("produto") or {}
                        code = prod_info.get("codigo")
                        if code:
                            all_codes.append({"codigoProduto": code})
                    
                    count = len(items)
                    fetched_count += count
                    items_since_renew += count
                    
                    logger.info(f"Page {page} done. Total Codes Collected: {len(all_codes)}/{total_elements}")
                    
                    if fetched_count >= total_elements:
                        break
                    
                    page += 1
                    time.sleep(random.uniform(1.0, 2.0))
                    
                except json.JSONDecodeError:
                    logger.error(f"JSON Decode Error on page {page}")
                    break
                    
        except Exception as e:
            logger.exception(f"Scraper crashed unexpectedly: {e}")
            
        finally:
            if driver:
                driver.quit()
            
            if all_codes:
                with open(self.output_file, 'w', encoding='utf-8') as f:
                    json.dump(all_codes, f, indent=2, ensure_ascii=False)
                logger.info(f"Saved {len(all_codes)} codes to {self.output_file}")
        
        return len(all_codes)
