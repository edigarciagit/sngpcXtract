import sys
import json
from app.services.scraper_single import SingleScraper
from app.core.driver import WebDriverFactory

def main():
    driver = WebDriverFactory.create_driver(headless=True)
    try:
        scraper = SingleScraper()
        print("Priming driver...")
        driver.get("https://consultas.anvisa.gov.br/")
        import time; time.sleep(5)
        print("Fetching code 45...")
        res = scraper.scrape(45, driver=driver)
        with open("test_45.json", "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2, ensure_ascii=False)
        print("Done. Saved to test_45.json")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
