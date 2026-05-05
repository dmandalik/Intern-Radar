export type PageId =
  | "overview"
  | "jobs"
  | "hidden_gems"
  | "coming_soon"
  | "saved"
  | "review"
  | "settings"
  | "export";

export interface DashboardJob {
  id: string;
  company_id: string;
  company_name: string;
  title: string;
  description: string | null;
  apply_url: string;
  source_url: string;
  source_type: string;
  role_family: string;
  role_subtype: string | null;
  role_confidence: number;
  role_evidence: string[];
  season: string | null;
  year: number | null;
  locations: string[];
  location_label: string;
  remote_type: string | null;
  status: string;
  status_confidence: number;
  status_evidence: string[];
  eligibility: {
    degree_levels: string[];
    graduation_years: number[];
    majors: string[];
    citizenship_requirement: string | null;
    sponsorship: string | null;
    minimum_gpa: number | null;
    class_years: string[];
    requires_phd: boolean;
    requires_masters: boolean;
    undergrad_friendly: boolean | null;
    freshman_sophomore_friendly: boolean | null;
    confidence: number;
    raw_evidence: string[];
  };
  eligibility_summary: string;
  scores: {
    prestige_score: number;
    role_fit_score: number;
    technical_depth_score: number;
    hidden_gem_score: number;
    freshness_score: number;
    eligibility_score: number;
    opportunity_score: number;
    explanation: string[];
  };
  score_explanation: string[];
  prestige_tier: string | null;
  tags: string[];
  first_seen: string;
  last_seen: string;
  last_verified: string;
  application_status: string;
  saved: boolean;
  applied: boolean;
  ignored: boolean;
  reviewed: boolean;
  notes: string;
  updated_at?: string | null;
  needs_review: boolean;
  raw_payload?: Record<string, unknown> | null;
}

export interface SummaryResponse {
  generated_at: string;
  database_ready: boolean;
  total_jobs: number;
  counts: Record<string, number>;
  apply_first: DashboardJob[];
  signals: {
    hidden_gems: DashboardJob[];
    coming_soon: DashboardJob[];
    review_needed: DashboardJob[];
  };
  charts: {
    status: Array<{ label: string; value: number }>;
    role_family: Array<{ label: string; value: number }>;
    top_companies: Array<{ label: string; value: number }>;
  };
  latest_scan: Record<string, unknown> | null;
  pack: string | null;
  last_scan_at: string | null;
}

export interface JobListResponse {
  items: DashboardJob[];
  total: number;
  limit: number | null;
  offset: number;
}

export interface FilterOptions {
  statuses: string[];
  role_families: string[];
  companies: string[];
  prestige_tiers: string[];
  locations: string[];
  seasons: string[];
  years: number[];
  application_statuses: string[];
  source_types: string[];
  remote_types: string[];
  sponsorships: string[];
}

export interface SettingsResponse {
  read_only: boolean;
  config_path: string;
  database_path: string;
  exports_path: string;
  active_pack: string | null;
  ranking_preset: string | null;
  candidate: Record<string, unknown> | null;
  target_roles: string[];
  deprioritized_roles: string[];
  preferred_locations: string[];
  raw_config: Record<string, unknown>;
}

export interface JobQuery {
  status?: string;
  role_family?: string;
  company?: string;
  prestige_tier?: string;
  location?: string;
  season?: string;
  year?: number | null;
  application_status?: string;
  source_type?: string;
  remote_type?: string;
  sponsorship?: string;
  min_opportunity_score?: number | null;
  min_hidden_gem_score?: number | null;
  min_eligibility_score?: number | null;
  sort?: string;
  limit?: number | null;
  offset?: number;
  search?: string;
}
