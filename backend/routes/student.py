from flask import Blueprint, request, jsonify, send_file, current_app
from flask_jwt_extended import jwt_required, get_jwt
from models import (
    db,
    User,
    StudentProfile,
    Application,
    Opportunity,
    Notification,
    StudentEducation,
    StudentInternship,
    StudentExperience,
    StudentProject,
    StudentTraining,
    StudentCertification,
    StudentPublication,
    StudentPosition,
    StudentAttachment,
    StudentOffer,
    StudentPlacementPolicy,
    StudentAcademicDetail,
)
from werkzeug.utils import secure_filename
from datetime import datetime
from io import BytesIO
from fpdf import FPDF
from resume_extraction_service import extract_resume_data
from sqlalchemy.exc import SQLAlchemyError
# Try free version first
try:
    from resume_extraction_service_free import extract_resume_data as extract_resume_data_free
    USE_FREE_EXTRACTION = True
except ImportError:
    USE_FREE_EXTRACTION = False
from apify_jobs_service import fetch_jobs_from_apify
from apify_recommendation_queue import get_apify_recommendation_queue
from ai_recommendation_service import AIRecommendationService
import os
import json
import re
from routes.helpers import get_user_id
# supabase imports removed
from skills_matching import SkillsMatchingService
from models import Skill, StudentSkill, OpportunitySkill, ExternalJob, ExternalJobSkill

student_bp = Blueprint('student', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt', 'png', 'jpg', 'jpeg'}
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

SECTION_CONFIG = {
    'education': {
        'model': StudentEducation,
        'fields': ['degree', 'institution', 'course', 'specialization', 'start_date', 'end_date', 'is_current', 'gpa', 'description', 'achievements'],
        'date_fields': ['start_date', 'end_date'],
        'bool_fields': ['is_current'],
        'order_by': StudentEducation.start_date.desc(),
    },
    'experiences': {
        'model': StudentExperience,
        'fields': ['company_name', 'designation', 'employment_type', 'start_date', 'end_date', 'is_current', 'location', 'description', 'technologies'],
        'date_fields': ['start_date', 'end_date'],
        'bool_fields': ['is_current'],
        'json_fields': ['technologies'],
        'order_by': StudentExperience.start_date.desc(),
    },
    'internships': {
        'model': StudentInternship,
        'fields': ['designation', 'organization', 'industry_sector', 'stipend', 'internship_type', 'start_date', 'end_date', 'is_current', 'country', 'state', 'city', 'mentor_name', 'mentor_contact', 'mentor_designation', 'description', 'technologies'],
        'date_fields': ['start_date', 'end_date'],
        'bool_fields': ['is_current'],
        'json_fields': ['technologies'],
        'order_by': StudentInternship.start_date.desc(),
    },
    'projects': {
        'model': StudentProject,
        'fields': ['title', 'organization', 'role', 'start_date', 'end_date', 'description', 'technologies', 'links'],
        'date_fields': ['start_date', 'end_date'],
        'json_fields': ['technologies', 'links'],
        'order_by': StudentProject.start_date.desc(),
    },
    'trainings': {
        'model': StudentTraining,
        'fields': ['title', 'provider', 'mode', 'start_date', 'end_date', 'description'],
        'date_fields': ['start_date', 'end_date'],
        'order_by': StudentTraining.start_date.desc(),
    },
    'certifications': {
        'model': StudentCertification,
        'fields': ['name', 'issuer', 'issue_date', 'expiry_date', 'credential_id', 'credential_url', 'description'],
        'date_fields': ['issue_date', 'expiry_date'],
        'order_by': StudentCertification.issue_date.desc(),
    },
    'publications': {
        'model': StudentPublication,
        'fields': ['title', 'publication_type', 'publisher', 'publication_date', 'url', 'description'],
        'date_fields': ['publication_date'],
        'order_by': StudentPublication.publication_date.desc(),
    },
    'positions': {
        'model': StudentPosition,
        'fields': ['title', 'organization', 'start_date', 'end_date', 'is_current', 'description'],
        'date_fields': ['start_date', 'end_date'],
        'bool_fields': ['is_current'],
        'order_by': StudentPosition.start_date.desc(),
    },
    'offers': {
        'model': StudentOffer,
        'fields': ['company_name', 'role', 'ctc', 'status', 'offer_date', 'joining_date', 'location', 'notes'],
        'date_fields': ['offer_date', 'joining_date'],
        'order_by': StudentOffer.offer_date.desc(),
    },
    'placement-policy': {
        'model': StudentPlacementPolicy,
        'fields': ['eligible_for_placements', 'interested_in_jobs', 'interested_in_internships', 'placement_policy_agreed', 'policy_version', 'policy_document_url'],
        'bool_fields': ['eligible_for_placements', 'interested_in_jobs', 'interested_in_internships', 'placement_policy_agreed'],
        'order_by': StudentPlacementPolicy.updated_at.desc(),
    },
    'academic-details': {
        'model': StudentAcademicDetail,
        'fields': ['degree_name', 'branch_name', 'batch_start_year', 'batch_end_year', 'semester_label', 'sgpa', 'closed_backlogs', 'live_backlogs', 'marksheet_file_path', 'display_order'],
        'order_by': StudentAcademicDetail.display_order.asc(),
    },
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def allowed_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

def _public_relative_path(*parts):
    return os.path.join('public', *parts).replace('\\', '/')

def _public_absolute_path(*parts):
    return os.path.join(current_app.root_path, 'public', *parts)

def _resolve_stored_file_path(path):
    if not path:
        return None
    normalized = str(path).replace('\\', '/')
    if normalized.startswith('http://') or normalized.startswith('https://'):
        return None
    if os.path.isabs(normalized):
        return normalized
    if normalized.startswith('public/'):
        return os.path.join(current_app.root_path, normalized)
    return os.path.join(current_app.root_path, normalized)

def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return None

def parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {'1', 'true', 'yes', 'y', 'on'}:
            return True
        if normalized in {'0', 'false', 'no', 'n', 'off', ''}:
            return False
    return bool(value)

def parse_int(value):
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

def normalize_json_field(value):
    if value is None:
        return json.dumps([])
    if isinstance(value, list):
        return json.dumps(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return json.dumps(parsed)
        except json.JSONDecodeError:
            pass
        parts = [part.strip() for part in value.split(',') if part.strip()]
        return json.dumps(parts)
    return json.dumps(value)

def assign_section_fields(instance, data, config):
    fields = config.get('fields', [])
    date_fields = set(config.get('date_fields', []))
    bool_fields = set(config.get('bool_fields', []))
    json_fields = set(config.get('json_fields', []))

    for field in fields:
        if field not in data:
            continue
        value = data[field]
        if field in date_fields:
            value = parse_date(value)
        elif field in bool_fields:
            value = parse_bool(value)
        elif field in json_fields:
            value = normalize_json_field(value)
        setattr(instance, field, value)

def parse_flexible_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    if not text:
        return None

    for date_format in (
        '%Y-%m-%d',
        '%Y/%m/%d',
        '%d-%m-%Y',
        '%d/%m/%Y',
        '%m/%d/%Y',
        '%Y-%m',
        '%m/%Y',
        '%b %Y',
        '%B %Y',
        '%Y',
    ):
        try:
            parsed = datetime.strptime(text, date_format)
            return parsed.date()
        except ValueError:
            continue
    return None

def _clean_text_value(value, max_len=1000):
    if value is None:
        return ''
    return str(value).strip()[:max_len]

def _to_string_list(value, limit=50):
    if not value:
        return []
    candidates = []
    if isinstance(value, list):
        candidates = value
    elif isinstance(value, str):
        candidates = [part.strip() for part in value.split(',')]
    else:
        candidates = [value]

    normalized = []
    seen = set()
    for item in candidates:
        text = str(item).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)
        if len(normalized) >= limit:
            break
    return normalized

def _normalize_module_date_text(value):
    parsed = parse_flexible_date(value)
    return parsed.isoformat() if parsed else ''

def _is_empty_for_payload(value):
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ''
    if isinstance(value, list):
        return len(value) == 0
    return False

def _identity_key_from_dict(data, fields):
    values = []
    for field in fields:
        value = data.get(field)
        if isinstance(value, list):
            norm = ','.join(sorted(str(item).strip().lower() for item in value if str(item).strip()))
        else:
            norm = str(value).strip().lower() if value is not None else ''
        values.append(norm)
    if not any(values):
        return None
    return '|'.join(values)

def _prepare_section_payload(section_key, raw_entry):
    config = SECTION_CONFIG.get(section_key, {})
    fields = config.get('fields', [])
    date_fields = set(config.get('date_fields', []))
    json_fields = set(config.get('json_fields', []))
    bool_fields = set(config.get('bool_fields', []))
    payload = {}

    for field in fields:
        if field not in raw_entry:
            continue
        value = raw_entry.get(field)

        if field in date_fields:
            normalized_date = _normalize_module_date_text(value)
            if normalized_date:
                payload[field] = normalized_date
            continue

        if field in json_fields:
            normalized_list = _to_string_list(value, limit=50)
            if normalized_list:
                payload[field] = normalized_list
            continue

        if field in bool_fields:
            payload[field] = parse_bool(value)
            continue

        if section_key == 'academic-details' and field in {'batch_start_year', 'batch_end_year', 'closed_backlogs', 'live_backlogs', 'display_order'}:
            parsed_number = parse_int(value)
            if parsed_number is not None:
                payload[field] = parsed_number
            continue

        if field == 'semester_label':
            normalized = _clean_text_value(value, max_len=20).upper()
            if normalized:
                numeric_to_roman = {
                    '1': 'I', '2': 'II', '3': 'III', '4': 'IV',
                    '5': 'V', '6': 'VI', '7': 'VII', '8': 'VIII',
                }
                normalized = numeric_to_roman.get(normalized, normalized)
                payload[field] = normalized
            continue

        if isinstance(value, (int, float)):
            payload[field] = value
            continue

        text = _clean_text_value(value, max_len=2000)
        if text:
            payload[field] = text

    return payload

def _upsert_section_entries_from_modules(profile_id, section_key, entries, required_fields, identity_fields):
    if not isinstance(entries, list):
        return {'added': 0, 'updated': 0, 'skipped': 0}

    config = SECTION_CONFIG.get(section_key)
    if not config:
        return {'added': 0, 'updated': 0, 'skipped': len(entries)}

    model = config['model']
    existing_entries = model.query.filter_by(student_id=profile_id).all()
    existing_map = {}
    for item in existing_entries:
        record = item.to_dict() if hasattr(item, 'to_dict') else {}
        key = _identity_key_from_dict(record, identity_fields)
        if key:
            existing_map[key] = item

    added = 0
    updated = 0
    skipped = 0
    for raw_entry in entries:
        if not isinstance(raw_entry, dict):
            skipped += 1
            continue

        payload = _prepare_section_payload(section_key, raw_entry)
        if any(_is_empty_for_payload(payload.get(field)) for field in required_fields):
            skipped += 1
            continue

        identity_key = _identity_key_from_dict(payload, identity_fields)
        if identity_key and identity_key in existing_map:
            entry = existing_map[identity_key]
            assign_section_fields(entry, payload, config)
            updated += 1
            continue

        entry = model(student_id=profile_id)
        assign_section_fields(entry, payload, config)
        db.session.add(entry)
        added += 1
        if identity_key:
            existing_map[identity_key] = entry

    return {'added': added, 'updated': updated, 'skipped': skipped}

def _split_full_name(name_value):
    text = _clean_text_value(name_value, max_len=200)
    if not text:
        return '', '', ''
    parts = [part for part in re.split(r'\s+', text) if part]
    if len(parts) == 1:
        return parts[0], '', ''
    if len(parts) == 2:
        return parts[0], '', parts[1]
    return parts[0], ' '.join(parts[1:-1]), parts[-1]

def _apply_profile_modules_from_resume(profile, modules):
    summary = {
        'profile_fields_updated': [],
        'skills_merged': 0,
        'interests_merged': 0,
        'sections': {},
        'total_added': 0,
        'total_updated': 0,
    }
    if not isinstance(modules, dict):
        return summary

    basic = modules.get('basic_profile') if isinstance(modules.get('basic_profile'), dict) else {}
    full_name = _clean_text_value(basic.get('full_name'), max_len=200)
    first_from_full, middle_from_full, last_from_full = _split_full_name(full_name)

    profile_field_specs = [
        ('first_name', basic.get('first_name') or first_from_full, 100),
        ('middle_name', basic.get('middle_name') or middle_from_full, 100),
        ('last_name', basic.get('last_name') or last_from_full, 100),
        ('phone', basic.get('phone'), 30),
        ('address', basic.get('address'), 1500),
        ('bio', basic.get('bio'), 2500),
        ('linkedin_url', basic.get('linkedin_url'), 255),
        ('github_url', basic.get('github_url'), 255),
        ('portfolio_url', basic.get('portfolio_url'), 255),
        ('course', basic.get('course'), 150),
        ('specialization', basic.get('specialization'), 150),
        ('gender', basic.get('gender'), 20),
    ]
    for field_name, value, max_len in profile_field_specs:
        normalized = _clean_text_value(value, max_len=max_len)
        if not normalized:
            continue
        current = getattr(profile, field_name, None)
        if _clean_text_value(current, max_len=max_len):
            continue
        setattr(profile, field_name, normalized)
        summary['profile_fields_updated'].append(field_name)

    dob_value = parse_flexible_date(basic.get('date_of_birth'))
    if dob_value and not profile.date_of_birth:
        profile.date_of_birth = dob_value
        summary['profile_fields_updated'].append('date_of_birth')

    parsed_skills = _to_string_list(basic.get('skills'), limit=60)
    if parsed_skills:
        existing_skills = _safe_json_list(profile.skills)
        merged_skills = []
        seen = set()
        for skill in existing_skills + parsed_skills:
            text = _clean_text_value(skill, max_len=120)
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            merged_skills.append(text)
        if merged_skills != existing_skills:
            profile.skills = json.dumps(merged_skills)
            summary['skills_merged'] = len(merged_skills)
            SkillsMatchingService.update_student_skills(profile.id, merged_skills, {})

    parsed_interests = _to_string_list(basic.get('interests'), limit=30)
    if parsed_interests:
        existing_interests = _safe_json_list(profile.interests)
        merged_interests = []
        seen = set()
        for interest in existing_interests + parsed_interests:
            text = _clean_text_value(interest, max_len=120)
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            merged_interests.append(text)
        if merged_interests != existing_interests:
            profile.interests = json.dumps(merged_interests)
            summary['interests_merged'] = len(merged_interests)

    section_specs = {
        'education': {'required_fields': ['degree', 'institution'], 'identity_fields': ['degree', 'institution', 'start_date']},
        'experiences': {'required_fields': ['company_name', 'designation'], 'identity_fields': ['company_name', 'designation', 'start_date']},
        'internships': {'required_fields': ['designation', 'organization'], 'identity_fields': ['designation', 'organization', 'start_date']},
        'projects': {'required_fields': ['title'], 'identity_fields': ['title', 'organization', 'start_date']},
        'trainings': {'required_fields': ['title'], 'identity_fields': ['title', 'provider', 'start_date']},
        'certifications': {'required_fields': ['name'], 'identity_fields': ['name', 'issuer', 'issue_date']},
        'publications': {'required_fields': ['title'], 'identity_fields': ['title', 'publisher', 'publication_date']},
        'positions': {'required_fields': ['title'], 'identity_fields': ['title', 'organization', 'start_date']},
        'offers': {'required_fields': ['company_name'], 'identity_fields': ['company_name', 'role', 'offer_date']},
        'academic-details': {'required_fields': ['semester_label'], 'identity_fields': ['semester_label']},
    }
    for section_key, spec in section_specs.items():
        data_key = section_key.replace('-', '_')
        entries = modules.get(data_key)
        if not isinstance(entries, list):
            continue
        outcome = _upsert_section_entries_from_modules(
            profile_id=profile.id,
            section_key=section_key,
            entries=entries,
            required_fields=spec['required_fields'],
            identity_fields=spec['identity_fields'],
        )
        if outcome['added'] or outcome['updated'] or outcome['skipped']:
            summary['sections'][section_key] = outcome
            summary['total_added'] += outcome['added']
            summary['total_updated'] += outcome['updated']

    placement_policy_data = modules.get('placement_policy')
    if isinstance(placement_policy_data, dict):
        placement_payload = _prepare_section_payload('placement-policy', placement_policy_data)
        if placement_payload:
            existing_policy = StudentPlacementPolicy.query.filter_by(student_id=profile.id).first()
            if existing_policy:
                assign_section_fields(existing_policy, placement_payload, SECTION_CONFIG['placement-policy'])
                summary['sections']['placement-policy'] = {'added': 0, 'updated': 1, 'skipped': 0}
                summary['total_updated'] += 1
            else:
                entry = StudentPlacementPolicy(student_id=profile.id)
                assign_section_fields(entry, placement_payload, SECTION_CONFIG['placement-policy'])
                db.session.add(entry)
                summary['sections']['placement-policy'] = {'added': 1, 'updated': 0, 'skipped': 0}
                summary['total_added'] += 1

    profile.updated_at = datetime.utcnow()
    return summary

def serialize_all_sections(profile):
    sections = {}
    for key, config in SECTION_CONFIG.items():
        model = config['model']
        query = model.query.filter_by(student_id=profile.id)
        order_by = config.get('order_by')
        if order_by is not None:
            query = query.order_by(order_by)
        sections[key] = [entry.to_dict() for entry in query.all()]
    attachments = StudentAttachment.query.filter_by(student_id=profile.id).all()
    sections['attachments'] = [attachment.to_dict() for attachment in attachments]
    return sections

def _safe_json_list(value):
    if not value:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            return []
    return []

def _has_value(value):
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True

def calculate_profile_completion(profile, sections):
    """
    Checklist-based completion score.
    Completion is derived from checklist coverage so the percentage remains
    consistent with the visible criteria count.
    """
    education_entries = sections.get('education') or []
    internship_entries = sections.get('internships') or []
    experience_entries = sections.get('experiences') or []
    project_entries = sections.get('projects') or []

    profile_skills = [skill for skill in _safe_json_list(profile.skills) if _has_value(skill)]
    has_mapped_skills = StudentSkill.query.filter_by(student_id=profile.id).first() is not None

    def _entry_has_skills(entry):
        if not isinstance(entry, dict):
            return False
        for key in ('technologies', 'skills'):
            value = entry.get(key)
            if isinstance(value, list):
                if any(_has_value(item) for item in value):
                    return True
            elif _has_value(value):
                return True
        return False

    has_section_skills = any(_entry_has_skills(entry) for entry in (internship_entries + experience_entries + project_entries))
    has_skills = bool(profile_skills) or has_mapped_skills or has_section_skills

    has_course = _has_value(profile.course) or any(_has_value(entry.get('course')) for entry in education_entries if isinstance(entry, dict))
    has_specialization = _has_value(profile.specialization) or any(
        _has_value(entry.get('specialization')) for entry in education_entries if isinstance(entry, dict)
    )

    has_core_experience = bool(internship_entries or experience_entries or project_entries)
    has_additional_achievements = bool(
        sections.get('trainings')
        or sections.get('certifications')
        or sections.get('publications')
        or sections.get('positions')
        or sections.get('offers')
        or sections.get('placement-policy')
        or sections.get('academic-details')
        or sections.get('attachments')
    )

    # Registration creates a minimal StudentProfile row. Keep completion at 0%
    # until the student starts filling profile-specific details.
    has_profile_specific_fields = any(
        (
            _has_value(profile.course),
            _has_value(profile.specialization),
            bool(profile.date_of_birth),
            _has_value(profile.prn_number),
            _has_value(profile.bio),
            _has_value(profile.resume_path),
            _has_value(profile.linkedin_url),
            _has_value(profile.github_url),
            _has_value(profile.portfolio_url),
            _has_value(profile.gender),
            bool(_safe_json_list(profile.interests)),
            has_skills,
            bool(education_entries),
            has_core_experience,
            has_additional_achievements,
        )
    )
    profile_was_edited = bool(
        profile.updated_at
        and profile.created_at
        and profile.updated_at > profile.created_at
    )
    profile_started = has_profile_specific_fields or profile_was_edited

    criteria = [
        {'label': 'Full name', 'done': _has_value(profile.first_name) and _has_value(profile.last_name)},
        {'label': 'Phone number', 'done': _has_value(profile.phone)},
        {'label': 'Course/branch', 'done': has_course},
        {'label': 'Specialization/class', 'done': has_specialization},
        {'label': 'Date of birth', 'done': bool(profile.date_of_birth)},
        {'label': 'Address', 'done': _has_value(profile.address)},
        {'label': 'Profile bio', 'done': _has_value(profile.bio)},
        {'label': 'PRN number', 'done': _has_value(profile.prn_number)},
        {'label': 'Skills', 'done': has_skills},
        {'label': 'Education section', 'done': bool(education_entries)},
        {
            'label': 'Internship/experience/project section',
            'done': has_core_experience,
        },
        {'label': 'Resume upload', 'done': _has_value(profile.resume_path)},
        {'label': 'Additional achievements', 'done': has_additional_achievements},
    ]

    if not profile_started:
        return {
            'percentage': 0,
            'completed_criteria': 0,
            'total_criteria': len(criteria),
            'missing_criteria': [item['label'] for item in criteria],
        }

    completed_criteria = sum(1 for item in criteria if item['done'])
    total_criteria = len(criteria)
    missing_criteria = [item['label'] for item in criteria if not item['done']]
    percentage = int(round((completed_criteria / total_criteria) * 100)) if total_criteria else 0

    return {
        'percentage': max(0, min(100, percentage)),
        'completed_criteria': completed_criteria,
        'total_criteria': total_criteria,
        'missing_criteria': missing_criteria,
    }

def friendly_application_status(status: str) -> str:
    mapping = {
        'pending': 'Next steps awaited',
        'shortlisted': 'Shortlisted',
        'rejected': 'Not selected',
        'interview': 'Interview scheduled',
        'accepted': 'Offer received',
        'withdrawn': 'Withdrawn',
    }
    return mapping.get(status, status.title() if status else 'In progress')

def get_student_profile():
    user_id = get_user_id()
    user = User.query.get(user_id)
    if not user or user.role != 'student':
        return None, jsonify({'error': 'Unauthorized'}), 403
    profile = user.student_profile
    if not profile:
        return None, jsonify({'error': 'Profile not found'}), 404
    return profile, None, None


def _build_resume_analysis_payload(profile, data):
    extracted_skills = data.get('extractedSkills', [])
    if not isinstance(extracted_skills, list):
        extracted_skills = []

    provided_keywords = data.get('keywords', extracted_skills)
    if not isinstance(provided_keywords, list):
        provided_keywords = extracted_skills

    suggested_roles = data.get('modelSuggestedRoles', [])
    if not isinstance(suggested_roles, list):
        suggested_roles = []

    tech_stack = data.get('techStack', [])
    if not isinstance(tech_stack, list):
        tech_stack = []

    resume_analysis = {
        'skills': extracted_skills,
        'keywords': provided_keywords,
        'experience_years': data.get('extractedExperience', 0),
        'professional_summary': data.get('summary', ''),
        'recommended_roles': suggested_roles,
        'tech_stack': tech_stack,
        'career_level': data.get('careerLevel', 'entry')
    }

    # Fallback to saved profile skills if extracted resume skills are missing.
    if not resume_analysis['skills']:
        student_skills = StudentSkill.query.filter_by(student_id=profile.id).all()
        saved_skills = [ss.skill.name for ss in student_skills if ss.skill]
        if saved_skills:
            resume_analysis['skills'] = saved_skills
            if not resume_analysis['keywords']:
                resume_analysis['keywords'] = saved_skills

    return resume_analysis


def _parse_top_n(default_value=200):
    try:
        top_n = int(request.args.get('topN', default_value))
    except (TypeError, ValueError):
        top_n = default_value
    return min(max(top_n, 1), 500)

@student_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status
    
    profile_dict = profile.to_dict()
    
    # Get skills from StudentSkill table (technical and non-technical)
    student_skills = StudentSkill.query.filter_by(student_id=profile.id).all()
    technical_skills = []
    non_technical_skills = []
    
    for ss in student_skills:
        skill = Skill.query.get(ss.skill_id)
        if skill:
            skill_data = {
                'id': skill.id,
                'name': skill.name,
                'category': skill.category,
                'proficiency_level': ss.proficiency_level,
                'years_of_experience': ss.years_of_experience
            }
            # Categorize as technical or non-technical based on category
            if skill.category in ['programming', 'framework', 'database', 'cloud', 'devops', 'mobile', 'data-science', 'web', 'library']:
                technical_skills.append(skill_data)
            else:
                non_technical_skills.append(skill_data)
    
    profile_dict['technical_skills'] = technical_skills
    profile_dict['non_technical_skills'] = non_technical_skills
    profile_dict['has_skills'] = len(student_skills) > 0  # Check if skills are set
    
    return jsonify(profile_dict), 200

@student_bp.route('/profile/full', methods=['GET'])
@jwt_required()
def get_full_profile_data():
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status

    sections = serialize_all_sections(profile)
    stats = {key: len(value) for key, value in sections.items()}
    
    completion_data = calculate_profile_completion(profile, sections)

    profile_payload = profile.to_dict()
    linked_student_skills = StudentSkill.query.filter_by(student_id=profile.id).all()
    linked_skill_names = [ss.skill.name for ss in linked_student_skills if ss.skill and ss.skill.name]
    if linked_skill_names:
        # Keep skills shown in profile/full consistent with canonical student_skills mappings.
        profile_payload['skills'] = list(dict.fromkeys(linked_skill_names))

    return jsonify({
        'profile': profile_payload,
        'sections': sections,
        'resume_path': profile.resume_path,
        'stats': stats,
        'completion_percentage': completion_data['percentage'],
        'completion_breakdown': {
            'completed_criteria': completion_data['completed_criteria'],
            'total_criteria': completion_data['total_criteria'],
            'missing_criteria': completion_data['missing_criteria'],
        }
    }), 200

@student_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    try:
        profile, error_response, status = get_student_profile()
        if error_response:
            return error_response, status

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({'error': 'Invalid request payload'}), 400

        def _to_text(value):
            if value is None:
                return ''
            if isinstance(value, str):
                return value.strip()
            return str(value).strip()

        updated_fields = []

        if 'first_name' in data:
            profile.first_name = _to_text(data['first_name'])
            updated_fields.append('first_name')
        if 'last_name' in data:
            profile.last_name = _to_text(data['last_name'])
            updated_fields.append('last_name')
        if 'middle_name' in data:
            profile.middle_name = _to_text(data['middle_name'])
            updated_fields.append('middle_name')
        if 'phone' in data:
            profile.phone = _to_text(data['phone'])
            updated_fields.append('phone')
        if 'date_of_birth' in data:
            dob = _to_text(data.get('date_of_birth'))
            profile.date_of_birth = parse_date(dob) if dob else None
            updated_fields.append('date_of_birth')
        if 'address' in data:
            profile.address = _to_text(data['address'])
            updated_fields.append('address')
        if 'prn_number' in data:
            profile.prn_number = _to_text(data['prn_number'])
            updated_fields.append('prn_number')
        if 'course' in data:
            profile.course = _to_text(data['course'])
            updated_fields.append('course')
        if 'specialization' in data:
            profile.specialization = _to_text(data['specialization'])
            updated_fields.append('specialization')
        if 'gender' in data:
            profile.gender = _to_text(data['gender'])
            updated_fields.append('gender')
        if 'education' in data:
            profile.education = json.dumps(data['education'])
            updated_fields.append('education')
        if 'skills' in data:
            normalized_skills_json = normalize_json_field(data['skills'])
            profile.skills = normalized_skills_json
            updated_fields.append('skills')
            try:
                normalized_skills_list = json.loads(normalized_skills_json)
            except (TypeError, ValueError, json.JSONDecodeError):
                normalized_skills_list = []

            if normalized_skills_list:
                SkillsMatchingService.update_student_skills(
                    profile.id,
                    normalized_skills_list,
                    {}
                )
            else:
                StudentSkill.query.filter_by(student_id=profile.id).delete(synchronize_session=False)
        if 'technical_skills' in data or 'non_technical_skills' in data:
            # Update skills from the new skills section
            technical_skills = data.get('technical_skills', [])
            non_technical_skills = data.get('non_technical_skills', [])
            
            # Combine all skill names
            all_skill_names = []
            proficiency_levels = {}
            
            for skill_data in technical_skills + non_technical_skills:
                if isinstance(skill_data, dict):
                    skill_name = skill_data.get('name') or skill_data.get('skill')
                    if skill_name:
                        all_skill_names.append(skill_name)
                        if 'proficiency_level' in skill_data:
                            proficiency_levels[skill_name] = skill_data['proficiency_level']
                elif isinstance(skill_data, str):
                    all_skill_names.append(skill_data)
            
            # Update skills using SkillsMatchingService
            if all_skill_names:
                SkillsMatchingService.update_student_skills(
                    profile.id,
                    all_skill_names,
                    proficiency_levels
                )
            profile.skills = json.dumps(all_skill_names)
            updated_fields.append('skills')
        if 'interests' in data:
            profile.interests = normalize_json_field(data['interests'])
            updated_fields.append('interests')
        if 'bio' in data:
            profile.bio = _to_text(data['bio'])
            updated_fields.append('bio')
        if 'linkedin_url' in data:
            profile.linkedin_url = _to_text(data['linkedin_url'])
            updated_fields.append('linkedin_url')
        if 'github_url' in data:
            profile.github_url = _to_text(data['github_url'])
            updated_fields.append('github_url')
        if 'portfolio_url' in data:
            profile.portfolio_url = _to_text(data['portfolio_url'])
            updated_fields.append('portfolio_url')
        if 'profile_picture' in data:
            profile.profile_picture = _to_text(data['profile_picture'])
            updated_fields.append('profile_picture')

        if not profile.first_name or not profile.last_name:
            db.session.rollback()
            return jsonify({'error': 'first_name and last_name are required'}), 400
        if not profile.phone:
            db.session.rollback()
            return jsonify({'error': 'phone is required'}), 400
        if not profile.course:
            db.session.rollback()
            return jsonify({'error': 'course is required'}), 400
        
        profile.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Profile updated successfully',
            'profile': profile.to_dict(),
            'updated_fields': updated_fields,
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
#
# ---------- Rich Profile Sections ----------
#

def _ensure_entry(query, entry_id, student_id):
    entry = query.filter_by(id=entry_id, student_id=student_id).first()
    if not entry:
        return None, jsonify({'error': 'Record not found'}), 404
    return entry, None, None

@student_bp.route('/education', methods=['GET', 'POST'])
@jwt_required()
def education_collection():
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status

    if request.method == 'GET':
        entries = StudentEducation.query.filter_by(student_id=profile.id).order_by(StudentEducation.start_date.desc().nullslast()).all()
        return jsonify([e.to_dict() for e in entries]), 200

    data = request.get_json()
    required = ['degree', 'institution']
    if any(not data.get(field) for field in required):
        return jsonify({'error': 'degree and institution are required'}), 400
    entry = StudentEducation(
        student_id=profile.id,
        degree=data.get('degree'),
        institution=data.get('institution'),
        course=data.get('course'),
        specialization=data.get('specialization'),
        start_date=parse_date(data.get('start_date')),
        end_date=parse_date(data.get('end_date')),
        is_current=data.get('is_current', False),
        gpa=data.get('gpa'),
        description=data.get('description'),
        achievements=data.get('achievements')
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify({'message': 'Education added', 'education': entry.to_dict()}), 201

@student_bp.route('/education/<int:entry_id>', methods=['PUT', 'DELETE'])
@jwt_required()
def education_detail(entry_id):
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status

    entry, error_response, status = _ensure_entry(StudentEducation.query, entry_id, profile.id)
    if error_response:
        return error_response, status

    if request.method == 'DELETE':
        db.session.delete(entry)
        db.session.commit()
        return jsonify({'message': 'Education removed'}), 200

    data = request.get_json()
    for field in ['degree', 'institution', 'course', 'specialization', 'gpa', 'description', 'achievements']:
        if field in data:
            setattr(entry, field, data[field])
    if 'is_current' in data:
        entry.is_current = data['is_current']
    if 'start_date' in data:
        entry.start_date = parse_date(data.get('start_date'))
    if 'end_date' in data:
        entry.end_date = parse_date(data.get('end_date'))
    db.session.commit()
    return jsonify({'message': 'Education updated', 'education': entry.to_dict()}), 200

def _create_internship(profile, data):
    if not isinstance(data, dict):
        return None, jsonify({'error': 'Invalid request body'}), 400

    designation = _clean_text_value(data.get('designation'), max_len=255)
    organization = _clean_text_value(data.get('organization'), max_len=255)
    if not designation or not organization:
        return None, jsonify({'error': 'designation and organization are required'}), 400

    is_current = parse_bool(data.get('is_current', False))
    start_date = parse_date(data.get('start_date'))
    end_date = parse_date(data.get('end_date'))
    if is_current:
        end_date = None
    if start_date and end_date and end_date < start_date:
        return None, jsonify({'error': 'end_date cannot be before start_date'}), 400

    entry = StudentInternship(
        student_id=profile.id,
        designation=designation,
        organization=organization,
        industry_sector=_clean_text_value(data.get('industry_sector'), max_len=150),
        stipend=_clean_text_value(data.get('stipend'), max_len=100),
        internship_type=_clean_text_value(data.get('internship_type'), max_len=100),
        start_date=start_date,
        end_date=end_date,
        is_current=is_current,
        country=_clean_text_value(data.get('country'), max_len=100),
        state=_clean_text_value(data.get('state'), max_len=100),
        city=_clean_text_value(data.get('city'), max_len=100),
        mentor_name=_clean_text_value(data.get('mentor_name'), max_len=150),
        mentor_contact=_clean_text_value(data.get('mentor_contact'), max_len=100),
        mentor_designation=_clean_text_value(data.get('mentor_designation'), max_len=150),
        description=_clean_text_value(data.get('description'), max_len=5000),
        technologies=json.dumps(_to_string_list(data.get('technologies'), limit=50)),
    )
    return entry, None, None

@student_bp.route('/internships', methods=['GET', 'POST'])
@jwt_required()
def internships_collection():
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status

    if request.method == 'GET':
        entries = StudentInternship.query.filter_by(student_id=profile.id).order_by(StudentInternship.start_date.desc().nullslast()).all()
        return jsonify([e.to_dict() for e in entries]), 200

    data = _get_json_payload()
    if not data:
        return jsonify({'error': 'Invalid request body'}), 400
    entry, error_response, status = _create_internship(profile, data)
    if error_response:
        return error_response, status
    try:
        db.session.add(entry)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({'error': 'Failed to save internship entry'}), 500
    return jsonify({'message': 'Internship added', 'internship': entry.to_dict()}), 201

@student_bp.route('/internships/<int:entry_id>', methods=['PUT', 'DELETE'])
@jwt_required()
def internships_detail(entry_id):
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status

    entry, error_response, status = _ensure_entry(StudentInternship.query, entry_id, profile.id)
    if error_response:
        return error_response, status

    if request.method == 'DELETE':
        try:
            db.session.delete(entry)
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            return jsonify({'error': 'Failed to remove internship entry'}), 500
        return jsonify({'message': 'Internship removed'}), 200

    data = _get_json_payload()
    if not data:
        return jsonify({'error': 'Invalid request body'}), 400

    if 'designation' in data:
        designation = _clean_text_value(data.get('designation'), max_len=255)
        if not designation:
            return jsonify({'error': 'designation is required'}), 400
        entry.designation = designation
    if 'organization' in data:
        organization = _clean_text_value(data.get('organization'), max_len=255)
        if not organization:
            return jsonify({'error': 'organization is required'}), 400
        entry.organization = organization

    for field in [
        'industry_sector', 'stipend', 'internship_type',
        'country', 'state', 'city', 'mentor_name', 'mentor_contact', 'mentor_designation',
        'description'
    ]:
        if field in data:
            max_length = {
                'industry_sector': 150,
                'stipend': 100,
                'internship_type': 100,
                'country': 100,
                'state': 100,
                'city': 100,
                'mentor_name': 150,
                'mentor_contact': 100,
                'mentor_designation': 150,
                'description': 5000,
            }.get(field, 255)
            setattr(entry, field, _clean_text_value(data[field], max_len=max_length))
    if 'technologies' in data:
        entry.technologies = json.dumps(_to_string_list(data.get('technologies'), limit=50))
    if 'is_current' in data:
        entry.is_current = parse_bool(data.get('is_current'))
        if entry.is_current:
            entry.end_date = None
    if 'start_date' in data:
        entry.start_date = parse_date(data.get('start_date'))
    if 'end_date' in data and not entry.is_current:
        entry.end_date = parse_date(data.get('end_date'))

    if entry.start_date and entry.end_date and entry.end_date < entry.start_date:
        return jsonify({'error': 'end_date cannot be before start_date'}), 400

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({'error': 'Failed to update internship entry'}), 500
    return jsonify({'message': 'Internship updated', 'internship': entry.to_dict()}), 200

def _generic_collection(model, order_by=None):
    def decorator(func):
        return func
    return decorator

def _handle_generic_get(model, student_id, order_by=None):
    query = model.query.filter_by(student_id=student_id)
    if order_by is not None:
        query = query.order_by(order_by)
    return [entry.to_dict() for entry in query.all()]

def _update_entry(entry, data, field_names):
    for field in field_names:
        if field in data:
            setattr(entry, field, data[field])

def _get_json_payload():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}

def _normalize_experience_payload(data):
    company_name = _clean_text_value(data.get('company_name'), max_len=255)
    designation = _clean_text_value(data.get('designation'), max_len=255)
    employment_type = _clean_text_value(data.get('employment_type'), max_len=100)
    location = _clean_text_value(data.get('location'), max_len=255)
    description = _clean_text_value(data.get('description'), max_len=5000)
    technologies = _to_string_list(data.get('technologies'), limit=50)
    is_current = parse_bool(data.get('is_current', False))
    start_date = parse_date(data.get('start_date'))
    end_date = parse_date(data.get('end_date'))

    if is_current:
        end_date = None

    return {
        'company_name': company_name,
        'designation': designation,
        'employment_type': employment_type,
        'start_date': start_date,
        'end_date': end_date,
        'is_current': is_current,
        'location': location,
        'description': description,
        'technologies': technologies,
    }

@student_bp.route('/experience', methods=['GET', 'POST'])
@student_bp.route('/experiences', methods=['GET', 'POST'])
@jwt_required()
def experiences_collection():
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status

    if request.method == 'GET':
        return jsonify(_handle_generic_get(StudentExperience, profile.id, StudentExperience.start_date.desc().nullslast())), 200

    data = _get_json_payload()
    if not data:
        return jsonify({'error': 'Invalid request body'}), 400

    payload = _normalize_experience_payload(data)
    if not payload['company_name'] or not payload['designation']:
        return jsonify({'error': 'company_name and designation are required'}), 400

    if payload['start_date'] and payload['end_date'] and payload['end_date'] < payload['start_date']:
        return jsonify({'error': 'end_date cannot be before start_date'}), 400

    entry = StudentExperience(
        student_id=profile.id,
        company_name=payload['company_name'],
        designation=payload['designation'],
        employment_type=payload['employment_type'],
        start_date=payload['start_date'],
        end_date=payload['end_date'],
        is_current=payload['is_current'],
        location=payload['location'],
        description=payload['description'],
        technologies=json.dumps(payload['technologies']),
    )

    try:
        db.session.add(entry)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({'error': 'Failed to save experience entry'}), 500
    return jsonify({'message': 'Experience added', 'experience': entry.to_dict()}), 201

@student_bp.route('/experience/<int:entry_id>', methods=['PUT', 'DELETE'])
@student_bp.route('/experiences/<int:entry_id>', methods=['PUT', 'DELETE'])
@jwt_required()
def experiences_detail(entry_id):
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status

    entry, error_response, status = _ensure_entry(StudentExperience.query, entry_id, profile.id)
    if error_response:
        return error_response, status

    if request.method == 'DELETE':
        try:
            db.session.delete(entry)
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            return jsonify({'error': 'Failed to remove experience entry'}), 500
        return jsonify({'message': 'Experience removed'}), 200

    data = _get_json_payload()
    if not data:
        return jsonify({'error': 'Invalid request body'}), 400

    if 'company_name' in data:
        company_name = _clean_text_value(data.get('company_name'), max_len=255)
        if not company_name:
            return jsonify({'error': 'company_name is required'}), 400
        entry.company_name = company_name
    if 'designation' in data:
        designation = _clean_text_value(data.get('designation'), max_len=255)
        if not designation:
            return jsonify({'error': 'designation is required'}), 400
        entry.designation = designation
    if 'employment_type' in data:
        entry.employment_type = _clean_text_value(data.get('employment_type'), max_len=100)
    if 'location' in data:
        entry.location = _clean_text_value(data.get('location'), max_len=255)
    if 'description' in data:
        entry.description = _clean_text_value(data.get('description'), max_len=5000)
    if 'technologies' in data:
        entry.technologies = json.dumps(_to_string_list(data.get('technologies'), limit=50))
    if 'is_current' in data:
        entry.is_current = parse_bool(data.get('is_current'))
        if entry.is_current:
            entry.end_date = None
    if 'start_date' in data:
        entry.start_date = parse_date(data.get('start_date'))
    if 'end_date' in data and not entry.is_current:
        entry.end_date = parse_date(data.get('end_date'))

    if entry.start_date and entry.end_date and entry.end_date < entry.start_date:
        return jsonify({'error': 'end_date cannot be before start_date'}), 400

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({'error': 'Failed to update experience entry'}), 500
    return jsonify({'message': 'Experience updated', 'experience': entry.to_dict()}), 200

@student_bp.route('/projects', methods=['GET', 'POST'])
@jwt_required()
def projects_collection():
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status

    if request.method == 'GET':
        entries = StudentProject.query.filter_by(student_id=profile.id).order_by(StudentProject.start_date.desc().nullslast()).all()
        return jsonify([e.to_dict() for e in entries]), 200

    data = request.get_json()
    if not data.get('title'):
        return jsonify({'error': 'title is required'}), 400
    entry = StudentProject(
        student_id=profile.id,
        title=data.get('title'),
        organization=data.get('organization'),
        role=data.get('role'),
        start_date=parse_date(data.get('start_date')),
        end_date=parse_date(data.get('end_date')),
        description=data.get('description'),
        technologies=json.dumps(data.get('technologies', [])),
        links=json.dumps(data.get('links', []))
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify({'message': 'Project added', 'project': entry.to_dict()}), 201

@student_bp.route('/projects/<int:entry_id>', methods=['PUT', 'DELETE'])
@jwt_required()
def projects_detail(entry_id):
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status

    entry, error_response, status = _ensure_entry(StudentProject.query, entry_id, profile.id)
    if error_response:
        return error_response, status

    if request.method == 'DELETE':
        db.session.delete(entry)
        db.session.commit()
        return jsonify({'message': 'Project removed'}), 200

    data = request.get_json()
    for field in ['title', 'organization', 'role', 'description']:
        if field in data:
            setattr(entry, field, data[field])
    if 'technologies' in data:
        entry.technologies = json.dumps(data.get('technologies', []))
    if 'links' in data:
        entry.links = json.dumps(data.get('links', []))
    if 'start_date' in data:
        entry.start_date = parse_date(data.get('start_date'))
    if 'end_date' in data:
        entry.end_date = parse_date(data.get('end_date'))
    db.session.commit()
    return jsonify({'message': 'Project updated', 'project': entry.to_dict()}), 200

@student_bp.route('/trainings', methods=['GET', 'POST'])
@jwt_required()
def trainings_collection():
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status

    if request.method == 'GET':
        entries = StudentTraining.query.filter_by(student_id=profile.id).order_by(StudentTraining.start_date.desc().nullslast()).all()
        return jsonify([e.to_dict() for e in entries]), 200

    data = request.get_json()
    if not data.get('title'):
        return jsonify({'error': 'title is required'}), 400
    entry = StudentTraining(
        student_id=profile.id,
        title=data.get('title'),
        provider=data.get('provider'),
        mode=data.get('mode'),
        start_date=parse_date(data.get('start_date')),
        end_date=parse_date(data.get('end_date')),
        description=data.get('description')
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify({'message': 'Training added', 'training': entry.to_dict()}), 201

@student_bp.route('/trainings/<int:entry_id>', methods=['PUT', 'DELETE'])
@jwt_required()
def trainings_detail(entry_id):
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status

    entry, error_response, status = _ensure_entry(StudentTraining.query, entry_id, profile.id)
    if error_response:
        return error_response, status

    if request.method == 'DELETE':
        db.session.delete(entry)
        db.session.commit()
        return jsonify({'message': 'Training removed'}), 200

    data = request.get_json()
    for field in ['title', 'provider', 'mode', 'description']:
        if field in data:
            setattr(entry, field, data[field])
    if 'start_date' in data:
        entry.start_date = parse_date(data.get('start_date'))
    if 'end_date' in data:
        entry.end_date = parse_date(data.get('end_date'))
    db.session.commit()
    return jsonify({'message': 'Training updated', 'training': entry.to_dict()}), 200

@student_bp.route('/certifications', methods=['GET', 'POST'])
@jwt_required()
def certifications_collection():
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status

    if request.method == 'GET':
        entries = StudentCertification.query.filter_by(student_id=profile.id).order_by(StudentCertification.issue_date.desc().nullslast()).all()
        return jsonify([e.to_dict() for e in entries]), 200

    data = request.get_json()
    if not data.get('name'):
        return jsonify({'error': 'name is required'}), 400
    entry = StudentCertification(
        student_id=profile.id,
        name=data.get('name'),
        issuer=data.get('issuer'),
        issue_date=parse_date(data.get('issue_date')),
        expiry_date=parse_date(data.get('expiry_date')),
        credential_id=data.get('credential_id'),
        credential_url=data.get('credential_url'),
        description=data.get('description')
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify({'message': 'Certification added', 'certification': entry.to_dict()}), 201

@student_bp.route('/certifications/<int:entry_id>', methods=['PUT', 'DELETE'])
@jwt_required()
def certifications_detail(entry_id):
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status

    entry, error_response, status = _ensure_entry(StudentCertification.query, entry_id, profile.id)
    if error_response:
        return error_response, status

    if request.method == 'DELETE':
        db.session.delete(entry)
        db.session.commit()
        return jsonify({'message': 'Certification removed'}), 200

    data = request.get_json()
    for field in ['name', 'issuer', 'credential_id', 'credential_url', 'description']:
        if field in data:
            setattr(entry, field, data[field])
    if 'issue_date' in data:
        entry.issue_date = parse_date(data.get('issue_date'))
    if 'expiry_date' in data:
        entry.expiry_date = parse_date(data.get('expiry_date'))
    db.session.commit()
    return jsonify({'message': 'Certification updated', 'certification': entry.to_dict()}), 200

@student_bp.route('/publications', methods=['GET', 'POST'])
@jwt_required()
def publications_collection():
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status

    if request.method == 'GET':
        entries = StudentPublication.query.filter_by(student_id=profile.id).order_by(StudentPublication.publication_date.desc().nullslast()).all()
        return jsonify([e.to_dict() for e in entries]), 200

    data = request.get_json()
    if not data.get('title'):
        return jsonify({'error': 'title is required'}), 400
    entry = StudentPublication(
        student_id=profile.id,
        title=data.get('title'),
        publication_type=data.get('publication_type'),
        publisher=data.get('publisher'),
        publication_date=parse_date(data.get('publication_date')),
        url=data.get('url'),
        description=data.get('description')
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify({'message': 'Publication added', 'publication': entry.to_dict()}), 201

@student_bp.route('/publications/<int:entry_id>', methods=['PUT', 'DELETE'])
@jwt_required()
def publications_detail(entry_id):
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status

    entry, error_response, status = _ensure_entry(StudentPublication.query, entry_id, profile.id)
    if error_response:
        return error_response, status

    if request.method == 'DELETE':
        db.session.delete(entry)
        db.session.commit()
        return jsonify({'message': 'Publication removed'}), 200

    data = request.get_json()
    for field in ['title', 'publication_type', 'publisher', 'url', 'description']:
        if field in data:
            setattr(entry, field, data[field])
    if 'publication_date' in data:
        entry.publication_date = parse_date(data.get('publication_date'))
    db.session.commit()
    return jsonify({'message': 'Publication updated', 'publication': entry.to_dict()}), 200

@student_bp.route('/positions', methods=['GET', 'POST'])
@jwt_required()
def positions_collection():
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status

    if request.method == 'GET':
        entries = StudentPosition.query.filter_by(student_id=profile.id).order_by(StudentPosition.start_date.desc().nullslast()).all()
        return jsonify([e.to_dict() for e in entries]), 200

    data = request.get_json()
    if not data.get('title'):
        return jsonify({'error': 'title is required'}), 400
    entry = StudentPosition(
        student_id=profile.id,
        title=data.get('title'),
        organization=data.get('organization'),
        start_date=parse_date(data.get('start_date')),
        end_date=parse_date(data.get('end_date')),
        is_current=data.get('is_current', False),
        description=data.get('description')
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify({'message': 'Position added', 'position': entry.to_dict()}), 201

@student_bp.route('/positions/<int:entry_id>', methods=['PUT', 'DELETE'])
@jwt_required()
def positions_detail(entry_id):
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status

    entry, error_response, status = _ensure_entry(StudentPosition.query, entry_id, profile.id)
    if error_response:
        return error_response, status

    if request.method == 'DELETE':
        db.session.delete(entry)
        db.session.commit()
        return jsonify({'message': 'Position removed'}), 200

    data = request.get_json()
    for field in ['title', 'organization', 'description']:
        if field in data:
            setattr(entry, field, data[field])
    if 'is_current' in data:
        entry.is_current = data['is_current']
    if 'start_date' in data:
        entry.start_date = parse_date(data.get('start_date'))
    if 'end_date' in data:
        entry.end_date = parse_date(data.get('end_date'))
    db.session.commit()
    return jsonify({'message': 'Position updated', 'position': entry.to_dict()}), 200

@student_bp.route('/attachments', methods=['GET', 'POST'])
@jwt_required()
def attachments_collection():
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status

    if request.method == 'GET':
        entries = StudentAttachment.query.filter_by(student_id=profile.id).all()
        return jsonify([e.to_dict() for e in entries]), 200

    # Handle file upload (form-data)
    if 'file' in request.files:
        upload = request.files['file']
        if upload.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        filename = secure_filename(upload.filename)

        # Store in local public filesystem
        attachments_dir = _public_absolute_path('attachments')
        os.makedirs(attachments_dir, exist_ok=True)
        filepath_abs = os.path.join(
            attachments_dir,
            f"{profile.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename}",
        )
        upload.save(filepath_abs)
        file_url = _public_relative_path('attachments', os.path.basename(filepath_abs))

        entry = StudentAttachment(
            student_id=profile.id,
            title=request.form.get('title', filename),
            file_path=file_url,
            attachment_type=request.form.get('attachment_type', 'document'),
        )
        db.session.add(entry)
        db.session.commit()
        return jsonify({'message': 'Attachment uploaded', 'attachment': entry.to_dict()}), 201

    data = request.get_json() or {}
    if not data.get('title') or not data.get('file_path'):
        return jsonify({'error': 'title and file_path are required'}), 400
    entry = StudentAttachment(
        student_id=profile.id,
        title=data.get('title'),
        file_path=data.get('file_path'),
        attachment_type=data.get('attachment_type')
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify({'message': 'Attachment added', 'attachment': entry.to_dict()}), 201

@student_bp.route('/attachments/<int:entry_id>', methods=['PUT', 'DELETE'])
@jwt_required()
def attachments_detail(entry_id):
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status

    entry, error_response, status = _ensure_entry(StudentAttachment.query, entry_id, profile.id)
    if error_response:
        return error_response, status

    if request.method == 'DELETE':
        # Remove from local filesystem
        if entry.file_path and os.path.exists(entry.file_path):
            try:
                os.remove(entry.file_path)
            except OSError:
                pass
        db.session.delete(entry)
        db.session.commit()
        return jsonify({'message': 'Attachment removed'}), 200

    data = request.get_json()
    for field in ['title', 'file_path', 'attachment_type']:
        if field in data:
            setattr(entry, field, data[field])
    db.session.commit()
    return jsonify({'message': 'Attachment updated', 'attachment': entry.to_dict()}), 200

@student_bp.route('/offers', methods=['GET', 'POST'])
@jwt_required()
def offers_collection():
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status

    if request.method == 'GET':
        entries = StudentOffer.query.filter_by(student_id=profile.id).order_by(StudentOffer.offer_date.desc().nullslast()).all()
        return jsonify([e.to_dict() for e in entries]), 200

    data = request.get_json()
    if not data.get('company_name'):
        return jsonify({'error': 'company_name is required'}), 400
    entry = StudentOffer(
        student_id=profile.id,
        company_name=data.get('company_name'),
        role=data.get('role'),
        ctc=data.get('ctc'),
        status=data.get('status', 'pending'),
        offer_date=parse_date(data.get('offer_date')),
        joining_date=parse_date(data.get('joining_date')),
        location=data.get('location'),
        notes=data.get('notes')
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify({'message': 'Offer added', 'offer': entry.to_dict()}), 201

@student_bp.route('/offers/<int:entry_id>', methods=['PUT', 'DELETE'])
@jwt_required()
def offers_detail(entry_id):
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status

    entry, error_response, status = _ensure_entry(StudentOffer.query, entry_id, profile.id)
    if error_response:
        return error_response, status

    if request.method == 'DELETE':
        db.session.delete(entry)
        db.session.commit()
        return jsonify({'message': 'Offer removed'}), 200

    data = request.get_json()
    for field in ['company_name', 'role', 'ctc', 'status', 'location', 'notes']:
        if field in data:
            setattr(entry, field, data[field])
    if 'offer_date' in data:
        entry.offer_date = parse_date(data.get('offer_date'))
    if 'joining_date' in data:
        entry.joining_date = parse_date(data.get('joining_date'))
    db.session.commit()
    return jsonify({'message': 'Offer updated', 'offer': entry.to_dict()}), 200

@student_bp.route('/placement-policy', methods=['GET', 'POST'])
@jwt_required()
def placement_policy_collection():
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status

    if request.method == 'GET':
        entries = StudentPlacementPolicy.query.filter_by(student_id=profile.id).order_by(StudentPlacementPolicy.updated_at.desc()).all()
        return jsonify([entry.to_dict() for entry in entries]), 200

    data = request.get_json(silent=True) or {}
    if 'interested_in_jobs' not in data or 'interested_in_internships' not in data:
        return jsonify({'error': 'interested_in_jobs and interested_in_internships are required'}), 400

    existing = StudentPlacementPolicy.query.filter_by(student_id=profile.id).first()
    if existing:
        assign_section_fields(existing, data, SECTION_CONFIG['placement-policy'])
        existing.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'message': 'Placement policy updated', 'placement_policy': existing.to_dict()}), 200

    entry = StudentPlacementPolicy(student_id=profile.id)
    assign_section_fields(entry, data, SECTION_CONFIG['placement-policy'])
    db.session.add(entry)
    db.session.commit()
    return jsonify({'message': 'Placement policy added', 'placement_policy': entry.to_dict()}), 201

@student_bp.route('/placement-policy/<int:entry_id>', methods=['PUT', 'DELETE'])
@jwt_required()
def placement_policy_detail(entry_id):
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status

    entry, error_response, status = _ensure_entry(StudentPlacementPolicy.query, entry_id, profile.id)
    if error_response:
        return error_response, status

    if request.method == 'DELETE':
        db.session.delete(entry)
        db.session.commit()
        return jsonify({'message': 'Placement policy removed'}), 200

    data = request.get_json(silent=True) or {}
    assign_section_fields(entry, data, SECTION_CONFIG['placement-policy'])
    entry.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'message': 'Placement policy updated', 'placement_policy': entry.to_dict()}), 200

def _normalize_semester_label(value):
    if not value:
        return ''
    normalized = str(value).strip().upper()
    numeric_to_roman = {
        '1': 'I', '2': 'II', '3': 'III', '4': 'IV',
        '5': 'V', '6': 'VI', '7': 'VII', '8': 'VIII',
    }
    return numeric_to_roman.get(normalized, normalized)

def _semester_display_order(label):
    order_map = {
        'I': 1, 'II': 2, 'III': 3, 'IV': 4,
        'V': 5, 'VI': 6, 'VII': 7, 'VIII': 8,
    }
    return order_map.get(label, 99)

def _apply_academic_fields(entry, data):
    semester_label = _normalize_semester_label(data.get('semester_label') or entry.semester_label)
    if not semester_label:
        return False

    entry.semester_label = semester_label
    entry.degree_name = data.get('degree_name')
    entry.branch_name = data.get('branch_name')
    entry.batch_start_year = parse_int(data.get('batch_start_year'))
    entry.batch_end_year = parse_int(data.get('batch_end_year'))

    sgpa = data.get('sgpa')
    entry.sgpa = str(sgpa).strip() if sgpa not in (None, '') else None

    closed_backlogs = parse_int(data.get('closed_backlogs'))
    live_backlogs = parse_int(data.get('live_backlogs'))
    entry.closed_backlogs = closed_backlogs if closed_backlogs is not None else 0
    entry.live_backlogs = live_backlogs if live_backlogs is not None else 0
    entry.marksheet_file_path = data.get('marksheet_file_path')
    requested_order = parse_int(data.get('display_order'))
    entry.display_order = requested_order if requested_order is not None else _semester_display_order(semester_label)
    return True

@student_bp.route('/academic-details', methods=['GET', 'POST'])
@jwt_required()
def academic_details_collection():
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status

    if request.method == 'GET':
        entries = StudentAcademicDetail.query.filter_by(student_id=profile.id).order_by(
            StudentAcademicDetail.display_order.asc(),
            StudentAcademicDetail.id.asc(),
        ).all()
        return jsonify([entry.to_dict() for entry in entries]), 200

    data = request.get_json(silent=True) or {}
    semester_label = _normalize_semester_label(data.get('semester_label'))
    if not semester_label:
        return jsonify({'error': 'semester_label is required'}), 400

    existing = StudentAcademicDetail.query.filter_by(student_id=profile.id, semester_label=semester_label).first()
    if existing:
        if not _apply_academic_fields(existing, data):
            return jsonify({'error': 'Invalid academic details payload'}), 400
        existing.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'message': 'Academic details updated', 'academic_detail': existing.to_dict()}), 200

    entry = StudentAcademicDetail(student_id=profile.id, semester_label=semester_label)
    if not _apply_academic_fields(entry, data):
        return jsonify({'error': 'Invalid academic details payload'}), 400
    db.session.add(entry)
    db.session.commit()
    return jsonify({'message': 'Academic details added', 'academic_detail': entry.to_dict()}), 201

@student_bp.route('/academic-details/<int:entry_id>', methods=['PUT', 'DELETE'])
@jwt_required()
def academic_details_detail(entry_id):
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status

    entry, error_response, status = _ensure_entry(StudentAcademicDetail.query, entry_id, profile.id)
    if error_response:
        return error_response, status

    if request.method == 'DELETE':
        db.session.delete(entry)
        db.session.commit()
        return jsonify({'message': 'Academic detail removed'}), 200

    data = request.get_json(silent=True) or {}
    if not _apply_academic_fields(entry, data):
        return jsonify({'error': 'semester_label is required'}), 400
    entry.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'message': 'Academic details updated', 'academic_detail': entry.to_dict()}), 200


@student_bp.route('/resume/upload', methods=['POST'])
@jwt_required()
def upload_resume():
    try:
        profile, error_response, status = get_student_profile()
        if error_response:
            return error_response, status
        
        if 'resume' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['resume']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Allowed: PDF, DOC, DOCX, TXT, PNG, JPG, JPEG'}), 400
        
        filename = secure_filename(f"{profile.user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")

        # Read bytes once for parsing, then reset pointer
        file_bytes = file.read()
        file.stream.seek(0)

        # Store in local public filesystem
        resumes_dir = _public_absolute_path('resumes')
        os.makedirs(resumes_dir, exist_ok=True)
        filepath_abs = os.path.join(resumes_dir, filename)
        file.save(filepath_abs)
        resume_url = _public_relative_path('resumes', filename)
        
        # Delete old resume if exists from local filesystem
        old_resume_path = _resolve_stored_file_path(profile.resume_path)
        if old_resume_path and os.path.exists(old_resume_path):
            try:
                os.remove(old_resume_path)
            except OSError:
                pass
        
        profile.resume_path = resume_url
        db.session.commit()

        # --------- AI Resume Analysis ----------
        resume_analysis = {}
        profile_autofill = {
            'enabled': False,
            'profile_fields_updated': [],
            'skills_merged': 0,
            'interests_merged': 0,
            'sections': {},
            'total_added': 0,
            'total_updated': 0,
        }
        try:
            from ai_recommendation_service import AIRecommendationService
            resume_analysis = AIRecommendationService.extract_and_analyze_resume(file_bytes, filename)

            # Update student skills from extracted resume
            extracted_skills = resume_analysis.get('skills', [])
            if extracted_skills:
                SkillsMatchingService.update_student_skills(
                    profile.id,
                    extracted_skills,
                    {}
                )

            extracted_data = resume_analysis.get('extracted_data', {})
            if isinstance(extracted_data, dict):
                profile_modules = extracted_data.get('profile_modules')
                if isinstance(profile_modules, dict):
                    profile_autofill = {
                        'enabled': True,
                        **_apply_profile_modules_from_resume(profile, profile_modules),
                    }
                    db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Resume analysis failed: {e}")
            resume_analysis = {"error": str(e)}
        
        return jsonify({
            'message': 'Resume uploaded and analyzed successfully',
            'resume_path': resume_url,
            'resume_analysis': resume_analysis,
            'profile_autofill': profile_autofill,
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@student_bp.route('/profile-picture', methods=['POST'])
@jwt_required()
def upload_profile_picture():
    try:
        profile, error_response, status = get_student_profile()
        if error_response:
            return error_response, status

        avatar = request.files.get('avatar') or request.files.get('profile_picture')
        if not avatar:
            return jsonify({'error': 'No profile image provided'}), 400
        if avatar.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        if not allowed_image_file(avatar.filename):
            return jsonify({'error': 'Invalid file type. Allowed: PNG, JPG, JPEG, WEBP'}), 400

        filename = secure_filename(
            f"{profile.user_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{avatar.filename}"
        )
        profile_pictures_dir = _public_absolute_path('profile_pictures')
        os.makedirs(profile_pictures_dir, exist_ok=True)
        filepath_abs = os.path.join(profile_pictures_dir, filename)
        avatar.save(filepath_abs)
        stored_profile_picture_path = _public_relative_path('profile_pictures', filename)

        old_profile_picture = _resolve_stored_file_path(profile.profile_picture)
        if old_profile_picture and os.path.exists(old_profile_picture):
            try:
                os.remove(old_profile_picture)
            except OSError:
                pass

        profile.profile_picture = stored_profile_picture_path
        profile.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({
            'message': 'Profile picture updated successfully',
            'profile_picture': profile.profile_picture,
            'profile': profile.to_dict(),
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@student_bp.route('/resume/download', methods=['GET'])
@jwt_required()
def download_resume():
    try:
        profile, error_response, status = get_student_profile()
        if error_response:
            return error_response, status
        
        if not profile.resume_path:
            return jsonify({'error': 'Resume not found'}), 404

        # Supabase URL check removed
        
        resume_file_path = _resolve_stored_file_path(profile.resume_path)
        if not resume_file_path or not os.path.exists(resume_file_path):
            return jsonify({'error': 'Resume not found'}), 404
        
        return send_file(resume_file_path, as_attachment=True)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@student_bp.route('/resume/generate', methods=['GET'])
@jwt_required()
def generate_resume():
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status

    sections = serialize_all_sections(profile)
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", 'B', 16)
    full_name = f"{profile.first_name} {profile.last_name}".strip()
    pdf.cell(0, 10, full_name or "Student Resume", ln=True)

    pdf.set_font("Helvetica", '', 11)
    contact_line = []
    if profile.phone:
        contact_line.append(f"Phone: {profile.phone}")
    if profile.linkedin_url:
        contact_line.append(f"LinkedIn: {profile.linkedin_url}")
    if profile.github_url:
        contact_line.append(f"GitHub: {profile.github_url}")
    if contact_line:
        pdf.multi_cell(0, 6, " | ".join(contact_line))
        pdf.ln(2)

    def add_section(title, items, formatter):
        if not items:
            return
        pdf.set_font("Helvetica", 'B', 13)
        pdf.cell(0, 8, title, ln=True)
        pdf.set_font("Helvetica", '', 11)
        for item in items:
            formatter(item)
            pdf.ln(2)
        pdf.ln(3)

    add_section("Education", sections.get('education', []), lambda item: pdf.multi_cell(
        0, 6, f"{item.get('degree', '')} - {item.get('institution', '')} ({item.get('start_date', '')} - {item.get('end_date', '') or 'Present'})\nGPA: {item.get('gpa', 'N/A')}"
    ))

    add_section("Professional Experience", sections.get('experiences', []), lambda item: pdf.multi_cell(
        0, 6, f"{item.get('designation', '')} @ {item.get('company_name', '')} ({item.get('start_date', '')} - {item.get('end_date', '') or 'Present'})\n{item.get('description', '')}"
    ))

    add_section("Internships", sections.get('internships', []), lambda item: pdf.multi_cell(
        0, 6, f"{item.get('designation', '')} @ {item.get('organization', '')} ({item.get('start_date', '')} - {item.get('end_date', '') or 'Present'})\nMentor: {item.get('mentor_name', '-')}\n{item.get('description', '')}"
    ))

    add_section("Projects", sections.get('projects', []), lambda item: pdf.multi_cell(
        0, 6, f"{item.get('title', '')} ({item.get('start_date', '')} - {item.get('end_date', '') or 'Present'})\n{item.get('description', '')}"
    ))

    add_section("Certifications", sections.get('certifications', []), lambda item: pdf.multi_cell(
        0, 6, f"{item.get('name', '')} - {item.get('issuer', '')} ({item.get('issue_date', '')})"
    ))

    pdf_output = pdf.output(dest='S').encode('latin-1')
    buffer = BytesIO(pdf_output)
    buffer.seek(0)
    filename = f"{full_name.replace(' ', '_') or 'resume'}.pdf"
    return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name=filename)

@student_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def get_dashboard():
    try:
        profile, error_response, status = get_student_profile()
        if error_response:
            return error_response, status
        
        # Get applications
        applications = Application.query.filter_by(student_id=profile.id).order_by(Application.applied_at.desc()).all()
        
        # Get recommended opportunities (basic - can be enhanced with AI)
        all_opportunities = Opportunity.query.filter_by(is_active=True, is_approved=True).all()
        
        # Simple recommendation based on skills
        student_skills = json.loads(profile.skills) if profile.skills else []
        recommended = []
        for opp in all_opportunities:
            if opp.id not in [app.opportunity_id for app in applications]:
                required_skills = json.loads(opp.required_skills) if opp.required_skills else []
                match_count = len(set(student_skills) & set(required_skills))
                if match_count > 0 or len(required_skills) == 0:
                    recommended.append(opp)
                    if len(recommended) >= 10:
                        break
        
        # Get notifications
        notifications = Notification.query.filter_by(user_id=profile.user_id, is_read=False).order_by(Notification.created_at.desc()).limit(10).all()
        
        return jsonify({
            'profile': profile.to_dict(),
            'applications': [app.to_dict() for app in applications],
            'recommended_opportunities': [opp.to_dict() for opp in recommended],
            'notifications': [notif.to_dict() for notif in notifications],
            'stats': {
                'total_applications': len(applications),
                'pending': len([a for a in applications if a.status == 'pending']),
                'shortlisted': len([a for a in applications if a.status == 'shortlisted']),
                'rejected': len([a for a in applications if a.status == 'rejected']),
                'interview': len([a for a in applications if a.status == 'interview'])
            }
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@student_bp.route('/jobs/summary', methods=['GET'])
@jwt_required()
def get_jobs_summary():
    try:
        profile, error_response, status = get_student_profile()
        if error_response:
            return error_response, status

        student_skills = set(json.loads(profile.skills) if profile.skills else [])
        applications = Application.query.filter_by(student_id=profile.id).order_by(Application.applied_at.desc()).all()
        applications_by_opp = {app.opportunity_id: app for app in applications}
        offers = StudentOffer.query.filter_by(student_id=profile.id).order_by(StudentOffer.offer_date.desc().nullslast()).all()

        opportunities_query = Opportunity.query.filter_by(is_active=True, is_approved=True).order_by(Opportunity.created_at.desc())
        opportunities = opportunities_query.limit(60).all()

        tag_counts = {}
        opportunity_cards = []
        eligible_count = 0

        for opp in opportunities:
            required = json.loads(opp.required_skills) if opp.required_skills else []
            match = len(student_skills & set(required))
            match_pct = int((match / len(required)) * 100) if required else 100
            eligible = match_pct >= 40
            if eligible:
                eligible_count += 1

            application = applications_by_opp.get(opp.id)
            status_label = friendly_application_status(application.status) if application else ('Eligible' if eligible else 'Upskill suggested')

            for tag in required[:10]:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

            opportunity_cards.append({
                'id': opp.id,
                'title': opp.title,
                'company': opp.company.name if opp.company else None,
                'job_type': opp.work_type.title() if opp.work_type else 'Full Time',
                'ctc': opp.stipend or 'Not disclosed',
                'location': opp.location or 'Remote',
                'tags': required[:6],
                'eligible': eligible,
                'match': match_pct,
                'status': status_label,
                'applied': bool(application),
                'application_status': application.status if application else None,
                'application_id': application.id if application else None,
                'posted_on': opp.created_at.isoformat() if opp.created_at else None,
            })

        applications_cards = []
        for app in applications:
            opportunity = app.opportunity
            applications_cards.append({
                'id': app.id,
                'title': opportunity.title if opportunity else 'Opportunity',
                'company': opportunity.company.name if opportunity and opportunity.company else None,
                'location': opportunity.location if opportunity else None,
                'status': friendly_application_status(app.status),
                'job_type': opportunity.work_type.title() if opportunity and opportunity.work_type else 'Full Time',
                'ctc': opportunity.stipend if opportunity else None,
                'submitted_on': app.applied_at.isoformat() if app.applied_at else None,
                'tags': json.loads(opportunity.required_skills)[:6] if opportunity and opportunity.required_skills else [],
            })

        offers_cards = [{
            'id': offer.id,
            'company_name': offer.company_name,
            'role': offer.role,
            'ctc': offer.ctc,
            'status': friendly_application_status(offer.status),
            'offer_date': offer.offer_date.isoformat() if offer.offer_date else None,
            'joining_date': offer.joining_date.isoformat() if offer.joining_date else None,
            'location': offer.location,
            'notes': offer.notes,
        } for offer in offers]

        stats = {
            'eligible': eligible_count,
            'applications': len(applications_cards),
            'offers': len(offers_cards),
            'opportunities': len(opportunity_cards),
        }

        popular_tags = [
            {'tag': tag, 'count': count}
            for tag, count in sorted(tag_counts.items(), key=lambda item: item[1], reverse=True)[:12]
        ]

        return jsonify({
            'opportunities': opportunity_cards,
            'applications': applications_cards,
            'offers': offers_cards,
            'stats': stats,
            'popular_tags': popular_tags,
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@student_bp.route('/applications', methods=['GET'])
@jwt_required()
def get_applications():
    try:
        profile, error_response, status = get_student_profile()
        if error_response:
            return error_response, status
        
        applications = Application.query.filter_by(student_id=profile.id).order_by(Application.applied_at.desc()).all()
        
        return jsonify([app.to_dict() for app in applications]), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@student_bp.route('/files/check', methods=['GET'])
@jwt_required()
def check_files_status():
    """
    Check the status of uploaded files - verify if they exist in Supabase.
    Returns information about resume and attachments for the current student.
    """
    try:
        profile, error_response, status = get_student_profile()
        if error_response:
            return error_response, status
        
        result = {
            'supabase_configured': False,
            'resume': None,
            'attachments': [],
            'storage_files': {
                'resumes': 0,
                'attachments': 0
            }
        }
        
        # Check resume
        if profile.resume_path:
            result['resume'] = {
                'path': profile.resume_path,
                'exists': os.path.exists(profile.resume_path),
                'location': 'local'
            }
            if result['resume']['exists']:
                result['storage_files']['resumes'] = 1
        
        # Check attachments
        attachments = StudentAttachment.query.filter_by(student_id=profile.id).all()
        for attachment in attachments:
            exists = os.path.exists(attachment.file_path) if attachment.file_path else False
            result['attachments'].append({
                'id': attachment.id,
                'title': attachment.title,
                'path': attachment.file_path,
                'exists': exists,
                'location': 'local'
            })
            if exists:
                result['storage_files']['attachments'] += 1
        
        return jsonify(result), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== SKILLS MATCHING ENDPOINTS ====================

@student_bp.route('/skills', methods=['GET', 'POST', 'PUT'])
@jwt_required()
def manage_skills():
    """Get, add, or update student skills (Technical and Non-Technical)"""
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status
    
    if request.method == 'GET':
        # Get all skills with student's skills marked
        all_skills = Skill.query.order_by(Skill.name).all()
        student_skill_ids = {ss.skill_id for ss in StudentSkill.query.filter_by(student_id=profile.id).all()}
        
        skills_list = []
        for skill in all_skills:
            skill_dict = skill.to_dict()
            skill_dict['has_skill'] = skill.id in student_skill_ids
            if skill.id in student_skill_ids:
                student_skill = StudentSkill.query.filter_by(
                    student_id=profile.id, 
                    skill_id=skill.id
                ).first()
                skill_dict['proficiency_level'] = student_skill.proficiency_level if student_skill else None
            skills_list.append(skill_dict)
        
        # Get student's current skills (separated by technical/non-technical)
        student_skills = StudentSkill.query.filter_by(student_id=profile.id).all()
        technical_skills = []
        non_technical_skills = []
        
        for ss in student_skills:
            skill = Skill.query.get(ss.skill_id)
            if skill:
                skill_data = ss.to_dict()
                skill_data['category'] = skill.category
                if skill.category in ['programming', 'framework', 'database', 'cloud', 'devops', 'mobile', 'data-science', 'web', 'library']:
                    technical_skills.append(skill_data)
                else:
                    non_technical_skills.append(skill_data)
        
        return jsonify({
            'all_skills': skills_list,
            'technical_skills': technical_skills,
            'non_technical_skills': non_technical_skills
        }), 200
    
    elif request.method == 'POST' or request.method == 'PUT':
        # Update student skills
        data = request.get_json() or {}
        technical_skills = data.get('technical_skills', [])
        non_technical_skills = data.get('non_technical_skills', [])
        proficiency_levels = data.get('proficiency_levels', {})
        
        # Combine all skills
        all_skill_names = []
        for skill_data in technical_skills + non_technical_skills:
            if isinstance(skill_data, dict):
                skill_name = skill_data.get('name') or skill_data.get('skill')
                if skill_name:
                    all_skill_names.append(skill_name)
                    if 'proficiency_level' in skill_data:
                        proficiency_levels[skill_name] = skill_data['proficiency_level']
            elif isinstance(skill_data, str):
                all_skill_names.append(skill_data)
        
        if not all_skill_names:
            return jsonify({'error': 'Skills list is required'}), 400
        
        try:
            SkillsMatchingService.update_student_skills(
                profile.id, 
                all_skill_names,
                proficiency_levels
            )
            
            # Return updated skills
            student_skills = StudentSkill.query.filter_by(student_id=profile.id).all()
            technical = []
            non_technical = []
            
            for ss in student_skills:
                skill = Skill.query.get(ss.skill_id)
                if skill:
                    skill_data = ss.to_dict()
                    skill_data['category'] = skill.category
                    if skill.category in ['programming', 'framework', 'database', 'cloud', 'devops', 'mobile', 'data-science', 'web', 'library']:
                        technical.append(skill_data)
                    else:
                        non_technical.append(skill_data)
            
            return jsonify({
                'message': 'Skills updated successfully',
                'technical_skills': technical,
                'non_technical_skills': non_technical
            }), 200
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500


@student_bp.route('/matched-opportunities', methods=['GET'])
@jwt_required()
def get_matched_opportunities():
    """Get opportunities matched with student's skills (70%+ match only - eligible to apply)"""
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status
    
    try:
        # Default to 70% minimum match as per requirement
        min_match = float(request.args.get('min_match', 70.0))
        limit = int(request.args.get('limit', 50))
        
        matched_opps = SkillsMatchingService.get_matched_opportunities(
            profile.id,
            limit=limit,
            min_match=min_match
        )
        
        # Filter to only show jobs with 70%+ match (can apply)
        applicable_jobs = [
            opp for opp in matched_opps 
            if opp['match_data']['match_percentage'] >= 70.0
        ]
        
        return jsonify({
            'matched_opportunities': applicable_jobs,
            'total': len(applicable_jobs),
            'min_match_threshold': 70.0,
            'message': 'Showing only jobs with 70%+ match (eligible to apply)'
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@student_bp.route('/external-jobs', methods=['GET'])
@jwt_required()
def get_external_jobs():
    """Get external jobs matched with student's skills (70%+ match only) - New Tab for External Jobs"""
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status
    
    try:
        # Default to 70% minimum match
        min_match = float(request.args.get('min_match', 70.0))
        limit = int(request.args.get('limit', 50))
        
        matched_jobs = SkillsMatchingService.get_matched_external_jobs(
            profile.id,
            limit=limit,
            min_match=min_match
        )
        
        # Filter to only show jobs with 70%+ match
        applicable_jobs = [
            job for job in matched_jobs 
            if job['match_data']['match_percentage'] >= 70.0
        ]
        
        return jsonify({
            'external_jobs': applicable_jobs,
            'total': len(applicable_jobs),
            'min_match_threshold': 70.0,
            'message': 'Showing only external jobs with 70%+ match'
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@student_bp.route('/opportunities/<int:opportunity_id>/match', methods=['GET'])
@jwt_required()
def get_opportunity_match(opportunity_id):
    """Get match details for a specific opportunity"""
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status
    
    try:
        opportunity = Opportunity.query.get_or_404(opportunity_id)
        match_data = SkillsMatchingService.calculate_match_score(profile.id, opportunity_id)
        
        return jsonify({
            'opportunity': opportunity.to_dict(),
            'match_data': match_data,
            'can_apply': match_data['match_percentage'] >= 70.0
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@student_bp.route('/external-jobs/<int:job_id>/match', methods=['GET'])
@jwt_required()
def get_external_job_match(job_id):
    """Get match details for a specific external job"""
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status
    
    try:
        job = ExternalJob.query.get_or_404(job_id)
        match_data = SkillsMatchingService.calculate_external_job_match(profile.id, job_id)
        
        return jsonify({
            'job': job.to_dict(),
            'match_data': match_data,
            'can_apply': match_data['match_percentage'] >= 70.0
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@student_bp.route('/check-skills-setup', methods=['GET'])
@jwt_required()
def check_skills_setup():
    """Check if student needs to set up skills (first-time login)"""
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status
    
    skill_count = StudentSkill.query.filter_by(student_id=profile.id).count()
    
    return jsonify({
        'has_skills': skill_count > 0,
        'skill_count': skill_count,
        'needs_setup': skill_count == 0,
        'message': 'Please add your skills to get matched with opportunities' if skill_count == 0 else 'Skills are set up'
    }), 200


# ==================== AI RECOMMENDATION ENDPOINTS ====================

@student_bp.route('/jobs/recommend/async', methods=['POST'])
@jwt_required()
def enqueue_job_recommendations():
    """
    Queue a recommendation job and return immediately.

    Use this for APIFY/live recommendations so the HTTP request does not block
    while external scrapers run.
    """
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status

    try:
        data = request.get_json() or {}
        resume_analysis = _build_resume_analysis_payload(profile, data)
        use_apify = request.args.get('useApify', 'true').lower() == 'true'
        top_n = _parse_top_n(default_value=200)
        location = AIRecommendationService.sanitize_location(request.args.get('location', 'India'))

        queue_service = get_apify_recommendation_queue(current_app._get_current_object())
        queued_job, created = queue_service.enqueue(
            user_id=get_user_id(),
            resume_analysis=resume_analysis,
            use_apify=use_apify,
            top_n=top_n,
            location=location,
        )

        response_payload = queue_service.serialize_job(queued_job, include_result=False)
        response_payload.update(
            {
                'enqueued': created,
                'poll_url': f'/api/student/jobs/recommend/async/{queued_job.job_id}',
                'data_source': 'apify' if use_apify else 'database',
            }
        )
        return jsonify(response_payload), 202 if created else 200
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 429
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@student_bp.route('/jobs/recommend/async/<job_id>', methods=['GET'])
@jwt_required()
def get_queued_job_recommendations(job_id):
    """Poll queued recommendation job status/results."""
    try:
        queue_service = get_apify_recommendation_queue(current_app._get_current_object())
        job = queue_service.get_job(job_id=job_id, user_id=get_user_id())
        if not job:
            return jsonify({'error': 'Recommendation job not found'}), 404

        payload = queue_service.serialize_job(job, include_result=True)
        payload['data_source'] = 'apify' if job.use_apify else 'database'
        if job.status in {'queued', 'running'}:
            return jsonify(payload), 202
        return jsonify(payload), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@student_bp.route('/jobs/recommend/async/<job_id>', methods=['DELETE'])
@jwt_required()
def cancel_queued_job_recommendations(job_id):
    """Cancel a queued (not yet running) recommendation job."""
    try:
        queue_service = get_apify_recommendation_queue(current_app._get_current_object())
        job = queue_service.get_job(job_id=job_id, user_id=get_user_id())
        if not job:
            return jsonify({'error': 'Recommendation job not found'}), 404

        cancelled = queue_service.cancel_job(job_id=job_id, user_id=get_user_id())
        if not cancelled:
            return jsonify({'error': f'Cannot cancel job in status: {job.status}', 'status': job.status}), 409

        payload = queue_service.serialize_job(job, include_result=True)
        return jsonify(payload), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@student_bp.route('/jobs/recommend', methods=['GET', 'POST'])
@jwt_required()
def get_job_recommendations():
    """
    Get AI-powered job recommendations based on resume analysis.
    
    GET: Use existing resume analysis from profile
    POST: Provide resume analysis data directly
    """
    profile, error_response, status = get_student_profile()
    if error_response:
        return error_response, status
    
    try:
        if request.method == 'POST':
            data = request.get_json() or {}
            resume_analysis = _build_resume_analysis_payload(profile, data)
        else:
            # Build resume analysis from student profile
            student_skills = StudentSkill.query.filter_by(student_id=profile.id).all()
            skills_list = [ss.skill.name for ss in student_skills if ss.skill]
            
            resume_analysis = {
                'skills': skills_list,
                'keywords': skills_list,
                'experience_years': 0,  # Could calculate from internships/experience
                'professional_summary': profile.bio or '',
                'recommended_roles': [],
                'tech_stack': skills_list,
                'career_level': 'entry'
            }
        
        # Get data source preference
        use_apify = request.args.get('useApify', 'true').lower() == 'true'
        top_n = _parse_top_n(default_value=200)
        location = AIRecommendationService.sanitize_location(request.args.get('location', 'India'))
        
        # Get recommendations with actual resume keywords for live job search
        recommendations = AIRecommendationService.get_recommendations(
            resume_analysis,
            use_apify=use_apify,
            top_n=top_n,
            location=location
        )
        
        return jsonify({
            'recommendations': recommendations,
            'total': len(recommendations),
            'data_source': 'apify' if use_apify else 'database'
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@student_bp.route('/jobs/source', methods=['GET'])
@jwt_required()
def get_job_source():
    """
    Get jobs from either database or Apify API.
    
    Query params:
        useApify: true/false (default: true)
        keywords: comma-separated keywords for Apify search
        location: location for Apify search (default: India)
    """
    try:
        use_apify = request.args.get('useApify', 'true').lower() == 'true'
        
        if use_apify:
            keywords_str = request.args.get('keywords', 'software engineer,developer,intern')
            location = AIRecommendationService.sanitize_location(request.args.get('location', 'India'))
            keywords = [k.strip() for k in keywords_str.split(',')]
            
            jobs = AIRecommendationService.get_job_sources(use_apify=True)
            
            # If keywords provided, filter or fetch with keywords
            if keywords and keywords != ['software engineer', 'developer', 'intern']:
                try:
                    jobs = fetch_jobs_from_apify(keywords, location=location)
                except Exception as e:
                    print(f"Apify fetch with keywords failed: {e}")
        else:
            jobs = AIRecommendationService.get_job_sources(use_apify=False)
        
        return jsonify({
            'jobs': jobs,
            'total': len(jobs),
            'source': 'apify' if use_apify else 'database'
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
