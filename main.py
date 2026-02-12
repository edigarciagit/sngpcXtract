import sys
import argparse
from app.api.server import run_server
from app.services.scraper_single import SingleScraper
from app.services.scraper_bulk import BulkScraper

def main():
    parser = argparse.ArgumentParser(description="SNGPC Xtract CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Server Command
    subparsers.add_parser("server", help="Run the Web App Server")

    # Scrape Single Command
    scrape_parser = subparsers.add_parser("scrape", help="Scrape a single product by code")
    scrape_parser.add_argument("code", help="Product Code (e.g., 832670)")

    # Bulk Scrape Command
    subparsers.add_parser("bulk", help="Run bulk scraper")

    args = parser.parse_args()

    if args.command == "server":
        run_server()
    elif args.command == "scrape":
        scraper = SingleScraper()
        scraper.scrape(args.code)
    elif args.command == "bulk":
        scraper = BulkScraper()
        scraper.run()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
