export type CallMode = 'outbound' | 'inbound';

export type AgentState =
  | 'disconnected'
  | 'connecting'
  | 'idle'
  | 'listening'
  | 'transcribing'
  | 'thinking'
  | 'speaking';

export interface LanguageDisplay {
  code: string;
  name: string;
  native: string;
  tts_lang: string;
  label: string;
}

export interface VoiceOption {
  id: string;
  label: string;
  gender: string;
  style: string;
}

export interface TranscriptMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  language?: LanguageDisplay;
  timestamp: number;
  interrupted?: boolean;
  streaming?: boolean;
}

export interface SchemeRecommendation {
  id: string;
  name: string;
  badge: string;
  highlight: string;
}

export interface CompletionStats {
  core_filled: number;
  core_total: number;
  total_filled: number;
  total_fields: number;
  percent: number;
}

export interface LoanApplicationData {
  facility_type: string | null;
  loan_purpose: string | null;
  amount_required_inr: string | null;
  full_name: string | null;
  father_or_spouse_name: string | null;
  age: string | null;
  gender: string | null;
  mobile_number: string | null;
  education_level: string | null;
  requires_thumb_impression_lti: string | null;
  social_category: string | null;
  village: string | null;
  post_office: string | null;
  taluka_mandal: string | null;
  district: string | null;
  state: string | null;
  pin_code: string | null;
  residence_type: string | null;
  land_title: string | null;
  total_land_acres: string | null;
  irrigated_acres: string | null;
  irrigation_source: string | null;
  survey_khasra_no: string | null;
  kharif_crops: string | null;
  rabi_crops: string | null;
  other_crops: string | null;
  allied_activities: string | null;
  farm_machinery: string | null;
  pm_kisan_beneficiary: string | null;
  existing_bank_name: string | null;
  has_savings_or_pmjdy_account: string | null;
  annual_agri_income_inr: string | null;
  annual_other_income_inr: string | null;
  available_kyc_docs: string | null;
  existing_loans_summary: string | null;
  pmfby_crop_insurance_consent: string | null;
  pmsby_pmjjby_consent: string | null;
  preferred_language: string | null;
  field_agent_visit_notes: string | null;
  verbal_consent_for_agent_callback: string | null;
}

export interface HealthStatus {
  status: 'ok' | 'degraded' | 'offline';
  services?: {
    stt_indic_transcribe: { ok: boolean };
    tts_maya2_native: { ok: boolean };
    llm_qwen35_9b: { ok: boolean; model?: string };
    vad_silero: { ok: boolean };
  };
}

export const EMPTY_APPLICATION: LoanApplicationData = {
  facility_type: null,
  loan_purpose: null,
  amount_required_inr: null,
  full_name: null,
  father_or_spouse_name: null,
  age: null,
  gender: null,
  mobile_number: null,
  education_level: null,
  requires_thumb_impression_lti: null,
  social_category: null,
  village: null,
  post_office: null,
  taluka_mandal: null,
  district: null,
  state: null,
  pin_code: null,
  residence_type: null,
  land_title: null,
  total_land_acres: null,
  irrigated_acres: null,
  irrigation_source: null,
  survey_khasra_no: null,
  kharif_crops: null,
  rabi_crops: null,
  other_crops: null,
  allied_activities: null,
  farm_machinery: null,
  pm_kisan_beneficiary: null,
  existing_bank_name: null,
  has_savings_or_pmjdy_account: null,
  annual_agri_income_inr: null,
  annual_other_income_inr: null,
  available_kyc_docs: null,
  existing_loans_summary: null,
  pmfby_crop_insurance_consent: null,
  pmsby_pmjjby_consent: null,
  preferred_language: null,
  field_agent_visit_notes: null,
  verbal_consent_for_agent_callback: null,
};
