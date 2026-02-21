from ai_recommendation_service import AIRecommendationService

print("Testing job sources...")
jobs = AIRecommendationService.get_job_sources(use_apify=True, keywords=["python", "developer"], location="India")
print(jobs[:2])
