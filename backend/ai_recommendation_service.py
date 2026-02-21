"""
AI-Powered Job Recommendation Service
Combines resume extraction, LLM analysis, and job matching
"""

import os
from typing import Dict, List, Any, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import re
from urllib.parse import quote_plus

from resume_extraction_service import extract_resume_data
# Optional fallback-only extractor
try:
    from resume_extraction_service_free import extract_resume_data as extract_resume_data_free
except ImportError:
    extract_resume_data_free = None

from apify_jobs_service import fetch_jobs_from_apify, create_naukri_search_jobs
from Demoapp import run_model, rank_jobs_with_llm
from models import db, Opportunity, ExternalJob, OpportunitySkill, Skill
from skills_matching import SkillsMatchingService
import json


class AIRecommendationService:
    """Main service for AI-powered job recommendations"""

    _GENERIC_KEYWORD_STOPWORDS = {
        "job",
        "jobs",
        "role",
        "roles",
        "fresher",
        "entry",
        "entry level",
        "full time",
        "part time",
        "work from home",
        "remote",
        "onsite",
        "hybrid",
        "intern",
        "internship",
        "company",
        "management",
        "question",
        "mapping",
        "creation",
    }

    _KEYWORD_TOKEN_STOPWORDS = {
        "and",
        "or",
        "with",
        "for",
        "the",
        "a",
        "an",
        "to",
        "in",
        "on",
        "of",
        "at",
        "by",
        "from",
        "user",
        "users",
        "based",
    }

    _RESUME_NOISE_TERMS = {
        "implemented",
        "feedback",
        "rating",
        "mechanisms",
        "notifications",
        "authentication",
        "tokenbased",
        "laravel",
        "frontend",
        "typescript",
        "interactive",
        "responsive",
        "university",
        "bachelor",
        "technology",
        "batch",
        "cgpa",
        "board",
        "hsc",
        "ssc",
    }

    _LOCATION_NOISE_TERMS = {
        "implemented",
        "feedback",
        "rating",
        "mechanism",
        "notification",
        "authentication",
        "laravel",
        "typescript",
        "university",
        "bachelor",
        "batch",
        "cgpa",
        "hsc",
        "ssc",
        "skills",
        "project",
    }

    @staticmethod
    def sanitize_location(location: Any, default: str = "India") -> str:
        """Return a short, safe location string. Fallback to default for noisy resume text."""
        cleaned = re.sub(r"\s+", " ", str(location or "")).strip(" ,;")
        if not cleaned:
            return default
        if len(cleaned) > 80:
            return default
        if "http://" in cleaned.lower() or "https://" in cleaned.lower():
            return default
        lowered = cleaned.lower()
        if any(term in lowered for term in AIRecommendationService._LOCATION_NOISE_TERMS):
            return default

        tokens = [token for token in re.split(r"[\s,]+", lowered) if token]
        if len(tokens) > 8:
            return default
        return cleaned

    @staticmethod
    def _build_internal_student_url(job_id: Any) -> str:
        """Return canonical in-app student opportunity path."""
        try:
            parsed_id = int(job_id)
            if parsed_id > 0:
                return f"/student/opportunities/{parsed_id}"
        except (TypeError, ValueError):
            pass
        return "/student/opportunities"

    @staticmethod
    def _ensure_http_url(url: Any) -> str:
        """Normalize external URL to an absolute HTTP(S) URL or empty string."""
        if not isinstance(url, str):
            return ""
        value = url.strip()
        if not value:
            return ""
        if value.startswith("http://") or value.startswith("https://"):
            return value
        if value.startswith("//"):
            return f"https:{value}"
        if value.startswith("www."):
            return f"https://{value}"
        return ""

    @staticmethod
    def _infer_source(source: Any, url: str) -> str:
        """Infer source platform from explicit source field and URL."""
        source_value = str(source or "").strip().lower()
        lower_url = (url or "").lower()

        if source_value:
            if "linkedin" in source_value:
                return "linkedin"
            if "naukri" in source_value:
                return "naukri"
            if "internshala" in source_value:
                return "internshala"
            if source_value == "internal":
                return "internal"
            return source_value
        if "linkedin.com" in lower_url:
            return "linkedin"
        if "naukri.com" in lower_url:
            return "naukri"
        if "internshala.com" in lower_url:
            return "internshala"
        return "external"

    @staticmethod
    def _fallback_external_url(source: str, title: str, location: str) -> str:
        """Generate safe fallback external job search URL by platform."""
        location = AIRecommendationService.sanitize_location(location)
        safe_title = (title or "software engineer").strip()
        keyword = quote_plus(safe_title)
        loc = quote_plus((location or "India").strip())
        keyword_slug = re.sub(r"[^a-z0-9]+", "-", safe_title.lower()).strip("-") or "software-engineer"
        loc_slug = re.sub(r"[^a-z0-9]+", "-", (location or "India").lower()).strip("-") or "india"

        if source == "linkedin":
            return f"https://www.linkedin.com/jobs/search/?keywords={keyword}&location={loc}"
        if source in {"naukri", "naukri_search"}:
            return f"https://www.naukri.com/{keyword_slug}-jobs-in-{loc_slug}"
        if source == "internshala":
            return f"https://internshala.com/internships/keywords-{keyword}/"
        return f"https://www.google.com/search?q={keyword}+jobs+{loc}"

    @staticmethod
    def normalize_job_apply_target(job: Dict[str, Any], location: str = "India") -> Dict[str, Any]:
        """
        Normalize job source + URL so frontend navigation is reliable.
        - Internal jobs always point to /student/opportunities/:id
        - External jobs always point to absolute HTTP(S) URLs
        """
        normalized = dict(job or {})
        location = AIRecommendationService.sanitize_location(location)

        # Allow alternate URL keys from upstream services.
        raw_url = (
            normalized.get("url")
            or normalized.get("jobUrl")
            or normalized.get("application_url")
            or normalized.get("applyUrl")
            or ""
        )

        source = AIRecommendationService._infer_source(normalized.get("source"), str(raw_url))
        normalized["source"] = source

        if source == "internal":
            normalized["url"] = AIRecommendationService._build_internal_student_url(normalized.get("id"))
            return normalized

        external_url = AIRecommendationService._ensure_http_url(raw_url)
        if not external_url:
            external_url = AIRecommendationService._fallback_external_url(
                source=source,
                title=str(normalized.get("title", "")),
                location=location,
            )
        normalized["url"] = external_url
        return normalized

    @staticmethod
    def _build_external_search_fallback(keywords: List[str], location: str) -> List[Dict[str, Any]]:
        """
        Build external search entries when live Apify jobs are unavailable.
        This keeps apply actions on external platforms instead of internal routes.
        """
        location = AIRecommendationService.sanitize_location(location)
        search_terms = AIRecommendationService._prepare_search_keywords(
            keywords=keywords,
            fallback_keywords=["software engineer", "developer", "intern"],
            max_items=4,
        )
        results: List[Dict[str, Any]] = []

        for term in search_terms:
            title_term = term.title()
            results.extend([
                {
                    "title": f"{title_term} - LinkedIn Search",
                    "company_name": "LinkedIn",
                    "location": location,
                    "description": f"Search LinkedIn jobs for {title_term}",
                    "required_skills": [term],
                    "source": "linkedin",
                    "url": AIRecommendationService._fallback_external_url("linkedin", term, location),
                    "is_search": True,
                },
                {
                    "title": f"{title_term} - Naukri Search",
                    "company_name": "Naukri",
                    "location": location,
                    "description": f"Search Naukri jobs for {title_term}",
                    "required_skills": [term],
                    "source": "naukri",
                    "url": AIRecommendationService._fallback_external_url("naukri", term, location),
                    "is_search": True,
                },
                {
                    "title": f"{title_term} - Internshala Search",
                    "company_name": "Internshala",
                    "location": location,
                    "description": f"Search Internshala roles for {title_term}",
                    "required_skills": [term],
                    "source": "internshala",
                    "url": AIRecommendationService._fallback_external_url("internshala", term, location),
                    "is_search": True,
                },
            ])

        return [
            AIRecommendationService.normalize_job_apply_target(job, location=location)
            for job in results
        ]
    
    @staticmethod
    def extract_and_analyze_resume(file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Extract resume data with OCR + Gemini structured parsing.
        Falls back to local rule-based extraction and free LLM paths when needed.
        
        Returns:
            {
                "extracted_data": {...},  # Raw extraction
                "llm_analysis": {...},   # LLM model output (FREE)
                "keywords": [...],        # Extracted keywords
                "skills": [...],         # Extracted skills
                "experience_years": int,
                "tech_stack": [...]
            }
        """
        # Step 1: Extract structured data (Gemini + OCR path)
        try:
            extracted = extract_resume_data(file_bytes, filename)
        except Exception:
            # Step 1 fallback: free extractor if primary extraction fails
            if extract_resume_data_free:
                extracted = extract_resume_data_free(file_bytes, filename)
            else:
                raise

        # Step 2: Prefer llm_analysis generated during extraction.
        # If unavailable/incomplete, fallback to existing FREE model pipeline.
        llm_output = extracted.get("llm_analysis", {})
        if not isinstance(llm_output, dict):
            llm_output = {}

        resume_text = extracted.get("raw_text", "")
        if not llm_output or (
            not llm_output.get("cleaned_skills")
            and not llm_output.get("professional_summary")
        ):
            fallback_llm = run_model(resume_text)
            if isinstance(fallback_llm, dict):
                llm_output = {
                    **fallback_llm,
                    **llm_output,
                }

        # Step 3: Combine results into backward-compatible payload
        extracted_skills = extracted.get("skills", [])
        if not isinstance(extracted_skills, list):
            extracted_skills = []
        llm_skills = llm_output.get("cleaned_skills", [])
        if not isinstance(llm_skills, list):
            llm_skills = []

        extracted_keywords = extracted.get("keywords", [])
        if not isinstance(extracted_keywords, list):
            extracted_keywords = []

        extracted_tech_stack = extracted.get("tech_stack", [])
        if not isinstance(extracted_tech_stack, list):
            extracted_tech_stack = []

        extracted_roles = extracted.get("recommended_roles", [])
        if not isinstance(extracted_roles, list):
            extracted_roles = []

        extracted_missing = extracted.get("missing_skills", [])
        if not isinstance(extracted_missing, list):
            extracted_missing = []

        extracted_strengths = extracted.get("strengths", [])
        if not isinstance(extracted_strengths, list):
            extracted_strengths = []

        try:
            experience_years = float(
                llm_output.get(
                    "experience_years",
                    extracted.get("experience_years", 0),
                )
                or 0
            )
        except (TypeError, ValueError):
            experience_years = 0.0

        return {
            "extracted_data": extracted,
            "llm_analysis": llm_output,
            "keywords": extracted_keywords,
            "skills": llm_skills or extracted_skills,
            "experience_years": experience_years,
            "tech_stack": llm_output.get("tech_stack", extracted_tech_stack),
            "professional_summary": llm_output.get(
                "professional_summary",
                extracted.get("professional_summary", ""),
            ),
            "recommended_roles": llm_output.get("recommended_roles", extracted_roles),
            "missing_skills": llm_output.get("missing_skills", extracted_missing),
            "strengths": llm_output.get("strengths", extracted_strengths),
            "career_level": llm_output.get(
                "career_level",
                extracted.get("career_level", "entry"),
            ),
            "raw_text_quality": extracted.get("raw_text_quality", {}),
            "model_meta": extracted.get("model_meta", {}),
            "contact": {
                **(extracted.get("contact", {}) if isinstance(extracted.get("contact"), dict) else {}),
                "location": AIRecommendationService.sanitize_location(
                    (extracted.get("contact", {}) or {}).get("location", "")
                    if isinstance(extracted.get("contact"), dict)
                    else ""
                ),
            },
        }
    
    @staticmethod
    def get_job_sources(use_apify: bool = True, keywords: Optional[List[str]] = None, location: str = "India", resume_skills: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Get jobs from either database (Opportunities) or Apify API.
        
        Args:
            use_apify: If True, fetch from Apify. If False, use database opportunities.
            keywords: List of keywords/skills to search for (from resume)
            location: Location to search jobs in
            
        Returns:
            List of job dictionaries with consistent structure and REAL apply URLs
        """
        location = AIRecommendationService.sanitize_location(location)
        if use_apify:
            # Fetch from Apify (live data) with actual resume keywords
            try:
                # Normalize keywords deterministically for stable results across repeated calls.
                search_keywords = AIRecommendationService._prepare_search_keywords(
                    keywords=keywords,
                    fallback_keywords=["software engineer", "python developer", "react developer", "data analyst"],
                    max_items=12
                )
                
                print(f"🔍 Fetching live jobs from Apify with keywords: {search_keywords[:5]}")
                jobs = fetch_jobs_from_apify(
                    keywords=search_keywords,
                    location=location,
                    resume_skills=resume_skills or search_keywords  # Pass skills for Naukri direct search
                )

                # If live APIs return no jobs, fall back to internal DB.
                if not jobs:
                    print("⚠️ Apify returned 0 jobs, combining internal jobs + external search fallbacks")
                    internal_jobs = AIRecommendationService.get_job_sources(
                        use_apify=False,
                        keywords=search_keywords,
                        location=location,
                        resume_skills=resume_skills or search_keywords,
                    )
                    external_fallback = AIRecommendationService._build_external_search_fallback(
                        keywords=search_keywords,
                        location=location,
                    )
                    return internal_jobs + external_fallback
                else:
                    jobs = [
                        AIRecommendationService.normalize_job_apply_target(job, location=location)
                        for job in jobs
                    ]
                    print(f"✅ Fetched {len(jobs)} live jobs from Apify")
                    return jobs
            except Exception as e:
                print(f"❌ Apify fetch failed: {e}, combining internal jobs + external search fallbacks")
                import traceback
                traceback.print_exc()
                internal_jobs = AIRecommendationService.get_job_sources(
                    use_apify=False,
                    keywords=keywords or [],
                    location=location,
                    resume_skills=resume_skills or (keywords or []),
                )
                external_fallback = AIRecommendationService._build_external_search_fallback(
                    keywords=keywords or [],
                    location=location,
                )
                return internal_jobs + external_fallback
        
        # Fetch from database (Opportunities table)
        opportunities = Opportunity.query.filter_by(
            is_active=True,
            is_approved=True
        ).all()
        
        jobs = []
        for opp in opportunities:
            # Get required skills from OpportunitySkill relationship
            required_skills = []
            for opp_skill in opp.skills_rel.filter_by(is_required=True).all():
                if opp_skill.skill:
                    required_skills.append(opp_skill.skill.name)
            
            # Fallback to JSON field if no skills in relationship
            if not required_skills:
                required_skills = json.loads(opp.required_skills) if opp.required_skills else []
            
            jobs.append({
                "id": opp.id,
                "title": opp.title,
                "company_name": opp.company.name if opp.company else "Unknown",
                "location": opp.location or "Not specified",
                "description": opp.description,
                "required_skills": required_skills,
                "duration": opp.duration,
                "stipend": opp.stipend,
                "work_type": opp.work_type,
                "url": AIRecommendationService._build_internal_student_url(opp.id),
                "source": "internal",
                "application_deadline": opp.application_deadline.isoformat() if opp.application_deadline else None
            })
        
        # Last-resort fallback: create direct search links from resume skills
        # so students still see actionable leads even when both live and DB sources are empty.
        if not jobs and resume_skills:
            print("⚠️ No DB opportunities found; generating skill-based search links")
            jobs = create_naukri_search_jobs(resume_skills=resume_skills, location=location)

        return [
            AIRecommendationService.normalize_job_apply_target(job, location=location)
            for job in jobs
        ]

    @staticmethod
    def _as_text_list(items: Any) -> List[str]:
        """Coerce unknown input to a clean list of non-empty strings."""
        if not items:
            return []
        if isinstance(items, str):
            return [items]
        if not isinstance(items, list):
            return []
        return [str(item) for item in items if isinstance(item, (str, int, float))]

    @staticmethod
    def _normalize_keyword(value: str) -> str:
        """Normalize keyword text for deterministic de-duplication."""
        if value is None:
            return ""
        normalized = re.sub(r"\s+", " ", str(value)).strip().lower()
        normalized = normalized.replace("_", " ").replace("-", " ")
        normalized = re.sub(r"[^\w\s\+\#\.]", "", normalized).strip()
        return normalized

    @staticmethod
    def _prepare_search_keywords(
        keywords: Optional[List[str]],
        fallback_keywords: Optional[List[str]] = None,
        max_items: int = 10
    ) -> List[str]:
        """
        Build a stable, de-duplicated keyword list.
        Keeps insertion order to avoid random results between calls.
        """
        candidates = AIRecommendationService._as_text_list(keywords)
        ordered: List[str] = []
        seen = set()

        for raw in candidates:
            key = AIRecommendationService._normalize_keyword(raw)
            if not key:
                continue
            if len(key) < 2 or len(key) > 64:
                continue
            if key.isdigit():
                continue
            tokens = [tok for tok in key.split() if tok and tok not in AIRecommendationService._KEYWORD_TOKEN_STOPWORDS]
            if not tokens:
                continue
            if len(tokens) > 4:
                continue
            if any(tok in AIRecommendationService._RESUME_NOISE_TERMS for tok in tokens):
                continue
            key = " ".join(tokens)
            if key in AIRecommendationService._GENERIC_KEYWORD_STOPWORDS:
                continue
            if key in seen:
                continue
            seen.add(key)
            ordered.append(key)
            if len(ordered) >= max_items:
                break

        if not ordered:
            for fallback in fallback_keywords or ["software engineer", "developer", "intern"]:
                key = AIRecommendationService._normalize_keyword(fallback)
                if key and key not in seen:
                    seen.add(key)
                    ordered.append(key)
                if len(ordered) >= max_items:
                    break

        return ordered
    
    @staticmethod
    def match_jobs(
        resume_data: Dict[str, Any],
        jobs: List[Dict[str, Any]],
        use_llm_ranking: bool = True,
        top_n: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Match jobs with resume data using multiple methods.
        
        Args:
            resume_data: Extracted resume data with skills, experience, etc.
            jobs: List of job dictionaries
            use_llm_ranking: If True, use LLM for ranking. If False, use cosine similarity.
            top_n: Number of top matches to return. Use <=0 to return all.
            
        Returns:
            List of jobs with match scores and reasons
        """
        if not jobs:
            return []
        
        resume_skills = set(s.lower().strip() for s in resume_data.get("skills", []))
        resume_keywords = set(k.lower().strip() for k in resume_data.get("keywords", []))
        
        # Method 1: LLM-based ranking (more accurate but slower)
        if use_llm_ranking:
            try:
                ranked = rank_jobs_with_llm(resume_data, jobs, top_n=top_n)
                if ranked:
                    return ranked
            except Exception as e:
                print(f"LLM ranking failed: {e}, using cosine similarity")
        
        # Method 2: Cosine similarity + keyword matching (faster)
        scored_jobs = []
        
        for job in jobs:
            # Skip matching for Naukri search redirects (they already have 100% match)
            if job.get("is_search") and job.get("source") == "naukri_search":
                # This is a direct search redirect, already has 100% match
                scored_jobs.append(job)
                continue
            
            # Get skills from required_skills if available
            job_skills = set(s.lower().strip() for s in job.get("required_skills", []))
            
            # If no skills in required_skills, extract from description and title
            if not job_skills:
                job_description = job.get("description", "") or ""
                job_title = job.get("title", "") or ""
                combined_text = f"{job_title} {job_description}"
                extracted_skills = AIRecommendationService._extract_skills_from_text(combined_text)
                job_skills = extracted_skills
                # Store extracted skills back for display
                job["extracted_skills"] = list(extracted_skills)
            
            job_description = job.get("description", "").lower()
            
            # Calculate multiple match scores
            skill_match_score = AIRecommendationService._calculate_skill_match(
                resume_skills, job_skills
            )
            
            keyword_match_score = AIRecommendationService._calculate_keyword_match(
                resume_keywords, job_description
            )
            
            cosine_score = AIRecommendationService._calculate_cosine_similarity(
                resume_data, job
            )
            
            # Weighted final score (ensure minimum score if any match found)
            base_score = (
                skill_match_score * 0.6 +  # Skills are most important (increased weight)
                keyword_match_score * 0.25 +  # Keywords help
                cosine_score * 0.15  # Description similarity
            )
            
            # Boost score if we have any matches at all
            if skill_match_score > 0 or keyword_match_score > 0:
                # Minimum 10% if any match found
                final_score = max(base_score, 10.0)
            else:
                final_score = base_score
            
            # Cap at 100
            final_score = min(final_score, 100.0)
            
            # Generate match reason
            matched_skills = resume_skills & job_skills
            match_reason = AIRecommendationService._generate_match_reason(
                matched_skills, job_skills, resume_data, job
            )
            
            # Ensure we have a reasonable match score
            match_score = max(int(final_score), 0)
            
            scored_jobs.append({
                **job,
                "match_score": match_score,
                "match_reason": match_reason,
                "matched_skills": list(matched_skills)[:10],  # Limit for display
                "missing_skills": list(job_skills - resume_skills)[:10]  # Limit for display
            })
        
        # Sort by match score (descending)
        scored_jobs.sort(key=lambda x: x.get("match_score", 0), reverse=True)
        
        if top_n is None or top_n <= 0:
            return scored_jobs
        return scored_jobs[:top_n]
    
    @staticmethod
    def _extract_skills_from_text(text: str) -> set:
        """Extract skills from job description or title"""
        if not text:
            return set()
        
        text_lower = text.lower()
        skills_found = set()
        
        # Common tech skills to look for
        tech_skills = [
            'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'go', 'rust', 'ruby', 'php',
            'react', 'angular', 'vue', 'node.js', 'nodejs', 'express', 'django', 'flask', 'spring',
            'sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'oracle', 'database',
            'aws', 'azure', 'gcp', 'google cloud', 'docker', 'kubernetes', 'k8s', 'terraform',
            'html', 'css', 'bootstrap', 'tailwind', 'sass', 'less',
            'android', 'ios', 'react native', 'flutter', 'swift', 'kotlin',
            'machine learning', 'ml', 'ai', 'artificial intelligence', 'data science',
            'pandas', 'numpy', 'tensorflow', 'pytorch', 'scikit-learn', 'keras',
            'git', 'github', 'gitlab', 'jenkins', 'ci/cd', 'devops',
            'agile', 'scrum', 'jira', 'confluence'
        ]
        
        for skill in tech_skills:
            if skill in text_lower:
                skills_found.add(skill)
        
        return skills_found
    
    @staticmethod
    def _normalize_skill(skill: str) -> str:
        """Normalize skill name for better matching"""
        skill = skill.lower().strip()
        # Remove common suffixes/prefixes
        skill = skill.replace('programming', '').replace('development', '').replace('developer', '')
        skill = skill.replace('experience', '').replace('knowledge', '').replace('skill', '')
        skill = skill.strip()
        return skill
    
    @staticmethod
    def _fuzzy_skill_match(resume_skill: str, job_skill: str) -> bool:
        """Check if skills match (fuzzy matching)"""
        resume_norm = AIRecommendationService._normalize_skill(resume_skill)
        job_norm = AIRecommendationService._normalize_skill(job_skill)
        
        # Exact match
        if resume_norm == job_norm:
            return True
        
        # One contains the other
        if resume_norm in job_norm or job_norm in resume_norm:
            return True
        
        # Common aliases
        aliases = {
            'js': 'javascript',
            'nodejs': 'node.js',
            'ml': 'machine learning',
            'ai': 'artificial intelligence',
            'k8s': 'kubernetes',
            'postgres': 'postgresql',
            'mongo': 'mongodb',
        }
        
        resume_alias = aliases.get(resume_norm, resume_norm)
        job_alias = aliases.get(job_norm, job_norm)
        
        return resume_alias == job_alias or resume_alias in job_alias or job_alias in resume_alias
    
    @staticmethod
    def _calculate_skill_match(resume_skills: set, job_skills: set) -> float:
        """Calculate skill match percentage (0-100) with fuzzy matching"""
        if not job_skills:
            return 0.0
        
        if not resume_skills:
            return 0.0
        
        # Try exact matches first
        exact_matches = len(resume_skills & job_skills)
        
        # Try fuzzy matches for remaining skills
        fuzzy_matches = 0
        remaining_resume = resume_skills - job_skills
        remaining_job = job_skills - resume_skills
        
        for resume_skill in remaining_resume:
            for job_skill in remaining_job:
                if AIRecommendationService._fuzzy_skill_match(resume_skill, job_skill):
                    fuzzy_matches += 1
                    break  # Match found, move to next resume skill
        
        total_matches = exact_matches + fuzzy_matches
        total = len(job_skills)
        
        if total == 0:
            return 0.0
        
        # Calculate percentage (cap at 100)
        match_percent = min((total_matches / total) * 100, 100.0)
        
        return match_percent
    
    @staticmethod
    def _calculate_keyword_match(resume_keywords: set, job_description: str) -> float:
        """Calculate keyword match percentage (0-100)"""
        if not resume_keywords or not job_description:
            return 0.0
        
        found_keywords = sum(1 for kw in resume_keywords if kw in job_description)
        return min((found_keywords / len(resume_keywords)) * 100, 100.0)
    
    @staticmethod
    def _calculate_cosine_similarity(resume_data: Dict, job: Dict) -> float:
        """Calculate cosine similarity between resume and job description"""
        try:
            resume_text = " ".join(resume_data.get("skills", []))
            resume_text += " " + resume_data.get("professional_summary", "")
            
            job_text = job.get("description", "")
            job_text += " " + " ".join(job.get("required_skills", []))
            
            if not resume_text.strip() or not job_text.strip():
                return 0.0
            
            vectorizer = TfidfVectorizer(max_features=100, stop_words='english')
            vectors = vectorizer.fit_transform([resume_text, job_text])
            
            similarity = cosine_similarity(vectors[0:1], vectors[1:2])[0][0]
            return float(similarity * 100)  # Convert to 0-100 scale
            
        except Exception:
            return 0.0
    
    @staticmethod
    def _generate_match_reason(
        matched_skills: set,
        job_skills: set,
        resume_data: Dict,
        job: Dict
    ) -> str:
        """Generate human-readable match reason"""
        matched_count = len(matched_skills)
        total_count = len(job_skills)
        
        if matched_count == 0:
            return "No skills match found"
        
        match_percent = int((matched_count / total_count) * 100) if total_count > 0 else 0
        
        if match_percent >= 80:
            return f"Excellent match! You have {matched_count} out of {total_count} required skills ({match_percent}% match)"
        elif match_percent >= 60:
            return f"Strong match with {matched_count} out of {total_count} required skills ({match_percent}% match)"
        elif match_percent >= 40:
            return f"Moderate match with {matched_count} out of {total_count} required skills ({match_percent}% match)"
        else:
            return f"Partial match with {matched_count} out of {total_count} required skills ({match_percent}% match)"
    
    @staticmethod
    def get_recommendations(
        resume_analysis: Dict[str, Any],
        use_apify: bool = True,
        top_n: int = 200,
        location: str = "India"
    ) -> List[Dict[str, Any]]:
        """
        Main recommendation function.
        
        Args:
            resume_analysis: Output from extract_and_analyze_resume
            use_apify: Whether to use Apify or database
            top_n: Number of recommendations
            location: Location to search jobs in
            
        Returns:
            List of recommended jobs with match scores and REAL apply URLs
        """
        location = AIRecommendationService.sanitize_location(location)

        # Extract keywords from resume analysis
        skills = AIRecommendationService._as_text_list(resume_analysis.get("skills", []))
        keywords = AIRecommendationService._as_text_list(resume_analysis.get("keywords", []))
        recommended_roles = AIRecommendationService._as_text_list(resume_analysis.get("recommended_roles", []))

        # Prefer hard skills first, then role titles, then generic keywords.
        # Use stable ordering instead of set(...) to avoid inconsistent search output.
        search_keywords = AIRecommendationService._prepare_search_keywords(
            keywords=skills + recommended_roles + keywords,
            max_items=12
        )
        
        # Get jobs with actual resume keywords
        # Pass skills separately for Naukri direct search redirects
        jobs = AIRecommendationService.get_job_sources(
            use_apify=use_apify,
            keywords=search_keywords,
            location=location,
            resume_skills=skills  # Pass skills for Naukri search redirects
        )
        
        # Match jobs
        recommendations = AIRecommendationService.match_jobs(
            resume_analysis,
            jobs,
            use_llm_ranking=False,  # Set to True for LLM ranking (slower but better)
            top_n=top_n
        )
        
        # Ensure all recommendations have proper apply URLs
        return [
            AIRecommendationService.normalize_job_apply_target(rec, location=location)
            for rec in recommendations
        ]


