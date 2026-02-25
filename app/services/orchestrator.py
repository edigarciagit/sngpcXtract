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
from app.core.logger import setup_logging, get_logger

# Initialize global logging once
setup_logging()
logger = get_logger("orchestrator")

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
                "percent": 0,
                "startTime": None,
                "elapsedTime": "00:00:00"
            }
            cls._instance.thread = None
            cls._instance.stop_event = threading.Event()
            cls._instance.confirmation_event = threading.Event()
            cls._instance.confirmation_response = None # True = Proceed, False = Abort
        return cls._instance

    def stop(self):
        if self.thread and self.thread.is_alive():
            logger.info("Stopping current extraction process...")
            self.stop_event.set()
            self.confirmation_event.set() # Release any waiting in confirmation
            self.thread.join(timeout=10)
            logger.info("Previous process stopped.")
        self.stop_event.clear()

    def start(self, reuse_bulk=False):
        if self.thread and self.thread.is_alive():
            logger.warning("Process already running. Killing it and starting new...")
            self.stop()
        
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run_pipeline, args=(reuse_bulk,))
        self.thread.start()
        return True, "Started."

    def confirm_extraction(self, proceed=True):
        self.confirmation_response = proceed
        self.confirmation_event.set()
        return True, "Confirmation received."

    def get_status(self):
        with self._lock:
            return self.status.copy()

    def _run_pipeline(self, reuse_bulk):
        try:
            with self._lock:
                self.status["startTime"] = time.time()
                self.status["elapsedTime"] = "00:00:00"

            # Initialize DB
            Database.init_db()
            
            if not reuse_bulk:
                self._update_status("RUNNING_BULK", "Clearing database and cache for fresh extraction...", 0, 0, 0)
                Database.clear_data()
                
                # Clear bulk products cache file
                bulk_file = "data/bulk_products.json"
                if os.path.exists(bulk_file):
                    try:
                        os.remove(bulk_file)
                        logger.info(f"Cleared existing cache: {bulk_file}")
                    except Exception as e:
                        logger.warning(f"Could not clear {bulk_file}: {e}")
                
                time.sleep(1)

            # Phase 1: Bulk
            if reuse_bulk and os.path.exists("data/bulk_products.json") and os.path.getsize("data/bulk_products.json") > 0:
                self._update_status("RUNNING_BULK", "Skipping fetch, using existing 'bulk_products.json'...", 0, 0, 5)
                time.sleep(1) # Visual delay
            else:
                self._update_status("RUNNING_BULK", "Fetching product codes list...", 0, 0, 5)
                bulk = BulkScraper()
                
                def on_count_found(count):
                    self._update_status("AWAITING_CONFIRMATION", f"Found {count} products.", count, 0, 5)
                    self.confirmation_event.clear()
                    self.confirmation_event.wait() # Blocking wait
                    return self.confirmation_response

                count = bulk.run(on_count_callback=on_count_found) 
                
                if count == 0 and not self.confirmation_response:
                    self._update_status("IDLE", "Extraction aborted by user.", 0, 0, 0)
                    return
                
                if not os.path.exists("data/bulk_products.json"):
                    logger.error("Bulk extraction failed - output file missing.")
                    raise Exception("Bulk scraping failed to produce output file.")
                logger.info(f"Bulk extraction completed: {count} codes found.")

            if self.stop_event.is_set():
                logger.info("Pipeline stopped before details phase.")
                return

            # Phase 2: Details (Parallel)
            with open("data/bulk_products.json", 'r', encoding='utf-8') as f:
                codes_list = json.load(f)
            
            total_items = len(codes_list)
            self._update_status("RUNNING_DETAILS", f"Processing {total_items} items (High Performance Mode)...", total_items, 0, 10)
            
            # Chunking strategies (Increased parallelism)
            num_workers = 8
            if total_items == 0:
                self._update_status("COMPLETED", "No items to process.", 0, 0, 100)
                return

            chunk_size = ceil(total_items / num_workers)
            chunks = [codes_list[i:i + chunk_size] for i in range(0, total_items, chunk_size)]
            
            logger.info(f"Starting {len(chunks)} threads for {total_items} items.")

            with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = []
                for chunk in chunks:
                    futures.append(executor.submit(self._process_chunk, chunk))
                
                # Wait for all to complete
                concurrent.futures.wait(futures)
                
                # Check for exceptions
                for future in futures:
                    if future.exception():
                        logger.error(f"Thread Error: {future.exception()}")

            self._update_status("COMPLETED", "Extraction finished successfully.", total_items, total_items, 100)
            
        except Exception as e:
            logger.exception(f"Orchestrator Pipeline Error: {e}")
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
            
            # Process in sub-batches of 10 for maximum JS concurrency
            sub_batch_size = 10
            for i in range(0, len(chunk), sub_batch_size):
                if self.stop_event.is_set():
                    break
                
                sub_batch = chunk[i:i + sub_batch_size]
                codes = [item.get("codigoProduto") for item in sub_batch if item.get("codigoProduto")]
                
                if not codes:
                    continue

                # Renew Session logic (approx 700 items safety per thread/browser)
                if items_since_renew >= 700:
                    logger.info("Renewing worker session for stability...")
                    driver.quit()
                    time.sleep(2)
                    driver = WebDriverFactory.create_driver(headless=True)
                    driver.get("https://consultas.anvisa.gov.br/")
                    time.sleep(5)
                    items_since_renew = 0
                
                # Scrape entire sub-batch concurrently in JS
                results = scraper.scrape_batch(codes, driver=driver)
                
                # Check for high failure rate (e.g., more than 50% failed)
                # Success count
                success_count = len([r for r in results if r[1]])
                failure_count = len(codes) - success_count
                
                if failure_count > (len(codes) // 2) and len(codes) > 1:
                    logger.warning(f"High failure rate detected ({failure_count}/{len(codes)}). Possible soft block. Cooling down...")
                    time.sleep(10)
                    items_since_renew = 701 # Trigger renewal in next loop
                
                # Save results in high-performance DB batch
                Database.save_products_batch(results)
                
                items_since_renew += len(codes)
                
                # Update Global Progress
                with self._lock:
                    self.status["current"] += len(codes)
                    current = self.status["current"]
                    total = self.status["total"]
                    if total > 0:
                        self.status["percent"] = 10 + int((min(current, total) / total) * 90)
                        self.status["message"] = f"Processed {current}/{total} (Turbo Mode)"
                    self._calculate_elapsed_time_locked()

                # Optimized polite delay
                time.sleep(random.uniform(0.3, 0.7))

        except Exception as e:
            logger.exception(f"Worker thread crashed: {e}")
            raise e
        finally:
            if driver:
                driver.quit()

    def _calculate_elapsed_time_locked(self):
        if self.status["startTime"]:
            elapsed = time.time() - self.status["startTime"]
            hrs = int(elapsed // 3600)
            mins = int((elapsed % 3600) // 60)
            secs = int(elapsed % 60)
            self.status["elapsedTime"] = f"{hrs:02d}:{mins:02d}:{secs:02d}"

    def _update_status(self, state, message, total, current, percent):
        with self._lock:
            self.status["state"] = state
            self.status["message"] = message
            self.status["total"] = total
            self.status["current"] = current
            self.status["percent"] = percent
            self._calculate_elapsed_time_locked()
