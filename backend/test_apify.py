from apify_jobs_service import fetch_naukri_jobs, fetch_linkedin_jobs, create_naukri_search_jobs
print("testing linkedin")
li = fetch_linkedin_jobs(["react"])
print(li)
print("testing naukri")
n = fetch_naukri_jobs(["react"])
print(n)
