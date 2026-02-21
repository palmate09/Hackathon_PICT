import io
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PyPDF2 import PdfReader
from docx import Document
from PIL import Image, ImageOps
from dotenv import dotenv_values

try:
    import numpy as np
except ImportError:
    np = None

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    from paddleocr import PaddleOCR
except ImportError:
    PaddleOCR = None

try:
    from resume_extraction_service_free import parse_resume_free
except ImportError:
    parse_resume_free = None


_PADDLE_INSTANCE = None
_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif"}
_SKILL_ALIASES = {
    "js": "javascript",
    "node": "node.js",
    "nodejs": "node.js",
    "py": "python",
    "ts": "typescript",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "reactjs": "react",
    "nextjs": "next.js",
}
_SKILL_NOISE_TERMS = {
    "company",
    "companies",
    "role",
    "roles",
    "quiz",
    "quizzes",
    "question",
    "questions",
    "submission",
    "submissions",
    "interactive",
    "efficient",
    "pimpri",
    "chinchwad",
    "batch",
    "cgpa",
    "hsc",
    "ssc",
    "board",
    "university",
    "college",
    "experience",
    "user",
    "users",
    "worker",
    "workers",
    "options",
    "real",
    "http",
    "https",
    "protocol",
    "protocols",
    "message",
    "broadcasting",
    "tailwind",
    "tailwindcss",
    "yashwant",
    "vidyalaya",
}
_SKILL_TOKEN_STOPWORDS = {"and", "or", "with", "on", "in", "at", "for", "to", "from", "of", "the", "a", "an"}
_TECH_TOKEN_WHITELIST = {
    "python", "java", "javascript", "typescript", "node", "node.js", "react", "angular", "vue", "next", "next.js",
    "express", "django", "flask", "spring", "sql", "mysql", "postgres", "postgresql", "mongodb", "redis",
    "aws", "azure", "gcp", "docker", "kubernetes", "html", "css", "go", "rust", "php", "c++", "c#", "c",
    "pandas", "numpy", "tensorflow", "pytorch", "git", "github", "gitlab", "jenkins", "tailwind",
}

_MODULE_DIR = Path(__file__).resolve().parent
_ROOT_ENV_PATH = _MODULE_DIR.parent / ".env"
_BACKEND_ENV_PATH = _MODULE_DIR / ".env"
_ROOT_ENV_VALUES = dotenv_values(_ROOT_ENV_PATH) if _ROOT_ENV_PATH.exists() else {}
_BACKEND_ENV_VALUES = dotenv_values(_BACKEND_ENV_PATH) if _BACKEND_ENV_PATH.exists() else {}


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _text_quality_score(text: str) -> float:
    """Heuristic text quality score in [0, 1] to compare native vs OCR text."""
    cleaned = _clean_text(text)
    if not cleaned:
        return 0.0

    total = len(cleaned)
    alnum_ratio = sum(1 for ch in cleaned if ch.isalnum()) / max(total, 1)
    space_ratio = cleaned.count(" ") / max(total, 1)
    tokens = re.findall(r"[a-z0-9\+\#\.\-]{2,}", cleaned.lower())
    token_count = len(tokens)
    unique_ratio = len(set(tokens)) / max(token_count, 1) if token_count else 0.0
    token_density = min(token_count / 180.0, 1.0)

    score = (
        (alnum_ratio * 0.3)
        + (min(space_ratio * 4.0, 1.0) * 0.25)
        + (token_density * 0.3)
        + (min(unique_ratio * 1.2, 1.0) * 0.15)
    )
    return round(max(0.0, min(score, 1.0)), 4)


def _likely_scanned_or_low_quality_pdf(text: str, scan_threshold: int) -> bool:
    cleaned = _clean_text(text)
    if len(cleaned) < scan_threshold:
        return True
    quality = _text_quality_score(cleaned)
    return quality < 0.5


def _as_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _get_config_value(key: str, default: str = "") -> str:
    """
    Resolve config with deterministic precedence:
    backend/.env -> root .env -> process env -> default.
    """
    for source in (_BACKEND_ENV_VALUES, _ROOT_ENV_VALUES, os.environ):
        raw = source.get(key) if source is not os.environ else os.getenv(key)
        if raw is None:
            continue
        text = str(raw).strip()
        if text:
            return text
    return default


def _get_extension(filename: str) -> str:
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].strip().lower()


def _decode_text_bytes(data: bytes) -> str:
    try:
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _normalize_unique(values: Any, limit: int = 50) -> List[str]:
    if not values:
        return []
    if isinstance(values, str):
        candidates = [part.strip() for part in values.split(",")]
    elif isinstance(values, list):
        candidates = [str(item).strip() for item in values]
    else:
        return []

    seen = set()
    output = []
    for value in candidates:
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(value)
        if len(output) >= limit:
            break
    return output


def _canonicalize_skill(raw_skill: str) -> str:
    if not raw_skill:
        return ""
    normalized = re.sub(r"\s+", " ", raw_skill).strip().lower()
    normalized = normalized.replace("_", " ").replace("-", " ")
    normalized = _SKILL_ALIASES.get(normalized, normalized)
    return normalized


def _is_valid_skill_candidate(raw_skill: str, canonical_skill: str) -> bool:
    candidate = _clean_text(canonical_skill or raw_skill).lower()
    if not candidate:
        return False
    if len(candidate) < 2 or len(candidate) > 40:
        return False
    if re.search(r"\b(19|20)\d{2}\b", candidate):
        return False

    tokens = [t for t in re.findall(r"[a-z0-9\+\#\.]+", candidate) if t]
    tokens = [token for token in tokens if token not in _SKILL_TOKEN_STOPWORDS]
    if not tokens or len(tokens) > 4:
        return False
    if all(token in _SKILL_NOISE_TERMS for token in tokens):
        return False
    if any(token in _SKILL_NOISE_TERMS for token in tokens) and len(tokens) <= 2:
        return False
    if len(tokens) > 1 and not any(token in _TECH_TOKEN_WHITELIST for token in tokens):
        return False

    return True


def _build_resilient_http_session() -> requests.Session:
    retry_total = int(_get_config_value("GEMINI_HTTP_RETRIES", "2"))
    retry_backoff = float(_get_config_value("GEMINI_HTTP_BACKOFF", "0.8"))

    retry = Retry(
        total=retry_total,
        connect=retry_total,
        read=retry_total,
        status=retry_total,
        allowed_methods=frozenset({"POST"}),
        status_forcelist=(408, 429, 500, 502, 503, 504),
        backoff_factor=retry_backoff,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.trust_env = _as_bool(_get_config_value("GEMINI_TRUST_ENV", "false"), default=False)
    return session


def _sanitize_error_text(value: str) -> str:
    text = str(value or "")
    # Remove query-param API key leakage
    text = re.sub(r"(key=)[^&\s]+", r"\1***", text, flags=re.IGNORECASE)
    # Remove accidental raw key leakage
    key = _get_config_value("GEMINI_API_KEY", "")
    if key:
        text = text.replace(key, "***")
    return text


def _extract_pdf_text_and_images(data: bytes, include_images: bool = False) -> Tuple[str, List[Image.Image]]:
    images: List[Image.Image] = []

    if fitz is not None:
        try:
            document = fitz.open(stream=data, filetype="pdf")
            page_texts = []
            dpi = int(_get_config_value("OCR_PDF_DPI", "220"))
            zoom = max(dpi, 72) / 72
            matrix = fitz.Matrix(zoom, zoom)

            try:
                for page in document:
                    page_texts.append(page.get_text("text") or "")
                    if include_images:
                        pix = page.get_pixmap(matrix=matrix, alpha=False)
                        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        images.append(image)
            finally:
                document.close()

            return "\n".join(page_texts), images
        except Exception:
            pass

    reader = PdfReader(io.BytesIO(data))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return text, images


def _extract_text_without_ocr(data: bytes, filename: str) -> str:
    ext = _get_extension(filename)
    if ext == "pdf":
        text, _ = _extract_pdf_text_and_images(data, include_images=False)
        return text
    if ext == "docx":
        doc = Document(io.BytesIO(data))
        return "\n".join(paragraph.text for paragraph in doc.paragraphs)
    return _decode_text_bytes(data)


def _prepare_image_for_ocr(image: Image.Image) -> Image.Image:
    prepared = ImageOps.exif_transpose(image).convert("RGB")

    if cv2 is None or np is None:
        grayscale = ImageOps.grayscale(prepared)
        return ImageOps.autocontrast(grayscale)

    bgr = cv2.cvtColor(np.array(prepared), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    denoised = cv2.GaussianBlur(gray, (3, 3), 0)
    thresholded = cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )
    return Image.fromarray(thresholded)


def _build_paddle_ocr():
    global _PADDLE_INSTANCE
    if _PADDLE_INSTANCE is not None:
        return _PADDLE_INSTANCE
    if PaddleOCR is None:
        return None

    lang = _get_config_value("OCR_LANG", "en")
    _PADDLE_INSTANCE = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
    return _PADDLE_INSTANCE


def _ocr_with_paddle(image: Image.Image) -> Tuple[str, float]:
    if np is None:
        raise RuntimeError("numpy is required for PaddleOCR")
    ocr = _build_paddle_ocr()
    if ocr is None:
        raise RuntimeError("PaddleOCR is not installed")

    prepared = _prepare_image_for_ocr(image).convert("RGB")
    result = ocr.ocr(np.array(prepared), cls=True) or []

    lines: List[str] = []
    confidences: List[float] = []
    for page in result:
        if not page:
            continue
        for entry in page:
            if not entry or len(entry) < 2:
                continue
            content = entry[1]
            if not isinstance(content, (list, tuple)) or len(content) < 2:
                continue
            text = str(content[0]).strip()
            confidence = float(content[1]) if content[1] is not None else 0.0
            if text:
                lines.append(text)
                confidences.append(confidence)

    merged = _clean_text("\n".join(lines))
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    return merged, round(avg_confidence, 4)


def _ocr_with_tesseract(image: Image.Image) -> Tuple[str, float]:
    if pytesseract is None:
        raise RuntimeError("pytesseract is not installed")

    tesseract_cmd = _get_config_value("TESSERACT_CMD", "").strip()
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    prepared = _prepare_image_for_ocr(image)
    lang = _get_config_value("OCR_LANG", "eng")

    data = pytesseract.image_to_data(
        prepared,
        lang=lang,
        config="--oem 3 --psm 6",
        output_type=pytesseract.Output.DICT,
    )

    tokens = []
    confidences = []
    for text, confidence in zip(data.get("text", []), data.get("conf", [])):
        token = str(text or "").strip()
        if not token:
            continue
        tokens.append(token)
        try:
            conf_value = float(confidence)
            if conf_value >= 0:
                confidences.append(conf_value / 100.0)
        except (TypeError, ValueError):
            continue

    merged = _clean_text(" ".join(tokens))
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    return merged, round(avg_confidence, 4)


def _select_ocr_engine() -> str:
    preference = _get_config_value("OCR_ENGINE", "auto").strip().lower()

    if preference == "paddle" and PaddleOCR is not None:
        return "paddleocr"
    if preference == "tesseract" and pytesseract is not None:
        return "tesseract"
    if preference == "none":
        return "none"

    if PaddleOCR is not None:
        return "paddleocr"
    if pytesseract is not None:
        return "tesseract"
    return "unavailable"


def _ocr_images(images: List[Image.Image]) -> Dict[str, Any]:
    engine = _select_ocr_engine()
    if engine in {"none", "unavailable"} or not images:
        return {
            "text": "",
            "engine": engine,
            "confidence": 0.0,
            "error": "OCR engine unavailable (install paddleocr or pytesseract+tesseract)." if engine == "unavailable" else "",
        }

    page_texts = []
    page_confidences = []
    for image in images:
        text = ""
        confidence = 0.0

        try:
            if engine == "paddleocr":
                text, confidence = _ocr_with_paddle(image)
            else:
                text, confidence = _ocr_with_tesseract(image)
        except Exception:
            # Fallback from PaddleOCR to Tesseract per image when available.
            if engine == "paddleocr" and pytesseract is not None:
                try:
                    text, confidence = _ocr_with_tesseract(image)
                    engine = "tesseract"
                except Exception:
                    text, confidence = "", 0.0

        if text:
            page_texts.append(text)
        if confidence > 0:
            page_confidences.append(confidence)

    merged = _clean_text("\n".join(page_texts))
    avg_confidence = sum(page_confidences) / len(page_confidences) if page_confidences else 0.0
    return {
        "text": merged,
        "engine": engine,
        "confidence": round(avg_confidence, 4),
        "error": "",
    }


def _extract_raw_text_with_metadata(data: bytes, filename: str) -> Tuple[str, Dict[str, Any]]:
    ext = _get_extension(filename)
    ocr_enabled = _as_bool(_get_config_value("OCR_ENABLE", "true"), default=True)
    scan_threshold = int(_get_config_value("OCR_SCAN_TEXT_THRESHOLD", "180"))

    raw_text = ""
    ocr_text = ""
    ocr_used = False
    ocr_engine = "none"
    ocr_confidence = 0.0
    ocr_error = ""

    if ext == "pdf":
        native_text, page_images = _extract_pdf_text_and_images(data, include_images=True)
        raw_text = _clean_text(native_text)
        force_pdf_ocr = _as_bool(_get_config_value("OCR_FORCE_PDF", "false"), default=False)
        likely_scanned = _likely_scanned_or_low_quality_pdf(raw_text, scan_threshold=scan_threshold)
        native_quality = _text_quality_score(raw_text)

        if ocr_enabled and page_images and (force_pdf_ocr or likely_scanned):
            ocr_result = _ocr_images(page_images)
            ocr_text = ocr_result["text"]
            ocr_engine = ocr_result["engine"]
            ocr_confidence = float(ocr_result["confidence"])
            ocr_error = str(ocr_result.get("error", "")).strip()
            ocr_used = bool(ocr_text)
            ocr_quality = _text_quality_score(ocr_text)
            ocr_weighted_quality = min(1.0, (ocr_quality * 0.8) + (ocr_confidence * 0.2))
            if ocr_weighted_quality >= native_quality or len(ocr_text) > len(raw_text):
                raw_text = ocr_text

    elif ext == "docx":
        raw_text = _clean_text(_extract_text_without_ocr(data, filename))
    elif ext in _IMAGE_EXTENSIONS:
        if ocr_enabled:
            image = Image.open(io.BytesIO(data))
            ocr_result = _ocr_images([image])
            raw_text = _clean_text(ocr_result["text"])
            ocr_engine = ocr_result["engine"]
            ocr_confidence = float(ocr_result["confidence"])
            ocr_error = str(ocr_result.get("error", "")).strip()
            ocr_used = bool(raw_text)
        else:
            raw_text = ""
    else:
        raw_text = _clean_text(_extract_text_without_ocr(data, filename))

    char_score = min(len(raw_text) / 5000.0, 1.0)
    ocr_component = ocr_confidence if ocr_used else 1.0
    text_component = _text_quality_score(raw_text)
    quality_score = round((char_score * 0.45) + (text_component * 0.35) + (ocr_component * 0.2), 4)

    metadata = {
        "chars": len(raw_text),
        "ocr_used": ocr_used,
        "ocr_engine": ocr_engine,
        "ocr_confidence": ocr_confidence,
        "quality_score": quality_score,
        "text_quality_score": text_component,
        "ocr_error": ocr_error,
        "ocr_available": ocr_engine not in {"none", "unavailable"},
    }
    return raw_text, metadata


def _extract_json_object(raw_text: str) -> Dict[str, Any]:
    if not raw_text:
        return {}
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


def _gemini_structured_parse(text: str) -> Dict[str, Any]:
    api_key = _get_config_value("GEMINI_API_KEY") or _get_config_value("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY (or GOOGLE_API_KEY) is not set")

    model = _get_config_value("GEMINI_MODEL", "gemini-2.5-flash")
    timeout_seconds = int(_get_config_value("GEMINI_TIMEOUT_SECONDS", "45"))
    max_chars = int(_get_config_value("RESUME_PARSE_MAX_CHARS", "22000"))

    prompt = (
        "You are a strict resume information extractor. "
        "Return ONLY valid JSON. No markdown. No explanations.\n"
        "Schema:\n"
        "{\n"
        '  "contact": {"name": "", "email": "", "phone": "", "location": ""},\n'
        '  "skills": [{"raw": "", "canonical": "", "confidence": 0.0, "evidence": ""}],\n'
        '  "experience": {"years": 0, "career_level": "entry"},\n'
        '  "summary": "",\n'
        '  "recommended_roles": [""],\n'
        '  "education": [{"degree": "", "institution": "", "start": "", "end": ""}],\n'
        '  "keywords": [""],\n'
        '  "tech_stack": [""],\n'
        '  "missing_skills": [""],\n'
        '  "strengths": [""]\n'
        "}\n"
        "Rules:\n"
        "- Infer carefully from resume text only.\n"
        "- Keep confidence between 0 and 1.\n"
        "- Canonical skill names should be lowercase.\n"
        "- If value unknown, use empty string/list or 0."
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            f"{prompt}\n\nResume text starts:\n{text[:max_chars]}\n\nResume text ends."
                        )
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }

    endpoints_raw = _get_config_value(
        "GEMINI_API_ENDPOINTS",
        "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent|https://generativelanguage.googleapis.com/v1/models/{model}:generateContent",
    )
    endpoints = [endpoint.strip() for endpoint in endpoints_raw.split("|") if endpoint.strip()]
    session = _build_resilient_http_session()

    body = None
    errors: List[str] = []
    for endpoint in endpoints:
        url = endpoint.format(model=model)
        try:
            response = session.post(
                url,
                params={"key": api_key},
                json=payload,
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
            break
        except Exception as exc:
            errors.append(_sanitize_error_text(str(exc)))
            continue

    if body is None:
        raise RuntimeError("Gemini request failed: " + " | ".join(errors[:2]))

    candidates = body.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini did not return any candidates")

    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        raise RuntimeError("Gemini response did not contain content parts")

    text_response = parts[0].get("text", "")
    parsed = _extract_json_object(text_response)
    if not parsed:
        raise RuntimeError("Gemini response was not valid JSON")
    parsed["_gemini_model"] = model
    parsed["_method"] = "gemini"
    return parsed


def _free_fallback_parse(text: str) -> Dict[str, Any]:
    parsed = parse_resume_free(text) if parse_resume_free else {}
    contact = {
        "name": parsed.get("name", ""),
        "email": parsed.get("email", ""),
        "phone": parsed.get("phone", ""),
        "location": parsed.get("location", ""),
    }
    skills = []
    for skill in _normalize_unique(parsed.get("skills", []), limit=50):
        canonical = _canonicalize_skill(skill)
        if not canonical:
            continue
        skills.append(
            {
                "raw": skill,
                "canonical": canonical,
                "confidence": 0.65,
                "evidence": "rule_based",
            }
        )

    return {
        "contact": contact,
        "skills": skills,
        "experience": {"years": 0, "career_level": "entry"},
        "summary": "",
        "recommended_roles": [],
        "education": parsed.get("education", []),
        "keywords": _normalize_unique(parsed.get("keywords", []), limit=20),
        "tech_stack": [],
        "missing_skills": [],
        "strengths": [],
        "_method": "rule_based",
        "_gemini_model": "",
    }


def parse_resume_with_llm(text: str) -> Dict[str, Any]:
    """
    Parse resume text into structured JSON using Gemini.
    Falls back to rule-based extraction when Gemini is unavailable.
    """
    cleaned = _clean_text(text)
    if not cleaned:
        fallback = _free_fallback_parse("")
        fallback["_gemini_status"] = "empty_input"
        fallback["_gemini_error"] = ""
        return fallback

    gemini_status = "not_configured"
    gemini_error = ""
    parsed = {}
    has_gemini_key = bool((_get_config_value("GEMINI_API_KEY") or _get_config_value("GOOGLE_API_KEY") or "").strip())
    try:
        if has_gemini_key:
            parsed = _gemini_structured_parse(cleaned)
            gemini_status = "success"
        else:
            parsed = _free_fallback_parse(cleaned)
    except Exception as exc:
        gemini_status = "failed"
        gemini_error = _sanitize_error_text(str(exc))
        print(f"[ResumeParse] Gemini parsing failed, falling back to rule-based parser: {gemini_error}", flush=True)
        parsed = _free_fallback_parse(cleaned)

    contact = parsed.get("contact", {})
    if not isinstance(contact, dict):
        contact = {}

    normalized_skills = []
    for item in parsed.get("skills", []):
        if isinstance(item, dict):
            raw_skill = str(item.get("raw", "")).strip()
            canonical_skill = _canonicalize_skill(str(item.get("canonical") or raw_skill))
            confidence = item.get("confidence", 0.0)
            try:
                confidence = max(0.0, min(1.0, float(confidence)))
            except (TypeError, ValueError):
                confidence = 0.0
            evidence = str(item.get("evidence", "")).strip()[:180]
        else:
            raw_skill = str(item).strip()
            canonical_skill = _canonicalize_skill(raw_skill)
            confidence = 0.7
            evidence = ""

        if not canonical_skill:
            continue
        if not _is_valid_skill_candidate(raw_skill, canonical_skill):
            continue

        normalized_skills.append(
            {
                "raw": raw_skill or canonical_skill,
                "canonical": canonical_skill,
                "confidence": round(confidence, 4),
                "evidence": evidence,
            }
        )

    if not normalized_skills:
        for skill in _normalize_unique(parsed.get("keywords", []), limit=15):
            canonical_skill = _canonicalize_skill(skill)
            if canonical_skill and _is_valid_skill_candidate(skill, canonical_skill):
                normalized_skills.append(
                    {
                        "raw": skill,
                        "canonical": canonical_skill,
                        "confidence": 0.55,
                        "evidence": "keyword_fallback",
                    }
                )

    experience = parsed.get("experience", {})
    if not isinstance(experience, dict):
        experience = {}
    try:
        years = float(experience.get("years", 0) or 0)
    except (TypeError, ValueError):
        years = 0.0
    career_level = str(experience.get("career_level", "entry") or "entry").strip().lower()
    if career_level not in {"entry", "junior", "mid", "senior", "lead"}:
        career_level = "entry"

    return {
        "contact": {
            "name": str(contact.get("name", "")).strip(),
            "email": str(contact.get("email", "")).strip(),
            "phone": str(contact.get("phone", "")).strip(),
            "location": str(contact.get("location", "")).strip(),
        },
        "skills": normalized_skills,
        "experience": {"years": years, "career_level": career_level},
        "summary": str(parsed.get("summary", "")).strip(),
        "recommended_roles": _normalize_unique(parsed.get("recommended_roles", []), limit=10),
        "education": parsed.get("education", []) if isinstance(parsed.get("education", []), list) else [],
        "keywords": _normalize_unique(parsed.get("keywords", []), limit=25),
        "tech_stack": _normalize_unique(parsed.get("tech_stack", []), limit=20),
        "missing_skills": _normalize_unique(parsed.get("missing_skills", []), limit=20),
        "strengths": _normalize_unique(parsed.get("strengths", []), limit=20),
        "_method": parsed.get("_method", "unknown"),
        "_gemini_model": parsed.get("_gemini_model", ""),
        "_gemini_status": gemini_status,
        "_gemini_error": gemini_error[:250],
        "_gemini_configured": has_gemini_key,
    }


def extract_text_from_bytes(data: bytes, filename: str) -> str:
    """
    Extract raw text from file bytes.
    OCR is automatically used for image files and scanned PDFs when enabled.
    """
    raw_text, _ = _extract_raw_text_with_metadata(data, filename)
    return raw_text


def extract_text_from_path(path: str) -> str:
    with open(path, "rb") as file_obj:
        payload = file_obj.read()
    return extract_text_from_bytes(payload, path)


def extract_resume_data(data: bytes, filename: str) -> Dict[str, Any]:
    """
    Extract raw text (with OCR when needed), then parse to structured output via Gemini.
    Returns a backward-compatible payload used by the recommendation service.
    """
    raw_text, text_meta = _extract_raw_text_with_metadata(data, filename)
    cleaned = _clean_text(raw_text)
    structured = parse_resume_with_llm(cleaned)

    contact = structured.get("contact", {})
    skills_detailed = structured.get("skills", [])
    canonical_skills = _normalize_unique(
        [item.get("canonical", "") for item in skills_detailed if isinstance(item, dict)],
        limit=50,
    )
    raw_skills = _normalize_unique(
        [item.get("raw", "") for item in skills_detailed if isinstance(item, dict)],
        limit=50,
    )
    keywords = structured.get("keywords", []) or canonical_skills[:15]

    experience = structured.get("experience", {})
    years = float(experience.get("years", 0) or 0)
    career_level = str(experience.get("career_level", "entry") or "entry")

    provider = "gemini" if structured.get("_method") == "gemini" else "rule_based"
    model_name = structured.get("_gemini_model", "")
    llm_method = structured.get("_method", provider)

    llm_analysis = {
        "cleaned_skills": canonical_skills,
        "professional_summary": structured.get("summary", ""),
        "recommended_roles": structured.get("recommended_roles", []),
        "missing_skills": structured.get("missing_skills", []),
        "experience_years": years,
        "tech_stack": structured.get("tech_stack", []),
        "strengths": structured.get("strengths", []),
        "career_level": career_level,
        "method": llm_method,
        "gemini_status": structured.get("_gemini_status", "unknown"),
        "gemini_configured": structured.get("_gemini_configured", False),
    }

    return {
        "name": contact.get("name", ""),
        "email": contact.get("email", ""),
        "phone": contact.get("phone", ""),
        "location": contact.get("location", ""),
        "contact": contact,
        "skills": canonical_skills or raw_skills,
        "skills_detailed": skills_detailed,
        "keywords": keywords,
        "education": structured.get("education", []),
        "experience": structured.get("experience", {}),
        "experience_years": years,
        "career_level": career_level,
        "summary": structured.get("summary", ""),
        "professional_summary": structured.get("summary", ""),
        "recommended_roles": structured.get("recommended_roles", []),
        "tech_stack": structured.get("tech_stack", []),
        "missing_skills": structured.get("missing_skills", []),
        "strengths": structured.get("strengths", []),
        "raw_text": cleaned[:5000],
        "raw_text_quality": {
            "chars": text_meta.get("chars", 0),
            "ocr_used": text_meta.get("ocr_used", False),
            "quality_score": text_meta.get("quality_score", 0.0),
            "ocr_confidence": text_meta.get("ocr_confidence", 0.0),
            "text_quality_score": text_meta.get("text_quality_score", 0.0),
            "ocr_error": text_meta.get("ocr_error", ""),
            "ocr_available": text_meta.get("ocr_available", False),
        },
        "model_meta": {
            "provider": provider,
            "model": model_name,
            "ocr_engine": text_meta.get("ocr_engine", "none"),
            "gemini_status": structured.get("_gemini_status", "unknown"),
            "gemini_error": structured.get("_gemini_error", ""),
            "gemini_configured": structured.get("_gemini_configured", False),
            "pipeline": "ocr_to_gemini",
        },
        "llm_analysis": llm_analysis,
    }

