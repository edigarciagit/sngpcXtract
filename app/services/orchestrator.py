import threading
import json
import os
import time
import random
import concurrent.futures
import queue
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

    def start(self, reuse_bulk=False, num_workers=4, inactive_only=False):
        if self.thread and self.thread.is_alive():
            logger.warning("Process already running. Killing it and starting new...")
            self.stop()
        
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run_pipeline, args=(reuse_bulk, num_workers, inactive_only))
        self.thread.start()
        return True, "Started."

    def confirm_extraction(self, proceed=True):
        self.confirmation_response = proceed
        self.confirmation_event.set()
        return True, "Confirmation received."

    def get_status(self):
        with self._lock:
            return self.status.copy()

    def _run_pipeline(self, reuse_bulk, num_workers, inactive_only):
        try:
            with self._lock:
                self.status["startTime"] = time.time()
                self.status["elapsedTime"] = "00:00:00"

            # Initialize DB
            Database.init_db()
            
            if not reuse_bulk:
                self._update_status("RUNNING_BULK", "Clearing database and cache for fresh extraction...", 0, 0, 0)
                Database.clear_bulk_codes()
                Database.clear_data()
                time.sleep(1)

            # Phase 1: Bulk
            # Check if there are any codes already in the bulk products queue table in SQLite
            existing_codes = Database.get_bulk_codes()
            has_existing_codes = len(existing_codes) > 0
            
            if reuse_bulk and has_existing_codes:
                self._update_status("RUNNING_BULK", "Skipping fetch, using existing codes in database...", 0, 0, 5)
                time.sleep(1) # Visual delay
            else:
                self._update_status("RUNNING_BULK", "Fetching product codes list...", 0, 0, 5)
                # Ensure we clear the old queue first if we are doing a fresh crawl
                Database.clear_bulk_codes()
                bulk = BulkScraper(inactive_only=inactive_only)
                
                def on_count_found(count):
                    self._update_status("AWAITING_CONFIRMATION", f"Found {count} products.", count, 0, 5)
                    self.confirmation_event.clear()
                    self.confirmation_event.wait() # Blocking wait
                    return self.confirmation_response

                count = bulk.run(on_count_callback=on_count_found) 
                
                if count == 0 and not self.confirmation_response:
                    self._update_status("IDLE", "Extraction aborted by user.", 0, 0, 0)
                    return
                
                # Verify that codes were saved in SQLite bulk_products queue
                total_in_db = len(Database.get_bulk_codes())
                if total_in_db == 0:
                    logger.error("Bulk extraction failed - queue in database is empty.")
                    raise Exception("Bulk scraping failed to populate SQLite queue.")
                logger.info(f"Bulk extraction completed: {total_in_db} codes saved in SQLite.")

            if self.stop_event.is_set():
                logger.info("Pipeline stopped before details phase.")
                return

            # Phase 2: Details (Parallel)
            # Resumption Support: Fetch only PENDING codes
            codes_list = Database.get_bulk_codes(status='PENDING')
            total_items = len(codes_list)
            
            # Let's check the total elements (both PROCESSED and PENDING) to report correct progress percentage
            all_codes_list = Database.get_bulk_codes()
            grand_total = len(all_codes_list)
            processed_count = grand_total - total_items
            
            self._update_status("RUNNING_DETAILS", f"Processing {total_items} pending items...", grand_total, processed_count, 10)
            
            # Dynamic Queue Worker Strategy
            # num_workers is passed as parameter, defaulting to 4
            if total_items == 0:
                self._update_dcb_after_extraction(grand_total)
                self._update_status("COMPLETED", "All items processed successfully.", grand_total, grand_total, 100)
                return

            # Put all pending codes in queue
            q = queue.Queue()
            for item in codes_list:
                code = item.get("codigoProduto")
                if code:
                    q.put(code)

            logger.info(f"Starting {num_workers} worker threads for {total_items} items.")

            with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = [executor.submit(self._worker_process, q) for _ in range(num_workers)]
                
                # Wait for all to complete
                concurrent.futures.wait(futures)
                
                # Check for exceptions
                for future in futures:
                    if future.exception():
                        logger.error(f"Worker Thread Error: {future.exception()}")

            # Check if execution was interrupted by stop signal
            if self.stop_event.is_set():
                self._update_status("IDLE", "Extraction stopped by user.", grand_total, self.status["current"], self.status["percent"])
            else:
                self._update_dcb_after_extraction(grand_total)
                self._update_status("COMPLETED", "Extraction finished successfully.", grand_total, grand_total, 100)
            
        except Exception as e:
            logger.exception(f"Orchestrator Pipeline Error: {e}")
            self._update_status("ERROR", str(e), 0, 0, 0)

    def _worker_process(self, q):
        driver = None
        try:
            driver = WebDriverFactory.create_driver(headless=True)
            scraper = SingleScraper()
            items_since_renew = 0
            
            # Prime session
            driver.get("https://consultas.anvisa.gov.br/")
            # Interruptible sleep for priming session
            for _ in range(50):
                if self.stop_event.is_set():
                    break
                time.sleep(0.1)
            
            while not self.stop_event.is_set():
                # Get a sub-batch of up to 5 codes from the queue
                sub_batch = []
                for _ in range(5):
                    try:
                        code = q.get_nowait()
                        sub_batch.append(code)
                    except queue.Empty:
                        break
                
                if not sub_batch or self.stop_event.is_set():
                    break
                
                # Renew Session logic (approx 700 items safety per thread/browser)
                if items_since_renew >= 700:
                    if self.stop_event.is_set():
                        break
                    logger.info("Renewing worker session for stability...")
                    driver.quit()
                    time.sleep(2)
                    if self.stop_event.is_set():
                        driver = None
                        break
                    driver = WebDriverFactory.create_driver(headless=True)
                    driver.get("https://consultas.anvisa.gov.br/")
                    for _ in range(50):
                        if self.stop_event.is_set():
                            break
                        time.sleep(0.1)
                    items_since_renew = 0
                
                # Scrape entire sub-batch concurrently in JS
                results = scraper.scrape_batch(sub_batch, driver=driver)
                
                if self.stop_event.is_set():
                    break
 
                # Check success rate for safety check
                success_count = len([c for c, r in results.items() if r["success"]])
                failure_count = len(sub_batch) - success_count
                
                if failure_count > (len(sub_batch) // 2) and len(sub_batch) > 1:
                    logger.warning(f"High failure rate detected ({failure_count}/{len(sub_batch)}). Possible soft block. Cooling down for 30s...")
                    # Interruptible sleep for 30 seconds
                    for _ in range(300):
                        if self.stop_event.is_set():
                            break
                        time.sleep(0.1)
                    items_since_renew = 701 # Trigger renewal in next loop
                
                # Save results and update queue statuses in SQLite
                Database.save_products_batch(results)
                
                items_since_renew += len(sub_batch)
                
                # Update Global Progress
                with self._lock:
                    self.status["current"] += len(sub_batch)
                    current = self.status["current"]
                    total = self.status["total"]
                    if total > 0:
                        self.status["percent"] = 10 + int((min(current, total) / total) * 90)
                        self.status["message"] = f"Processed {current}/{total} (Turbo Mode)"
                    self._calculate_elapsed_time_locked()
                
                # Mark tasks as done in queue
                for _ in range(len(sub_batch)):
                    q.task_done()
                
                # Optimized polite delay (interruptible) - increased to 1.5s - 3.0s
                delay = random.uniform(1.5, 3.0)
                for _ in range(int(delay * 10)):
                    if self.stop_event.is_set():
                        break
                    time.sleep(0.1)
                
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

    def _update_dcb_after_extraction(self, grand_total):
        try:
            self._update_status("RUNNING_DETAILS", "Atualizando Denominações Comuns Brasileiras (DCB)...", grand_total, grand_total, 99)
            from app.services.dcb_service import DCBService
            url = "https://bibliotecadigital.anvisa.gov.br/jspui/bitstream/anvisa/20673/3/1-%20Lista%20DCB%20consolidada%20abr%202026.xlsx"
            dest_dir = r"data/dcb"
            dest_file = os.path.join(dest_dir, "dcb_list.xlsx")
            os.makedirs(dest_dir, exist_ok=True)
            
            import urllib.request
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            req = urllib.request.Request(url, headers=headers)
            logger.info("Auto-updating DCB database from Anvisa digital library...")
            with urllib.request.urlopen(req, timeout=30) as response:
                with open(dest_file, 'wb') as out_file:
                    out_file.write(response.read())
            
            success, msg = DCBService.import_from_xlsx(dest_file)
            if success:
                logger.info("DCB database updated successfully.")
            else:
                logger.error(f"DCB database update failed: {msg}")
        except Exception as dcb_err:
            logger.error(f"Failed to auto-update DCB: {dcb_err}")
