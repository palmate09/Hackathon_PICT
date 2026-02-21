# APIFY Async Fetch Review (`/student/ai-resume-matcher`)

## Findings (ordered by severity)

1. **High: request lifecycle was blocked by live APIFY fetch + ranking**
   - Before this update, `POST /api/student/jobs/recommend` did the complete APIFY job pull and ranking inline.
   - Result: long response times, frontend spinner lock, and higher timeout risk under slow actor runs.
   - Code path: `frontend/src/pages/student/AIResumeMatcher.tsx` -> `frontend/src/services/studentService.ts` -> `backend/routes/student.py` -> `backend/ai_recommendation_service.py` -> `backend/apify_jobs_service.py` -> `apify/app/utils/apify_client.py`.

2. **High: no job queue contract for async progress polling**
   - The page had no enqueue/status polling model, so the UI could only wait for one large blocking HTTP response.
   - This made it hard to provide accurate state like `queued/running/failed/succeeded` and hard to recover cleanly.

3. **Medium: repeated identical requests could trigger repeated expensive APIFY scrapes**
   - Toggle/retry behavior could re-run the same payload immediately.
   - No dedupe key for active jobs was present before.

4. **Medium: no bounded per-user async workload policy**
   - There was no cap preventing a single user from creating too many expensive live fetches.

5. **Medium: stale UI requests were not cancel-aware**
   - A newer request could supersede an older one, but the old expensive work would still continue.

## What Was Implemented

### 1. Queue Worker Service (backend)
- Added `backend/apify_recommendation_queue.py`.
- Introduced in-process async queue with worker threads and job lifecycle:
  - statuses: `queued`, `running`, `succeeded`, `failed`, `cancelled`
  - bounded workers (`APIFY_ASYNC_WORKERS`, capped by `APIFY_ASYNC_MAX_WORKERS`)
  - per-user active job limit (`APIFY_ASYNC_MAX_ACTIVE_JOBS_PER_USER`)
  - payload-hash dedupe for identical active requests
  - terminal job TTL cleanup (`APIFY_ASYNC_JOB_TTL_SECONDS`)
  - polling hint (`APIFY_ASYNC_POLL_INTERVAL_MS`)
- Worker executes `AIRecommendationService.get_recommendations(...)` under Flask app context and clears SQLAlchemy thread session.

### 2. Async Recommendation API Endpoints
Added to `backend/routes/student.py`:
- `POST /api/student/jobs/recommend/async`
  - enqueues recommendation task and returns quickly (`202` when new, `200` when deduped existing)
- `GET /api/student/jobs/recommend/async/<job_id>`
  - returns current status; returns recommendations when succeeded
- `DELETE /api/student/jobs/recommend/async/<job_id>`
  - cancels queued jobs (not running/completed)

Also refactored payload parsing in `backend/routes/student.py`:
- `_build_resume_analysis_payload(...)` to normalize and fallback to saved profile skills
- `_parse_top_n(...)` for consistent bounds handling

### 3. Frontend Async Polling Flow (`/student/ai-resume-matcher`)
Updated `frontend/src/pages/student/AIResumeMatcher.tsx` and `frontend/src/services/studentService.ts`:
- When `Use Live Apify Jobs` is enabled:
  - enqueue async recommendation job
  - poll status until `succeeded/failed/cancelled` with timeout guard
  - show meaningful loading state (`queued` position / running message)
  - cancel stale queued jobs when user triggers a newer request
- Database source (`useApify=false`) stays on existing synchronous recommendation path.
- Existing fallback behavior remains:
  - if live returns zero jobs or fails, auto-fallback to internal source.

## Best-Practice Notes for APIFY Fetching

1. **Do not keep live scraping in the request path**
   - enqueue + poll (or websocket push) is the right model for unpredictable external scraper latency.

2. **Use bounded workers + per-user quotas**
   - prevents one user/session from saturating workers.

3. **Deduplicate active payloads**
   - avoids repeating identical expensive APIFY runs.

4. **Expose explicit task state contract**
   - `queued/running/succeeded/failed/cancelled` improves UX and troubleshooting.

5. **Session hygiene in worker threads**
   - always remove DB sessions at end of background thread work.

## Important Production Consideration

Current implementation is **in-process queueing** (thread workers in Flask process), which is appropriate for immediate improvement and local/single-instance deployment.

For multi-instance production, use an external durable queue (Redis + RQ/Celery/Arq) so jobs survive restarts and can be consumed across replicas.

## Verification Performed

- `python -m py_compile backend/apify_recommendation_queue.py backend/routes/student.py`
- `npm run -s build` in `frontend/` (build succeeded)

