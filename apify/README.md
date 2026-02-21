# Job Recommendation Engine

A Python-based application that analyzes your resume and finds job recommendations from multiple platforms (LinkedIn, Naukri, Internshala) using the Apify API.

## Features

- 📄 **Resume Parsing**: Extract skills, experience, and contact information from PDF, DOCX, or TXT files
- 🔍 **Job Search**: Search for relevant jobs across multiple platforms:
  - LinkedIn
  - Naukri.com
  - Internshala
- 💼 **Smart Matching**: Match job recommendations based on detected skills
- 🎨 **Beautiful UI**: Clean and responsive web interface
- 🌍 **Location-based**: Filter jobs by location
- 📊 **Display all results on one page**

## Tech Stack

- **Backend**: Python, Flask, Flask-CORS
- **Frontend**: HTML, CSS, JavaScript
- **Resume Processing**: PyPDF2, python-docx
- **Job Scraping**: Apify API
- **API Client**: apify-client

## Prerequisites

- Python 3.8+
- Apify API Token (provided)

## Installation

### 1. Clone or Navigate to Project

```bash
cd apify
```

### 2. Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

The `.env` file is already configured with your API key:
```
APIFY_API_TOKEN=<YOUR_APIFY_API_TOKEN>
FLASK_ENV=development
FLASK_DEBUG=True
MAX_UPLOAD_SIZE=10485760
```

## Running the Application

### Start the Flask Server

```bash
python app.py
```

The application will be available at: **http://localhost:5000**

## Usage

1. **Open the Web Interface**: Navigate to http://localhost:5000
2. **Upload Resume**: Select a PDF, DOCX, or TXT file (max 10MB)
3. **Add Location** (Optional): Specify your preferred job location
4. **Click "Find Jobs"**: The application will:
   - Parse your resume
   - Extract skills and experience
   - Search for matching jobs
5. **View Results**: All job recommendations are displayed on a single page with:
   - Job title and company
   - Location and salary
   - Platform badge (LinkedIn/Naukri/Internshala)
   - Direct link to apply

## Project Structure

```
apify/
├── app/
│   ├── __init__.py           # Flask app factory
│   ├── routes.py             # Route handlers
│   └── utils/
│       ├── resume_parser.py   # Resume parsing logic
│       └── apify_client.py    # Apify API integration
├── templates/
│   ├── index.html            # Main upload page
│   └── jobs.html             # Jobs listing page
├── static/
│   ├── style.css             # Styling
│   ├── script.js             # Main page logic
│   └── jobs-script.js        # Jobs page logic
├── app.py                    # Application entry point
├── config.py                 # Configuration
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables
└── README.md                 # This file
```

## API Endpoints

### `POST /upload`
Upload and process a resume file.

**Request:**
- `resume` (file): Resume file (PDF, DOCX, TXT)
- `location` (string, optional): Preferred job location

**Response:**
```json
{
  "success": true,
  "resume_data": {
    "skills": ["Python", "Django", "PostgreSQL"],
    "experience": ["5", "3"],
    "email": "user@example.com",
    "phone": "+1-234-567-8900"
  },
  "jobs": [...],
  "total_jobs": 25
}
```

### `POST /search`
Search for jobs based on skills.

**Request:**
```json
{
  "skills": ["Python", "Django"],
  "location": "San Francisco"
}
```

## Supported Resume Formats

- **PDF** (.pdf)
- **Word Document** (.docx)
- **Text File** (.txt)

Maximum file size: **10MB**

## Skills Detected

The parser can detect:

### Programming Languages
Python, Java, JavaScript, TypeScript, C++, C#, PHP, Ruby, Go, Rust, etc.

### Frameworks
Django, Flask, FastAPI, Spring Boot, React, Angular, Vue, Next.js, etc.

### Tools & Platforms
Git, Docker, Kubernetes, AWS, Azure, GCP, Jenkins, Linux, etc.

### Soft Skills
Leadership, Communication, Teamwork, Project Management, Agile, etc.

## Job Platforms

### LinkedIn
- Direct link to LinkedIn job postings
- Salary range (when available)
- Job description preview

### Naukri.com
- Naukri-specific job listings
- Indian job market focus
- Salary in INR

### Internshala
- Internship and entry-level opportunities
- Duration information
- Stipend details

## Error Handling

- **File Type Error**: Only PDF, DOCX, and TXT files are supported
- **File Size Error**: Maximum file size is 10MB
- **Parsing Error**: If resume cannot be parsed, error message is displayed
- **API Error**: If job search fails, mock data is provided for testing

## Development

### Debug Mode

The application runs in debug mode by default (FLASK_DEBUG=True). This enables:
- Auto-reloading on code changes
- Detailed error pages
- Interactive debugger

### Testing

To test the resume parser:

```python
from app.utils.resume_parser import ResumeParser

parser = ResumeParser()
result = parser.parse_resume('path/to/resume.pdf')
print(result['skills'])
```

## Notes

- The application uses mock data for testing and demonstration
- For production use with real Apify actors, replace the actor IDs in `apify_client.py`
- The Apify API token is already configured in `.env`

## Troubleshooting

### Port 5000 Already in Use
```bash
# Change port in app.py or use:
python app.py --port 5001
```

### Module Not Found
```bash
pip install -r requirements.txt --upgrade
```

### Resume Not Parsing
- Ensure file format is supported (PDF, DOCX, TXT)
- Check file size is under 10MB
- Ensure resume contains visible text (not scanned image)

## Future Enhancements

- [ ] User authentication and profiles
- [ ] Save favorite jobs
- [ ] Email notifications for new matching jobs
- [ ] Resume version history
- [ ] Job application tracking
- [ ] Salary negotiation insights
- [ ] Interview preparation resources
- [ ] API integration with job boards for real-time data

## License

This project is provided as-is for educational and commercial use.

## Support

For issues or questions:
1. Check the error messages displayed
2. Verify your resume format
3. Ensure Apify API token is valid
4. Check internet connection for API calls

## Contact

Created with ❤️ using Apify API

---

**Enjoy finding your perfect job!** 💼
