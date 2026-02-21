import React, { useState, useCallback, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { 
  FiUpload, 
  FiFileText, 
  FiX, 
  FiMapPin,
  FiDollarSign,
  FiExternalLink,
  FiLoader,
  FiTrendingUp
} from 'react-icons/fi';
import { studentService } from '../../services/studentService';
import './AIResumeMatcher.css';

interface ResumeAnalysis {
  error?: string;
  extracted_data?: any;
  raw_text_quality?: {
    chars?: number;
    ocr_used?: boolean;
    quality_score?: number;
    ocr_confidence?: number;
    text_quality_score?: number;
    ocr_error?: string;
    ocr_available?: boolean;
  };
  model_meta?: {
    provider?: string;
    model?: string;
    ocr_engine?: string;
    gemini_status?: string;
    gemini_error?: string;
    gemini_configured?: boolean;
    pipeline?: string;
  };
  contact?: {
    name?: string;
    email?: string;
    phone?: string;
    location?: string;
  };
  llm_analysis?: {
    cleaned_skills?: string[];
    professional_summary?: string;
    recommended_roles?: string[];
    missing_skills?: string[];
    experience_years?: number;
    tech_stack?: string[];
    strengths?: string[];
    career_level?: string;
  };
  skills?: string[];
  keywords?: string[];
  experience_years?: number;
  tech_stack?: string[];
  professional_summary?: string;
  recommended_roles?: string[];
  missing_skills?: string[];
}

interface JobRecommendation {
  id?: number;
  title: string;
  company_name: string;
  location: string;
  required_skills: string[];
  match_score: number;
  match_reason: string;
  url?: string;
  source?: string;
  description?: string;
  stipend?: string;
  duration?: string;
  work_type?: string;
  matched_skills?: string[];
  missing_skills?: string[];
  // Flag used for Naukri "direct search" pseudo-jobs
  // These are just redirects to a generic Naukri search page, not real job postings
  is_search?: boolean;
}

const DEFAULT_PAGE_SIZE = 12;
const PAGE_SIZE_OPTIONS = [12, 24, 48, 96];
const DEFAULT_LOCATION_HINT = 'India';

const AIResumeMatcher: React.FC = () => {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [resumeAnalysis, setResumeAnalysis] = useState<ResumeAnalysis | null>(null);
  const [recommendations, setRecommendations] = useState<JobRecommendation[]>([]);
  const [loadingRecommendations, setLoadingRecommendations] = useState(false);
  const [recommendationStatusText, setRecommendationStatusText] = useState<string | null>(null);
  const [useApify, setUseApify] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recommendationRequestRef = useRef(0);
  const supportedMimeTypes = new Set([
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/plain',
    'image/png',
    'image/jpeg',
    'image/jpg',
  ]);

  const hasSupportedExtension = (filename: string): boolean => {
    const ext = filename.split('.').pop()?.toLowerCase();
    return ['pdf', 'doc', 'docx', 'txt', 'png', 'jpg', 'jpeg'].includes(ext || '');
  };

  const isSupportedResumeFile = (candidate: File): boolean =>
    supportedMimeTypes.has(candidate.type) || hasSupportedExtension(candidate.name);

  const normalizeStringList = (value: unknown): string[] => {
    if (Array.isArray(value)) {
      return value
        .map((item) => String(item).trim())
        .filter(Boolean);
    }
    if (typeof value === 'string') {
      return value
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean);
    }
    return [];
  };

  const normalizeResumeAnalysis = (analysis: ResumeAnalysis): ResumeAnalysis => {
    const extractedSkills = normalizeStringList(analysis?.extracted_data?.skills);
    const extractedKeywords = normalizeStringList(analysis?.extracted_data?.keywords);
    const llmSkills = normalizeStringList(analysis?.llm_analysis?.cleaned_skills);

    const normalizedSkills = normalizeStringList(analysis.skills);
    const normalizedKeywords = normalizeStringList(analysis.keywords);
    const normalizedRoles = normalizeStringList(analysis.recommended_roles || analysis.llm_analysis?.recommended_roles);
    const normalizedTechStack = normalizeStringList(analysis.tech_stack || analysis.llm_analysis?.tech_stack);
    const normalizedMissingSkills = normalizeStringList(analysis.missing_skills || analysis.llm_analysis?.missing_skills);
    const extractedRawTextQuality = analysis.raw_text_quality || analysis?.extracted_data?.raw_text_quality;
    const extractedModelMeta = analysis.model_meta || analysis?.extracted_data?.model_meta;
    const extractedContact = analysis.contact || analysis?.extracted_data?.contact;

    return {
      ...analysis,
      skills: normalizedSkills.length ? normalizedSkills : llmSkills.length ? llmSkills : extractedSkills,
      keywords: normalizedKeywords.length ? normalizedKeywords : extractedKeywords,
      recommended_roles: normalizedRoles,
      tech_stack: normalizedTechStack,
      missing_skills: normalizedMissingSkills,
      raw_text_quality: extractedRawTextQuality,
      model_meta: extractedModelMeta,
      contact: extractedContact,
    };
  };

  const normalizeRecommendation = (job: any): JobRecommendation | null => {
    if (!job || typeof job !== 'object') {
      return null;
    }
    const title = String(job.title || '').trim();
    if (!title) {
      return null;
    }

    const parsedMatchScore = Number(job.match_score);
    const matchScore = Number.isFinite(parsedMatchScore)
      ? Math.max(0, Math.min(100, Math.round(parsedMatchScore)))
      : 0;

    const normalizedLocation = String(job.location || 'Not specified')
      .replace(/\s+/g, ' ')
      .trim();
    const safeLocation =
      normalizedLocation.length > 80 || /cgpa|batch|board|university|hsc|ssc|implemented|token-based/i.test(normalizedLocation)
        ? DEFAULT_LOCATION_HINT
        : normalizedLocation;

    return {
      id: typeof job.id === 'number' ? job.id : undefined,
      title,
      company_name: String(job.company_name || 'Unknown Company'),
      location: safeLocation || DEFAULT_LOCATION_HINT,
      required_skills: normalizeStringList(job.required_skills),
      match_score: matchScore,
      match_reason: String(job.match_reason || 'Recommendation based on your profile'),
      url: typeof job.url === 'string' ? job.url : undefined,
      source: typeof job.source === 'string' ? job.source : undefined,
      description: typeof job.description === 'string' ? job.description : undefined,
      stipend: typeof job.stipend === 'string' ? job.stipend : undefined,
      duration: typeof job.duration === 'string' ? job.duration : undefined,
      work_type: typeof job.work_type === 'string' ? job.work_type : undefined,
      matched_skills: normalizeStringList(job.matched_skills),
      missing_skills: normalizeStringList(job.missing_skills),
      is_search: Boolean(job.is_search),
    };
  };

  const isHttpUrl = (value?: string): boolean => {
    if (!value) return false;
    return /^https?:\/\//i.test(value.trim());
  };

  const normalizeInternalPath = (job: JobRecommendation): string => {
    const rawUrl = (job.url || '').trim();
    if (rawUrl.startsWith('/student/opportunities/')) {
      return rawUrl;
    }

    const idFromLegacyUrl = rawUrl.match(/\/opportunities\/(\d+)/i)?.[1];
    const fallbackId = typeof job.id === 'number' ? String(job.id) : '';
    const resolvedId = idFromLegacyUrl || fallbackId;
    if (resolvedId) {
      return `/student/opportunities/${resolvedId}`;
    }
    return '/student/opportunities';
  };

  const normalizeExternalUrl = (job: JobRecommendation): string | null => {
    const rawUrl = (job.url || '').trim();
    if (isHttpUrl(rawUrl)) {
      return rawUrl;
    }
    if (rawUrl.startsWith('//')) {
      return `https:${rawUrl}`;
    }
    if (rawUrl.startsWith('www.')) {
      return `https://${rawUrl}`;
    }

    const encodedTitle = encodeURIComponent(job.title || 'software engineer');
    if (job.source === 'linkedin') {
      return `https://www.linkedin.com/jobs/search/?keywords=${encodedTitle}`;
    }
    if (job.source === 'naukri' || job.source === 'naukri_search') {
      return `https://www.naukri.com/${(job.title || 'software engineer').toLowerCase().replace(/\s+/g, '-')}-jobs`;
    }
    if (job.source === 'internshala') {
      return `https://internshala.com/internships/keywords-${encodedTitle}/`;
    }
    return null;
  };

  const sanitizeLocationHint = (value?: string): string => {
    const normalized = String(value || '')
      .replace(/\s+/g, ' ')
      .trim();
    if (!normalized) return DEFAULT_LOCATION_HINT;
    if (normalized.length > 80) return DEFAULT_LOCATION_HINT;
    if (/https?:\/\//i.test(normalized)) return DEFAULT_LOCATION_HINT;
    if (/cgpa|batch|board|university|hsc|ssc|implemented|token-based|typescript|laravel/i.test(normalized)) {
      return DEFAULT_LOCATION_HINT;
    }
    const words = normalized.split(/[,\s]+/).filter(Boolean);
    if (words.length > 8) return DEFAULT_LOCATION_HINT;
    return normalized;
  };

  const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

  const pollQueuedRecommendations = async (
    recommendationRequestId: number,
    resumePayload: {
      extractedSkills: string[];
      extractedExperience: number;
      summary: string;
      modelSuggestedRoles: string[];
      techStack: string[];
      careerLevel?: string;
      keywords?: string[];
    },
    locationHint: string
  ): Promise<any[]> => {
    const enqueueResponse = await studentService.enqueueJobRecommendationsAsync(
      resumePayload,
      true,
      locationHint,
      500
    );
    const jobId = String(enqueueResponse?.job_id || '').trim();
    if (!jobId) {
      throw new Error('Live job queue did not return a job id');
    }

    const timeoutMs = 180000;
    const startedAt = Date.now();
    let nextPollDelay = Math.max(1000, Number(enqueueResponse?.retry_after_ms) || 1500);

    while (Date.now() - startedAt < timeoutMs) {
      if (recommendationRequestId !== recommendationRequestRef.current) {
        try {
          await studentService.cancelJobRecommendationsAsync(jobId);
        } catch (_) {
          // Ignore cancel races for stale requests.
        }
        return [];
      }

      const statusResponse = await studentService.getJobRecommendationsAsyncStatus(jobId);
      const status = String(statusResponse?.status || '').toLowerCase();
      const queuePosition = Number(statusResponse?.queue_position || 0);
      const retryAfter = Number(statusResponse?.retry_after_ms);
      if (Number.isFinite(retryAfter) && retryAfter > 0) {
        nextPollDelay = Math.min(5000, Math.max(1000, retryAfter));
      }

      if (status === 'succeeded') {
        setRecommendationStatusText('Live jobs fetched and ranked.');
        return Array.isArray(statusResponse?.recommendations) ? statusResponse.recommendations : [];
      }
      if (status === 'failed') {
        throw new Error(String(statusResponse?.error || 'Live APIFY job fetch failed'));
      }
      if (status === 'cancelled') {
        throw new Error('Live APIFY job fetch was cancelled');
      }

      if (status === 'queued') {
        setRecommendationStatusText(
          queuePosition > 0
            ? `Queued for live fetch (position ${queuePosition})...`
            : 'Queued for live APIFY fetch...'
        );
      } else {
        setRecommendationStatusText('Fetching jobs from APIFY and ranking matches...');
      }
      await sleep(nextPollDelay);
    }

    throw new Error('Live APIFY fetch timed out. Please try again.');
  };

  const totalRecommendations = recommendations.length;
  const totalPages = Math.max(1, Math.ceil(totalRecommendations / pageSize));
  const pageStartIndex = (currentPage - 1) * pageSize;
  const pageEndIndex = pageStartIndex + pageSize;
  const paginatedRecommendations = recommendations.slice(pageStartIndex, pageEndIndex);
  const pageStart = totalRecommendations === 0 ? 0 : pageStartIndex + 1;
  const pageEnd = Math.min(pageEndIndex, totalRecommendations);

  const goToPage = (page: number) => {
    const boundedPage = Math.min(Math.max(1, page), totalPages);
    setCurrentPage(boundedPage);
  };

  const getVisiblePages = () => {
    const maxVisible = 5;
    let start = Math.max(1, currentPage - 2);
    let end = Math.min(totalPages, start + maxVisible - 1);
    start = Math.max(1, end - maxVisible + 1);
    const pages: number[] = [];
    for (let page = start; page <= end; page += 1) {
      pages.push(page);
    }
    return pages;
  };

  useEffect(() => {
    setCurrentPage(1);
  }, [recommendations]);

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      if (isSupportedResumeFile(droppedFile)) {
        setFile(droppedFile);
        setError(null);
      } else {
        setError('Please upload PDF, DOC, DOCX, TXT, PNG, JPG, or JPEG');
      }
    }
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      if (!isSupportedResumeFile(selectedFile)) {
        setError('Please upload PDF, DOC, DOCX, TXT, PNG, JPG, or JPEG');
        setFile(null);
        return;
      }
      setFile(selectedFile);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setError('Please select a file');
      return;
    }

    setUploading(true);
    setAnalyzing(true);
    setError(null);

    try {
      const response = await studentService.uploadResume(file);
      const analysisPayload = response.resume_analysis as ResumeAnalysis | undefined;
      
      if (analysisPayload) {
        if (analysisPayload.error) {
          setError(`Resume analysis failed: ${analysisPayload.error}`);
          setResumeAnalysis(null);
          setRecommendations([]);
          setCurrentPage(1);
          return;
        }

        const normalizedAnalysis = normalizeResumeAnalysis(analysisPayload);
        setResumeAnalysis(normalizedAnalysis);
        
        // Automatically fetch recommendations
        await fetchRecommendations(normalizedAnalysis, useApify);
      } else {
        setError('Resume uploaded but analysis failed');
      }
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to upload resume');
    } finally {
      setUploading(false);
      setAnalyzing(false);
    }
  };

  const fetchRecommendations = async (
    analysis?: ResumeAnalysis,
    useApifyOverride?: boolean,
    allowSourceFallback: boolean = true
  ) => {
    const analysisData = analysis || resumeAnalysis;
    if (!analysisData) {
      return;
    }

    const requestId = ++recommendationRequestRef.current;
    const sourceSelection = useApifyOverride ?? useApify;
    const normalizedAnalysis = normalizeResumeAnalysis(analysisData);
    setLoadingRecommendations(true);
    setRecommendationStatusText(
      sourceSelection ? 'Preparing live APIFY job search...' : 'Finding the best matches for you...'
    );
    setError(null);
    try {
      const llmAnalysis = normalizedAnalysis.llm_analysis || {};
      const skills = normalizeStringList(normalizedAnalysis.skills);
      const keywords = normalizeStringList(normalizedAnalysis.keywords).length
        ? normalizeStringList(normalizedAnalysis.keywords)
        : skills;

      const recommendationPayload = {
        extractedSkills: skills,
        extractedExperience: normalizedAnalysis.experience_years || llmAnalysis.experience_years || 0,
        summary: normalizedAnalysis.professional_summary || llmAnalysis.professional_summary || '',
        modelSuggestedRoles: normalizeStringList(normalizedAnalysis.recommended_roles || llmAnalysis.recommended_roles),
        techStack: normalizeStringList(normalizedAnalysis.tech_stack || llmAnalysis.tech_stack),
        careerLevel: llmAnalysis.career_level || 'entry',
        keywords,  // Pass keywords for better job search
      };
      const normalizedLocation = sanitizeLocationHint(normalizedAnalysis.contact?.location);

      const response = sourceSelection
        ? {
            recommendations: await pollQueuedRecommendations(
              requestId,
              recommendationPayload,
              normalizedLocation
            ),
          }
        : await studentService.getJobRecommendations(
            recommendationPayload,
            false,
            normalizedLocation,
            300
          );

      // Keep normalized recommendations; do not over-filter by URL because some
      // sources may provide delayed/optional apply links.
      const validJobs = (response.recommendations || [])
        .map((job: any) => normalizeRecommendation(job))
        .filter((job: JobRecommendation | null): job is JobRecommendation => Boolean(job))
        .sort((a: JobRecommendation, b: JobRecommendation) => b.match_score - a.match_score);
      
      if (requestId !== recommendationRequestRef.current) {
        return;
      }

      if (validJobs.length === 0 && sourceSelection && allowSourceFallback) {
        // Live source returned nothing; automatically retry with internal source.
        setUseApify(false);
        setCurrentPage(1);
        await fetchRecommendations(normalizedAnalysis, false, false);
        return;
      }

      setRecommendations(validJobs);

      if (validJobs.length === 0) {
        setError('No recommendations found yet. Upload an updated resume or add profile skills and try again.');
      }
    } catch (err: any) {
      if (requestId !== recommendationRequestRef.current) {
        return;
      }
      if (sourceSelection && allowSourceFallback) {
        setUseApify(false);
        setCurrentPage(1);
        await fetchRecommendations(normalizedAnalysis, false, false);
        return;
      }
      setRecommendations([]);
      setCurrentPage(1);
      setError(err.response?.data?.error || err.message || 'Failed to fetch recommendations');
    } finally {
      if (requestId === recommendationRequestRef.current) {
        setLoadingRecommendations(false);
        setRecommendationStatusText(null);
      }
    }
  };

  const handleApply = (job: JobRecommendation) => {
    const rawUrl = (job.url || '').trim();
    const isInternal = job.source === 'internal' || (rawUrl.startsWith('/') && !isHttpUrl(rawUrl));

    if (isInternal) {
      navigate(normalizeInternalPath(job));
      return;
    }

    const externalUrl = normalizeExternalUrl(job);
    if (externalUrl) {
      window.open(externalUrl, '_blank', 'noopener,noreferrer');
      return;
    }

    setError(`Apply link is unavailable for "${job.title}".`);
  };

  const getSourceBadgeClass = (source?: string) => {
    if (source === 'naukri') return 'source-badge source-naukri';
    if (source === 'linkedin') return 'source-badge source-linkedin';
    return 'source-badge source-generic';
  };

  const getSourceBadgeLabel = (source?: string) => {
    if (source === 'naukri') return 'Naukri';
    if (source === 'linkedin') return 'LinkedIn';
    if (source === 'internshala') return 'Internshala';
    return source || 'External';
  };

  return (
    <div className="ai-resume-matcher">
      <motion.div
        className="matcher-header"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1>🤖 AI Resume Matcher</h1>
        <p>Upload your resume and get AI-powered job recommendations</p>
      </motion.div>

      {/* Section 1: Resume Upload */}
      <motion.div
        className="upload-section card"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <h2>📄 Upload Resume</h2>
        <div
          className={`upload-area ${dragActive ? 'drag-active' : ''} ${file ? 'has-file' : ''}`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <input
            type="file"
            id="resume-upload"
            accept=".pdf,.doc,.docx,.txt,.png,.jpg,.jpeg"
            onChange={handleFileChange}
            className="file-input"
          />
          <label htmlFor="resume-upload" className="upload-label">
            {file ? (
              <>
                <FiFileText size={48} />
                <p className="file-name">{file.name}</p>
                <button
                  className="remove-file-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    recommendationRequestRef.current += 1;
                    setFile(null);
                    setResumeAnalysis(null);
                    setRecommendations([]);
                    setCurrentPage(1);
                    setLoadingRecommendations(false);
                    setRecommendationStatusText(null);
                    setError(null);
                  }}
                >
                  <FiX size={20} /> Remove
                </button>
              </>
            ) : (
              <>
                <FiUpload size={48} />
                <p>Drag & drop your resume here</p>
                <p className="upload-hint">or click to browse</p>
                <p className="file-types">PDF, DOC, DOCX, TXT, PNG, JPG, JPEG</p>
              </>
            )}
          </label>
        </div>

        {error && (
          <motion.div
            className="error-message"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            {error}
          </motion.div>
        )}

        <button
          className="btn btn-primary upload-btn"
          onClick={handleUpload}
          disabled={!file || uploading}
        >
          {uploading ? (
            <>
              <FiLoader className="spinner" />
              {analyzing ? 'Analyzing Resume...' : 'Uploading...'}
            </>
          ) : (
            <>
              <FiUpload size={18} />
              Upload & Analyze
            </>
          )}
        </button>
      </motion.div>

      {/* Section 2: Extracted Data */}
      <AnimatePresence>
        {resumeAnalysis && (
          <motion.div
            className="extracted-data-section card"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ delay: 0.2 }}
          >
            <h2>✨ Extracted Information</h2>

            <div className="data-grid">
              {/* Skills */}
              {resumeAnalysis.skills && resumeAnalysis.skills.length > 0 && (
                <motion.div
                  className="data-card"
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.3 }}
                >
                  <h3>✅ Extracted Skills</h3>
                  <div className="skills-list">
                    {resumeAnalysis.skills.slice(0, 20).map((skill, idx) => (
                      <span key={idx} className="skill-tag">{skill}</span>
                    ))}
                  </div>
                </motion.div>
              )}

              {(resumeAnalysis.raw_text_quality || resumeAnalysis.model_meta) && (
                <motion.div
                  className="data-card"
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.35 }}
                >
                  <h3>🧠 Extraction Engine</h3>
                  <p>
                    Provider: {resumeAnalysis.model_meta?.provider || 'unknown'}
                  </p>
                  <p>
                    Model: {resumeAnalysis.model_meta?.model || 'fallback'}
                  </p>
                  <p>
                    OCR: {resumeAnalysis.raw_text_quality?.ocr_used ? 'Yes' : 'No'} ({resumeAnalysis.model_meta?.ocr_engine || 'none'})
                  </p>
                  {resumeAnalysis.raw_text_quality?.ocr_error && (
                    <p>
                      OCR note: {resumeAnalysis.raw_text_quality.ocr_error}
                    </p>
                  )}
                  <p>
                    Gemini: {resumeAnalysis.model_meta?.gemini_status || 'unknown'}
                  </p>
                  <p>
                    Gemini key: {resumeAnalysis.model_meta?.gemini_configured ? 'configured' : 'missing'}
                  </p>
                  {resumeAnalysis.model_meta?.gemini_error && (
                    <p>
                      Gemini error: {resumeAnalysis.model_meta.gemini_error}
                    </p>
                  )}
                  <p>
                    Text chars: {resumeAnalysis.raw_text_quality?.chars || 0}
                  </p>
                  <p>
                    Quality: {Math.round((resumeAnalysis.raw_text_quality?.quality_score || 0) * 100)}%
                  </p>
                </motion.div>
              )}

              {/* Experience */}
              {(resumeAnalysis.experience_years !== undefined || 
                resumeAnalysis.llm_analysis?.experience_years !== undefined) && (
                <motion.div
                  className="data-card"
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.4 }}
                >
                  <h3>💼 Experience</h3>
                  <p className="experience-value">
                    {resumeAnalysis.experience_years || resumeAnalysis.llm_analysis?.experience_years || 0} years
                  </p>
                  <p className="career-level">
                    Level: {resumeAnalysis.llm_analysis?.career_level || 'Entry'}
                  </p>
                </motion.div>
              )}

              {/* Summary */}
              {(resumeAnalysis.professional_summary || 
                resumeAnalysis.llm_analysis?.professional_summary) && (
                <motion.div
                  className="data-card full-width"
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.5 }}
                >
                  <h3>📝 Professional Summary</h3>
                  <p className="summary-text">
                    {resumeAnalysis.professional_summary || 
                     resumeAnalysis.llm_analysis?.professional_summary}
                  </p>
                </motion.div>
              )}

              {/* Recommended Roles */}
              {(resumeAnalysis.recommended_roles || 
                resumeAnalysis.llm_analysis?.recommended_roles) && (
                <motion.div
                  className="data-card"
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.6 }}
                >
                  <h3>🎯 Recommended Roles</h3>
                  <ul className="roles-list">
                    {(resumeAnalysis.recommended_roles || 
                      resumeAnalysis.llm_analysis?.recommended_roles || []).map((role, idx) => (
                      <li key={idx}>{role}</li>
                    ))}
                  </ul>
                </motion.div>
              )}

              {/* Missing Skills */}
              {(resumeAnalysis.missing_skills || 
                resumeAnalysis.llm_analysis?.missing_skills) && (
                <motion.div
                  className="data-card"
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.7 }}
                >
                  <h3>⚠️ Missing Skills</h3>
                  <ul className="missing-skills-list">
                    {(resumeAnalysis.missing_skills || 
                      resumeAnalysis.llm_analysis?.missing_skills || []).map((skill, idx) => (
                      <li key={idx}>{skill}</li>
                    ))}
                  </ul>
                </motion.div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Section 3: Job Recommendations */}
      {resumeAnalysis && (
        <motion.div
          className="recommendations-section"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <div className="recommendations-header">
            <h2>🚀 AI Job Recommendations</h2>
            <div className="source-toggle">
              <label>
                <input
                  type="checkbox"
                  checked={useApify}
                  onChange={(e) => {
                    const nextUseApify = e.target.checked;
                    setUseApify(nextUseApify);
                    void fetchRecommendations(undefined, nextUseApify);
                  }}
                />
                Use Live Apify Jobs
              </label>
            </div>
          </div>

          {loadingRecommendations ? (
            <div className="loading-state">
              <FiLoader className="spinner" />
              <p>{recommendationStatusText || 'Finding the best matches for you...'}</p>
            </div>
          ) : recommendations.length > 0 ? (
            <>
              <div className="recommendations-toolbar">
                <p className="recommendations-count">
                  Showing {pageStart}-{pageEnd} of {totalRecommendations} jobs
                </p>
                <label className="page-size-selector">
                  Per page
                  <select
                    value={pageSize}
                    onChange={(e) => {
                      const nextPageSize = Number(e.target.value);
                      if (!Number.isFinite(nextPageSize) || nextPageSize < 1) return;
                      setPageSize(nextPageSize);
                      setCurrentPage(1);
                    }}
                  >
                    {PAGE_SIZE_OPTIONS.map((size) => (
                      <option key={size} value={size}>
                        {size}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="recommendations-grid">
                {paginatedRecommendations.map((job, idx) => (
                <motion.div
                  key={`${job.id ?? job.url ?? job.title}-${pageStartIndex + idx}`}
                  className="job-card"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  whileHover={{ y: -4 }}
                >
                  <div className="job-card-header">
                    <div>
                      <h3>{job.title}</h3>
                      <p className="company-name">{job.company_name}</p>
                      {job.source && job.source !== 'internal' && (
                        <span className={getSourceBadgeClass(job.source)}>
                          {getSourceBadgeLabel(job.source)}
                        </span>
                      )}
                    </div>
                    <div className="match-badge">
                      <FiTrendingUp size={16} />
                      <span>{job.match_score}% Match</span>
                    </div>
                  </div>

                  <div className="job-card-meta">
                    <span>
                      <FiMapPin size={14} />
                      {job.location}
                    </span>
                    {job.stipend && (
                      <span>
                        <FiDollarSign size={14} />
                        {job.stipend}
                      </span>
                    )}
                    {job.work_type && (
                      <span>{job.work_type}</span>
                    )}
                  </div>

                  {job.is_search && (
                    <div className="search-badge">
                      <span>🔍 Direct Search - Click to view all matching jobs</span>
                    </div>
                  )}
                  <div className="match-reason">
                    <p>{job.match_reason}</p>
                  </div>

                  {job.matched_skills && job.matched_skills.length > 0 && (
                    <div className="matched-skills">
                      <strong>Matched Skills:</strong>
                      <div className="skills-tags">
                        {job.matched_skills.slice(0, 5).map((skill, i) => (
                          <span key={i} className="skill-tag matched">{skill}</span>
                        ))}
                      </div>
                    </div>
                  )}

                  {job.required_skills && job.required_skills.length > 0 && (
                    <div className="required-skills">
                      <strong>Required:</strong>
                      <div className="skills-tags">
                        {job.required_skills.slice(0, 8).map((skill, i) => (
                          <span key={i} className="skill-tag">{skill}</span>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="job-card-actions">
                    {job.url && (
                      <button
                        className="btn btn-primary"
                        onClick={() => handleApply(job)}
                        title={job.url}
                      >
                        {job.source === 'internal' 
                          ? 'Apply Now' 
                          : job.source === 'naukri_search'
                          ? `Search ${job.title} Jobs on Naukri`
                          : job.source === 'linkedin'
                          ? 'Apply on LinkedIn'
                          : job.source === 'naukri'
                          ? 'Apply on Naukri'
                          : job.source === 'internshala'
                          ? 'Apply on Internshala'
                          : 'View on External Site'}
                        <FiExternalLink size={16} />
                      </button>
                    )}
                    {!job.url && (
                      <span className="no-url-message">Apply link not available</span>
                    )}
                  </div>
                </motion.div>
                ))}
              </div>
              {totalPages > 1 && (
                <div className="pagination-controls">
                  <button
                    type="button"
                    className="pagination-btn"
                    onClick={() => goToPage(currentPage - 1)}
                    disabled={currentPage === 1}
                  >
                    Previous
                  </button>
                  {getVisiblePages().map((page) => (
                    <button
                      key={page}
                      type="button"
                      className={`pagination-btn ${page === currentPage ? 'active' : ''}`}
                      onClick={() => goToPage(page)}
                    >
                      {page}
                    </button>
                  ))}
                  <button
                    type="button"
                    className="pagination-btn"
                    onClick={() => goToPage(currentPage + 1)}
                    disabled={currentPage === totalPages}
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          ) : (
            <div className="empty-state">
              <p>No recommendations found. Try uploading your resume first.</p>
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
};

export default AIResumeMatcher;


