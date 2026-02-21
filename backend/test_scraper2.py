import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from apify.app.utils.apify_client import ApifyJobScraper

print("Testing linkedin...")
scraper = ApifyJobScraper()
jobs = scraper.search_linkedin_jobs(["python developer"])
print(jobs)
