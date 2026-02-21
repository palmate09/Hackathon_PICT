// Load jobs from session storage or localStorage
document.addEventListener('DOMContentLoaded', function () {
    const platformFilter = document.getElementById('platformFilter');
    const searchFilter = document.getElementById('searchFilter');
    const jobsContainer = document.getElementById('jobsContainer');

    let allJobs = [];

    // Try to get jobs from localStorage
    const storedJobs = localStorage.getItem('recommendedJobs');
    if (storedJobs) {
        allJobs = JSON.parse(storedJobs);
        displayJobs(allJobs);
    }

    // Filter by platform
    platformFilter.addEventListener('change', filterJobs);
    
    // Filter by search
    searchFilter.addEventListener('input', filterJobs);

    function filterJobs() {
        const platform = platformFilter.value.toLowerCase();
        const search = searchFilter.value.toLowerCase();

        const filtered = allJobs.filter(job => {
            const platformMatch = !platform || job.platform.toLowerCase() === platform;
            const searchMatch = !search || 
                job.title.toLowerCase().includes(search) ||
                job.company.toLowerCase().includes(search) ||
                job.description.toLowerCase().includes(search);
            
            return platformMatch && searchMatch;
        });

        displayJobs(filtered);
    }

    function displayJobs(jobs) {
        if (!jobs || jobs.length === 0) {
            jobsContainer.innerHTML = '<p>No jobs found.</p>';
            return;
        }

        jobsContainer.innerHTML = '';
        jobs.forEach(job => {
            const jobCard = createJobCard(job);
            jobsContainer.appendChild(jobCard);
        });
    }

    function createJobCard(job) {
        const card = document.createElement('div');
        card.className = 'job-card';

        const description = job.description ? job.description.substring(0, 200) + '...' : 'No description';
        const salary = job.salary || 'Not specified';
        const duration = job.duration ? `<span>Duration: ${job.duration}</span>` : '';

        card.innerHTML = `
            <div class="job-header">
                <div>
                    <div class="job-title">${escape(job.title)}</div>
                    <div class="job-company">${escape(job.company)}</div>
                </div>
                <span class="platform-badge ${job.platform}">${job.platform}</span>
            </div>
            <div class="job-meta">
                <span>📍 ${escape(job.location)}</span>
                <span>💰 ${escape(salary)}</span>
                ${duration}
            </div>
            <div class="job-description">
                ${escape(description)}
            </div>
            <div class="job-footer">
                <span class="job-salary">${escape(salary)}</span>
                <a href="${job.link}" target="_blank" rel="noopener noreferrer" class="job-link">View Job →</a>
            </div>
        `;

        return card;
    }

    function escape(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
});
