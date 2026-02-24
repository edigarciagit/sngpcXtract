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
        
        # Injected JS to fetch all concurrently
        batch_fetch_script = f"""
            var callback = arguments[arguments.length - 1];
            var urls = {urls_json};
            
            Promise.all(urls.map(url => 
                fetch(url, {{
                    method: 'GET',
                    headers: {{
                        'Accept': 'application/json',
                        'Authorization': 'Guest',
                        'X-Requested-With': 'XMLHttpRequest'
                    }}
                }})
                .then(r => r.ok ? r.text() : Promise.reject('HTTP ' + r.status))
                .then(text => ({{ url: url, status: 'SUCCESS', data: JSON.parse(text) }}))
                .catch(err => ({{ url: url, status: 'ERROR', message: err.toString() }}))
            ))
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
