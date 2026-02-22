export type ChosenSource =
  | "ct_registry"
  | "domain_rdap"
  | "whoisxml"
  | "social_hint"
  | "not_found";

export interface JobSettings {
  high_confidence_threshold: number;
  prefer_earliest_known_date: boolean;
  enable_rdap_lookup: boolean;
  enable_whois_fallback: boolean;
  enable_social_hints: boolean;
  min_plausible_date: string;
  denylist_domains: string[];
}

export interface JobCounts {
  total_rows: number;
  auto_matched: number;
  needs_review: number;
  not_found: number;
  filled_via_domain: number;
  filled_via_social: number;
}

export interface JobStatusResponse {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  progress_done: number;
  progress_total: number;
  progress_pct: number;
  message: string;
  counts: JobCounts;
  can_download: boolean;
  error?: string | null;
}

export interface ReviewCandidate {
  name: string;
  city: string;
  zip: string;
  entity_id: string;
  registration_date_raw: string;
  similarity: number;
  confidence: number;
}

export interface ReviewRow {
  row_index: number;
  business: string;
  city: string;
  zip: string;
  url: string;
  candidates: ReviewCandidate[];
}

export interface ReviewResponse {
  job_id: string;
  rows: ReviewRow[];
}

export interface AppConfigResponse {
  defaults: JobSettings;
  whois_key_present: boolean;
  feature_social_hints_env: boolean;
}

