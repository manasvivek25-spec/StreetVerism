export type Language = 'en' | 'hi' | 'ta' | 'fr' | 'de' | 'ja';

export type HazardStatus = 'SAFE' | 'ADVISORY' | 'WARNING' | 'EMERGENCY' | 'UNVERIFIED';

export type CheckInState = 'SAFE' | 'HELP_NEEDED' | 'UNKNOWN';

export interface CrowdClaim {
  id: string;
  claim_type: string;
  description: string;
  timestamp: string;
  location?: string;
  confidence_score?: number;
  [key: string]: unknown;
}

export interface Alert {
  id: string;
  title: string;
  severity: string;
  description: string;
  timestamp: string;
  area?: string;
  [key: string]: unknown;
}

export interface Instruction {
  id: string;
  step: number;
  text: string;
  category?: string;
  [key: string]: unknown;
}

export interface Evidence {
  id: string;
  type: string;
  source: string;
  details?: string;
  timestamp?: string;
  [key: string]: unknown;
}

export interface Shelter {
  id: string;
  name: string;
  address?: string;
  capacity?: number;
  occupancy?: number;
  is_verified: boolean;
  latitude?: number;
  longitude?: number;
  [key: string]: unknown;
}

export interface StateResponse {
  language: Language;
  hazard_status: HazardStatus;
  headline?: string;
  summary?: string;
  unverified_claim?: CrowdClaim | null;
  alerts: Alert[];
  instructions: Instruction[];
  evidence: Evidence[];
  shelters: Shelter[];
  is_demo?: boolean;
  [key: string]: unknown;
}

export interface CheckInRequest {
  status: CheckInState;
  state?: CheckInState;
  device_id?: string;
  user_id?: string;
  language?: Language;
  group_size?: number;
  lat?: number;
  lng?: number;
  location?: {
    latitude: number;
    longitude: number;
  };
  note?: string;
  [key: string]: unknown;
}

export interface CheckInResponse {
  success: boolean;
  message?: string;
  recorded_at?: string;
  status: CheckInState;
  [key: string]: unknown;
}

export interface ReportRequest {
  description?: string;
  text?: string;
  claim?: 'flooded' | 'blocked' | 'safe' | string;
  claim_type?: 'flooded' | 'blocked' | 'safe' | string;
  category?: string;
  device_id?: string;
  lat?: number;
  lng?: number;
  location?: {
    latitude: number;
    longitude: number;
  };
  photo_url?: string;
  [key: string]: unknown;
}

export interface ReportResponse {
  success: boolean;
  report_id?: string;
  message?: string;
  timestamp?: string;
  [key: string]: unknown;
}

export interface TemplatesResponse {
  templates: Record<string, string>;
  categories?: string[];
  [key: string]: unknown;
}
