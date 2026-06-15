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
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
