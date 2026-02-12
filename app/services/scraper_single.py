import json
import random
import time
from selenium.webdriver.common.by import By
from app.core.driver import WebDriverFactory

class SingleScraper:
    def __init__(self):
        self.output_file = "data/scraped_data.json"
        self.api_url_template = "https://consultas.anvisa.gov.br/api/consulta/medicamento/produtos/codigo/{}"

    def scrape(self, code, driver=None):
        should_close_driver = False
        if driver is None:
            driver = WebDriverFactory.create_driver(headless=True)
            should_close_driver = True
            
            # Prime if new driver (conceptually, though Orchestrator should prime reused driver)
            try:
                print("Priming new session...", flush=True)
                driver.get("https://consultas.anvisa.gov.br/")
                time.sleep(random.uniform(3, 5))
            except:
                pass

        try:
            target_url = self.api_url_template.format(code)
            # print(f"Fetching {target_url}...", flush=True) # Verbose

            fetch_script = f"""
                var callback = arguments[arguments.length - 1];
                fetch('{target_url}', {{
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
                # raise Exception(content)
                print(f"Error content for {code}: {content}")
                return None
            
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                print(f"JSON Decode Error for {code}")
                return None
            
            if "error" in data:
                print(f"API Error for {code}: {data.get('error')}")
                return None

            return data

        except Exception as e:
            print(f"Error scraping {code}: {e}")
            return None
        finally:
            if should_close_driver:
                driver.quit()
