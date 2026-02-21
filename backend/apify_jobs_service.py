import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import os
from typing import List, Dict, Any
import re
from urllib.parse import quote_plus
import json
import time

from apify_client import ApifyClient


def _get_client(naukri: bool = False) -> ApifyClient:
    """Get Apify client. Use Naukri-specific token if available, otherwise use main token."""
    if naukri:
        # Try Naukri-specific token first
        token = os.getenv("NAUKRI_APIFY_API_TOKEN") or os.getenv("APIFY_API_TOKEN")
    else:
        token = os.getenv("APIFY_API_TOKEN")
    
    if not token:
        raise RuntimeError("APIFY_API_TOKEN not set")
    return ApifyClient(token)


def _normalize_external_url(value: Any) -> str:
    """Normalize any URL-like value to absolute HTTP(S), else return empty string."""
    if value is None:
        return ""

    if isinstance(value, dict):
        for key in ("url", "link", "href", "applyUrl", "jobUrl", "application_url"):
            if key in value:
                normalized = _normalize_external_url(value.get(key))
                if normalized:
                    return normalized
        return ""

    if isinstance(value, list):
        for item in value:
            normalized = _normalize_external_url(item)
            if normalized:
                return normalized
        return ""

    text = str(value).strip()
    text = text.replace("?amp;", "?").replace("&amp;", "&").replace("amp;", "")
    if not text:
        return ""
    if text.startswith("http://") or text.startswith("https://"):
        return text
    if text.startswith("//"):
        return f"https:{text}"
    if text.startswith("www."):
        return f"https://{text}"
    return ""


def _sanitize_location(location: str, default: str = "India") -> str:
    cleaned = re.sub(r"\s+", " ", str(location or "")).strip(" ,;")
    if not cleaned:
        return default
    if len(cleaned) > 80:
        return default
    lowered = cleaned.lower()
    if any(term in lowered for term in ("cgpa", "batch", "board", "university", "hsc", "ssc", "implemented", "laravel")):
        return default
    if "http://" in lowered or "https://" in lowered:
        return default
    if len([t for t in re.split(r"[\s,]+", cleaned) if t]) > 8:
        return default
    return cleaned


def _cache_path() -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cache_dir = os.path.join(base_dir, "instance")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, "apify_jobs_cache.json")


def _normalize_keywords_for_cache(keywords: List[str]) -> List[str]:
    cleaned = []
    seen = set()
    for keyword in keywords or []:
        token = re.sub(r"\s+", " ", str(keyword or "")).strip().lower()
        if not token or token in seen:
            continue
        seen.add(token)
        cleaned.append(token)
    return cleaned


def _build_cache_key(keywords: List[str], location: str) -> str:
    safe_location = _sanitize_location(location, default="India").lower()
    normalized_keywords = _normalize_keywords_for_cache(keywords)
    payload = {
        "location": safe_location,
        "keywords": normalized_keywords[:16],
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return serialized


def _load_cached_jobs(cache_key: str = "", max_age_seconds: int = 24 * 3600) -> List[Dict[str, Any]]:
    path = _cache_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)

        # Backward compatibility: legacy single-entry cache shape.
        if isinstance(payload, dict) and isinstance(payload.get("jobs"), list):
            created_at = float(payload.get("created_at", 0))
            jobs = payload.get("jobs", [])
            if max_age_seconds > 0 and created_at > 0:
                age = time.time() - created_at
                if age > max_age_seconds:
                    return []
            return jobs

        if not isinstance(payload, dict):
            return []

        entries = payload.get("entries", {})
        if not isinstance(entries, dict):
            return []

        if cache_key and cache_key in entries:
            entry = entries.get(cache_key, {})
            jobs = entry.get("jobs", []) if isinstance(entry, dict) else []
            created_at = float((entry or {}).get("created_at", 0)) if isinstance(entry, dict) else 0.0
            if not isinstance(jobs, list):
                return []
            if max_age_seconds > 0 and created_at > 0 and (time.time() - created_at) > max_age_seconds:
                return []
            return jobs

        # If no key provided, return the latest available entry.
        latest_key = payload.get("latest_key", "")
        if latest_key and latest_key in entries:
            latest = entries.get(latest_key, {})
            jobs = latest.get("jobs", []) if isinstance(latest, dict) else []
            created_at = float((latest or {}).get("created_at", 0)) if isinstance(latest, dict) else 0.0
            if not isinstance(jobs, list):
                return []
            if max_age_seconds > 0 and created_at > 0 and (time.time() - created_at) > max_age_seconds:
                return []
            return jobs
        return []
    except Exception as exc:
        print(f"⚠️ Failed to load Apify cache: {exc}")
        return []


def _save_cached_jobs(jobs: List[Dict[str, Any]], cache_key: str, keywords: List[str], location: str) -> None:
    if not jobs:
        return
    path = _cache_path()
    try:
        payload: Dict[str, Any] = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        if not isinstance(payload, dict):
            payload = {}

        entries = payload.get("entries", {})
        if not isinstance(entries, dict):
            entries = {}

        entries[cache_key] = {
            "created_at": time.time(),
            "jobs": jobs,
            "keywords": _normalize_keywords_for_cache(keywords),
            "location": _sanitize_location(location, default="India"),
        }

        payload = {
            "version": 2,
            "latest_key": cache_key,
            "entries": entries,
        }

        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
    except Exception as exc:
        print(f"⚠️ Failed to save Apify cache: {exc}")


def _canonical_platform(source: Any) -> str:
    source_text = str(source or "").strip().lower()
    if "linkedin" in source_text:
        return "linkedin"
    if "naukri" in source_text:
        return "naukri"
    if "internshala" in source_text:
        return "internshala"
    return source_text or "external"


def _build_platform_search_url(platform: str, title: str, location: str) -> str:
    safe_title = (title or "software engineer").strip()
    safe_location = _sanitize_location(location, default="India")
    title_q = quote_plus(safe_title)
    location_q = quote_plus(safe_location)
    title_slug = re.sub(r"[^a-z0-9]+", "-", safe_title.lower()).strip("-") or "software-engineer"
    location_slug = re.sub(r"[^a-z0-9]+", "-", safe_location.lower()).strip("-") or "india"

    if platform == "linkedin":
        return f"https://www.linkedin.com/jobs/search/?keywords={title_q}&location={location_q}"
    if platform == "naukri":
        return f"https://www.naukri.com/{title_slug}-jobs-in-{location_slug}"
    if platform == "internshala":
        return f"https://internshala.com/internships/keywords-{title_q}/"
    return f"https://www.google.com/search?q={title_q}+jobs+{location_q}"


def _extract_best_job_url(job: Dict[str, Any], platform: str, default_location: str) -> str:
    candidates = [
        job.get("link"),
        job.get("url"),
        job.get("jobUrl"),
        job.get("applyUrl"),
        job.get("applyLink"),
        job.get("job_url"),
        job.get("apply_url"),
        job.get("job_link"),
        job.get("apply_link"),
        job.get("application_url"),
        job.get("href"),
        job.get("jobHref"),
    ]
    for candidate in candidates:
        normalized = _normalize_external_url(candidate)
        if normalized:
            return normalized

    return _build_platform_search_url(
        platform=platform,
        title=str(job.get("title") or "software engineer"),
        location=str(job.get("location") or default_location or "India"),
    )


def fetch_linkedin_jobs(keywords: List[str], location: str = "India", rows: int = 50) -> List[Dict[str, Any]]:
    """Fetch jobs from Apify LinkedIn Jobs Scraper actor (real LinkedIn postings)."""
    if not keywords:
        return []
    try:
        client = _get_client()
        # Use first keyword as primary search term
        title_query = keywords[0] if keywords else "software engineer"

        run_input = {
            "title": title_query,
            "location": location,
            "rows": rows,
            "proxy": {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"]},
        }

        print(f"📡 Calling LinkedIn scraper with: {title_query} in {location}")
        run = client.actor("BHzefUZlZRKWxkTck").call(run_input=run_input)

        results: List[Dict[str, Any]] = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            # Ensure we have a valid URL
            job_url = item.get("jobUrl") or item.get("url") or item.get("link")
            if not job_url or not job_url.startswith("http"):
                # Skip jobs without valid URLs
                continue

            # Extract description (could contain skills)
            description = (
                item.get("description")
                or item.get("summary")
                or item.get("jobDescription")
                or ""
            )

            results.append(
                {
                    "title": item.get("title") or "Job Title",
                    "company_name": item.get("companyName") or item.get("company") or "Company",
                    "location": item.get("location") or location,
                    "url": job_url,  # REAL LinkedIn job URL
                    "description": description,  # Full description for skill extraction
                    "source": "linkedin",
                    "posted_at": item.get("postedAt") or item.get("datePosted"),
                    "required_skills": [],  # Will be extracted from description
                }
            )

        print(f"✅ Fetched {len(results)} LinkedIn jobs")
        return results
    except Exception as e:
        print(f"❌ LinkedIn fetch error: {e}")
        import traceback
        traceback.print_exc()
        return []


def fetch_naukri_jobs(keywords: List[str], location: str = "India", rows: int = 50) -> List[Dict[str, Any]]:
    """Fetch jobs from Apify Naukri Jobs Scraper actor (real Naukri postings).

    This uses the Naukri scraper actor and maps its dataset items into our internal 
    job representation so that Naukri jobs look just like LinkedIn cards in the frontend.
    """
    if not keywords:
        return []
    try:
        # Use Naukri-specific client (will use NAUKRI_APIFY_API_TOKEN if set)
        client = _get_client(naukri=True)
        
        # Use first keyword as primary search term (similar to LinkedIn)
        title_query = keywords[0] if keywords else "software engineer"
        
        # Try different input formats based on common Naukri actor patterns
        # Some actors use "searchQuery", others use "title" or "keyword"
        run_input = {
            "searchQuery": title_query,
            "location": location,
            "maxItems": rows,
            "proxy": {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"]},
        }
        
        # Alternative input format (try if first fails)
        alt_run_input = {
            "title": title_query,
            "location": location,
            "rows": rows,
            "proxy": {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"]},
        }

        print(f"📡 Calling Naukri scraper with: {title_query} in {location}")
        
        # Try the primary actor ID first, then fallback to alternative
        try:
            # Common Naukri actor IDs - try the most common one first
            run = client.actor("wsrn5gy5C4EDeYCcD").call(run_input=run_input)
        except Exception as e1:
            print(f"⚠️ Primary Naukri actor failed, trying alternative format: {e1}")
            try:
                run = client.actor("wsrn5gy5C4EDeYCcD").call(run_input=alt_run_input)
            except Exception as e2:
                print(f"❌ Naukri actor call failed: {e2}")
                raise

        results: List[Dict[str, Any]] = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            # Try multiple possible fields for URL depending on actor output
            job_url = (
                item.get("jobUrl")
                or item.get("url")
                or item.get("applyUrl")
                or item.get("jdURL")
            )
            if not job_url or not job_url.startswith("http"):
                # Skip jobs without valid URLs
                continue

            # Best-effort mapping of fields – adjust if your actor schema differs
            title = (
                item.get("title")
                or item.get("jobTitle")
                or item.get("role")
                or "Job Title"
            )
            company = (
                item.get("companyName")
                or item.get("company")
                or item.get("employer")
                or "Company"
            )
            naukri_location = (
                item.get("location")
                or item.get("place")
                or item.get("city")
                or location
            )
            description = (
                item.get("description")
                or item.get("jobDescription")
                or item.get("summary")
                or ""
            )

            results.append(
                {
                    "title": title,
                    "company_name": company,
                    "location": naukri_location,
                    "url": job_url,  # REAL Naukri job URL
                    "description": description,
                    "source": "naukri",
                    "posted_at": item.get("postedAt") or item.get("datePosted"),
                    "required_skills": [],  # Will be extracted from description
                }
            )

        print(f"✅ Fetched {len(results)} Naukri jobs")
        return results
    except Exception as e:
        print(f"❌ Naukri fetch error: {e}")
        import traceback
        traceback.print_exc()
        return []


def create_naukri_search_jobs(resume_skills: List[str], location: str = "India") -> List[Dict[str, Any]]:
    """
    Create direct Naukri search URLs based on resume skills.
    Instead of using API, redirects directly to Naukri search pages.
    Each skill gets its own search result with match percentage.
    """
    if not resume_skills:
        return []
    
    # Common job title patterns for skills
    job_title_patterns = {
        'python': 'Python Developer',
        'java': 'Java Developer',
        'javascript': 'JavaScript Developer',
        'react': 'React Developer',
        'node.js': 'Node.js Developer',
        'nodejs': 'Node.js Developer',
        'angular': 'Angular Developer',
        'vue': 'Vue.js Developer',
        'sql': 'SQL Developer',
        'mongodb': 'MongoDB Developer',
        'aws': 'AWS Developer',
        'docker': 'Docker Engineer',
        'kubernetes': 'Kubernetes Engineer',
        'machine learning': 'Machine Learning Engineer',
        'data science': 'Data Scientist',
        'android': 'Android Developer',
        'ios': 'iOS Developer',
        'flutter': 'Flutter Developer',
    }
    
    results = []
    seen_skills = set()
    
    # Create search jobs for top skills (max 10)
    for skill in resume_skills[:10]:
        skill_lower = skill.lower().strip()
        
        # Skip duplicates
        if skill_lower in seen_skills:
            continue
        seen_skills.add(skill_lower)
        
        # Get job title pattern or create one
        job_title = job_title_patterns.get(skill_lower, f"{skill.title()} Developer")
        
        # Create Naukri search URL
        # Format: https://www.naukri.com/{skill}-jobs
        skill_slug = skill_lower.replace(' ', '-').replace('.', '-').replace('+', '-')
        naukri_url = f"https://www.naukri.com/{skill_slug}-jobs"
        
        # Alternative: Use Naukri search API format
        # naukri_url = f"https://www.naukri.com/jobapi/v3/search?noOfResults=20&urlType=search_by_keyword&searchType=adv&keyword={skill_slug.replace('-', '+')}"
        
        # Create a "virtual" job entry for this skill search
        results.append({
            "title": job_title,
            "company_name": "Multiple Companies",  # Since it's a search, not a specific company
            "location": location,
            "url": naukri_url,  # Direct Naukri search URL
            "description": f"Search for {job_title} jobs on Naukri. Click to view all available positions matching your {skill} skills.",
            "source": "naukri_search",  # Mark as search, not API result
            "required_skills": [skill],  # The skill being searched
            "is_search": True,  # Flag to indicate this is a search redirect
            "match_score": 100,  # 100% match since it's based on your skill
            "match_reason": f"Perfect match! This search is based on your {skill} skill.",
        })
    
    print(f"✅ Created {len(results)} Naukri search redirects")
    return results


from apify.app.utils.apify_client import ApifyJobScraper

def fetch_jobs_from_apify(keywords: List[str], location: str = "India", resume_skills: List[str] = None) -> List[Dict[str, Any]]:
    """Aggregate jobs from LinkedIn, Naukri, and Internshala API (via ApifyJobScraper)."""
    location = _sanitize_location(location, default="India")
    print(f"🚀 Fetching jobs dynamically from Apify for: {keywords[:5]}")

    cache_key = _build_cache_key(keywords, location)
    fresh_cache_seconds = int(os.getenv("APIFY_CACHE_FRESH_SECONDS", "600"))
    fallback_cache_seconds = int(os.getenv("APIFY_CACHE_FALLBACK_SECONDS", str(24 * 3600)))

    # Fast path: return fresh cache immediately for identical query.
    fresh_cached_jobs = _load_cached_jobs(cache_key=cache_key, max_age_seconds=fresh_cache_seconds)
    if fresh_cached_jobs:
        print(f"⚡ Using fresh Apify cache for query: {len(fresh_cached_jobs)} jobs")
        return fresh_cached_jobs

    all_jobs: List[Dict[str, Any]] = []
    fallback_url_counts: Dict[str, int] = {"linkedin": 0, "naukri": 0, "internshala": 0, "external": 0}

    try:
        scraper = ApifyJobScraper()
        # ApifyJobScraper.search_all_platforms returns Dict[str, List[Dict]]
        scraped_data = scraper.search_all_platforms(keywords, location=location)
        
        # Flatten and map keys to match frontend expectations
        for platform_name, jobs_list in scraped_data.items():
            for job in jobs_list:
                source = _canonical_platform(job.get("platform", platform_name))
                direct_url = _normalize_external_url(
                    job.get("link")
                    or job.get("url")
                    or job.get("jobUrl")
                    or job.get("applyUrl")
                    or job.get("applyLink")
                    or job.get("job_url")
                    or job.get("apply_url")
                    or job.get("job_link")
                    or job.get("apply_link")
                    or job.get("application_url")
                    or job.get("href")
                    or job.get("jobHref")
                )
                url = direct_url or _extract_best_job_url(job, platform=source, default_location=location)
                if not direct_url:
                    fallback_url_counts[source if source in fallback_url_counts else "external"] += 1

                mapped_job = {
                    "title": job.get("title") or "Job Title",
                    "company_name": job.get("company") or "Company",
                    "location": job.get("location") or location,
                    "url": url,
                    "description": job.get("description", ""),
                    "source": source,
                    "posted_at": job.get("posted_date"),
                    "stipend": job.get("salary"),
                    "duration": job.get("duration"),
                    "required_skills": []
                }
                all_jobs.append(mapped_job)
                
    except Exception as e:
        print(f"⚠️ Apify dynamic fetch failed: {e}")
        import traceback
        traceback.print_exc()

    # De-duplicate with URL-first strategy to avoid collapsing distinct jobs
    # that share similar titles/companies.
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for job in all_jobs:
        normalized_url = _normalize_external_url(job.get("url"))
        if normalized_url:
            key = ("url", normalized_url.lower())
        else:
            key = (
                "meta",
                str(job.get("title", "")).strip().lower(),
                str(job.get("company_name", "")).strip().lower(),
                str(job.get("source", "")).strip().lower(),
            )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(job)

    print(f"🔗 Fallback URLs used: {fallback_url_counts}")
    print(f"✅ Total unique jobs: {len(deduped)} (Dynamic multi-platform via Apify)")
    if deduped:
        _save_cached_jobs(deduped, cache_key=cache_key, keywords=keywords, location=location)
        return deduped

    # If live fetch is empty (e.g., quota exhausted), use query cache as fallback.
    cached_jobs = _load_cached_jobs(cache_key=cache_key, max_age_seconds=fallback_cache_seconds)
    if cached_jobs:
        print(f"♻️ Using fallback Apify cache for query: {len(cached_jobs)}")
        return cached_jobs

    # Last fallback: use latest cached dataset if query-specific cache is unavailable.
    latest_cached_jobs = _load_cached_jobs(cache_key="", max_age_seconds=fallback_cache_seconds)
    if latest_cached_jobs:
        print(f"♻️ Using latest fallback Apify cache: {len(latest_cached_jobs)}")
        return latest_cached_jobs

    return deduped
