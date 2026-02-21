import api from './api';
import {
  StudentProfile,
  Application,
  AIRecommendation,
  ResumeScore,
  StudentAttachment,
  StudentFullProfileResponse,
  JobsSummary,
} from '../types';

export const studentService = {
  getProfile: async (): Promise<StudentProfile> => {
    const response = await api.get('/student/profile');
    return response.data;
  },

  getFullProfile: async (): Promise<StudentFullProfileResponse> => {
    const response = await api.get('/student/profile/full');
    return response.data;
  },

  updateProfile: async (profile: Partial<StudentProfile>): Promise<StudentProfile> => {
    const response = await api.put('/student/profile', profile);
    return response.data.profile;
  },

  uploadResume: async (
    file: File
  ): Promise<{ resume_path: string; resume_analysis?: any; message?: string }> => {
    const formData = new FormData();
    formData.append('resume', file);
    const response = await api.post('/student/resume/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  getDashboard: async () => {
    const response = await api.get('/student/dashboard');
    return response.data;
  },

  getApplications: async (): Promise<Application[]> => {
    const response = await api.get('/student/applications');
    return response.data;
  },

  getRecommendations: async (): Promise<AIRecommendation[]> => {
    const response = await api.get('/ai/recommendations');
    return response.data;
  },

  getResumeScore: async (opportunityId: number): Promise<ResumeScore> => {
    const response = await api.post('/ai/resume-score', { opportunity_id: opportunityId });
    return response.data;
  },

  generateResumePdf: async (): Promise<Blob> => {
    const response = await api.get('/student/resume/generate', { responseType: 'blob' });
    return response.data;
  },

  getSection: async (section: string) => {
    const response = await api.get(`/student/${section}`);
    return response.data;
  },

  createSection: async (section: string, payload: Record<string, unknown>) => {
    const response = await api.post(`/student/${section}`, payload);
    return response.data;
  },

  updateSection: async (section: string, id: number, payload: Record<string, unknown>) => {
    const response = await api.put(`/student/${section}/${id}`, payload);
    return response.data;
  },

  deleteSection: async (section: string, id: number) => {
    await api.delete(`/student/${section}/${id}`);
  },

  uploadAttachment: async (payload: FormData): Promise<StudentAttachment> => {
    const response = await api.post('/student/attachments', payload, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data.attachment;
  },

  deleteAttachment: async (id: number) => {
    await api.delete(`/student/attachments/${id}`);
  },

  getJobsSummary: async (): Promise<JobsSummary> => {
    const response = await api.get('/student/jobs/summary');
    return response.data;
  },

  // Skills Matching Endpoints
  getSkills: async () => {
    const response = await api.get('/student/skills');
    return response.data;
  },

  updateSkills: async (skills: { technical_skills?: string[]; non_technical_skills?: string[]; proficiency_levels?: Record<string, string> }) => {
    const response = await api.post('/student/skills', skills);
    return response.data;
  },

  getMatchedOpportunities: async (minMatch: number = 70) => {
    const response = await api.get(`/student/matched-opportunities?min_match=${minMatch}`);
    return response.data;
  },

  getExternalJobs: async (minMatch: number = 70) => {
    const response = await api.get(`/student/external-jobs?min_match=${minMatch}`);
    return response.data;
  },

  checkSkillsSetup: async () => {
    const response = await api.get('/student/check-skills-setup');
    return response.data;
  },

  getOpportunityMatch: async (opportunityId: number) => {
    const response = await api.get(`/student/opportunities/${opportunityId}/match`);
    return response.data;
  },

  // AI Recommendation Endpoints
  getJobRecommendations: async (
    resumeAnalysis: {
      extractedSkills: string[];
      extractedExperience: number;
      summary: string;
      modelSuggestedRoles: string[];
      techStack: string[];
      careerLevel?: string;
      keywords?: string[];
    },
    useApify: boolean = true,
    location: string = 'India',
    topN: number = 200,
  ) => {
    const normalizedTopN = Math.max(1, Math.min(500, Math.round(topN)));
    const response = await api.post(
      `/student/jobs/recommend?useApify=${useApify}&topN=${normalizedTopN}&location=${encodeURIComponent(location)}`,
      resumeAnalysis
    );
    return response.data;
  },

  enqueueJobRecommendationsAsync: async (
    resumeAnalysis: {
      extractedSkills: string[];
      extractedExperience: number;
      summary: string;
      modelSuggestedRoles: string[];
      techStack: string[];
      careerLevel?: string;
      keywords?: string[];
    },
    useApify: boolean = true,
    location: string = 'India',
    topN: number = 200,
  ) => {
    const normalizedTopN = Math.max(1, Math.min(500, Math.round(topN)));
    const response = await api.post(
      '/student/jobs/recommend/async',
      resumeAnalysis,
      {
        params: {
          useApify,
          topN: normalizedTopN,
          location,
        },
      }
    );
    return response.data;
  },

  getJobRecommendationsAsyncStatus: async (jobId: string) => {
    const response = await api.get(`/student/jobs/recommend/async/${jobId}`);
    return response.data;
  },

  cancelJobRecommendationsAsync: async (jobId: string) => {
    const response = await api.delete(`/student/jobs/recommend/async/${jobId}`);
    return response.data;
  },

  getJobSource: async (useApify: boolean = true, keywords?: string, location?: string) => {
    const params = new URLSearchParams();
    params.append('useApify', useApify.toString());
    if (keywords) params.append('keywords', keywords);
    if (location) params.append('location', location);
    const response = await api.get(`/student/jobs/source?${params.toString()}`);
    return response.data;
  },
};
