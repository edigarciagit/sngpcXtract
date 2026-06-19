import sys
import argparse
from app.api.server import run_server
from app.services.scraper_single import SingleScraper
from app.services.scraper_bulk import BulkScraper
from app.core.database import Database

def main():
    parser = argparse.ArgumentParser(description="SNGPC Xtract CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Server Command
    subparsers.add_parser("server", help="Run the Web App Server")

    # Scrape Single Command
    scrape_parser = subparsers.add_parser("scrape", help="Scrape a single product by code")
    scrape_parser.add_argument("code", help="Product Code (e.g., 832670)")

    # Bulk Scrape Command
    bulk_parser = subparsers.add_parser("bulk", help="Run bulk scraper")
    bulk_parser.add_argument("--inactive", action="store_true", help="Scrape only inactive registrations")

    # Cron Command
    cron_parser = subparsers.add_parser("cron", help="Run non-interactive sync job and output report")
    cron_parser.add_argument("--workers", type=int, default=4, help="Number of concurrent worker threads")
    cron_parser.add_argument("--inactive", action="store_true", help="Scrape only inactive registrations")

    args = parser.parse_args()

    if args.command == "server":
        run_server()
    elif args.command == "scrape":
        scraper = SingleScraper()
        data = scraper.scrape(args.code)
        if data:
            Database.init_db()
            Database.save_product(int(args.code), data)
            print(f"Product {args.code} scraped and saved directly to SQLite.")
        else:
            print(f"Failed to scrape product {args.code}.")
    elif args.command == "bulk":
        scraper = BulkScraper(inactive_only=args.inactive)
        scraper.run()
    elif args.command == "cron":
        from app.services.orchestrator import ExtractionOrchestrator
        from app.services.scheduler import DailyScheduler
        import time
        import json
        
        # Load config parameters as fallback
        scheduler = DailyScheduler()
        config = scheduler.load_config()
        num_workers = args.workers if args.workers != 4 else config.get("num_workers", 4)
        inactive_only = args.inactive if args.inactive else config.get("inactive_only", False)
        
        print(f"Starting non-interactive cron sync job (workers={num_workers}, inactive_only={inactive_only})...")
        orchestrator = ExtractionOrchestrator()
        
        # Start the pipeline with auto_confirm=True
        success, msg = orchestrator.start(
            reuse_bulk=False,
            num_workers=num_workers,
            inactive_only=inactive_only,
            auto_confirm=True
        )
        
        if not success:
            print(f"Failed to start sync: {msg}")
            sys.exit(1)
            
        print("Sync started. Awaiting execution completion...")
        # Poll status until completed, error or idle
        while True:
            time.sleep(5)
            status = orchestrator.get_status()
            state = status.get("state")
            message = status.get("message")
            percent = status.get("percent", 0)
            elapsed = status.get("elapsedTime", "00:00:00")
            
            print(f"[{elapsed}] State: {state} | {message} ({percent}%)")
            
            if state in ["COMPLETED", "ERROR", "IDLE"]:
                if state == "ERROR":
                    print(f"Sync failed with error: {message}")
                    sys.exit(1)
                elif state == "COMPLETED":
                    print("Sync completed successfully.")
                    
                    # Locate the latest report
                    import glob
                    import os
                    report_files = glob.glob(os.path.join("data", "reports", "sync_*.json"))
                    if report_files:
                        latest_report_file = max(report_files, key=os.path.getctime)
                        print(f"\nCompletion Report ({os.path.basename(latest_report_file)}):")
                        try:
                            with open(latest_report_file, 'r', encoding='utf-8') as rf:
                                rdata = json.load(rf)
                                print(f"  Duration: {rdata.get('duration')}")
                                print(f"  Total Bulk Codes: {rdata.get('total_bulk_codes')}")
                                print(f"  Successfully Scraped: {rdata.get('scraped_successfully')}")
                                print(f"  Failed: {rdata.get('scraped_failed')}")
                                print(f"  New Presentations Added: {rdata.get('new_presentations_count')}")
                                print(f"  Presentations Updated: {rdata.get('updated_presentations_count')}")
                        except Exception as re_err:
                            print(f"  Failed to read report details: {re_err}")
                    sys.exit(0)
                else:
                    print("Sync aborted.")
                    sys.exit(1)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
