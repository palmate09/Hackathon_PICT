from flask import Blueprint, render_template, request, jsonify, current_app, session
import os
import re
import time
import uuid
from werkzeug.utils import secure_filename
from app.utils.resume_parser import ResumeParser
from app.utils.apify_client import ApifyJobScraper


_PLATFORM_ORDER = {'LinkedIn': 0, 'Naukri': 1, 'Internshala': 2}
_JOB_CACHE = {}
_JOB_CACHE_TTL_SECONDS = int(os.environ.get('JOB_CACHE_TTL_SECONDS', '1800'))
_JOB_CACHE_MAX_ENTRIES = int(os.environ.get('JOB_CACHE_MAX_ENTRIES', '200'))


def _prune_job_cache():
    now = time.time()
    expired_keys = [
        key for key, payload in _JOB_CACHE.items()
        if now - payload.get('created_at', 0) > _JOB_CACHE_TTL_SECONDS
    ]
    for key in expired_keys:
        _JOB_CACHE.pop(key, None)

    if len(_JOB_CACHE) <= _JOB_CACHE_MAX_ENTRIES:
        return

    # Remove oldest entries to keep memory bounded.
    overflow = len(_JOB_CACHE) - _JOB_CACHE_MAX_ENTRIES
    oldest = sorted(
        _JOB_CACHE.items(),
        key=lambda item: item[1].get('created_at', 0)
    )[:overflow]
    for key, _ in oldest:
        _JOB_CACHE.pop(key, None)


def _store_jobs_in_cache(jobs):
    _prune_job_cache()
    cache_id = uuid.uuid4().hex
    _JOB_CACHE[cache_id] = {
        'created_at': time.time(),
        'jobs': jobs,
    }
    return cache_id


def _load_jobs_from_cache(cache_id):
    if not cache_id:
        return []
    _prune_job_cache()
    payload = _JOB_CACHE.get(cache_id) or {}
    return payload.get('jobs', [])

def filter_and_rank_jobs(jobs, skills):
    """Keep only jobs that mention at least one resume skill.
    Results are ordered: LinkedIn first, then Naukri, then Internshala.
    Within each platform, sorted by number of skill matches (descending).
    """
    filtered = []
    for job in jobs:
        searchable = f"{job.get('title', '')} {job.get('description', '')}".lower()
        matched = [
            s for s in skills
            if re.search(r'\b' + re.escape(s.lower()) + r'\b', searchable)
        ]
        if matched:
            job['matched_skills'] = matched
            job['match_count'] = len(matched)
            filtered.append(job)
    filtered.sort(key=lambda j: (
        _PLATFORM_ORDER.get(j.get('platform', ''), 99),  # platform order
        -j['match_count']                                 # most matches first within platform
    ))
    return filtered

main_bp = Blueprint('main', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@main_bp.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@main_bp.route('/job/<int:job_id>')
def view_job_details(job_id):
    """View job details before applying"""
    # Keep cookie small by storing only cache id in session.
    cache_id = session.get('job_cache_id')
    all_jobs = _load_jobs_from_cache(cache_id)
    
    if job_id < 0 or job_id >= len(all_jobs):
        return render_template('job_details.html', job=None, error='Job not found')
    
    job = all_jobs[job_id]
    return render_template('job_details.html', job=job, job_id=job_id)

@main_bp.route('/upload', methods=['POST'])
def upload_resume():
    """Handle resume upload and process"""
    try:
        # Check if file is in request
        if 'resume' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['resume']
        location = request.form.get('location', '')
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'File type not allowed. Use PDF, DOCX, or TXT'}), 400
        
        # Save file
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Parse resume
        parser = ResumeParser()
        resume_data = parser.parse_resume(filepath)
        
        if 'error' in resume_data:
            return jsonify({'error': resume_data['error']}), 400
        
        # Search for jobs
        scraper = ApifyJobScraper()
        jobs = scraper.search_all_platforms(resume_data['skills'], location)

        # Combine all jobs
        all_jobs = []
        for platform, platform_jobs in jobs.items():
            all_jobs.extend(platform_jobs)

        # Keep only jobs that match resume skills, ranked by match count
        all_jobs = filter_and_rank_jobs(all_jobs, resume_data['skills'])

        # Store only a cache reference in session to avoid oversized cookie warnings.
        cache_id = _store_jobs_in_cache(all_jobs)
        session['job_cache_id'] = cache_id
        session.pop('all_jobs', None)

        # Clean up uploaded file
        try:
            os.remove(filepath)
        except:
            pass

        return jsonify({
            'success': True,
            'resume_data': {
                'skills': resume_data['skills'],
                'experience': resume_data['experience'],
                'email': resume_data['email'],
                'phone': resume_data['phone']
            },
            'job_cache_id': cache_id,
            'jobs': all_jobs,
            'total_jobs': len(all_jobs)
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/search', methods=['POST'])
def search_jobs():
    """Search for jobs based on skills"""
    try:
        data = request.get_json()
        skills = data.get('skills', [])
        location = data.get('location', '')
        
        if not skills:
            return jsonify({'error': 'No skills provided'}), 400
        
        # Search for jobs
        scraper = ApifyJobScraper()
        jobs = scraper.search_all_platforms(skills, location)

        # Combine all jobs
        all_jobs = []
        for platform, platform_jobs in jobs.items():
            all_jobs.extend(platform_jobs)

        # Keep only jobs that match the requested skills, ranked by match count
        all_jobs = filter_and_rank_jobs(all_jobs, skills)

        # Store only a cache reference in session to avoid oversized cookie warnings.
        cache_id = _store_jobs_in_cache(all_jobs)
        session['job_cache_id'] = cache_id
        session.pop('all_jobs', None)

        return jsonify({
            'success': True,
            'job_cache_id': cache_id,
            'jobs': all_jobs,
            'total_jobs': len(all_jobs),
            'searched_skills': skills
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/jobs')
def view_jobs():
    """View jobs page"""
    return render_template('jobs.html')

@main_bp.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large error"""
    return jsonify({'error': 'File is too large. Maximum allowed size is 10MB'}), 413

@main_bp.errorhandler(404)
def not_found(error):
    """Handle 404 error"""
    return jsonify({'error': 'Page not found'}), 404

@main_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 error"""
    return jsonify({'error': 'Internal server error'}), 500
