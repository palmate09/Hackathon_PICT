import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { FiX } from 'react-icons/fi';
import { studentService } from '../../services/studentService';

type FormField = {
  name: string;
  label: string;
  type?: 'text' | 'textarea' | 'date' | 'tags' | 'file';
  placeholder?: string;
  required?: boolean;
};

const NAV_TABS = [
  { key: 'basic', label: 'Basic Details', description: 'Personal profile & identifiers' },
  { key: 'education', label: 'Education', description: 'Academic achievements & CGPA' },
  { key: 'placement-policy', label: 'Placement Policy', description: 'Eligibility, preferences & declaration' },
  { key: 'academic-details', label: 'Academic Details', description: 'Semester SGPA, backlogs & marksheets' },
  { key: 'experiences', label: 'Professional Experience', description: 'Full-time or part-time roles' },
  { key: 'internships', label: 'Internships', description: 'Industry internships & mentors' },
  { key: 'projects', label: 'Projects', description: 'Capstone, personal & research work' },
  { key: 'trainings', label: 'Seminars / Trainings', description: 'Workshops, hackathons & courses' },
  { key: 'certifications', label: 'Certifications', description: 'Professional credentials' },
  { key: 'publications', label: 'Publications', description: 'Whitepapers & journals' },
  { key: 'positions', label: 'Positions of Responsibility', description: 'Clubs, committees & leads' },
  { key: 'offers', label: 'Offers', description: 'Final placement / internship offers' },
  { key: 'attachments', label: 'Attachments', description: 'Transcripts, offer letters, more' },
];

const SECTION_FIELDS: Record<string, FormField[]> = {
  education: [
    { name: 'degree', label: 'Degree', required: true },
    { name: 'institution', label: 'Institution', required: true },
    { name: 'course', label: 'Course' },
    { name: 'specialization', label: 'Specialization' },
    { name: 'start_date', label: 'Start Date', type: 'date' },
    { name: 'end_date', label: 'End Date', type: 'date' },
    { name: 'gpa', label: 'GPA / Percentage', required: true },
    { name: 'achievements', label: 'Highlights', type: 'textarea' },
  ],
  experiences: [
    { name: 'company_name', label: 'Company', required: true },
    { name: 'designation', label: 'Designation', required: true },
    { name: 'employment_type', label: 'Employment Type' },
    { name: 'start_date', label: 'Start Date', type: 'date' },
    { name: 'end_date', label: 'End Date', type: 'date' },
    { name: 'location', label: 'Location' },
    { name: 'technologies', label: 'Technologies', type: 'tags', placeholder: 'React, Node, SQL' },
    { name: 'description', label: 'Summary', type: 'textarea' },
  ],
  internships: [
    { name: 'designation', label: 'Designation', required: true },
    { name: 'organization', label: 'Organisation', required: true },
    { name: 'industry_sector', label: 'Industry Sector' },
    { name: 'internship_type', label: 'Internship Type' },
    { name: 'stipend', label: 'Stipend' },
    { name: 'start_date', label: 'Start Date', type: 'date' },
    { name: 'end_date', label: 'End Date', type: 'date' },
    { name: 'mentor_name', label: 'Mentor' },
    { name: 'mentor_contact', label: 'Mentor Contact' },
    { name: 'mentor_designation', label: 'Mentor Designation' },
    { name: 'technologies', label: 'Skills', type: 'tags' },
    { name: 'description', label: 'Description', type: 'textarea' },
  ],
  projects: [
    { name: 'title', label: 'Project Title', required: true },
    { name: 'organization', label: 'Client / Organisation' },
    { name: 'role', label: 'Role' },
    { name: 'start_date', label: 'Start Date', type: 'date' },
    { name: 'end_date', label: 'End Date', type: 'date' },
    { name: 'technologies', label: 'Stack', type: 'tags', placeholder: 'React, Firebase' },
    { name: 'links', label: 'Links', type: 'textarea', placeholder: 'GitHub, Demo' },
    { name: 'description', label: 'Description', type: 'textarea' },
  ],
  trainings: [
    { name: 'title', label: 'Programme Title', required: true },
    { name: 'provider', label: 'Provider' },
    { name: 'mode', label: 'Mode' },
    { name: 'start_date', label: 'Start Date', type: 'date' },
    { name: 'end_date', label: 'End Date', type: 'date' },
    { name: 'description', label: 'Description', type: 'textarea' },
  ],
  certifications: [
    { name: 'name', label: 'Certification', required: true },
    { name: 'issuer', label: 'Issuer' },
    { name: 'issue_date', label: 'Issue Date', type: 'date' },
    { name: 'expiry_date', label: 'Expiry Date', type: 'date' },
    { name: 'credential_id', label: 'Credential ID' },
    { name: 'credential_url', label: 'Credential URL' },
    { name: 'certificate_file', label: 'Upload Certificate', type: 'file' },
    { name: 'description', label: 'Notes', type: 'textarea' },
  ],
  publications: [
    { name: 'title', label: 'Title', required: true },
    { name: 'publication_type', label: 'Type' },
    { name: 'publisher', label: 'Publisher' },
    { name: 'publication_date', label: 'Publication Date', type: 'date' },
    { name: 'url', label: 'URL' },
    { name: 'description', label: 'Abstract', type: 'textarea' },
  ],
  positions: [
    { name: 'title', label: 'Position', required: true },
    { name: 'organization', label: 'Organisation' },
    { name: 'start_date', label: 'Start Date', type: 'date' },
    { name: 'end_date', label: 'End Date', type: 'date' },
    { name: 'description', label: 'Contributions', type: 'textarea' },
  ],
  offers: [
    { name: 'company_name', label: 'Company', required: true },
    { name: 'role', label: 'Role' },
    { name: 'ctc', label: 'CTC' },
    { name: 'status', label: 'Status' },
    { name: 'offer_date', label: 'Offer Date', type: 'date' },
    { name: 'joining_date', label: 'Joining Date', type: 'date' },
    { name: 'notes', label: 'Notes', type: 'textarea' },
  ],
};

const BASIC_FIELD_PLACEHOLDERS: Record<string, string> = {
  first_name: 'Enter first name',
  middle_name: 'Enter middle name',
  last_name: 'Enter last name',
  phone: 'Enter phone number',
  prn_number: 'Enter PRN number',
  course: 'Computer, IT, ENTC...',
  specialization: 'TE A, BE B...',
  date_of_birth: 'Select date of birth',
  address: 'Enter current address',
  bio: 'Write a short profile summary',
  skills: 'React, Node.js, SQL',
  interests: 'AI, Product Design, Cybersecurity',
  linkedin_url: 'https://linkedin.com/in/your-profile',
  github_url: 'https://github.com/your-username',
  portfolio_url: 'https://yourportfolio.com',
};

const BASIC_NAME_FIELDS: Array<{ key: string; label: string; required: boolean }> = [
  { key: 'first_name', label: 'First Name', required: true },
  { key: 'middle_name', label: 'Middle Name', required: false },
  { key: 'last_name', label: 'Last Name', required: true },
];
const PROFILE_DB_FIELDS = [
  'first_name',
  'middle_name',
  'last_name',
  'phone',
  'date_of_birth',
  'address',
  'prn_number',
  'course',
  'specialization',
  'gender',
  'skills',
  'interests',
  'bio',
  'linkedin_url',
  'github_url',
  'portfolio_url',
] as const;

const getSectionFieldPlaceholder = (field: FormField) => {
  if (field.placeholder) return field.placeholder;
  if (field.type === 'date') return `Select ${field.label.toLowerCase()}`;
  if (field.type === 'tags') return `Enter ${field.label.toLowerCase()} separated by commas`;
  return `Enter ${field.label.toLowerCase()}`;
};

const resolveAssetUrl = (assetPath?: string) => {
  if (!assetPath) return '';
  const normalizedPath = assetPath.replace(/\\/g, '/');
  if (normalizedPath.startsWith('http://') || normalizedPath.startsWith('https://')) {
    return normalizedPath;
  }
  if (normalizedPath.startsWith('/')) {
    return normalizedPath;
  }
  if (normalizedPath.startsWith('public/')) {
    return `/${normalizedPath}`;
  }
  return `/${normalizedPath}`;
};

const getInitials = (firstName?: string, lastName?: string) => {
  const parts = [firstName, lastName].filter(Boolean) as string[];
  if (parts.length === 0) return 'S';
  return parts.map((part) => part[0]?.toUpperCase() || '').join('').slice(0, 2);
};

const hasDisplayValue = (value: unknown) => {
  if (value === null || value === undefined) return false;
  if (typeof value === 'string') return value.trim().length > 0;
  if (Array.isArray(value)) return value.length > 0;
  return true;
};

const toTitleCaseLabel = (fieldName: string) =>
  fieldName
    .replace(/_/g, ' ')
    .split(' ')
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');

const FIELD_LABEL_OVERRIDES: Record<string, string> = {
  gpa: 'GPA',
  sgpa: 'SGPA',
  ctc: 'CTC',
  prn_number: 'PRN Number',
  is_current: 'Currently Active',
  certificate_file: 'Certificate',
};

const SECTION_CARD_FIELDS: Record<string, string[]> = {
  education: ['institution', 'course', 'specialization', 'gpa', 'start_date', 'end_date'],
  experiences: ['company_name', 'employment_type', 'location', 'start_date', 'end_date', 'technologies'],
  internships: ['organization', 'industry_sector', 'internship_type', 'stipend', 'start_date', 'end_date'],
  projects: ['organization', 'role', 'start_date', 'end_date', 'technologies'],
  trainings: ['provider', 'mode', 'start_date', 'end_date'],
  certifications: ['issuer', 'issue_date', 'expiry_date', 'credential_id', 'certificate_file'],
  publications: ['publication_type', 'publisher', 'publication_date', 'url'],
  positions: ['organization', 'start_date', 'end_date', 'is_current'],
  offers: ['role', 'ctc', 'status', 'offer_date', 'joining_date', 'location'],
  attachments: ['attachment_type', 'file_path'],
};

const HIDDEN_MODAL_FIELDS = new Set(['id', 'student_id', 'display_order']);

const formatDisplayValue = (value: unknown) => {
  if (value === null || value === undefined) return '-';
  if (Array.isArray(value)) {
    if (!value.length) return '-';
    return value
      .map((item) => (typeof item === 'string' ? item.trim() : String(item)))
      .filter(Boolean)
      .join(', ');
  }
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'number') return String(value);
  if (typeof value === 'string') {
    const normalized = value.trim();
    if (!normalized) return '-';
    if (/^\d{4}-\d{2}-\d{2}/.test(normalized)) {
      const parsedDate = new Date(normalized);
      if (!Number.isNaN(parsedDate.getTime())) {
        return parsedDate.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
      }
    }
    return normalized;
  }
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
};

const getEntryTitle = (entry: Record<string, any>) =>
  entry.title || entry.designation || entry.company_name || entry.degree || entry.name || `Record #${entry.id}`;

type PlacementPolicyFormState = {
  id?: number;
  interested_in_jobs: 'yes' | 'no' | '';
  interested_in_internships: 'yes' | 'no' | '';
  placement_policy_agreed: boolean;
  policy_version: string;
  policy_document_url: string;
};

type AcademicDetailsMetaState = {
  degree_name: string;
  branch_name: string;
  batch_start_year: string;
  batch_end_year: string;
};

type AcademicSemesterState = {
  id?: number;
  semester_label: string;
  sgpa: string;
  closed_backlogs: string;
  live_backlogs: string;
  marksheet_file_path: string;
};

const SEMESTER_LABELS = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII'] as const;

const DEFAULT_POLICY_LINK = '#';

const DEFAULT_PLACEMENT_POLICY_FORM: PlacementPolicyFormState = {
  interested_in_jobs: 'yes',
  interested_in_internships: 'yes',
  placement_policy_agreed: false,
  policy_version: '2026',
  policy_document_url: DEFAULT_POLICY_LINK,
};

const DEFAULT_ACADEMIC_META = (branch = ''): AcademicDetailsMetaState => ({
  degree_name: 'B.E.',
  branch_name: branch || 'Information Technology',
  batch_start_year: '',
  batch_end_year: '',
});

const parseBooleanLike = (value: unknown): boolean => {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'number') return value !== 0;
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase();
    return ['1', 'true', 'yes', 'y'].includes(normalized);
  }
  return false;
};

const toYesNo = (value: unknown): 'yes' | 'no' => (parseBooleanLike(value) ? 'yes' : 'no');

const normalizeSemesterLabel = (value: unknown): string => {
  const raw = String(value || '').trim().toUpperCase();
  const numberToRoman: Record<string, string> = {
    '1': 'I',
    '2': 'II',
    '3': 'III',
    '4': 'IV',
    '5': 'V',
    '6': 'VI',
    '7': 'VII',
    '8': 'VIII',
  };
  return numberToRoman[raw] || raw;
};

const buildAcademicRows = (entries: Record<string, any>[]): AcademicSemesterState[] => {
  const bySemester = new Map<string, Record<string, any>>();
  entries.forEach((entry) => {
    const label = normalizeSemesterLabel(entry.semester_label);
    if (label) {
      bySemester.set(label, entry);
    }
  });

  return SEMESTER_LABELS.map((semesterLabel) => {
    const savedEntry = bySemester.get(semesterLabel);
    return {
      id: savedEntry?.id,
      semester_label: semesterLabel,
      sgpa: savedEntry?.sgpa ? String(savedEntry.sgpa) : '',
      closed_backlogs:
        savedEntry?.closed_backlogs === 0 || savedEntry?.closed_backlogs
          ? String(savedEntry.closed_backlogs)
          : '',
      live_backlogs:
        savedEntry?.live_backlogs === 0 || savedEntry?.live_backlogs
          ? String(savedEntry.live_backlogs)
          : '',
      marksheet_file_path: savedEntry?.marksheet_file_path || '',
    };
  });
};

const computeAggregateCgpa = (rows: AcademicSemesterState[]): string => {
  const sgpaValues = rows
    .map((row) => Number.parseFloat(row.sgpa))
    .filter((value) => Number.isFinite(value));
  if (!sgpaValues.length) return '';
  const total = sgpaValues.reduce((sum, value) => sum + value, 0);
  return (total / sgpaValues.length).toFixed(2);
};

const StudentProfileWorkspace: React.FC = () => {
  const { tab: urlTab } = useParams();
  const navigate = useNavigate();

  const activeTabKey = urlTab || 'basic';
  const isValidTab = NAV_TABS.some(t => t.key === activeTabKey);
  const activeTab = isValidTab ? activeTabKey : 'basic';
  const [formState, setFormState] = useState<Record<string, any>>({});
  const [savedBasicProfile, setSavedBasicProfile] = useState<Record<string, any>>({});
  const [sections, setSections] = useState<Record<string, any[]>>({});
  const [stats, setStats] = useState<Record<string, number>>({});
  const [sectionForm, setSectionForm] = useState<Record<string, any>>({});
  const [editingEntry, setEditingEntry] = useState<number | null>(null);
  const [savingSection, setSavingSection] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingProfile, setSavingProfile] = useState(false);
  const [completionPercentage, setCompletionPercentage] = useState(0);
  const [completionBreakdown, setCompletionBreakdown] = useState<{
    completed_criteria: number;
    total_criteria: number;
    missing_criteria: string[];
  } | null>(null);
  const [avatarUploading, setAvatarUploading] = useState(false);
  const [pendingAvatarFile, setPendingAvatarFile] = useState<File | null>(null);
  const [pendingAvatarPreview, setPendingAvatarPreview] = useState('');
  const [avatarPreviewFailed, setAvatarPreviewFailed] = useState(false);
  const [placementPolicyForm, setPlacementPolicyForm] = useState<PlacementPolicyFormState>(DEFAULT_PLACEMENT_POLICY_FORM);
  const [savingPlacementPolicy, setSavingPlacementPolicy] = useState(false);
  const [academicMeta, setAcademicMeta] = useState<AcademicDetailsMetaState>(DEFAULT_ACADEMIC_META());
  const [academicRows, setAcademicRows] = useState<AcademicSemesterState[]>(() => buildAcademicRows([]));
  const [savingAcademicDetails, setSavingAcademicDetails] = useState(false);
  const [uploadingSemesterMarksheet, setUploadingSemesterMarksheet] = useState<string | null>(null);
  const [viewingEntry, setViewingEntry] = useState<{ sectionKey: string; entry: Record<string, any> } | null>(null);
  const [certificateFile, setCertificateFile] = useState<File | null>(null);

  useEffect(() => {
    loadProfile();
  }, []);

  useEffect(() => {
    return () => {
      if (pendingAvatarPreview) {
        URL.revokeObjectURL(pendingAvatarPreview);
      }
    };
  }, [pendingAvatarPreview]);

  const clearPendingAvatar = () => {
    setPendingAvatarFile(null);
    setPendingAvatarPreview((previousPreview) => {
      if (previousPreview) {
        URL.revokeObjectURL(previousPreview);
      }
      return '';
    });
  };

  const hydratePlacementPolicyForm = (nextSections: Record<string, any[]>) => {
    const policyEntry = (nextSections['placement-policy'] || [])[0];
    if (!policyEntry) {
      setPlacementPolicyForm(DEFAULT_PLACEMENT_POLICY_FORM);
      return;
    }

    setPlacementPolicyForm({
      id: policyEntry.id,
      interested_in_jobs: toYesNo(policyEntry.interested_in_jobs),
      interested_in_internships: toYesNo(policyEntry.interested_in_internships),
      placement_policy_agreed: parseBooleanLike(policyEntry.placement_policy_agreed),
      policy_version: policyEntry.policy_version || DEFAULT_PLACEMENT_POLICY_FORM.policy_version,
      policy_document_url: policyEntry.policy_document_url || DEFAULT_POLICY_LINK,
    });
  };

  const hydrateAcademicDetails = (nextSections: Record<string, any[]>, branchFromProfile?: string) => {
    const entries = nextSections['academic-details'] || [];
    const firstEntry = entries[0];
    const derivedBranch = (firstEntry?.branch_name || branchFromProfile || '').trim();

    setAcademicMeta({
      degree_name: firstEntry?.degree_name || 'B.E.',
      branch_name: derivedBranch || 'Information Technology',
      batch_start_year:
        firstEntry?.batch_start_year === 0 || firstEntry?.batch_start_year
          ? String(firstEntry.batch_start_year)
          : '',
      batch_end_year:
        firstEntry?.batch_end_year === 0 || firstEntry?.batch_end_year ? String(firstEntry.batch_end_year) : '',
    });
    setAcademicRows(buildAcademicRows(entries));
  };

  const loadProfile = async () => {
    setLoading(true);
    try {
      const data = await studentService.getFullProfile();
      const nextSections = data.sections || {};
      setSections(nextSections);
      setStats(data.stats || {});
      setCompletionPercentage(data.completion_percentage || 0);
      setCompletionBreakdown(data.completion_breakdown || null);
      const nextProfileState = {
        first_name: data.profile.first_name || '',
        middle_name: (data.profile as any).middle_name || '',
        last_name: data.profile.last_name || '',
        prn_number: (data.profile as any).prn_number || '',
        course: (data.profile as any).course || '',
        specialization: (data.profile as any).specialization || '',
        gender: (data.profile as any).gender || '',
        date_of_birth: data.profile.date_of_birth ? data.profile.date_of_birth.substring(0, 10) : '',
        phone: data.profile.phone || '',
        address: data.profile.address || '',
        bio: data.profile.bio || '',
        profile_picture: data.profile.profile_picture || '',
        linkedin_url: data.profile.linkedin_url || '',
        github_url: data.profile.github_url || '',
        portfolio_url: data.profile.portfolio_url || '',
        skills: (data.profile.skills || []).join(', '),
        interests: (data.profile.interests || []).join(', '),
      };
      hydratePlacementPolicyForm(nextSections);
      hydrateAcademicDetails(nextSections, nextProfileState.course);
      setFormState(nextProfileState);
      setSavedBasicProfile({
        first_name: nextProfileState.first_name,
        last_name: nextProfileState.last_name,
        prn_number: nextProfileState.prn_number,
        phone: nextProfileState.phone,
        course: nextProfileState.course,
        specialization: nextProfileState.specialization,
        profile_picture: nextProfileState.profile_picture,
      });
    } finally {
      setLoading(false);
    }
  };

  const showToast = (message: string) => {
    setToast(message);
    setTimeout(() => setToast(null), 2500);
  };

  const saveProfile = async (event: React.FormEvent) => {
    event.preventDefault();

    // Validate mandatory fields
    if (!formState.first_name || !formState.last_name) {
      showToast('First name and last name are required');
      return;
    }
    if (!formState.phone) {
      showToast('Phone number is required');
      return;
    }
    if (!formState.course) {
      showToast('Branch/Course is required');
      return;
    }

    if (savingProfile) {
      return;
    }

    const profilePayload = PROFILE_DB_FIELDS.reduce<Record<string, any>>((acc, field) => {
      acc[field] = formState[field] ?? '';
      return acc;
    }, {});
    setSavingProfile(true);
    try {
      await studentService.updateProfile({
        ...profilePayload,
        skills: (profilePayload.skills || '')
          .split(',')
          .map((item: string) => item.trim())
          .filter(Boolean),
        interests: (profilePayload.interests || '')
          .split(',')
          .map((item: string) => item.trim())
          .filter(Boolean),
      });

      let avatarUploadError: string | null = null;
      if (pendingAvatarFile) {
        setAvatarUploading(true);
        try {
          await studentService.uploadProfilePicture(pendingAvatarFile);
        } catch (error: any) {
          avatarUploadError = error?.response?.data?.error || 'Profile data saved, but avatar upload failed';
        }
      }

      clearPendingAvatar();
      await loadProfile();
      showToast(avatarUploadError || 'Profile updated');
    } catch (error: any) {
      showToast(error?.response?.data?.error || 'Failed to update profile');
    } finally {
      setAvatarUploading(false);
      setSavingProfile(false);
    }
  };

  const uploadResume = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const result = await studentService.uploadResume(file);
      const autofill = result.profile_autofill;
      if (autofill?.enabled) {
        const added = autofill.total_added || 0;
        const updated = autofill.total_updated || 0;
        showToast(`Resume uploaded. Auto-filled profile (${added} added, ${updated} updated).`);
      } else {
        showToast('Resume uploaded');
      }
      loadProfile();
    } catch (error: any) {
      showToast(error?.response?.data?.error || 'Failed to upload resume');
    } finally {
      event.target.value = '';
    }
  };

  const uploadProfilePicture = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      showToast('Please upload an image file');
      event.target.value = '';
      return;
    }

    const previewUrl = URL.createObjectURL(file);
    setPendingAvatarFile(file);
    setPendingAvatarPreview((previousPreview) => {
      if (previousPreview) {
        URL.revokeObjectURL(previousPreview);
      }
      return previewUrl;
    });
    setAvatarPreviewFailed(false);
    showToast('Photo selected. Save profile to apply changes.');
    event.target.value = '';
  };

  const downloadResume = async () => {
    const blob = await studentService.generateResumePdf();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'resume.pdf';
    link.click();
    URL.revokeObjectURL(url);
  };

  const savePlacementPolicy = async (event: React.FormEvent) => {
    event.preventDefault();
    if (savingPlacementPolicy) return;

    if (!placementPolicyForm.interested_in_jobs || !placementPolicyForm.interested_in_internships) {
      showToast('Please select job and internship preferences');
      return;
    }

    if (!placementPolicyForm.placement_policy_agreed) {
      showToast('Please accept the placement policy declaration');
      return;
    }

    const payload = {
      interested_in_jobs: placementPolicyForm.interested_in_jobs === 'yes',
      interested_in_internships: placementPolicyForm.interested_in_internships === 'yes',
      placement_policy_agreed: placementPolicyForm.placement_policy_agreed,
      policy_version: placementPolicyForm.policy_version,
      policy_document_url: placementPolicyForm.policy_document_url || DEFAULT_POLICY_LINK,
    };

    setSavingPlacementPolicy(true);
    try {
      if (placementPolicyForm.id) {
        await studentService.updateSection('placement-policy', placementPolicyForm.id, payload);
      } else {
        await studentService.createSection('placement-policy', payload);
      }
      await loadProfile();
      showToast('Placement policy saved');
    } catch (error: any) {
      showToast(error?.response?.data?.error || 'Failed to save placement policy');
    } finally {
      setSavingPlacementPolicy(false);
    }
  };

  const updateAcademicRow = (semesterLabel: string, key: keyof AcademicSemesterState, value: string) => {
    setAcademicRows((previousRows) =>
      previousRows.map((row) =>
        row.semester_label === semesterLabel
          ? {
            ...row,
            [key]: value,
          }
          : row
      )
    );
  };

  const uploadAcademicMarksheet = async (semesterLabel: string, file: File) => {
    if (!file) return;
    setUploadingSemesterMarksheet(semesterLabel);
    try {
      const formData = new FormData();
      formData.append('title', `${semesterLabel} Marksheet`);
      formData.append('attachment_type', `marksheet_${semesterLabel.toLowerCase()}`);
      formData.append('file', file);
      const attachment = await studentService.uploadAttachment(formData);
      updateAcademicRow(semesterLabel, 'marksheet_file_path', attachment.file_path);
      showToast(`${semesterLabel} marksheet uploaded`);
    } catch (error: any) {
      showToast(error?.response?.data?.error || 'Failed to upload marksheet');
    } finally {
      setUploadingSemesterMarksheet(null);
    }
  };

  const saveAcademicDetails = async (event: React.FormEvent) => {
    event.preventDefault();
    if (savingAcademicDetails) return;

    const normalizedDegree = academicMeta.degree_name.trim() || 'B.E.';
    const normalizedBranch = academicMeta.branch_name.trim() || formState.course || 'Information Technology';
    const startYear = academicMeta.batch_start_year.trim();
    const endYear = academicMeta.batch_end_year.trim();

    setSavingAcademicDetails(true);
    try {
      const operations: Promise<any>[] = [];
      academicRows.forEach((row, index) => {
        const rowHasData =
          row.sgpa.trim() !== '' ||
          row.closed_backlogs.trim() !== '' ||
          row.live_backlogs.trim() !== '' ||
          row.marksheet_file_path.trim() !== '';

        const payload = {
          degree_name: normalizedDegree,
          branch_name: normalizedBranch,
          batch_start_year: startYear ? Number.parseInt(startYear, 10) : null,
          batch_end_year: endYear ? Number.parseInt(endYear, 10) : null,
          semester_label: row.semester_label,
          sgpa: row.sgpa.trim(),
          closed_backlogs: row.closed_backlogs.trim() === '' ? 0 : Number.parseInt(row.closed_backlogs, 10),
          live_backlogs: row.live_backlogs.trim() === '' ? 0 : Number.parseInt(row.live_backlogs, 10),
          marksheet_file_path: row.marksheet_file_path.trim(),
          display_order: index + 1,
        };

        if (row.id && !rowHasData) {
          operations.push(studentService.deleteSection('academic-details', row.id));
          return;
        }
        if (row.id && rowHasData) {
          operations.push(studentService.updateSection('academic-details', row.id, payload));
          return;
        }
        if (!row.id && rowHasData) {
          operations.push(studentService.createSection('academic-details', payload));
        }
      });

      await Promise.all(operations);
      await loadProfile();
      showToast('Academic details saved');
    } catch (error: any) {
      showToast(error?.response?.data?.error || 'Failed to save academic details');
    } finally {
      setSavingAcademicDetails(false);
    }
  };

  const handleSectionSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (savingSection) return;

    const fields = SECTION_FIELDS[activeTab] || [];
    const payload: Record<string, any> = {};
    const missingFields: string[] = [];

    fields.forEach((field) => {
      const value = sectionForm[field.name];
      if (field.type === 'tags') {
        payload[field.name] = (value || '')
          .split(',')
          .map((item: string) => item.trim())
          .filter(Boolean);
      } else {
        payload[field.name] = typeof value === 'string' ? value.trim() : value || '';
      }

      if (field.required) {
        const fieldValue = payload[field.name];
        const hasValue = Array.isArray(fieldValue)
          ? fieldValue.length > 0
          : typeof fieldValue === 'string'
            ? fieldValue.trim().length > 0
            : Boolean(fieldValue);
        if (!hasValue) {
          missingFields.push(field.label);
        }
      }
    });

    if (missingFields.length > 0) {
      showToast(`Please fill required fields: ${missingFields.join(', ')}`);
      return;
    }

    if (payload.start_date && payload.end_date && payload.end_date < payload.start_date) {
      showToast('End date cannot be before start date');
      return;
    }

    setSavingSection(true);
    try {
      const hasFileUpload = activeTab === 'certifications' && certificateFile;

      if (hasFileUpload) {
        const formData = new FormData();
        Object.entries(payload).forEach(([key, value]) => {
          if (value !== undefined && value !== null && value !== '') {
            formData.append(key, value);
          }
        });
        formData.append('certificate_file', certificateFile);

        if (editingEntry) {
          await studentService.updateSection(activeTab, editingEntry, formData as unknown as Record<string, unknown>);
        } else {
          await studentService.createSection(activeTab, formData as unknown as Record<string, unknown>);
        }

        showToast(editingEntry ? 'Entry updated' : 'Entry added');
      } else {
        if (editingEntry) {
          await studentService.updateSection(activeTab, editingEntry, payload);
          showToast('Entry updated');
        } else {
          await studentService.createSection(activeTab, payload);
          showToast('Entry added');
        }
      }
      setSectionForm({});
      setEditingEntry(null);
      setCertificateFile(null);
      await loadProfile();
    } catch (error: any) {
      showToast(error?.response?.data?.error || 'Failed to save entry');
    } finally {
      setSavingSection(false);
    }
  };

  const startEditing = (entry: Record<string, any>) => {
    const fields = SECTION_FIELDS[activeTab] || [];
    const patch: Record<string, any> = {};
    fields.forEach((field) => {
      const value = entry[field.name];
      if (field.type === 'tags') {
        patch[field.name] = Array.isArray(value) ? value.join(', ') : value || '';
      } else {
        patch[field.name] = value || '';
      }
    });
    setSectionForm(patch);
    setEditingEntry(entry.id);
  };

  const deleteEntry = async (id: number) => {
    if (!window.confirm('Delete this entry?')) return;
    try {
      await studentService.deleteSection(activeTab, id);
      showToast('Entry removed');
      await loadProfile();
    } catch (error: any) {
      showToast(error?.response?.data?.error || 'Failed to delete entry');
    }
  };

  useEffect(() => {
    setAvatarPreviewFailed(false);
  }, [savedBasicProfile.profile_picture, pendingAvatarPreview]);

  const getEntryHighlights = (entry: Record<string, any>, sectionKey: string) => {
    const preferredFields = SECTION_CARD_FIELDS[sectionKey] || [];
    const highlights = preferredFields
      .map((fieldName) => ({
        label: FIELD_LABEL_OVERRIDES[fieldName] || toTitleCaseLabel(fieldName),
        value: formatDisplayValue(entry[fieldName]),
      }))
      .filter((item) => item.value !== '-')
      .slice(0, 3);

    if (highlights.length > 0) {
      return highlights;
    }

    return Object.entries(entry)
      .filter(([key, value]) => !HIDDEN_MODAL_FIELDS.has(key) && hasDisplayValue(value))
      .slice(0, 3)
      .map(([key, value]) => ({
        label: FIELD_LABEL_OVERRIDES[key] || toTitleCaseLabel(key),
        value: formatDisplayValue(value),
      }));
  };

  const getEntryModalFields = (entry: Record<string, any>) =>
    Object.entries(entry)
      .filter(([key, value]) => !HIDDEN_MODAL_FIELDS.has(key) && hasDisplayValue(value))
      .map(([key, value]) => ({
        key,
        label: FIELD_LABEL_OVERRIDES[key] || toTitleCaseLabel(key),
        value,
      }));

  if (loading) return <div className="loading">Preparing workspace...</div>;

  const fullName = `${savedBasicProfile.first_name || ''} ${savedBasicProfile.last_name || ''}`.trim() || 'Student';
  const avatarUrl = pendingAvatarPreview || resolveAssetUrl(savedBasicProfile.profile_picture);
  const avatarInitials = getInitials(savedBasicProfile.first_name, savedBasicProfile.last_name);
  const aggregateCgpa = computeAggregateCgpa(academicRows);
  const placementPolicyLink = placementPolicyForm.policy_document_url || DEFAULT_POLICY_LINK;

  return (
    <div className="profile-workspace">
      <aside className="profile-sidebar">
        <div className="sidebar-header">
          <span className="badge badge-info">Student Workspace</span>
          <h2>Profile Builder</h2>
          <p>Prepare a resume-ready profile</p>
        </div>
        <nav>
          {NAV_TABS.map((tab) => (
            <button
              key={tab.key}
              className={`sidebar-tab ${tab.key === activeTab ? 'active' : ''}`}
              onClick={() => {
                navigate(`/student/profile/${tab.key}`);
                setSectionForm({});
                setEditingEntry(null);
                setViewingEntry(null);
                setCertificateFile(null);
                if (tab.key === 'basic' && activeTab !== 'basic') {
                  loadProfile();
                }
              }}
            >
              <div>
                <strong>{tab.label}</strong>
                <p>{tab.description}</p>
              </div>
              {stats[tab.key] !== undefined && <span className="badge badge-pill">{stats[tab.key]}</span>}
            </button>
          ))}
        </nav>
      </aside>

      <section className="profile-content">
        {toast && <div className="alert alert-info">{toast}</div>}

        {/* Profile Completion Bar */}
        <div className="profile-completion-card">
          <div className="profile-completion-header">
            <h3>Profile Completion</h3>
            <span
              className={`profile-completion-percent ${completionPercentage >= 80 ? 'is-good' : completionPercentage >= 60 ? 'is-mid' : 'is-low'
                }`}
            >
              {completionPercentage}%
            </span>
          </div>
          <div className="profile-completion-track">
            <div
              className={`profile-completion-fill ${completionPercentage >= 80 ? 'is-good' : completionPercentage >= 60 ? 'is-mid' : 'is-low'
                }`}
              style={{ width: `${completionPercentage}%` }}
            />
          </div>
          <p className="profile-completion-note">
            {completionPercentage < 60 &&
              `Complete at least 60% of your profile to apply for opportunities.${completionBreakdown?.missing_criteria?.length
                ? ` Missing: ${completionBreakdown.missing_criteria.slice(0, 2).join(', ')}${completionBreakdown.missing_criteria.length > 2 ? ', ...' : ''
                }.`
                : ''
              }`}
            {completionPercentage >= 60 && completionPercentage < 80 && 'Good progress! Complete more sections to improve your profile.'}
            {completionPercentage >= 80 && 'Excellent! Your profile is well-completed.'}
          </p>
          {completionBreakdown && (
            <p className="profile-completion-note">
              Criteria completed: {completionBreakdown.completed_criteria}/{completionBreakdown.total_criteria}
            </p>
          )}
        </div>

        {activeTab === 'basic' && (
          <div className="profile-basic">
            <div className="basic-profile-hero">
              <div className="basic-profile-identity">
                <div className="avatar-uploader-block">
                  <label className={`avatar-uploader ${avatarUploading ? 'is-uploading' : ''}`}>
                    <input
                      type="file"
                      hidden
                      accept=".png,.jpg,.jpeg,.webp"
                      onChange={uploadProfilePicture}
                      disabled={avatarUploading || savingProfile}
                    />
                    <div className="avatar-circle">
                      {avatarUrl && !avatarPreviewFailed ? (
                        <img
                          src={avatarUrl}
                          alt={`${fullName} profile`}
                          onError={() => setAvatarPreviewFailed(true)}
                        />
                      ) : (
                        <span>{avatarInitials}</span>
                      )}
                    </div>
                    <span className="avatar-upload-cta">
                      {avatarUploading ? 'Saving photo...' : pendingAvatarFile ? 'Photo selected' : 'Change photo'}
                    </span>
                  </label>
                  <p className="avatar-upload-help">
                    {pendingAvatarFile ? 'Preview ready. Save profile to apply.' : 'PNG, JPG or WEBP'}
                  </p>
                </div>

                <div className="basic-profile-summary">
                  <span className="profile-kicker">Profile Identity</span>
                  <h3>{fullName}</h3>
                  <p className="basic-profile-subtitle">
                    {savedBasicProfile.course || 'Add branch / course'}
                    {savedBasicProfile.specialization ? ` • ${savedBasicProfile.specialization}` : ''}
                  </p>
                  <div className="basic-profile-meta">
                    <span className="basic-profile-chip">
                      {savedBasicProfile.prn_number ? `PRN: ${savedBasicProfile.prn_number}` : 'PRN not added'}
                    </span>
                    <span className="basic-profile-chip">
                      {savedBasicProfile.phone ? `Phone: ${savedBasicProfile.phone}` : 'Phone not added'}
                    </span>
                  </div>
                </div>
              </div>

              <div className="profile-actions profile-actions-panel">
                <label className="btn btn-secondary" htmlFor="resume-upload-profile" style={{ cursor: 'pointer' }}>
                  Upload Resume
                </label>
                <input
                  id="resume-upload-profile"
                  type="file"
                  style={{ display: 'none' }}
                  accept=".pdf,.doc,.docx,.txt,.png,.jpg,.jpeg"
                  onChange={uploadResume}
                />
                <button className="btn btn-success" type="button" onClick={downloadResume}>
                  Generate Resume
                </button>
              </div>
            </div>
            <form className="profile-form" onSubmit={saveProfile}>
              <div className="profile-form-block">
                <h4>Personal Information</h4>
                <div className="grid-3">
                  {BASIC_NAME_FIELDS.map((field) => (
                    <div className="form-group" key={field.key}>
                      <label>
                        {field.label}
                        {field.required && <span className="required-mark"> *</span>}
                      </label>
                      <input
                        value={formState[field.key] || ''}
                        placeholder={BASIC_FIELD_PLACEHOLDERS[field.key]}
                        onChange={(e) => setFormState({ ...formState, [field.key]: e.target.value })}
                        required={field.required}
                      />
                    </div>
                  ))}
                </div>

                <div className="grid-2">
                  <div className="form-group">
                    <label>Phone <span className="required-mark"> *</span></label>
                    <input
                      value={formState.phone || ''}
                      placeholder={BASIC_FIELD_PLACEHOLDERS.phone}
                      onChange={(e) => setFormState({ ...formState, phone: e.target.value })}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label>PRN Number</label>
                    <input
                      value={formState.prn_number || ''}
                      placeholder={BASIC_FIELD_PLACEHOLDERS.prn_number}
                      onChange={(e) => setFormState({ ...formState, prn_number: e.target.value })}
                    />
                  </div>
                </div>

                <div className="grid-2">
                  <div className="form-group">
                    <label>Date of Birth</label>
                    <input
                      type="date"
                      value={formState.date_of_birth || ''}
                      placeholder={BASIC_FIELD_PLACEHOLDERS.date_of_birth}
                      onChange={(e) => setFormState({ ...formState, date_of_birth: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label>Gender</label>
                    <select value={formState.gender || ''} onChange={(e) => setFormState({ ...formState, gender: e.target.value })}>
                      <option value="">Select gender</option>
                      <option value="Male">Male</option>
                      <option value="Female">Female</option>
                      <option value="Other">Other</option>
                      <option value="Prefer not to say">Prefer not to say</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="profile-form-block">
                <h4>Academic Details</h4>
                <div className="grid-2">
                  <div className="form-group">
                    <label>Branch</label>
                    <input
                      value={formState.course || ''}
                      onChange={(e) => setFormState({ ...formState, course: e.target.value })}
                      placeholder={BASIC_FIELD_PLACEHOLDERS.course}
                    />
                  </div>
                  <div className="form-group">
                    <label>Year / Division</label>
                    <input
                      value={formState.specialization || ''}
                      onChange={(e) => setFormState({ ...formState, specialization: e.target.value })}
                      placeholder={BASIC_FIELD_PLACEHOLDERS.specialization}
                    />
                  </div>
                </div>
              </div>

              <div className="profile-form-block">
                <h4>About You</h4>
                <div className="form-group">
                  <label>Address</label>
                  <textarea
                    rows={3}
                    value={formState.address || ''}
                    placeholder={BASIC_FIELD_PLACEHOLDERS.address}
                    onChange={(e) => setFormState({ ...formState, address: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label>About / Bio</label>
                  <textarea
                    rows={3}
                    value={formState.bio || ''}
                    placeholder={BASIC_FIELD_PLACEHOLDERS.bio}
                    onChange={(e) => setFormState({ ...formState, bio: e.target.value })}
                  />
                </div>
                <div className="grid-2">
                  <div className="form-group">
                    <label>Skills</label>
                    <textarea
                      rows={2}
                      value={formState.skills || ''}
                      placeholder={BASIC_FIELD_PLACEHOLDERS.skills}
                      onChange={(e) => setFormState({ ...formState, skills: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label>Interests</label>
                    <textarea
                      rows={2}
                      value={formState.interests || ''}
                      placeholder={BASIC_FIELD_PLACEHOLDERS.interests}
                      onChange={(e) => setFormState({ ...formState, interests: e.target.value })}
                    />
                  </div>
                </div>
              </div>

              <div className="profile-form-block">
                <h4>Public Links</h4>
                <div className="grid-3">
                  {['linkedin_url', 'github_url', 'portfolio_url'].map((field) => (
                    <div className="form-group" key={field}>
                      <label>{field.replace('_url', '').toUpperCase()}</label>
                      <input
                        value={formState[field] || ''}
                        placeholder={BASIC_FIELD_PLACEHOLDERS[field]}
                        onChange={(e) => setFormState({ ...formState, [field]: e.target.value })}
                      />
                    </div>
                  ))}
                </div>
              </div>

              <button className="btn btn-primary" type="submit" disabled={savingProfile}>
                {savingProfile ? 'Saving...' : 'Save Profile'}
              </button>
            </form>
          </div>
        )}

        {activeTab === 'placement-policy' && (
          <form className="placement-policy-card" onSubmit={savePlacementPolicy}>
            <div className="placement-policy-block form-group">
              <label>
                Interested In Jobs <span className="required-mark">*</span>
              </label>
              <select
                value={placementPolicyForm.interested_in_jobs}
                onChange={(event) =>
                  setPlacementPolicyForm((previous) => ({
                    ...previous,
                    interested_in_jobs: event.target.value as 'yes' | 'no',
                  }))
                }
                required
              >
                <option value="">Select</option>
                <option value="yes">Yes</option>
                <option value="no">No</option>
              </select>
            </div>

            <div className="placement-policy-block form-group">
              <label>
                Interested In Internships <span className="required-mark">*</span>
              </label>
              <select
                value={placementPolicyForm.interested_in_internships}
                onChange={(event) =>
                  setPlacementPolicyForm((previous) => ({
                    ...previous,
                    interested_in_internships: event.target.value as 'yes' | 'no',
                  }))
                }
                required
              >
                <option value="">Select</option>
                <option value="yes">Yes</option>
                <option value="no">No</option>
              </select>
            </div>

            <div className="placement-policy-block">
              <h4>Placement Policy</h4>
              <label className="placement-policy-checkbox">
                <input
                  type="checkbox"
                  checked={placementPolicyForm.placement_policy_agreed}
                  onChange={(event) =>
                    setPlacementPolicyForm((previous) => ({
                      ...previous,
                      placement_policy_agreed: event.target.checked,
                    }))
                  }
                  required
                />
                <span>
                  I hereby certify that all of the information provided by me in this application is correct and
                  complete, and I have read, acknowledged and agreed to the placement policy and terms mentioned.
                </span>
              </label>
              <p className="placement-policy-link-row">
                <a href={placementPolicyLink} target="_blank" rel="noreferrer">
                  Click here
                </a>{' '}
                to read Placement Policy.
              </p>
            </div>

            <button className="btn btn-primary placement-policy-save" type="submit" disabled={savingPlacementPolicy}>
              {savingPlacementPolicy ? 'Saving...' : 'Save'}
            </button>
          </form>
        )}

        {activeTab === 'academic-details' && (
          <form className="academic-details-card" onSubmit={saveAcademicDetails}>
            <div className="academic-details-header">
              <div className="academic-details-title-row">
                <input
                  value={academicMeta.degree_name}
                  onChange={(event) =>
                    setAcademicMeta((previous) => ({
                      ...previous,
                      degree_name: event.target.value,
                    }))
                  }
                  placeholder="Degree (e.g. B.E.)"
                />
                <input
                  value={academicMeta.branch_name}
                  onChange={(event) =>
                    setAcademicMeta((previous) => ({
                      ...previous,
                      branch_name: event.target.value,
                    }))
                  }
                  placeholder="Branch"
                />
                <input
                  value={academicMeta.batch_start_year}
                  onChange={(event) =>
                    setAcademicMeta((previous) => ({
                      ...previous,
                      batch_start_year: event.target.value,
                    }))
                  }
                  placeholder="Start Year"
                  maxLength={4}
                />
                <input
                  value={academicMeta.batch_end_year}
                  onChange={(event) =>
                    setAcademicMeta((previous) => ({
                      ...previous,
                      batch_end_year: event.target.value,
                    }))
                  }
                  placeholder="End Year"
                  maxLength={4}
                />
              </div>
              <h4>
                {academicMeta.degree_name || 'B.E.'} - {academicMeta.branch_name || 'Branch'}{' '}
                {(academicMeta.batch_start_year || '----') + ' - ' + (academicMeta.batch_end_year || '----')} Academics
              </h4>
            </div>

            <div className="academic-details-table-wrapper">
              <table className="academic-details-table">
                <thead>
                  <tr>
                    <th>Year - Semester</th>
                    <th>SGPA</th>
                    <th>Closed Backlogs</th>
                    <th>Live Backlogs</th>
                    <th>Marksheet</th>
                  </tr>
                </thead>
                <tbody>
                  {academicRows.map((row) => {
                    const marksheetUrl = resolveAssetUrl(row.marksheet_file_path);
                    const isUploading = uploadingSemesterMarksheet === row.semester_label;
                    return (
                      <tr key={row.semester_label}>
                        <td>{row.semester_label}</td>
                        <td>
                          <input
                            value={row.sgpa}
                            onChange={(event) => updateAcademicRow(row.semester_label, 'sgpa', event.target.value)}
                            placeholder="SGPA"
                          />
                        </td>
                        <td>
                          <input
                            value={row.closed_backlogs}
                            onChange={(event) =>
                              updateAcademicRow(row.semester_label, 'closed_backlogs', event.target.value)
                            }
                            placeholder="0"
                          />
                        </td>
                        <td>
                          <input
                            value={row.live_backlogs}
                            onChange={(event) =>
                              updateAcademicRow(row.semester_label, 'live_backlogs', event.target.value)
                            }
                            placeholder="0"
                          />
                        </td>
                        <td>
                          <div className="academic-marksheet-cell">
                            {marksheetUrl ? (
                              <a href={marksheetUrl} target="_blank" rel="noreferrer">
                                View
                              </a>
                            ) : (
                              <span>N/A</span>
                            )}
                            <label className={`btn btn-secondary btn-sm ${isUploading ? 'is-disabled' : ''}`}>
                              {isUploading ? 'Uploading...' : marksheetUrl ? 'Replace' : 'Upload'}
                              <input
                                type="file"
                                hidden
                                accept=".pdf,.png,.jpg,.jpeg"
                                disabled={isUploading}
                                onChange={(event) => {
                                  const file = event.target.files?.[0];
                                  if (!file) return;
                                  uploadAcademicMarksheet(row.semester_label, file);
                                  event.target.value = '';
                                }}
                              />
                            </label>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
                <tfoot>
                  <tr>
                    <th>Aggregate CGPA</th>
                    <th>{aggregateCgpa || '-'}</th>
                    <th>
                      {academicRows.reduce((sum, row) => sum + (Number.parseInt(row.closed_backlogs, 10) || 0), 0)}
                    </th>
                    <th>{academicRows.reduce((sum, row) => sum + (Number.parseInt(row.live_backlogs, 10) || 0), 0)}</th>
                    <th>-</th>
                  </tr>
                </tfoot>
              </table>
            </div>

            <button className="btn btn-primary academic-details-save" type="submit" disabled={savingAcademicDetails}>
              {savingAcademicDetails ? 'Saving...' : 'Save'}
            </button>
          </form>
        )}

        {activeTab !== 'basic' && activeTab !== 'placement-policy' && activeTab !== 'academic-details' && (
          <div className={`section-wrapper ${activeTab === 'attachments' ? 'attachments-layout' : ''}`}>
            {activeTab === 'attachments' && (
              <div className="section-form upload-attachment-card">
                <h4>Upload Attachment</h4>
                <p className="muted">Choose a file (transcript, offer letter, certificate, etc.)</p>
                <input
                  type="file"
                  accept=".pdf,.doc,.docx,.png,.jpg,.jpeg"
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    const formData = new FormData();
                    formData.append('title', file.name);
                    formData.append('file', file);
                    await studentService.uploadAttachment(formData);
                    showToast('Attachment uploaded');
                    loadProfile();
                  }}
                />
              </div>
            )}

            <div className="section-list">
              {(sections[activeTab] || []).length === 0 ? (
                <p className="empty-state">No records added yet.</p>
              ) : (
                (sections[activeTab] || []).map((entry) => (
                  <div className="section-card" key={entry.id}>
                    <div>
                      <h4>{getEntryTitle(entry)}</h4>
                      {entry.organization && <p className="muted">{entry.organization}</p>}
                      {entry.company_name && <p className="muted">{entry.company_name}</p>}
                      {entry.description && <p className="muted">{entry.description}</p>}
                      <div className="section-card-details">
                        {getEntryHighlights(entry, activeTab).map((item) => (
                          <div className="section-card-detail-row" key={`${entry.id}-${item.label}`}>
                            <span>{item.label}</span>
                            <strong>{item.value}</strong>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="section-card-actions">
                      <button
                        className="btn btn-info section-btn-view"
                        onClick={() => setViewingEntry({ sectionKey: activeTab, entry })}
                        type="button"
                      >
                        View
                      </button>
                      {activeTab !== 'attachments' && (
                        <button className="btn btn-secondary" onClick={() => startEditing(entry)} type="button">
                          Edit
                        </button>
                      )}
                      <button className="btn btn-danger" onClick={() => deleteEntry(entry.id)} type="button">
                        Delete
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>

            {activeTab !== 'attachments' && SECTION_FIELDS[activeTab] && (
              <form className="section-form" onSubmit={handleSectionSubmit} noValidate>
                <h4>{editingEntry ? 'Update Entry' : `Add ${NAV_TABS.find((tab) => tab.key === activeTab)?.label}`}</h4>
                {SECTION_FIELDS[activeTab].map((field) => (
                  <div className="form-group" key={field.name}>
                    <label>
                      {field.label}
                      {field.required && <span className="required-mark"> *</span>}
                    </label>
                    {field.type === 'textarea' ? (
                      <textarea
                        rows={3}
                        value={sectionForm[field.name] || ''}
                        placeholder={getSectionFieldPlaceholder(field)}
                        onChange={(e) =>
                          setSectionForm((previous) => ({
                            ...previous,
                            [field.name]: e.target.value,
                          }))
                        }
                      />
                    ) : field.type === 'file' ? (
                      <div className="file-upload-wrapper">
                        <input
                          type="file"
                          accept=".pdf,.doc,.docx,.png,.jpg,.jpeg"
                          onChange={(e) => {
                            const file = e.target.files?.[0] || null;
                            setCertificateFile(file);
                          }}
                        />
                        {certificateFile && (
                          <span className="file-selected">{certificateFile.name}</span>
                        )}
                        {sectionForm[field.name] && !certificateFile && (
                          <span className="file-exists">Current: {sectionForm[field.name]}</span>
                        )}
                      </div>
                    ) : (
                      <input
                        type={field.type === 'date' ? 'date' : 'text'}
                        value={sectionForm[field.name] || ''}
                        placeholder={getSectionFieldPlaceholder(field)}
                        onChange={(e) =>
                          setSectionForm((previous) => ({
                            ...previous,
                            [field.name]: e.target.value,
                          }))
                        }
                      />
                    )}
                  </div>
                ))}
                <div className="section-form-actions">
                  {editingEntry && (
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => {
                        setSectionForm({});
                        setEditingEntry(null);
                        setCertificateFile(null);
                      }}
                    >
                      Cancel
                    </button>
                  )}
                  <button className="btn btn-primary" type="submit" disabled={savingSection}>
                    {savingSection ? 'Saving...' : editingEntry ? 'Update Entry' : 'Add Entry'}
                  </button>
                </div>
              </form>
            )}

          </div>
        )}

        {viewingEntry && (
          <div className="profile-entry-modal-overlay" onClick={() => setViewingEntry(null)}>
            <div className="profile-entry-modal-content" onClick={(event) => event.stopPropagation()}>
              <div className="profile-entry-modal-header">
                <div>
                  <h3>{getEntryTitle(viewingEntry.entry)}</h3>
                  <p>{NAV_TABS.find((tab) => tab.key === viewingEntry.sectionKey)?.label || 'Details'}</p>
                </div>
                <button className="modal-close" onClick={() => setViewingEntry(null)} aria-label="Close" title="Close">
                  <FiX />
                </button>
              </div>
              <div className="profile-entry-modal-body">
                {getEntryModalFields(viewingEntry.entry).map((field) => {
                  const rawValue = field.value;
                  const formattedValue = formatDisplayValue(rawValue);
                  const isPathOrUrlField =
                    field.key.includes('_url') || field.key.includes('_path') || field.key === 'file_path' || field.key === 'certificate_file';
                  const resolvedLink = typeof rawValue === 'string' ? resolveAssetUrl(rawValue) : '';

                  return (
                    <div className="profile-entry-modal-item" key={`${viewingEntry.entry.id}-${field.key}`}>
                      <span>{field.label}</span>
                      {isPathOrUrlField && formattedValue !== '-' ? (
                        <a href={resolvedLink} target="_blank" rel="noreferrer">
                          {field.key === 'certificate_file' ? 'View Certificate' : formattedValue}
                        </a>
                      ) : (
                        <strong>{formattedValue}</strong>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
};

export default StudentProfileWorkspace;
