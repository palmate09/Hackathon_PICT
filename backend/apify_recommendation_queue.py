import hashlib
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from queue import Queue
from typing import Any, Dict, List, Optional, Tuple

from flask import Flask

from ai_recommendation_service import AIRecommendationService
from models import db


DEFAULT_WORKER_COUNT = int(os.getenv("APIFY_ASYNC_WORKERS", "2"))
MAX_WORKER_COUNT = int(os.getenv("APIFY_ASYNC_MAX_WORKERS", "6"))
JOB_TTL_SECONDS = int(os.getenv("APIFY_ASYNC_JOB_TTL_SECONDS", "900"))
MAX_ACTIVE_JOBS_PER_USER = int(os.getenv("APIFY_ASYNC_MAX_ACTIVE_JOBS_PER_USER", "2"))
DEFAULT_POLL_INTERVAL_MS = int(os.getenv("APIFY_ASYNC_POLL_INTERVAL_MS", "1500"))


@dataclass
class RecommendationJob:
    job_id: str
    user_id: Any
    payload_hash: str
    resume_analysis: Dict[str, Any]
    use_apify: bool
    top_n: int
    location: str
    status: str = "queued"  # queued | running | succeeded | failed | cancelled
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: str = ""
    recommendations: List[Dict[str, Any]] = field(default_factory=list)


class ApifyRecommendationQueue:
    def __init__(self, app: Flask, worker_count: int = DEFAULT_WORKER_COUNT):
        self._app = app
        bounded_worker_count = max(1, min(worker_count, MAX_WORKER_COUNT))
        self._worker_count = bounded_worker_count
        self._queue: Queue = Queue()
        self._jobs: Dict[str, RecommendationJob] = {}
        self._jobs_lock = threading.Lock()
        self._workers: List[threading.Thread] = []
        self._started = False
        self._start_lock = threading.Lock()

    def bind_app(self, app: Flask) -> None:
        self._app = app

    def start(self) -> None:
        with self._start_lock:
            if self._started:
                return
            for idx in range(self._worker_count):
                thread = threading.Thread(
                    target=self._worker_loop,
                    name=f"apify-recommendation-worker-{idx + 1}",
                    daemon=True,
                )
                thread.start()
                self._workers.append(thread)
            self._started = True
            self._app.logger.info(
                "Apify async recommendation queue started with %s worker(s)",
                self._worker_count,
            )

    def enqueue(
        self,
        *,
        user_id: Any,
        resume_analysis: Dict[str, Any],
        use_apify: bool,
        top_n: int,
        location: str,
    ) -> Tuple[RecommendationJob, bool]:
        self.start()
        payload_hash = self._hash_payload(
            user_id=user_id,
            resume_analysis=resume_analysis,
            use_apify=use_apify,
            top_n=top_n,
            location=location,
        )

        with self._jobs_lock:
            self._cleanup_expired_locked()

            duplicate = self._find_duplicate_active_job_locked(user_id, payload_hash)
            if duplicate:
                return duplicate, False

            active_count = self._active_jobs_for_user_locked(user_id)
            if active_count >= MAX_ACTIVE_JOBS_PER_USER:
                raise RuntimeError(
                    f"Too many active recommendation jobs ({MAX_ACTIVE_JOBS_PER_USER} max). Please wait."
                )

            job = RecommendationJob(
                job_id=uuid.uuid4().hex,
                user_id=user_id,
                payload_hash=payload_hash,
                resume_analysis=resume_analysis,
                use_apify=use_apify,
                top_n=top_n,
                location=AIRecommendationService.sanitize_location(location),
            )
            self._jobs[job.job_id] = job

        self._queue.put(job.job_id)
        return job, True

    def get_job(self, job_id: str, user_id: Any) -> Optional[RecommendationJob]:
        with self._jobs_lock:
            self._cleanup_expired_locked()
            job = self._jobs.get(job_id)
            if not job or str(job.user_id) != str(user_id):
                return None
            return job

    def cancel_job(self, job_id: str, user_id: Any) -> bool:
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            if not job or str(job.user_id) != str(user_id):
                return False
            if job.status != "queued":
                return False
            job.status = "cancelled"
            job.completed_at = time.time()
            job.error = "Cancelled by user"
            return True

    def serialize_job(self, job: RecommendationJob, include_result: bool = True) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "job_id": job.job_id,
            "status": job.status,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "retry_after_ms": DEFAULT_POLL_INTERVAL_MS,
        }

        if job.status == "queued":
            payload["queue_position"] = self._queue_position(job.job_id)

        if include_result and job.status == "succeeded":
            payload["recommendations"] = job.recommendations
            payload["total"] = len(job.recommendations)
        elif include_result and job.status in {"failed", "cancelled"}:
            payload["error"] = job.error or "Recommendation job failed"
        return payload

    def _worker_loop(self) -> None:
        while True:
            job_id = self._queue.get()
            try:
                self._process_job(job_id)
            finally:
                self._queue.task_done()

    def _process_job(self, job_id: str) -> None:
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            if job.status != "queued":
                return
            job.status = "running"
            job.started_at = time.time()

        recommendations: List[Dict[str, Any]] = []
        error_text = ""
        try:
            with self._app.app_context():
                recommendations = AIRecommendationService.get_recommendations(
                    resume_analysis=job.resume_analysis,
                    use_apify=job.use_apify,
                    top_n=job.top_n,
                    location=job.location,
                )
                db.session.remove()
        except Exception as exc:
            error_text = str(exc)
            try:
                with self._app.app_context():
                    db.session.remove()
            except Exception:
                pass

        with self._jobs_lock:
            current = self._jobs.get(job_id)
            if not current:
                return
            if current.status == "cancelled":
                current.completed_at = time.time()
                return
            if error_text:
                current.status = "failed"
                current.error = error_text
                current.completed_at = time.time()
                return
            current.status = "succeeded"
            current.recommendations = recommendations
            current.completed_at = time.time()

    def _queue_position(self, job_id: str) -> int:
        with self._queue.mutex:
            pending_ids = list(self._queue.queue)
        try:
            return pending_ids.index(job_id) + 1
        except ValueError:
            return 0

    def _find_duplicate_active_job_locked(
        self, user_id: Any, payload_hash: str
    ) -> Optional[RecommendationJob]:
        for job in self._jobs.values():
            if str(job.user_id) != str(user_id):
                continue
            if job.status not in {"queued", "running"}:
                continue
            if job.payload_hash == payload_hash:
                return job
        return None

    def _active_jobs_for_user_locked(self, user_id: Any) -> int:
        return sum(
            1
            for job in self._jobs.values()
            if str(job.user_id) == str(user_id) and job.status in {"queued", "running"}
        )

    def _cleanup_expired_locked(self) -> None:
        now = time.time()
        to_delete: List[str] = []
        for job_id, job in self._jobs.items():
            if job.status in {"queued", "running"}:
                continue
            terminal_at = job.completed_at or job.created_at
            if now - terminal_at > JOB_TTL_SECONDS:
                to_delete.append(job_id)
        for job_id in to_delete:
            self._jobs.pop(job_id, None)

    @staticmethod
    def _hash_payload(
        *,
        user_id: Any,
        resume_analysis: Dict[str, Any],
        use_apify: bool,
        top_n: int,
        location: str,
    ) -> str:
        key_payload = {
            "user_id": str(user_id),
            "use_apify": bool(use_apify),
            "top_n": int(top_n),
            "location": AIRecommendationService.sanitize_location(location),
            "resume_analysis": resume_analysis,
        }
        normalized = json.dumps(key_payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


_queue_instance: Optional[ApifyRecommendationQueue] = None
_queue_instance_lock = threading.Lock()


def get_apify_recommendation_queue(app: Flask) -> ApifyRecommendationQueue:
    global _queue_instance
    with _queue_instance_lock:
        if _queue_instance is None:
            _queue_instance = ApifyRecommendationQueue(app=app)
        else:
            _queue_instance.bind_app(app)
        _queue_instance.start()
        return _queue_instance
