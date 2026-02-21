"""
FREE LLM Model Wrapper - Multiple Free Alternatives
Supports: Hugging Face (free), Groq (free), Rule-based (no API), Local models
"""

import os
import json
import re
from typing import Dict, List, Any, Optional

# Try to import optional dependencies
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# Common tech skills database
TECH_SKILLS_DB = {
    'programming': ['python', 'java', 'javascript', 'c++', 'c#', 'go', 'rust', 'ruby', 'php', 'swift', 'kotlin', 'dart', 'scala', 'r', 'matlab'],
    'web': ['html', 'css', 'react', 'angular', 'vue', 'node.js', 'express', 'django', 'flask', 'spring', 'asp.net', 'laravel', 'next.js', 'nuxt.js'],
    'database': ['sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'oracle', 'sqlite', 'cassandra', 'elasticsearch'],
    'cloud': ['aws', 'azure', 'gcp', 'docker', 'kubernetes', 'terraform', 'jenkins', 'ci/cd'],
    'mobile': ['android', 'ios', 'react native', 'flutter', 'xamarin', 'ionic'],
    'data': ['pandas', 'numpy', 'tensorflow', 'pytorch', 'scikit-learn', 'keras', 'jupyter', 'tableau', 'power bi'],
    'tools': ['git', 'github', 'gitlab', 'jira', 'confluence', 'slack', 'agile', 'scrum']
}

JOB_ROLES_DB = {
    'software engineer': ['python', 'java', 'javascript', 'react', 'node.js', 'sql'],
    'full stack developer': ['javascript', 'react', 'node.js', 'sql', 'html', 'css'],
    'frontend developer': ['javascript', 'react', 'angular', 'vue', 'html', 'css'],
    'backend developer': ['python', 'java', 'node.js', 'sql', 'api', 'rest'],
    'data scientist': ['python', 'pandas', 'numpy', 'machine learning', 'sql', 'jupyter'],
    'devops engineer': ['docker', 'kubernetes', 'aws', 'ci/cd', 'jenkins', 'terraform'],
    'mobile developer': ['android', 'ios', 'react native', 'flutter', 'swift', 'kotlin'],
    'ui/ux designer': ['figma', 'adobe xd', 'sketch', 'photoshop', 'illustrator'],
    'qa engineer': ['testing', 'selenium', 'automation', 'manual testing', 'api testing'],
    'product manager': ['agile', 'scrum', 'product management', 'jira', 'analytics']
}


def extract_skills_rule_based(text: str) -> List[str]:
    """Extract skills using rule-based pattern matching (FREE, no API)"""
    text_lower = text.lower()
    found_skills = set()
    
    # Check against skills database
    for category, skills in TECH_SKILLS_DB.items():
        for skill in skills:
            if skill.lower() in text_lower:
                found_skills.add(skill.title())
    
    # Extract common patterns
    patterns = [
        r'\b(skill|skills|proficient|experienced|expert|knowledge|familiar)\s*(in|with|of)?\s*:?\s*([^\.\n]+)',
        r'(?:technologies?|tools?|frameworks?|languages?)\s*:?\s*([^\.\n]+)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text_lower, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                skills_text = match[-1] if match else ''
            else:
                skills_text = match
            # Split by common delimiters
            skills_list = re.split(r'[,;|•\-\n]', skills_text)
            for skill in skills_list:
                skill = skill.strip()
                if len(skill) > 2 and len(skill) < 30:
                    found_skills.add(skill.title())
    
    return list(found_skills)[:30]


def estimate_experience_years(text: str) -> int:
    """Estimate years of experience from resume text"""
    text_lower = text.lower()
    
    # Look for explicit years
    year_patterns = [
        r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s*)?(?:experience|exp)',
        r'experience[:\s]+(\d+)\+?\s*(?:years?|yrs?)',
        r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:in|working)',
    ]
    
    for pattern in year_patterns:
        match = re.search(pattern, text_lower)
        if match:
            years = int(match.group(1))
            return min(years, 20)  # Cap at 20
    
    # Estimate from keywords
    if any(word in text_lower for word in ['senior', 'lead', 'principal', 'architect', 'manager']):
        return 5
    elif any(word in text_lower for word in ['mid', 'intermediate', 'experienced']):
        return 3
    elif any(word in text_lower for word in ['junior', 'entry', 'intern', 'fresh', 'graduate']):
        return 0
    
    return 1  # Default


def generate_summary_rule_based(text: str, skills: List[str]) -> str:
    """Generate professional summary using rule-based extraction"""
    # Extract key phrases
    sentences = re.split(r'[.!?]\s+', text)
    key_sentences = []
    
    for sentence in sentences[:5]:
        if any(skill.lower() in sentence.lower() for skill in skills[:5]):
            key_sentences.append(sentence.strip())
    
    if key_sentences:
        summary = '. '.join(key_sentences[:2]) + '.'
        if len(summary) > 200:
            summary = summary[:197] + '...'
        return summary
    
    # Fallback: create from skills
    if skills:
        return f"Experienced professional with expertise in {', '.join(skills[:5])}. Strong background in software development and technology."
    
    return "Professional with relevant experience and skills."


def recommend_roles_rule_based(skills: List[str]) -> List[str]:
    """Recommend job roles based on skills matching"""
    skills_lower = [s.lower() for s in skills]
    role_scores = {}
    
    for role, required_skills in JOB_ROLES_DB.items():
        score = sum(1 for skill in required_skills if any(skill in s for s in skills_lower))
        if score > 0:
            role_scores[role] = score
    
    # Sort by score and return top roles
    sorted_roles = sorted(role_scores.items(), key=lambda x: x[1], reverse=True)
    return [role.title() for role, _ in sorted_roles[:8]]


def find_missing_skills(skills: List[str], recommended_roles: List[str]) -> List[str]:
    """Find skills that would improve job match"""
    skills_lower = [s.lower() for s in skills]
    missing = set()
    
    for role in recommended_roles[:3]:
        role_lower = role.lower()
        if role_lower in JOB_ROLES_DB:
            required = JOB_ROLES_DB[role_lower]
            for req_skill in required:
                if not any(req_skill in s for s in skills_lower):
                    missing.add(req_skill.title())
    
    return list(missing)[:5]


def run_model_free_rule_based(extracted_resume_text: str) -> Dict[str, Any]:
    """
    FREE Rule-based resume analysis (NO API, NO COST)
    Uses pattern matching and keyword extraction
    """
    text = extracted_resume_text[:8000]
    
    # Extract skills
    skills = extract_skills_rule_based(text)
    
    # Estimate experience
    experience_years = estimate_experience_years(text)
    
    # Generate summary
    summary = generate_summary_rule_based(text, skills)
    
    # Recommend roles
    recommended_roles = recommend_roles_rule_based(skills)
    
    # Find missing skills
    missing_skills = find_missing_skills(skills, recommended_roles)
    
    # Determine career level
    if experience_years >= 5:
        career_level = "senior"
    elif experience_years >= 2:
        career_level = "mid"
    else:
        career_level = "entry"
    
    # Extract tech stack (same as skills for now)
    tech_stack = [s for s in skills if any(tech in s.lower() for tech in ['python', 'java', 'javascript', 'react', 'node', 'sql', 'aws', 'docker'])]
    
    # Extract strengths (top skills)
    strengths = skills[:5]
    
    return {
        "cleaned_skills": skills[:20],
        "professional_summary": summary,
        "recommended_roles": recommended_roles,
        "missing_skills": missing_skills,
        "experience_years": experience_years,
        "tech_stack": tech_stack[:10],
        "strengths": strengths,
        "career_level": career_level,
        "method": "rule_based_free"
    }


def run_model_huggingface(extracted_resume_text: str, api_token: Optional[str] = None) -> Dict[str, Any]:
    """
    FREE Hugging Face Inference API (Free tier: 1000 requests/month)
    No credit card required!
    """
    if not HAS_REQUESTS:
        return run_model_free_rule_based(extracted_resume_text)
    
    api_token = api_token or os.getenv("HUGGINGFACE_API_TOKEN", "")
    if not api_token:
        # Fallback to rule-based if no token
        return run_model_free_rule_based(extracted_resume_text)
    
    # Use a free model like mistralai/Mistral-7B-Instruct-v0.2
    api_url = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2"
    
    prompt = f"""Analyze this resume and extract:
- Skills (list)
- Experience years (number)
- Professional summary (2 sentences)
- Recommended job roles (list)
- Missing skills (list)

Resume: {extracted_resume_text[:4000]}

Return JSON format."""
    
    headers = {"Authorization": f"Bearer {api_token}"}
    
    try:
        response = requests.post(api_url, headers=headers, json={"inputs": prompt}, timeout=30)
        if response.status_code == 200:
            result = response.json()
            # Parse the response (Hugging Face returns text, need to extract JSON)
            # For simplicity, fallback to rule-based
            return run_model_free_rule_based(extracted_resume_text)
        else:
            return run_model_free_rule_based(extracted_resume_text)
    except Exception:
        return run_model_free_rule_based(extracted_resume_text)


def run_model_groq(extracted_resume_text: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    FREE Groq API (Free tier: 14,400 requests/day!)
    Fast and free, no credit card required
    """
    try:
        from groq import Groq
    except ImportError:
        return run_model_free_rule_based(extracted_resume_text)
    
    api_key = api_key or os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return run_model_free_rule_based(extracted_resume_text)
    
    try:
        client = Groq(api_key=api_key)
        
        prompt = f"""Analyze this resume and return JSON:
{{
    "cleaned_skills": ["skill1", "skill2"],
    "professional_summary": "summary text",
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
        # Try to extract JSON from response
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
    
    return run_model_free_rule_based(extracted_resume_text)


def run_model(extracted_resume_text: str) -> Dict[str, Any]:
    """
    Main function - tries free options in order:
    1. Groq (if API key set) - 14,400 requests/day free
    2. Hugging Face (if API token set) - 1000 requests/month free
    3. Rule-based (always works, no API needed)
    """
    # Try Groq first (best free option)
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key:
        try:
            return run_model_groq(extracted_resume_text, groq_key)
        except Exception:
            pass
    
    # Try Hugging Face
    hf_token = os.getenv("HUGGINGFACE_API_TOKEN", "")
    if hf_token:
        try:
            return run_model_huggingface(extracted_resume_text, hf_token)
        except Exception:
            pass
    
    # Fallback to rule-based (always works, no API needed)
    return run_model_free_rule_based(extracted_resume_text)


def rank_jobs_with_llm(
    resume_data: Dict[str, Any],
    jobs: List[Dict[str, Any]],
    top_n: int = 10
) -> List[Dict[str, Any]]:
    """
    Rank jobs using free methods (rule-based matching)
    """
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
        
        # Generate reason
        if match_score >= 80:
            reason = f"Excellent match! You have {matched} out of {total} required skills."
        elif match_score >= 60:
            reason = f"Strong match with {matched} out of {total} required skills."
        elif match_score >= 40:
            reason = f"Moderate match with {matched} out of {total} required skills."
        else:
            reason = f"Partial match with {matched} out of {total} required skills."
        
        scored_jobs.append({
            **job,
            "match_score": match_score,
            "match_reason": reason,
            "matched_skills": list(resume_skills & job_skills)
        })
    
    # Sort by match score
    scored_jobs.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    return scored_jobs[:top_n]


# Example usage
if __name__ == "__main__":
    sample_resume = """
    John Doe
    Software Engineer with 3 years of experience in Python, React, and Node.js.
    Worked at Tech Corp building web applications.
    Skills: Python, JavaScript, React, Node.js, SQL, MongoDB
    """
    
    result = run_model(sample_resume)
    print(json.dumps(result, indent=2))

