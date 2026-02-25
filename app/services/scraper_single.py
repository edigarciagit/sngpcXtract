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
                        if (i === retries) return {{ url: url, status: 'ERROR', message: err.toString() }};
                        
                        // Smart Pause: Wait MUCH longer if it was an empty response (likely rate limit)
                        const isRateLimit = err.toString().includes('Empty response');
                        const baseWait = isRateLimit ? 3000 : 1500;
                        const waitTime = (i + 1) * baseWait + Math.random() * 2000;
                        
                        await new Promise(r => setTimeout(r, waitTime));
                    }}
                }}
            }}

            Promise.all(urls.map(url => fetchWithRetry(url)))
                .then(results => callback(results))
                .catch(err => callback('GLOBAL_ERROR: ' + err));
        """

        try:
            results = driver.execute_async_script(batch_fetch_script)
            
            if isinstance(results, str) and results.startswith("GLOBAL_ERROR:"):
                logger.error(f"Global batch fetch error: {results}")
                return []

            # Map results back to codes
            final_data = []
            # Create a reverse map URL -> Code
            url_to_code = {v: k for k, v in url_map.items()}
            
            for res in results:
                url = res.get('url')
                code = url_to_code.get(url)
                if res.get('status') == 'SUCCESS':
                    final_data.append((code, res.get('data')))
                else:
                    logger.warning(f"Batch item failed for {code}: {res.get('message')}")
                    # We could implement individual retries here if needed, 
                    # but for now we'll rely on the orchestrator's chunking logic.
            
            return final_data

        except Exception as e:
            logger.error(f"Error executing batch script: {e}")
            return []

    def scrape(self, code, driver=None):
        """
        KEEPS COMPATIBILITY: Scrapes a single code using the new batch logic (batch of 1).
        """
        results = self.scrape_batch([code], driver)
        if results:
            return results[0][1]
        return None
