document.addEventListener('DOMContentLoaded', function () {
    const uploadForm = document.getElementById('uploadForm');
    const loadingSpinner = document.getElementById('loadingSpinner');
    const errorMessage = document.getElementById('errorMessage');
    const successMessage = document.getElementById('successMessage');
    const resultsSection = document.getElementById('resultsSection');

    const JOBS_PER_PAGE = 5;
    let allJobs = [];
    let currentPage = 1;

    uploadForm.addEventListener('submit', async function (e) {
        e.preventDefault();

        errorMessage.classList.add('hidden');
        successMessage.classList.add('hidden');
        resultsSection.classList.add('hidden');

        const resumeFile = document.getElementById('resume').files[0];
        const location = document.getElementById('location').value;

        if (!resumeFile) {
            showError('Please select a resume file');
            return;
        }

        loadingSpinner.classList.remove('hidden');

        try {
            const formData = new FormData();
            formData.append('resume', resumeFile);
            formData.append('location', location);

            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to process resume');
            }

            displayResumeData(data.resume_data);

            allJobs = data.jobs;
            currentPage = 1;
            renderPage();

            resultsSection.classList.remove('hidden');
            showSuccess(`Found ${data.total_jobs} matching job${data.total_jobs !== 1 ? 's' : ''}!`);
            resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

        } catch (error) {
            showError(error.message);
        } finally {
            loadingSpinner.classList.add('hidden');
        }
    });

    function displayResumeData(resumeData) {
        const skillsList = document.getElementById('skillsList');
        skillsList.innerHTML = '';

        if (resumeData.skills.length > 0) {
            resumeData.skills.forEach(skill => {
                const tag = document.createElement('span');
                tag.className = 'skill-tag';
                tag.textContent = skill;
                skillsList.appendChild(tag);
            });
        } else {
            skillsList.innerHTML = '<p>No skills found</p>';
        }

        const experienceText = document.getElementById('experienceText');
        experienceText.textContent = resumeData.experience.length > 0
            ? resumeData.experience.join(', ') + ' years'
            : 'Not found';

        document.getElementById('emailText').textContent = resumeData.email || 'Not found';
        document.getElementById('phoneText').textContent = resumeData.phone || 'Not found';
    }

    function renderPage() {
        const jobsList = document.getElementById('jobsList');
        const totalJobs = document.getElementById('totalJobs');
        const totalPages = Math.ceil(allJobs.length / JOBS_PER_PAGE);

        if (allJobs.length === 0) {
            totalJobs.textContent = 'No matching jobs found';
            jobsList.innerHTML = '<p class="no-jobs">No jobs matched your resume skills. Try uploading a different resume or check back later.</p>';
            document.getElementById('pagination').innerHTML = '';
            return;
        }

        const start = (currentPage - 1) * JOBS_PER_PAGE;
        const pageJobs = allJobs.slice(start, start + JOBS_PER_PAGE);

        totalJobs.textContent = `Showing ${start + 1}–${Math.min(start + JOBS_PER_PAGE, allJobs.length)} of ${allJobs.length} jobs`;

        jobsList.innerHTML = '';
        pageJobs.forEach(job => jobsList.appendChild(createJobCard(job)));

        renderPagination(totalPages);
    }

    function renderPagination(totalPages) {
        const container = document.getElementById('pagination');
        if (totalPages <= 1) {
            container.innerHTML = '';
            return;
        }

        let html = `<button class="page-btn" ${currentPage === 1 ? 'disabled' : ''} data-page="${currentPage - 1}">&#8592; Prev</button>`;

        for (let i = 1; i <= totalPages; i++) {
            html += `<button class="page-btn ${i === currentPage ? 'active' : ''}" data-page="${i}">${i}</button>`;
        }

        html += `<button class="page-btn" ${currentPage === totalPages ? 'disabled' : ''} data-page="${currentPage + 1}">Next &#8594;</button>`;

        container.innerHTML = html;

        container.querySelectorAll('.page-btn:not([disabled])').forEach(btn => {
            btn.addEventListener('click', () => {
                currentPage = parseInt(btn.dataset.page);
                renderPage();
                document.getElementById('jobsList').scrollIntoView({ behavior: 'smooth', block: 'start' });
            });
        });
    }

    function createJobCard(job) {
        const card = document.createElement('div');
        card.className = 'job-card';

        const salary = job.salary && job.salary !== 'Not specified' ? job.salary : null;
        const applicants = job.applicants && job.applicants !== 'N/A' ? job.applicants : null;
        const deadline = resolveDeadline(job.deadline, job.posted_date);

        const metaItems = [
            `<span class="meta-item">📍 ${escape(job.location || 'Location not specified')}</span>`,
            salary ? `<span class="meta-item">💰 ${escape(salary)}</span>` : '',
            job.duration ? `<span class="meta-item">⏱ ${escape(job.duration)}</span>` : '',
            deadline ? `<span class="meta-item deadline-meta">🗓 Apply by: <strong>${escape(deadline)}</strong></span>` : '',
            applicants ? `<span class="meta-item">👥 ${escape(String(applicants))} applicants</span>` : '',
        ].filter(Boolean).join('');

        const matchedSkills = (job.matched_skills && job.matched_skills.length > 0)
            ? `<div class="matched-skills">
                   <span class="match-label">✅ ${job.matched_skills.length} skill match${job.matched_skills.length > 1 ? 'es' : ''}:</span>
                   ${job.matched_skills.map(s => `<span class="skill-tag skill-tag--match">${escape(s)}</span>`).join('')}
               </div>`
            : '';

        const applyBtn = job.link
            ? `<a href="${encodeURI(job.link)}" target="_blank" rel="noopener noreferrer" class="apply-btn">Apply Now →</a>`
            : `<span class="apply-btn apply-btn--disabled">No link available</span>`;

        card.innerHTML = `
            <div class="job-card__header">
                <div class="job-card__title-block">
                    <div class="job-title">${escape(job.title || 'Untitled')}</div>
                    <div class="job-company">${escape(job.company || 'Unknown Company')}</div>
                </div>
                <span class="platform-badge platform-badge--${(job.platform || '').toLowerCase()}">${escape(job.platform || '')}</span>
            </div>
            <div class="job-meta">${metaItems}</div>
            ${matchedSkills}
            <div class="job-card__footer">
                ${applyBtn}
            </div>
        `;

        return card;
    }

    function formatDate(dateStr) {
        if (!dateStr) return null;
        const d = new Date(dateStr);
        if (isNaN(d)) return null;
        return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    }

    // Returns the apply-by deadline:
    // 1. Use the actor-provided deadline if present
    // 2. Otherwise derive posted_date + 30 days (standard LinkedIn window)
    function resolveDeadline(deadlineStr, postedStr) {
        if (deadlineStr) return formatDate(deadlineStr);
        if (postedStr) {
            const posted = new Date(postedStr);
            if (!isNaN(posted)) {
                posted.setDate(posted.getDate() + 30);
                return formatDate(posted.toISOString());
            }
        }
        return null;
    }

    function showError(message) {
        errorMessage.textContent = message;
        errorMessage.classList.remove('hidden');
    }

    function showSuccess(message) {
        successMessage.textContent = message;
        successMessage.classList.remove('hidden');
    }

    function escape(text) {
        const div = document.createElement('div');
        div.textContent = String(text ?? '');
        return div.innerHTML;
    }
});
