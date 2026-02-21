from apify.app.utils.apify_client import ApifyJobScraper
try:
    s = ApifyJobScraper()
    print("Scraper loaded.")
except Exception as e:
    print(e)
