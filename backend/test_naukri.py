from apify.app.utils.apify_client import ApifyJobScraper
scraper = ApifyJobScraper()
print(scraper.search_naukri_jobs(["react developer"]))
