import json
import random
import time
from app.core.driver import WebDriverFactory
from app.core.logger import get_logger

logger = get_logger("scraper_single")

class SingleScraper:
    def __init__(self):
        self.api_url_template = "https://consultas.anvisa.gov.br/api/consulta/medicamento/produtos/codigo/{}"
        self.max_retries = 3

    def scrape_batch(self, codes, driver):
        """
        Scrapes a batch of product codes concurrently using Promise.all inside the browser.
        Returns a list of (code, data) tuples.
        """
        if not codes:
            return []

        # Prepare URLs
        url_map = {code: self.api_url_template.format(code) for code in codes}
        urls_json = json.dumps(list(url_map.values()))
        
        # Injected JS to fetch all concurrently with internal retry logic
        batch_fetch_script = f"""
            var callback = arguments[arguments.length - 1];
            var urls = {urls_json};
            
            async function fetchWithRetry(url, retries = 3) {{
                for (let i = 0; i <= retries; i++) {{
                    try {{
                        const response = await fetch(url, {{
                            method: 'GET',
                            headers: {{
                                'Accept': 'application/json',
                                'Authorization': 'Guest',
                                'X-Requested-With': 'XMLHttpRequest'
                            }}
                        }});
                        
                        if (!response.ok) throw new Error('HTTP ' + response.status);
                        
                        const text = await response.text();
                        if (!text || text.trim().length === 0) throw new Error('Empty response');
                        
                        // Check if we got HTML instead of JSON (common when blocked/redirected)
                        if (text.trim().startsWith('<')) throw new Error('Received HTML instead of JSON (Possible block)');
                        
                        try {{
                            const data = JSON.parse(text);
                            return {{ url: url, status: 'SUCCESS', data: data }};
                        }} catch (e) {{
                            throw new Error('Malformed JSON: ' + e.message + ' (Snippet: ' + text.substring(0, 50) + '...)');
                        }}
                    }} catch (err) {{
                        const errStr = err.toString();
                        const isRateLimit = errStr.includes('Empty response') || errStr.includes('429') || errStr.includes('403');
                        
                        // Fail fast on rate limits, let Python orchestrator handle the cooldown and retries
                        if (isRateLimit || i === retries) {{
                            return {{ url: url, status: 'ERROR', message: errStr }};
                        }}
                        
                        const baseWait = 1500;
                        const waitTime = (i + 1) * baseWait + Math.random() * 2000;
                        
                        await new Promise(r => setTimeout(r, waitTime));
                    }}
                }}
            }}

            // Stagger request starts by 200ms increments to avoid concurrency spikes
            Promise.all(urls.map((url, index) => {{
                return new Promise(resolve => setTimeout(resolve, index * 200))
                    .then(() => fetchWithRetry(url));
            }}))
                .then(results => callback(results))
                .catch(err => callback('GLOBAL_ERROR: ' + err));
        """

        try:
            results = driver.execute_async_script(batch_fetch_script)
            
            if isinstance(results, str) and results.startswith("GLOBAL_ERROR:"):
                logger.error(f"Global batch fetch error: {results}")
                return []

            # Map results back to codes
            batch_results = {}
            # Create a reverse map URL -> Code
            url_to_code = {v: k for k, v in url_map.items()}
            
            # Initialize all requested codes as failed in case they are missing from results
            for code in codes:
                batch_results[code] = {"success": False, "data": None, "error": "No response returned from browser script"}
            
            if isinstance(results, list):
                for res in results:
                    url = res.get('url')
                    code = url_to_code.get(url)
                    if not code:
                        continue
                    if res.get('status') == 'SUCCESS':
                        batch_results[code] = {"success": True, "data": res.get('data'), "error": None}
                    else:
                        logger.warning(f"Batch item failed for {code}: {res.get('message')}")
                        batch_results[code] = {"success": False, "data": None, "error": res.get('message')}
            
            return batch_results

        except Exception as e:
            logger.error(f"Error executing batch script: {e}")
            # Return all requested codes as failed with the exception message
            return {code: {"success": False, "data": None, "error": str(e)} for code in codes}

    def scrape(self, code, driver=None):
        """
        KEEPS COMPATIBILITY: Scrapes a single code using the new batch logic (batch of 1).
        """
        created_driver = False
        if driver is None:
            driver = WebDriverFactory.create_driver(headless=True)
            driver.get("https://consultas.anvisa.gov.br/")
            time.sleep(5)
            created_driver = True
            
        try:
            results = self.scrape_batch([code], driver)
            if results and code in results and results[code]["success"]:
                return results[code]["data"]
            return None
        finally:
            if created_driver:
                driver.quit()
