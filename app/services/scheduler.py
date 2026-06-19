import os
import json
import time
import threading
from datetime import datetime
from app.services.orchestrator import ExtractionOrchestrator
from app.core.logger import get_logger

logger = get_logger("scheduler")

class DailyScheduler:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DailyScheduler, cls).__new__(cls)
            cls._instance.thread = None
            cls._instance.stop_event = threading.Event()
            cls._instance.config_path = "config.json"
        return cls._instance

    def load_config(self):
        default_config = {
            "daily_job": {
                "enabled": True,
                "time": "02:00",
                "num_workers": 4,
                "inactive_only": False
            }
        }
        
        if not os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=2)
                return default_config["daily_job"]
            except Exception as e:
                logger.error(f"Error creating default config.json: {e}")
                return default_config["daily_job"]
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("daily_job", default_config["daily_job"])
        except Exception as e:
            logger.error(f"Error loading config.json: {e}. Using defaults.")
            return default_config["daily_job"]

    def start(self):
        with self._lock:
            if self.thread and self.thread.is_alive():
                logger.warning("Daily Scheduler is already running.")
                return False
                
            self.stop_event.clear()
            self.thread = threading.Thread(target=self._scheduler_loop, name="DailySchedulerThread", daemon=True)
            self.thread.start()
            logger.info("Daily Scheduler started successfully.")
            return True

    def stop(self):
        with self._lock:
            if self.thread and self.thread.is_alive():
                logger.info("Stopping Daily Scheduler...")
                self.stop_event.set()
                self.thread.join(timeout=5)
                logger.info("Daily Scheduler stopped.")
                return True
            return False

    def _scheduler_loop(self):
        last_run_date = None
        
        while not self.stop_event.is_set():
            try:
                config = self.load_config()
                if not config.get("enabled", True):
                    # Check again in 1 minute
                    for _ in range(60):
                        if self.stop_event.is_set():
                            break
                        time.sleep(1)
                    continue

                schedule_time_str = config.get("time", "02:00")
                num_workers = config.get("num_workers", 4)
                inactive_only = config.get("inactive_only", False)

                now = datetime.now()
                current_time_str = now.strftime("%H:%M")
                current_date_str = now.strftime("%Y-%m-%d")

                # If scheduled time matches and we haven't run today
                if current_time_str == schedule_time_str and last_run_date != current_date_str:
                    logger.info(f"Triggering scheduled daily sync job for {current_date_str} at {schedule_time_str}...")
                    
                    orchestrator = ExtractionOrchestrator()
                    status = orchestrator.get_status()
                    
                    # Ensure orchestrator is not already running a manual job
                    if status.get("state") == "IDLE":
                        # We use reuse_bulk=False to fetch a fresh list of codes from ANVISA
                        # We set auto_confirm=True to bypass blocking web UI manual approvals
                        success, msg = orchestrator.start(
                            reuse_bulk=False,
                            num_workers=num_workers,
                            inactive_only=inactive_only,
                            auto_confirm=True
                        )
                        if success:
                            logger.info(f"Daily sync job started successfully: {msg}")
                            last_run_date = current_date_str
                        else:
                            logger.error(f"Failed to start daily sync job: {msg}")
                    else:
                        logger.warning(f"Orchestrator is currently active ({status.get('state')}). Skipping scheduled run.")
                        # Mark as run for today to avoid continuous warnings
                        last_run_date = current_date_str

                # Sleep 30 seconds (interruptible)
                for _ in range(300):
                    if self.stop_event.is_set():
                        break
                    time.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                time.sleep(10)
