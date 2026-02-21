# Quick Start Guide

## ✅ Project Setup Complete

Your Job Recommendation Engine is fully configured and ready to use!

## 🚀 Getting Started (3 Easy Steps)

### Step 1: Open Terminal
Navigate to your project folder:
```bash
cd c:\Users\ASUS\Desktop\apify
```

### Step 2: Start the Application
```bash
python app.py
```

You should see:
```
 * Running on http://127.0.0.1:5000
 * Press CTRL+C to quit
```

### Step 3: Open in Browser
Go to: **http://localhost:5000**

---

## 📋 Features

### ✨ Resume Upload
- Upload PDF, DOCX, or TXT files
- Extracts skills, experience, email, and phone
- Maximum file size: 10MB

### 💼 Job Search
- LinkedIn positions
- Naukri.com jobs (India-focused)
- Internshala internships
- All results on one page

### 🎯 Smart Matching
- Detects 60+ skills (programming languages, frameworks, tools)
- Filters jobs by location (optional)
- Shows salary and job details

---

## 📁 Project Structure

```
apify/
├── app/                          # Flask application
│   ├── __init__.py              # App factory
│   ├── routes.py                # API endpoints
│   └── utils/
│       ├── resume_parser.py      # Resume extraction
│       └── apify_client.py       # Job search API
├── templates/                    # HTML pages
│   ├── index.html               # Main upload page
│   └── jobs.html                # Jobs listing
├── static/                       # CSS & JavaScript
│   ├── style.css                # Responsive styling
│   ├── script.js                # Upload logic
│   └── jobs-script.js           # Jobs filtering
├── app.py                       # Entry point
├── config.py                    # Configuration
├── requirements.txt             # Dependencies
├── .env                         # API key & settings
└── README.md                    # Full documentation
```

---

## 🔧 API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Main upload page |
| `/upload` | POST | Upload & process resume |
| `/search` | POST | Search jobs by skills |
| `/jobs` | GET | View jobs page |

---

## 🛠️ Configuration

Your API key is already configured in `.env`:
```
APIFY_API_TOKEN=<YOUR_APIFY_API_TOKEN>
```

---

## 📝 Workflow

1. **Upload Resume**
   - Click "Select Resume" button
   - Choose PDF, DOCX, or TXT file
   - Optionally add location

2. **Processing**
   - App extracts skills & experience
   - Searches Apify for jobs
   - Displays all results

3. **View Jobs**
   - See all recommendations on one page
   - Filter by platform (LinkedIn/Naukri/Internshala)
   - Click "View Job" to apply

---

## 🎓 Sample Skills Detected

**Programming:** Python, Java, JavaScript, TypeScript, C++, C#, Go, Rust...

**Frameworks:** Django, Flask, React, Angular, Vue, Spring Boot, FastAPI...

**Tools:** Git, Docker, Kubernetes, AWS, Azure, GCP, Jenkins...

**Soft Skills:** Leadership, Communication, Project Management, Agile...

---

## ⚠️ Troubleshooting

### Port 5000 Already in Use
```bash
python app.py --port 5001
```

### Module Not Found
```bash
pip install -r requirements.txt
```

### Resume Not Parsing
- Ensure file is PDF, DOCX, or TXT
- File must be under 10MB
- Avoid scanned image PDFs

---

## 🚀 Advanced Usage

### Run with Production Settings
```bash
export FLASK_ENV=production
python app.py
```

### Test Resume Parser
```python
from app.utils.resume_parser import ResumeParser

parser = ResumeParser()
result = parser.parse_resume('your_resume.pdf')
print(result['skills'])
```

---

## 📚 Supported Formats

- **PDF** - Most common, fully supported
- **DOCX** - Microsoft Word documents
- **TXT** - Plain text files

---

## 🎉 You're All Set!

Start the app and begin finding jobs that match your skills!

```bash
python app.py
```

Then open: **http://localhost:5000**

---

## 📞 Need Help?

Refer to `README.md` for complete documentation.

Happy job hunting! 💼✨
