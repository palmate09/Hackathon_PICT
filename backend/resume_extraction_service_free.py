"""
FREE Resume Extraction Service - No OpenAI Required
Uses rule-based extraction and pattern matching
"""

import os
import io
import re
import json
from typing import Dict, List, Any

from PyPDF2 import PdfReader
from docx import Document


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def extract_text_from_bytes(data: bytes, filename: str) -> str:
    """Extract raw text from PDF/DOCX/others using in-memory bytes."""
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return "\n".join([page.extract_text() or "" for page in reader.pages])
    if name.endswith(".docx"):
        doc = Document(io.BytesIO(data))
        return "\n".join([para.text for para in doc.paragraphs])
    # Fallback: treat as plain text
    try:
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def extract_text_from_path(path: str) -> str:
    """Extract text from a saved file path."""
    with open(path, "rb") as f:
        data = f.read()
    return extract_text_from_bytes(data, path)


def extract_name(text: str) -> str:
    """Extract name from resume (usually first line or after 'Name:')"""
    lines = text.split('\n')[:10]
    for line in lines:
        line = line.strip()
        if len(line) > 3 and len(line) < 50:
            # Check if it looks like a name
            if re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+', line):
                return line
    return ""


def extract_email(text: str) -> str:
    """Extract email address"""
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    match = re.search(email_pattern, text)
    return match.group(0) if match else ""


def extract_phone(text: str) -> str:
    """Extract phone number"""
    phone_patterns = [
        r'\b\d{10}\b',
        r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',
        r'\b\+?\d{1,3}[-.\s]?\d{3,4}[-.\s]?\d{3,4}[-.\s]?\d{4}\b',
    ]
    for pattern in phone_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return ""


def extract_location(text: str) -> str:
    """Extract location"""
    location_keywords = ['location', 'address', 'city', 'state', 'country']
    for keyword in location_keywords:
        pattern = rf'{keyword}[:\s]+([^\n]+)'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def extract_education(text: str) -> List[Dict[str, Any]]:
    """Extract education information"""
    education = []
    edu_keywords = ['education', 'degree', 'university', 'college', 'bachelor', 'master', 'phd', 'diploma']
    
    lines = text.split('\n')
    current_edu = {}
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(keyword in line_lower for keyword in edu_keywords):
            # Extract degree
            degree_match = re.search(r'(bachelor|master|phd|doctorate|diploma|b\.?tech|m\.?tech|b\.?e|m\.?e)', line_lower)
            if degree_match:
                current_edu['degree'] = line.strip()
            
            # Look for institution in next lines
            for j in range(i+1, min(i+3, len(lines))):
                if len(lines[j].strip()) > 5:
                    current_edu['institution'] = lines[j].strip()
                    break
            
            # Look for years
            year_match = re.search(r'(19|20)\d{2}', line)
            if year_match:
                current_edu['start'] = year_match.group(0)
            
            if current_edu:
                education.append(current_edu)
                current_edu = {}
    
    return education[:5]  # Limit to 5


def extract_experience(text: str) -> List[Dict[str, Any]]:
    """Extract work experience"""
    experience = []
    exp_keywords = ['experience', 'employment', 'work history', 'career', 'position']
    
    # Find experience section
    exp_section_start = -1
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if any(keyword in line.lower() for keyword in exp_keywords):
            exp_section_start = i
            break
    
    if exp_section_start == -1:
        return []
    
    # Extract job entries
    current_exp = {}
    for i in range(exp_section_start, min(exp_section_start + 50, len(lines))):
        line = lines[i].strip()
        if not line:
            if current_exp:
                experience.append(current_exp)
                current_exp = {}
            continue
        
        # Check for job title (usually has keywords)
        if any(word in line.lower() for word in ['engineer', 'developer', 'manager', 'analyst', 'designer', 'intern']):
            current_exp['title'] = line
        
        # Check for company (often after title)
        if 'title' in current_exp and 'company' not in current_exp:
            if len(line) > 3 and len(line) < 50:
                current_exp['company'] = line
        
        # Extract years
        year_match = re.search(r'(19|20)\d{2}', line)
        if year_match:
            if 'start' not in current_exp:
                current_exp['start'] = year_match.group(0)
            else:
                current_exp['end'] = year_match.group(0)
    
    if current_exp:
        experience.append(current_exp)
    
    return experience[:5]  # Limit to 5


def extract_skills_free(text: str) -> List[str]:
    """Extract skills using pattern matching (FREE)"""
    skills = set()
    text_lower = text.lower()
    
    # Common tech skills
    tech_skills = [
        'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'go', 'rust', 'ruby', 'php',
        'react', 'angular', 'vue', 'node.js', 'express', 'django', 'flask', 'spring', 'asp.net',
        'sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'oracle',
        'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'terraform',
        'git', 'github', 'gitlab', 'jenkins', 'ci/cd',
        'html', 'css', 'bootstrap', 'tailwind',
        'android', 'ios', 'react native', 'flutter',
        'machine learning', 'ai', 'data science', 'pandas', 'numpy', 'tensorflow', 'pytorch'
    ]
    
    for skill in tech_skills:
        if skill in text_lower:
            skills.add(skill.title())
    
    # Extract from "Skills:" section
    skills_pattern = r'skills?[:\s]+([^\n]+(?:\n[^\n]+){0,5})'
    match = re.search(skills_pattern, text, re.IGNORECASE)
    if match:
        skills_text = match.group(1)
        skill_list = re.split(r'[,;|•\-\n]', skills_text)
        for skill in skill_list:
            skill = skill.strip()
            if len(skill) > 2 and len(skill) < 30:
                skills.add(skill.title())
    
    return list(skills)[:50]


def extract_keywords(text: str) -> List[str]:
    """Extract important keywords"""
    # Remove common words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should', 'could', 'may', 'might', 'can', 'this', 'that', 'these', 'those'}
    
    words = re.findall(r'\b[a-z]{3,}\b', text.lower())
    keywords = [w for w in words if w not in stop_words]
    
    # Count frequency
    from collections import Counter
    word_freq = Counter(keywords)
    
    # Return top keywords
    top_keywords = [word for word, _ in word_freq.most_common(15)]
    return top_keywords


def parse_resume_free(text: str) -> Dict[str, Any]:
    """Parse resume using rule-based extraction (FREE, no API)"""
    cleaned = _clean_text(text)
    
    return {
        "name": extract_name(cleaned),
        "email": extract_email(cleaned),
        "phone": extract_phone(cleaned),
        "location": extract_location(cleaned),
        "summary": "",  # Will be generated by LLM model
        "education": extract_education(cleaned),
        "experience": extract_experience(cleaned),
        "skills": extract_skills_free(cleaned),
        "keywords": extract_keywords(cleaned)
    }


def extract_resume_data(data: bytes, filename: str) -> Dict[str, Any]:
    """High-level helper: extract text, parse, return structured result."""
    raw_text = extract_text_from_bytes(data, filename)
    cleaned = _clean_text(raw_text)
    parsed_data = parse_resume_free(cleaned)
    parsed_data["raw_text"] = cleaned[:5000]  # return snippet for debug
    return parsed_data

