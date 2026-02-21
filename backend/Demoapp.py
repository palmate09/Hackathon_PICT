"""
LLM Model Wrapper for Resume Analysis and Job Recommendations
Supports multiple free options:
1. Groq API (FREE: 14,400 requests/day) - Best option
2. Hugging Face (FREE: 1000 requests/month)
3. Rule-based (ALWAYS FREE, no API needed) - Fallback
4. OpenAI (Paid) - Optional

By default uses FREE options. Set GROQ_API_KEY for best free experience.
"""

import os
import json
from typing import Dict, List, Any, Optional

# Try to import free alternatives
try:
    from groq import Groq
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

# Import free rule-based functions
try:
    from Demoapp_free import run_model_free_rule_based, rank_jobs_with_llm as rank_jobs_free
    HAS_FREE_MODULE = True
except ImportError:
    HAS_FREE_MODULE = False


def run_model_groq_free(extracted_resume_text: str) -> Dict[str, Any]:
    """
    FREE Groq API - 14,400 requests/day, no credit card needed!
    Get free API key: https://console.groq.com/
    """
    if not HAS_GROQ:
        return run_model_free_fallback(extracted_resume_text)
    
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return run_model_free_fallback(extracted_resume_text)
    
    try:
        client = Groq(api_key=api_key)
        
        prompt = f"""Analyze this resume and return JSON:
{{
    "cleaned_skills": ["skill1", "skill2"],
    "professional_summary": "2-3 sentence summary",
    "recommended_roles": ["role1", "role2"],
    "missing_skills": ["skill1"],
    "experience_years": 2,
    "tech_stack": ["tech1"],
    "strengths": ["strength1"],
    "career_level": "mid"
}}

Resume: {extracted_resume_text[:6000]}"""
        
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",  # Free fast model
            messages=[
                {"role": "system", "content": "You are a resume analyzer. Return ONLY valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
        )
        
        content = completion.choices[0].message.content
        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            result.setdefault("cleaned_skills", [])
            result.setdefault("professional_summary", "")
            result.setdefault("recommended_roles", [])
            result.setdefault("missing_skills", [])
            result.setdefault("experience_years", 0)
            result.setdefault("tech_stack", [])
            result.setdefault("strengths", [])
            result.setdefault("career_level", "entry")
            result["method"] = "groq_free"
            return result
    except Exception:
        pass
    
    return run_model_free_fallback(extracted_resume_text)


def run_model_free_fallback(extracted_resume_text: str) -> Dict[str, Any]:
    """Free rule-based fallback (always works, no API needed)"""
    if HAS_FREE_MODULE:
        return run_model_free_rule_based(extracted_resume_text)
    
    # Simple fallback if module not available
    return {
        "cleaned_skills": [],
        "professional_summary": "Resume analysis available. Please set up free API key for better results.",
        "recommended_roles": [],
        "missing_skills": [],
        "experience_years": 0,
        "tech_stack": [],
        "strengths": [],
        "career_level": "entry",
        "method": "fallback"
    }


def run_model(extracted_resume_text: str) -> Dict[str, Any]:
    """
    Main function - tries FREE options first, then paid OpenAI if available.
    Priority:
    1. Groq (FREE, 14,400 requests/day) - Best free option
    2. Rule-based (FREE, always works) - No API needed
    3. OpenAI (Paid) - Optional fallback
    """
    # Try Groq first (best free option)
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key:
        try:
            return run_model_groq_free(extracted_resume_text)
        except Exception:
            pass
    
    # Try rule-based (always free, no API)
    if HAS_FREE_MODULE:
        try:
            return run_model_free_rule_based(extracted_resume_text)
        except Exception:
            pass
    
    # Optional: Try OpenAI if key is set (paid)
    if HAS_OPENAI:
        openai_key = os.getenv("OPENAI_API_KEY", "")
        if openai_key:
            try:
                client = OpenAI(api_key=openai_key)
                prompt = f"""Analyze this resume and return JSON:
{{
    "cleaned_skills": ["skill1", "skill2"],
    "professional_summary": "2-3 sentence summary",
    "recommended_roles": ["role1", "role2"],
    "missing_skills": ["skill1"],
    "experience_years": 2,
    "tech_stack": ["tech1"],
    "strengths": ["strength1"],
    "career_level": "mid"
}}

Resume: {extracted_resume_text[:8000]}"""
                
                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a resume analyzer. Return ONLY valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.3,
                )
                
                content = completion.choices[0].message.content
                result = json.loads(content or "{}")
                result.setdefault("cleaned_skills", [])
                result.setdefault("professional_summary", "")
                result.setdefault("recommended_roles", [])
                result.setdefault("missing_skills", [])
                result.setdefault("experience_years", 0)
                result.setdefault("tech_stack", [])
                result.setdefault("strengths", [])
                result.setdefault("career_level", "entry")
                result["method"] = "openai_paid"
                return result
            except Exception:
                pass
    
    # Final fallback
    return run_model_free_fallback(extracted_resume_text)


def rank_jobs_with_llm(
    resume_data: Dict[str, Any],
    jobs: List[Dict[str, Any]],
    top_n: int = 10
) -> List[Dict[str, Any]]:
    """
    Rank jobs using FREE rule-based matching (no API needed)
    """
    if not jobs:
        return []
    
    # Use free rule-based ranking
    if HAS_FREE_MODULE:
        return rank_jobs_free(resume_data, jobs, top_n)
    
    # Simple fallback
    return _fallback_rank_jobs(resume_data, jobs, top_n)


def _fallback_rank_jobs(
    resume_data: Dict[str, Any],
    jobs: List[Dict[str, Any]],
    top_n: int = 10
) -> List[Dict[str, Any]]:
    """Fallback ranking using keyword matching if LLM fails"""
    resume_skills = set(s.lower() for s in resume_data.get('skills', []))
    
    scored_jobs = []
    for job in jobs:
        job_skills = set(s.lower() for s in job.get('required_skills', []))
        if not job_skills:
            continue
        
        # Calculate match percentage
        matched = len(resume_skills & job_skills)
        total = len(job_skills)
        match_score = int((matched / total) * 100) if total > 0 else 0
        
        scored_jobs.append({
            **job,
            "match_score": match_score,
            "match_reason": f"Matched {matched} out of {total} required skills"
        })
    
    # Sort by match score descending
    scored_jobs.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    return scored_jobs[:top_n]


# Example usage (for testing)
if __name__ == "__main__":
    sample_resume = """
    John Doe
    Software Engineer with 3 years of experience in Python, React, and Node.js.
    Worked at Tech Corp building web applications.
    Skills: Python, JavaScript, React, Node.js, SQL, MongoDB
    """
    
    result = run_model(sample_resume)
    print(json.dumps(result, indent=2))


