import os
import re
from docx import Document
import PyPDF2
from typing import List, Dict, Tuple

class ResumeParser:
    """Parse resume files and extract skills and details"""
    
    # Common skills and keywords
    PROGRAMMING_LANGUAGES = [
        'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'php', 'ruby',
        'go', 'rust', 'kotlin', 'swift', 'objective-c', 'r', 'matlab', 'scala',
        'perl', 'groovy', 'bash', 'shell', 'sql', 'html', 'css', 'xml'
    ]
    
    FRAMEWORKS = [
        'django', 'flask', 'fastapi', 'spring', 'spring boot', 'asp.net',
        'react', 'angular', 'vue', 'next.js', 'svelte', 'ember',
        'express', 'koa', 'rails', 'sinatra', 'laravel', 'symfony',
        'tensorflow', 'pytorch', 'keras', 'scikit-learn', 'pandas', 'numpy',
        'unity', 'unreal engine', 'godot'
    ]
    
    TOOLS_PLATFORMS = [
        'git', 'docker', 'kubernetes', 'jenkins', 'aws', 'azure', 'gcp',
        'linux', 'windows', 'macos', 'ios', 'android', 'firebase',
        'mongodb', 'postgresql', 'mysql', 'redis', 'elasticsearch',
        'jira', 'confluence', 'slack', 'gitlab', 'github',
        'tableau', 'powerbi', 'datadog', 'newrelic'
    ]
    
    SOFT_SKILLS = [
        'leadership', 'communication', 'teamwork', 'problem solving',
        'project management', 'agile', 'scrum', 'critical thinking',
        'negotiation', 'presentation', 'collaboration', 'time management'
    ]
    
    def __init__(self):
        self.all_skills = (
            self.PROGRAMMING_LANGUAGES + 
            self.FRAMEWORKS + 
            self.TOOLS_PLATFORMS + 
            self.SOFT_SKILLS
        )
    
    def extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF file"""
        text = ""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text()
        except Exception as e:
            print(f"Error reading PDF: {e}")
        return text
    
    def extract_text_from_docx(self, file_path: str) -> str:
        """Extract text from DOCX file"""
        text = ""
        try:
            doc = Document(file_path)
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
        except Exception as e:
            print(f"Error reading DOCX: {e}")
        return text
    
    def extract_text_from_txt(self, file_path: str) -> str:
        """Extract text from TXT file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            print(f"Error reading TXT: {e}")
            return ""
    
    def extract_text(self, file_path: str) -> str:
        """Extract text based on file type"""
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        if ext == '.pdf':
            return self.extract_text_from_pdf(file_path)
        elif ext == '.docx':
            return self.extract_text_from_docx(file_path)
        elif ext == '.txt':
            return self.extract_text_from_txt(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}")
    
    def extract_skills(self, text: str) -> List[str]:
        """Extract skills from resume text"""
        text_lower = text.lower()
        found_skills = set()
        
        for skill in self.all_skills:
            # Use word boundary to avoid partial matches
            pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(pattern, text_lower):
                found_skills.add(skill.title())
        
        return sorted(list(found_skills))
    
    def extract_experience(self, text: str) -> List[str]:
        """Extract years of experience from resume"""
        # Look for patterns like "5 years", "3+ years", etc.
        years_pattern = r'(\d+)\+?\s+(?:years?|yrs?)'
        matches = re.findall(years_pattern, text, re.IGNORECASE)
        
        if matches:
            return matches
        return []
    
    def extract_email(self, text: str) -> str:
        """Extract email address from resume"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        matches = re.findall(email_pattern, text)
        return matches[0] if matches else ""
    
    def extract_phone(self, text: str) -> str:
        """Extract phone number from resume"""
        phone_pattern = r'(?:\+\d{1,3})?\s*(?:\(?\d{3}\)?[\s.-]?)?\d{3}[\s.-]?\d{4}'
        matches = re.findall(phone_pattern, text)
        return matches[0] if matches else ""
    
    def parse_resume(self, file_path: str) -> Dict:
        """Parse resume and extract all information"""
        try:
            text = self.extract_text(file_path)
            
            resume_data = {
                'skills': self.extract_skills(text),
                'experience': self.extract_experience(text),
                'email': self.extract_email(text),
                'phone': self.extract_phone(text),
                'full_text': text[:1000]  # Store first 1000 chars for context
            }
            
            return resume_data
        except Exception as e:
            print(f"Error parsing resume: {e}")
            return {
                'skills': [],
                'experience': [],
                'email': '',
                'phone': '',
                'full_text': '',
                'error': str(e)
            }
