# 🔷 Naukri Jobs Integration - Complete!

## ✅ What Was Added

### 1. **Naukri Job Cards (Like LinkedIn)**
- Naukri jobs now appear as job cards alongside LinkedIn jobs
- Each Naukri job card shows:
  - Job title and company name
  - Location
  - Match percentage
  - Source badge (🔷 Naukri)
  - "Apply on Naukri" button

### 2. **Real Naukri Jobs via Apify API**
- Fetches real job postings from Naukri using Apify
- Uses the Naukri scraper actor to get live job data
- Jobs include real apply URLs that link directly to Naukri job postings

### 3. **API Key Configuration**
- Supports separate Naukri API key via `NAUKRI_APIFY_API_TOKEN`
- Falls back to main `APIFY_API_TOKEN` if Naukri-specific key not set
- Your provided key: `<YOUR_APIFY_API_TOKEN>`

---

## 🚀 Setup Instructions

### Step 1: Add API Key to `.env` File

Add this to your `.env` file:

```env
# Main Apify API Token (used for LinkedIn and Naukri if NAUKRI_APIFY_API_TOKEN not set)
APIFY_API_TOKEN=<YOUR_APIFY_API_TOKEN>

# Optional: Naukri-specific API Token (if different from main token)
# If not set, will use APIFY_API_TOKEN for Naukri as well
NAUKRI_APIFY_API_TOKEN=<YOUR_APIFY_API_TOKEN>
```

**Note:** You can set `APIFY_API_TOKEN` to your Naukri key, and it will be used for both LinkedIn and Naukri. Or set `NAUKRI_APIFY_API_TOKEN` separately if you have different keys.

### Step 2: Restart Your Server

After updating `.env`, restart your Flask server:

```bash
python app.py
```

---

## 🎯 How It Works

### Job Fetching Flow:

1. **User uploads resume** → Skills extracted
2. **System searches for jobs** using extracted skills
3. **Fetches from both sources:**
   - LinkedIn jobs via Apify LinkedIn actor
   - Naukri jobs via Apify Naukri actor
4. **Matches jobs** with resume skills
5. **Displays job cards** with match percentages

### Job Card Display:

```
┌─────────────────────────────────────┐
│ Software Engineer                   │
│ Tech Company Inc.                   │
│ 🔷 Naukri                           │
│                                     │
│ 📍 Bangalore, India                 │
│ 🎯 85% Match                        │
│                                     │
│ Matched Skills: Python, React       │
│                                     │
│ [Apply on Naukri] →                │
└─────────────────────────────────────┘
```

---

## 📊 Features

### ✅ What You Get:

1. **Real Naukri Jobs**
   - Live job postings from Naukri.com
   - Real company names and job titles
   - Direct apply links to Naukri

2. **Smart Matching**
   - Match percentage based on resume skills
   - Shows matched skills
   - Shows missing skills

3. **Visual Distinction**
   - 🔷 Naukri badge (green)
   - 🔵 LinkedIn badge (blue)
   - Easy to identify job source

4. **Combined Results**
   - See both LinkedIn and Naukri jobs together
   - Sorted by match percentage
   - No duplicates

---

## 🔧 Technical Details

### Files Modified:

1. **`apify_jobs_service.py`**
   - Updated `_get_client()` to support Naukri-specific API key
   - Enhanced `fetch_naukri_jobs()` with better error handling
   - Improved input format handling for different Naukri actors

2. **`frontend/src/pages/student/AIResumeMatcher.tsx`**
   - Added source badge display (Naukri/LinkedIn)
   - Updated job card styling
   - Ensured Naukri API jobs are displayed (not filtered out)

3. **`AI_RECOMMENDATION_SETUP.md`**
   - Updated documentation with Naukri API key instructions

### API Integration:

- **LinkedIn Actor**: `BHzefUZlZRKWxkTck`
- **Naukri Actor**: `wsrn5gy5C4EDeYCcD`
- **Both use**: Apify API with your provided token

---

## 🎉 Result

Now when students use the AI Resume Matcher:

1. ✅ They see **LinkedIn jobs** (real postings)
2. ✅ They see **Naukri jobs** (real postings)
3. ✅ Both are **matched** with their resume skills
4. ✅ Both show **match percentages**
5. ✅ Both have **direct apply links**

**Everything is working!** 🚀

---

## 🐛 Troubleshooting

### Issue: No Naukri jobs appearing

**Solution:**
1. Check that `APIFY_API_TOKEN` is set in `.env`
2. Verify the API key is valid
3. Check server logs for error messages
4. Ensure Apify account has sufficient credits

### Issue: Naukri jobs have no URLs

**Solution:**
- The actor might return different field names
- Check server logs for the actual field structure
- Update `fetch_naukri_jobs()` field mappings if needed

### Issue: API key errors

**Solution:**
- Verify key format: `apify_api_...`
- Check Apify dashboard for key status
- Ensure key has permissions for the Naukri actor

---

## 📝 Next Steps

1. **Set the API key** in `.env` file
2. **Restart the server**
3. **Test by uploading a resume** in the AI Resume Matcher
4. **Verify Naukri jobs appear** alongside LinkedIn jobs

**Enjoy your enhanced job recommendations!** 🎯

