import os
import json
from typing import List, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor, wait
import requests
import sys
from apify_client import ApifyClient
from dotenv import load_dotenv, dotenv_values
import re
from urllib.parse import quote_plus
import html
from pathlib import Path

# Deterministic env loading: support both repo-root .env and backend/.env
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[3]
ROOT_ENV_PATH = PROJECT_ROOT / ".env"
BACKEND_ENV_PATH = PROJECT_ROOT / "backend" / ".env"

if ROOT_ENV_PATH.exists():
    load_dotenv(dotenv_path=ROOT_ENV_PATH, override=False)
if BACKEND_ENV_PATH.exists():
    load_dotenv(dotenv_path=BACKEND_ENV_PATH, override=False)

class ApifyJobScraper:
    """Scrape job listings from multiple platforms using Apify API"""
    
    def __init__(self):
        self._root_env = dotenv_values(ROOT_ENV_PATH) if ROOT_ENV_PATH.exists() else {}
        self._backend_env = dotenv_values(BACKEND_ENV_PATH) if BACKEND_ENV_PATH.exists() else {}

        self.default_tokens = self._build_token_pool(
            *self._resolve_values('APIFY_API_TOKENS', 'APIFY_API_TOKEN'),
        )
        if not self.default_tokens:
            raise ValueError(
                "APIFY token not configured. Set APIFY_API_TOKEN (or APIFY_API_TOKENS) in backend/.env or .env."
            )

        self.linkedin_tokens = self._build_token_pool(
            *self._resolve_values('LINKEDIN_APIFY_API_TOKEN', 'APIFY_API_TOKENS', 'APIFY_API_TOKEN'),
        )
        self.naukri_tokens = self._build_token_pool(
            *self._resolve_values('NAUKRI_APIFY_API_TOKEN', 'APIFY_API_TOKENS', 'APIFY_API_TOKEN'),
        )
        self.internshala_tokens = self._build_token_pool(
            *self._resolve_values('INTERNSHALA_APIFY_API_TOKEN', 'APIFY_API_TOKENS', 'APIFY_API_TOKEN'),
        )
        self._clients: Dict[str, ApifyClient] = {}
        self.actor_timeout_secs = self._resolve_int_value("APIFY_ACTOR_TIMEOUT_SECONDS", 35)
        self.platform_timeout_secs = self._resolve_int_value("APIFY_PLATFORM_TIMEOUT_SECONDS", 45)
        
        # Apify Actor IDs — loaded from environment variables
        self.linkedin_actor_id = self._resolve_value('LINKEDIN_ACTOR_ID') or 'bebity/linkedin-jobs-scraper'
        self.naukri_actor_id = self._resolve_value('NAUKRI_ACTOR_ID')
        self.internshala_actor_id = self._resolve_value('INTERNSHALA_ACTOR_ID')
        print(
            f"[ApifyConfig] Actors — LinkedIn: {self.linkedin_actor_id}, "
            f"Naukri: {self.naukri_actor_id or 'unset'}, Internshala: {self.internshala_actor_id or 'unset'} | "
            f"token pools: default={len(self.default_tokens)}, linkedin={len(self.linkedin_tokens)}, "
            f"naukri={len(self.naukri_tokens)}, internshala={len(self.internshala_tokens)}, "
            f"actor_timeout={self.actor_timeout_secs}s, platform_timeout={self.platform_timeout_secs}s",
            flush=True,
        )

    @staticmethod
    def _normalize_http_url(value) -> str:
        """Normalize URL-like values to absolute HTTP(S) URLs."""
        if value is None:
            return ""

        if isinstance(value, dict):
            for key in ("url", "link", "href", "applyUrl", "jobUrl"):
                if key in value:
                    nested = ApifyJobScraper._normalize_http_url(value.get(key))
                    if nested:
                        return nested
            return ""

        if isinstance(value, list):
            for item in value:
                nested = ApifyJobScraper._normalize_http_url(item)
                if nested:
                    return nested
            return ""

        url = html.unescape(str(value).strip())
        # Some actor outputs include malformed "amp;" fragments in query strings.
        url = url.replace("?amp;", "?").replace("&amp;", "&").replace("amp;", "")
        if not url:
            return ""

        if url.startswith("http://") or url.startswith("https://"):
            return url
        if url.startswith("//"):
            return f"https:{url}"
        if url.startswith("www."):
            return f"https://{url}"
        return ""

    @staticmethod
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

    @staticmethod
    def _is_apify_limit_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return "monthly usage hard limit exceeded" in message or "usage hard limit exceeded" in message

    @staticmethod
    def _split_tokens(raw_value: str) -> List[str]:
        if not raw_value:
            return []
        return [token.strip() for token in re.split(r"[,\n;]+", str(raw_value)) if token.strip()]

    def _resolve_values(self, *keys: str) -> List[str]:
        values: List[str] = []
        # Prefer repository env files over inherited shell env
        # so local .env updates take effect without shell cleanup.
        sources = (self._backend_env, self._root_env, os.environ)
        for key in keys:
            for source in sources:
                raw = source.get(key)
                if raw is None:
                    continue
                text = str(raw).strip()
                if text:
                    values.append(text)
        return values

    def _resolve_value(self, key: str) -> str:
        values = self._resolve_values(key)
        return values[0] if values else ""

    def _resolve_int_value(self, key: str, default: int) -> int:
        raw = self._resolve_value(key)
        if not raw:
            return default
        try:
            value = int(raw)
            return value if value > 0 else default
        except (TypeError, ValueError):
            return default

    @classmethod
    def _build_token_pool(cls, *raw_values: str) -> List[str]:
        seen = set()
        tokens: List[str] = []
        for raw in raw_values:
            for token in cls._split_tokens(raw):
                if token not in seen:
                    seen.add(token)
                    tokens.append(token)
        return tokens

    def _get_client(self, token: str) -> ApifyClient:
        if token not in self._clients:
            self._clients[token] = ApifyClient(token)
        return self._clients[token]

    def _call_actor_with_fallback(
        self,
        actor_id: str,
        run_input: Dict,
        token_pool: List[str],
        platform_name: str,
        timeout_secs: int = 90,
    ) -> Tuple[Dict, ApifyClient]:
        if not token_pool:
            raise ValueError(f"{platform_name} token pool is empty")

        last_error = None
        for idx, token in enumerate(token_pool):
            client = self._get_client(token)
            try:
                run = client.actor(actor_id).call(run_input=run_input, timeout_secs=timeout_secs)
                if idx > 0:
                    print(f"[{platform_name}] Recovered using fallback token #{idx + 1}", flush=True)
                return run, client
            except Exception as e:
                last_error = e
                is_limit = self._is_apify_limit_error(e)
                has_next = idx < len(token_pool) - 1
                if is_limit and has_next:
                    print(f"[{platform_name}] Token #{idx + 1} quota exceeded, rotating token...", flush=True)
                    continue
                if has_next and not is_limit:
                    print(f"[{platform_name}] Token #{idx + 1} failed ({e}), trying next token...", flush=True)
                    continue
                raise
        if last_error:
            raise last_error
        raise RuntimeError(f"[{platform_name}] Actor call failed")

    @staticmethod
    def _build_platform_search_url(platform: str, title: str, location: str = "") -> str:
        """Build platform-specific search URL fallback."""
        platform_name = (platform or "").strip().lower()
        safe_title = (title or "software engineer").strip()
        safe_location = (location or "India").strip()
        title_q = quote_plus(safe_title)
        location_q = quote_plus(safe_location)
        title_slug = re.sub(r"[^a-z0-9]+", "-", safe_title.lower()).strip("-") or "software-engineer"
        location_slug = re.sub(r"[^a-z0-9]+", "-", safe_location.lower()).strip("-") or "india"

        if platform_name == "linkedin":
            return f"https://www.linkedin.com/jobs/search/?keywords={title_q}&location={location_q}"
        if platform_name == "naukri":
            return f"https://www.naukri.com/{title_slug}-jobs-in-{location_slug}"
        if platform_name == "internshala":
            return f"https://internshala.com/internships/keywords-{title_q}/"
        return f"https://www.google.com/search?q={title_q}+jobs+{location_q}"

    def _extract_item_url(self, item: Dict, candidate_keys: List[str], platform: str, title: str, location: str = "") -> str:
        """Extract URL from a scraped item using multiple schema variants."""
        for key in candidate_keys:
            if key in item:
                raw_value = item.get(key)
                normalized = self._normalize_http_url(raw_value)
                if normalized:
                    return normalized
                # Handle platform-relative URLs
                if isinstance(raw_value, str):
                    raw_text = html.unescape(raw_value.strip())
                    if raw_text.startswith("/"):
                        if platform == "linkedin":
                            return f"https://www.linkedin.com{raw_text}"
                        if platform == "naukri":
                            return f"https://www.naukri.com{raw_text}"
                        if platform == "internshala":
                            return f"https://internshala.com{raw_text}"

        # Some actors keep links in nested metadata structures.
        for nested_key in ("job", "jobData", "meta", "metadata", "details"):
            nested_value = item.get(nested_key)
            normalized = self._normalize_http_url(nested_value)
            if normalized:
                return normalized

        return self._build_platform_search_url(platform, title, location)
    
    def search_linkedin_jobs(self, skills: List[str], location: str = "") -> List[Dict]:
        """Search for jobs on LinkedIn using Apify real actor"""
        jobs = []
        safe_location = self._sanitize_location(location, default="India")
        try:
            # Convert skills to search query
            search_query = " ".join(skills[:3])  # Use top 3 skills
            
            # LinkedIn Job Search Actor - using bebity/linkedin-jobs-scraper
            run_input = {
                "keyword": search_query,
                "location": safe_location,
                "rows": 100,
                "maxItems": 100,
            }
            
            print(f"[LinkedIn] Searching for: {search_query} in {safe_location}", flush=True)
            print(f"[LinkedIn] Input parameters: {run_input}", flush=True)
            
            try:
                # Call the real LinkedIn actor (cap at 90 s so we don't block forever)
                run, client = self._call_actor_with_fallback(
                    actor_id=self.linkedin_actor_id,
                    run_input=run_input,
                    token_pool=self.linkedin_tokens or self.default_tokens,
                    platform_name="LinkedIn",
                    timeout_secs=self.actor_timeout_secs,
                )
                print(f"[LinkedIn] Run completed with ID: {run.get('id')}", flush=True)
                print(f"[LinkedIn] Run status: {run.get('status')}", flush=True)
                
                # Get results from the dataset
                dataset_id = run.get('defaultDatasetId')
                print(f"[LinkedIn] Dataset ID: {dataset_id}", flush=True)
                
                if dataset_id:
                    dataset = client.dataset(dataset_id)
                    items_response = dataset.list_items()
                    print(f"[LinkedIn] Total items in dataset: {len(list(items_response.items))}", flush=True)
                    
                    # Restart iterator
                    items_response = dataset.list_items()
                    for item in items_response.items:
                        print(f"[LinkedIn] Processing item: {item.get('jobTitle', item.get('title', 'N/A'))}", flush=True)

                        title = item.get('jobTitle') or item.get('title') or item.get('positionName', '')
                        link = self._extract_item_url(
                            item=item,
                            candidate_keys=[
                                'link', 'url', 'jobLink', 'URL', 'linkedinUrl', 'applyUrl',
                                'jobUrl', 'externalApplyLink', 'applyLink', 'href',
                                'job_url', 'apply_url', 'job_link', 'apply_link'
                            ],
                            platform='linkedin',
                            title=title,
                            location=safe_location,
                        )

                        # company can be a dict {name, link, logo} or a plain string
                        company_raw = item.get('companyName') or item.get('company', '')
                        company = company_raw.get('name', '') if isinstance(company_raw, dict) else (company_raw or '')

                        job_data = {
                            'title': title,
                            'company': company,
                            'location': item.get('location') or item.get('jobLocation', ''),
                            'description': item.get('description') or item.get('jobDescription') or '',
                            'link': link,
                            'platform': 'LinkedIn',
                            'salary': item.get('salary') or item.get('salaryRange') or 'Not specified',
                            'posted_date': item.get('publishedAt') or item.get('postedDate') or item.get('postedOn', ''),
                            'deadline': (item.get('expiresAt') or item.get('closingDate') or
                                         item.get('applicationDeadline') or item.get('validThrough') or ''),
                            'applicants': item.get('applicationsCount') or item.get('applicants', 'N/A')
                        }
                        
                        if job_data['title']:  # Only add if title exists
                            print(f"[LinkedIn] Added job: {job_data['title']} with link: {link}", flush=True)
                            jobs.append(job_data)
                    
                    print(f"[LinkedIn] Final count: Found {len(jobs)} jobs", flush=True)
                else:
                    print("[LinkedIn] No dataset returned from actor", flush=True)
                    
            except Exception as e:
                print(f"[LinkedIn] Actor execution error: {e}", flush=True)
                print(f"[LinkedIn] Error type: {type(e).__name__}", flush=True)
                if not self._is_apify_limit_error(e):
                    import traceback
                    traceback.print_exc()
        
        except Exception as e:
            print(f"[LinkedIn] Error searching jobs: {e}", flush=True)
            if not self._is_apify_limit_error(e):
                import traceback
                traceback.print_exc()
        
        return jobs
    
    def set_actor_ids(self, linkedin_id: str = None, naukri_id: str = None, internshala_id: str = None):
        """Set Apify actor IDs for job scraping"""
        if linkedin_id:
            self.linkedin_actor_id = linkedin_id
        if naukri_id:
            self.naukri_actor_id = naukri_id
        if internshala_id:
            self.internshala_actor_id = internshala_id
        print(f"[Actors] Updated - LinkedIn: {bool(self.linkedin_actor_id)}, Naukri: {bool(self.naukri_actor_id)}, Internshala: {bool(self.internshala_actor_id)}", flush=True)
    
    def search_naukri_jobs(self, skills: List[str], location: str = "") -> List[Dict]:
        """Search for jobs on Naukri.com using Apify"""
        jobs = []
        safe_location = self._sanitize_location(location, default="India")

        if not self.naukri_actor_id:
            print("[Naukri] Actor ID not configured - waiting for configuration", flush=True)
            return jobs

        try:
            search_query = " ".join(skills[:3])

            # Try common input param names used by Naukri scrapers
            run_input = {
                "keyword": search_query,
                "searchKeyword": search_query,
                "query": search_query,
                "location": safe_location,
                "locations": safe_location,
                "count": 100,
                "limit": 100,
                "maxResults": 100,
                "maxItems": 100,
                "rows": 100,
            }

            print(f"[Naukri] Searching for: {search_query} in {safe_location}", flush=True)

            try:
                run, client = self._call_actor_with_fallback(
                    actor_id=self.naukri_actor_id,
                    run_input=run_input,
                    token_pool=self.naukri_tokens or self.default_tokens,
                    platform_name="Naukri",
                    timeout_secs=self.actor_timeout_secs,
                )
                print(f"[Naukri] Run completed with ID: {run.get('id')}", flush=True)

                dataset_id = run.get('defaultDatasetId')
                if dataset_id:
                    dataset = client.dataset(dataset_id)
                    items_response = dataset.list_items()
                    items = list(items_response.items)

                    # Debug: print all field names from first item so we know the schema
                    if items:
                        print(f"[Naukri] Available fields: {list(items[0].keys())}", flush=True)

                    for item in items:
                        company_raw = item.get('companyName') or item.get('company', '')
                        company = company_raw.get('name', '') if isinstance(company_raw, dict) else (company_raw or '')

                        title = item.get('jobTitle') or item.get('title') or item.get('role', '')
                        link = self._extract_item_url(
                            item=item,
                            candidate_keys=[
                                'jobUrl', 'url', 'jobLink', 'link', 'applyLink', 'jobHref',
                                'applyUrl', 'jobDetailUrl', 'detailsUrl', 'redirectUrl',
                                'job_url', 'apply_url', 'job_link', 'apply_link', 'details_url', 'redirect_url'
                            ],
                            platform='naukri',
                            title=title,
                            location=safe_location,
                        )

                        job_data = {
                            'title': title,
                            'company': company,
                            'location': item.get('location') or item.get('jobLocation', ''),
                            'description': item.get('description') or item.get('jobDescription', ''),
                            'link': link,
                            'platform': 'Naukri',
                            'salary': item.get('salary') or item.get('salaryRange') or item.get('ctc', 'Not specified'),
                            'experience': item.get('experience') or item.get('experienceRange', ''),
                            'posted_date': item.get('postedDate') or item.get('createdOn', ''),
                            'deadline': (item.get('expiresAt') or item.get('closingDate') or
                                         item.get('applicationDeadline') or ''),
                            'applicants': item.get('applicationsCount') or item.get('applicants', 'N/A'),
                        }
                        if job_data['title']:
                            print(f"[Naukri] Added job: {job_data['title']} | link: {link}", flush=True)
                            jobs.append(job_data)

                    print(f"[Naukri] Found {len(jobs)} jobs", flush=True)

            except Exception as e:
                print(f"[Naukri] Actor execution error: {e}", flush=True)
                if not self._is_apify_limit_error(e):
                    import traceback; traceback.print_exc()

        except Exception as e:
            print(f"[Naukri] Error searching jobs: {e}", flush=True)
            if not self._is_apify_limit_error(e):
                import traceback; traceback.print_exc()

        return jobs
    
    def search_internshala_jobs(self, skills: List[str], is_internship: bool = True) -> List[Dict]:
        """Search for internships and jobs on Internshala using Apify"""
        jobs = []

        if not self.internshala_actor_id:
            print("[Internshala] Actor ID not configured - waiting for configuration", flush=True)
            return jobs

        try:
            search_query = " ".join(skills[:3])

            # Try common input param names used by Internshala scrapers
            run_input = {
                "keyword": search_query,
                "searchKeyword": search_query,
                "query": search_query,
                "category": search_query,
                "count": 100,
                "limit": 100,
                "maxResults": 100,
                "maxItems": 100,
                "rows": 100,
            }

            print(f"[Internshala] Searching for: {search_query}", flush=True)

            try:
                run, client = self._call_actor_with_fallback(
                    actor_id=self.internshala_actor_id,
                    run_input=run_input,
                    token_pool=self.internshala_tokens or self.default_tokens,
                    platform_name="Internshala",
                    timeout_secs=self.actor_timeout_secs,
                )
                print(f"[Internshala] Run completed with ID: {run.get('id')}", flush=True)

                dataset_id = run.get('defaultDatasetId')
                if dataset_id:
                    dataset = client.dataset(dataset_id)
                    items_response = dataset.list_items()
                    items = list(items_response.items)

                    # Debug: print all field names from first item so we know the schema
                    if items:
                        print(f"[Internshala] Available fields: {list(items[0].keys())}", flush=True)

                    for item in items:
                        company_raw = item.get('companyName') or item.get('company', '')
                        company = company_raw.get('name', '') if isinstance(company_raw, dict) else (company_raw or '')

                        title = item.get('title') or item.get('jobTitle') or item.get('profile', '')
                        link = self._extract_item_url(
                            item=item,
                            candidate_keys=[
                                'url', 'URL', 'link', 'jobUrl', 'applyLink', 'applyUrl',
                                'internshipUrl', 'href', 'detailsUrl', 'internship_link',
                                'job_url', 'apply_url', 'internship_url', 'apply_link', 'details_url'
                            ],
                            platform='internshala',
                            title=title,
                            location='India',
                        )

                        job_data = {
                            'title': title,
                            'company': company,
                            'location': item.get('location') or item.get('jobLocation', ''),
                            'description': item.get('description') or item.get('aboutInternship', ''),
                            'link': link,
                            'platform': 'Internshala',
                            'salary': (item.get('stipend') or item.get('salary') or
                                       item.get('salaryRange') or item.get('ctc', 'Not specified')),
                            'duration': item.get('duration', ''),
                            'posted_date': item.get('postedDate') or item.get('startDate', ''),
                            'deadline': (item.get('lastDate') or item.get('applicationDeadline') or
                                         item.get('expiresAt') or item.get('closingDate') or ''),
                            'applicants': item.get('applicationsCount') or item.get('applicants', 'N/A'),
                        }
                        if job_data['title']:
                            print(f"[Internshala] Added job: {job_data['title']} | link: {link}", flush=True)
                            jobs.append(job_data)

                    print(f"[Internshala] Found {len(jobs)} jobs", flush=True)

            except Exception as e:
                print(f"[Internshala] Actor execution error: {e}", flush=True)
                if not self._is_apify_limit_error(e):
                    import traceback; traceback.print_exc()

        except Exception as e:
            print(f"[Internshala] Error searching jobs: {e}", flush=True)
            if not self._is_apify_limit_error(e):
                import traceback; traceback.print_exc()

        return jobs
    
    def search_all_platforms(self, skills: List[str], location: str = "") -> Dict[str, List[Dict]]:
        """Search for jobs on all platforms in parallel."""
        safe_location = self._sanitize_location(location, default="India")
        print(f"\n[Job Search] Starting parallel search — skills: {skills}, location: {safe_location}", flush=True)

        tasks = {
            'linkedin':    lambda: self.search_linkedin_jobs(skills, safe_location),
            'naukri':      lambda: self.search_naukri_jobs(skills, safe_location),
            'internshala': lambda: self.search_internshala_jobs(skills),
        }

        all_jobs = {'linkedin': [], 'naukri': [], 'internshala': []}

        # Run all platform scrapers simultaneously with bounded wall-clock timeout.
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {name: executor.submit(fn) for name, fn in tasks.items()}
            done, not_done = wait(futures.values(), timeout=self.platform_timeout_secs)

            future_to_name = {future: name for name, future in futures.items()}
            for future in done:
                name = future_to_name.get(future, "unknown")
                try:
                    all_jobs[name] = future.result()
                except Exception as e:
                    print(f"[Job Search] {name} scraper raised an exception: {e}", flush=True)

            for future in not_done:
                name = future_to_name.get(future, "unknown")
                future.cancel()
                print(
                    f"[Job Search] {name} scraper timed out after {self.platform_timeout_secs}s; using partial results",
                    flush=True,
                )

        total_jobs = sum(len(j) for j in all_jobs.values())
        print(f"[Job Search] Total jobs found: {total_jobs}", flush=True)
        print(f"[Job Search] Breakdown — LinkedIn: {len(all_jobs['linkedin'])}, "
              f"Naukri: {len(all_jobs['naukri'])}, Internshala: {len(all_jobs['internshala'])}", flush=True)

        return all_jobs
    
    def _get_mock_linkedin_jobs(self, query: str) -> List[Dict]:
        """Mock LinkedIn job data for testing"""
        return [
            {
                'title': f'{query} Developer',
                'company': 'Tech Company A',
                'location': 'San Francisco, CA',
                'description': f'We are looking for a talented {query} developer...',
                'link': 'https://linkedin.com/jobs/view/example',
                'platform': 'LinkedIn',
                'salary': '$120,000 - $150,000'
            },
            {
                'title': f'Senior {query} Engineer',
                'company': 'Tech Company B',
                'location': 'New York, NY',
                'description': f'Join our team as a senior {query} engineer...',
                'link': 'https://linkedin.com/jobs/view/example2',
                'platform': 'LinkedIn',
                'salary': '$150,000 - $180,000'
            }
        ]
    
    def _get_mock_naukri_jobs(self, query: str) -> List[Dict]:
        """Mock Naukri job data for testing"""
        return [
            {
                'title': f'{query} Developer',
                'company': 'Indian Tech Company A',
                'location': 'Bangalore, India',
                'description': f'Seeking {query} developer for growing startup...',
                'link': 'https://naukri.com/jobs/example',
                'platform': 'Naukri',
                'salary': '₹8,00,000 - ₹12,00,000'
            },
            {
                'title': f'{query} Engineer',
                'company': 'Indian Tech Company B',
                'location': 'Pune, India',
                'description': f'Full-time {query} engineer position...',
                'link': 'https://naukri.com/jobs/example2',
                'platform': 'Naukri',
                'salary': '₹6,00,000 - ₹10,00,000'
            }
        ]
    
    def _get_mock_internshala_jobs(self, query: str) -> List[Dict]:
        """Mock Internshala job data for testing"""
        return [
            {
                'title': f'{query} Intern',
                'company': 'Startup A',
                'location': 'Remote',
                'description': f'{query} internship opportunity...',
                'link': 'https://internshala.com/example',
                'platform': 'Internshala',
                'salary': '₹10,000 - ₹20,000/month',
                'duration': '3-6 months'
            },
            {
                'title': f'{query} Internship',
                'company': 'Startup B',
                'location': 'Mumbai, India',
                'description': f'Learn and grow with us as a {query} intern...',
                'link': 'https://internshala.com/example2',
                'platform': 'Internshala',
                'salary': '₹15,000/month',
                'duration': '2-3 months'
            }
        ]
