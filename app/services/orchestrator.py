import threading
import json
import os
import time
import random
import concurrent.futures
from math import ceil
from app.services.scraper_bulk import BulkScraper
from app.services.scraper_single import SingleScraper
from app.core.driver import WebDriverFactory
from app.core.database import Database

class ExtractionOrchestrator:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ExtractionOrchestrator, cls).__new__(cls)
            cls._instance.status = {
                "state": "IDLE", # IDLE, RUNNING_BULK, RUNNING_DETAILS, COMPLETED, ERROR
                "message": "Ready to start.",
                "total": 0,
                "current": 0,
                "percent": 0
            }
            cls._instance.thread = None
            cls._instance.stop_event = threading.Event()
        return cls._instance

    def start(self, reuse_bulk=False):
        if self.thread and self.thread.is_alive():
            return False, "Process already running."
        
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run_pipeline, args=(reuse_bulk,))
        self.thread.start()
        return True, "Started."

    def get_status(self):
        with self._lock:
            return self.status.copy()

    def _run_pipeline(self, reuse_bulk):
        try:
            # Initialize DB
            Database.init_db()
            
            if not reuse_bulk:
                self._update_status("RUNNING_BULK", "Clearing database for fresh extraction...", 0, 0, 0)
                Database.clear_data()
                time.sleep(1)

            # Phase 1: Bulk
            if reuse_bulk and os.path.exists("data/bulk_products.json") and os.path.getsize("data/bulk_products.json") > 0:
                self._update_status("RUNNING_BULK", "Skipping fetch, using existing 'bulk_products.json'...", 0, 0, 5)
                time.sleep(1) # Visual delay
            else:
                self._update_status("RUNNING_BULK", "Fetching product codes list...", 0, 0, 5)
                bulk = BulkScraper()
                count = bulk.run() 
                
                if not os.path.exists("data/bulk_products.json"):
                    raise Exception("Bulk scraping failed to produce output file.")

            # Phase 2: Details (Parallel)
            with open("data/bulk_products.json", 'r', encoding='utf-8') as f:
                codes_list = json.load(f)
            
            total_items = len(codes_list)
            self._update_status("RUNNING_DETAILS", f"Processing {total_items} items (Parallel x5)...", total_items, 0, 10)
            
            # Chunking strategies
            num_workers = 5
            if total_items == 0:
                self._update_status("COMPLETED", "No items to process.", 0, 0, 100)
                return

            chunk_size = ceil(total_items / num_workers)
            chunks = [codes_list[i:i + chunk_size] for i in range(0, total_items, chunk_size)]
            
            print(f"Starting {len(chunks)} threads for {total_items} items.", flush=True)

            with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = []
                for chunk in chunks:
                    futures.append(executor.submit(self._process_chunk, chunk))
                
                # Wait for all to complete
                concurrent.futures.wait(futures)
                
                # Check for exceptions
                for future in futures:
                    if future.exception():
                        print(f"Thread Error: {future.exception()}")
                        # We continue even if one thread fails, but log it? 
                        # Or fail whole process? Let's check if all failed.

            self._update_status("COMPLETED", "Extraction finished successfully.", total_items, total_items, 100)
            
        except Exception as e:
            print(f"Orchestrator Error: {e}")
            self._update_status("ERROR", str(e), 0, 0, 0)

    def _process_chunk(self, chunk):
        driver = None
        try:
            driver = WebDriverFactory.create_driver(headless=True)
            scraper = SingleScraper()
            items_since_renew = 0
            
            # Prime session
            driver.get("https://consultas.anvisa.gov.br/")
            time.sleep(5)
            
            for item in chunk:
                if self.stop_event.is_set():
                    break
                    
                code = item.get("codigoProduto")
                if not code: 
                    continue
                
                # Renew Session logic (200 items safety per thread)
                if items_since_renew >= 200:
                    driver.quit()
                    time.sleep(2)
                    driver = WebDriverFactory.create_driver(headless=True)
                    driver.get("https://consultas.anvisa.gov.br/")
                    time.sleep(5)
                    items_since_renew = 0
                
                # Scrape
                data = scraper.scrape(code, driver=driver)
                
                if data:
                    # Save to DB instead of file
                    Database.save_product(code, data)
                
                items_since_renew += 1
                
                # Update Global Progress
                with self._lock:
                    self.status["current"] += 1
                    current = self.status["current"]
                    total = self.status["total"]
                    if total > 0:
                        self.status["percent"] = 10 + int((current / total) * 90)
                        self.status["message"] = f"Processed {current}/{total}"

                time.sleep(random.uniform(0.2, 0.5)) # Slightly faster delay for parallel

        except Exception as e:
            print(f"Worker Crash: {e}", flush=True)
            raise e
        finally:
            if driver:
                driver.quit()

    def _update_status(self, state, message, total, current, percent):
        with self._lock:
            self.status["state"] = state
            self.status["message"] = message
            self.status["total"] = total
            self.status["current"] = current
            self.status["percent"] = percent
