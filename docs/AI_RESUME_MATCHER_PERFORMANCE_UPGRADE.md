# AI Resume Matcher Performance Upgrade

This update improves `/student/ai-resume-matcher` speed and reliability for Gemini parsing, APIFY fetching, and OCR behavior.

## What Was Fixed

### 1) Faster APIFY Fetch With Partial Results
- Added strict timeout controls in `apify/app/utils/apify_client.py`:
  - `APIFY_ACTOR_TIMEOUT_SECONDS` (default: `35`)
  - `APIFY_PLATFORM_TIMEOUT_SECONDS` (default: `45`)
- Platform fetch now returns partial results instead of waiting too long for slow scrapers.
- Slow platform futures are cancelled after timeout, so UI receives results faster.

### 2) Query-Aware APIFY Cache (Fast Repeats)
- Upgraded APIFY cache in `backend/apify_jobs_service.py` to be query-specific (keywords + location).
- Added fast-cache path:
  - `APIFY_CACHE_FRESH_SECONDS` (default: `600`)
  - identical query returns immediately from cache.
- Added fallback cache path:
  - `APIFY_CACHE_FALLBACK_SECONDS` (default: `86400`)
  - used when live APIFY returns empty/errors.

### 3) OCR Reliability Improvements
- Improved Tesseract language handling in `backend/resume_extraction_service.py`:
  - supports aliases like `en -> eng`, `english -> eng`, `hi -> hin`.
  - configurable via `OCR_TESSERACT_LANG` (falls back to `OCR_LANG`).
- OCR errors are now preserved and surfaced in metadata instead of being silently swallowed.
- Frontend now shows OCR notes whenever OCR error text exists.

### 4) Faster Gemini Resume Parsing
- Reduced default Gemini request timeout from `45s` to `22s`.
- Reduced default HTTP retries from `2` to `1` for faster failover.
- Added in-memory parse cache keyed by resume text hash:
  - `RESUME_PARSE_CACHE_TTL_SECONDS` (default: `21600`)
  - `RESUME_PARSE_CACHE_MAX_ENTRIES` (default: `128`)
- Repeat uploads of same content now return parse results much faster.

## Files Updated
- `apify/app/utils/apify_client.py`
- `backend/apify_jobs_service.py`
- `backend/resume_extraction_service.py`
- `frontend/src/pages/student/AIResumeMatcher.tsx`

## Recommended Environment Settings

Use these in `.env` (or `backend/.env`) for a fast and stable baseline:

```env
APIFY_ACTOR_TIMEOUT_SECONDS=35
APIFY_PLATFORM_TIMEOUT_SECONDS=45
APIFY_CACHE_FRESH_SECONDS=600
APIFY_CACHE_FALLBACK_SECONDS=86400

GEMINI_TIMEOUT_SECONDS=22
GEMINI_HTTP_RETRIES=1

OCR_ENABLE=true
OCR_ENGINE=auto
OCR_LANG=en
OCR_TESSERACT_LANG=eng

RESUME_PARSE_CACHE_TTL_SECONDS=21600
RESUME_PARSE_CACHE_MAX_ENTRIES=128
```

## Notes
- Queue-based async recommendations are already active in the backend (`/student/jobs/recommend/async`).
- This change keeps that queue flow and makes each job complete faster by reducing long-tail waits and reusing cache.
- "Fetch all jobs" still depends on upstream actor availability, but now partial results and cache fallback avoid empty/slow UX.
