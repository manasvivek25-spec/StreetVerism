export type Language = 'en' | 'hi' | 'ta' | 'fr' | 'de' | 'ja';

export type CellStatus = 'official_hazard' | 'likely_hazard' | 'unverified' | 'contradicted' | 'clear';

export type CheckInState = 'safe' | 'need_help';

export type ClaimType = 'flooded' | 'blocked' | 'safe';

export interface Alert {
  id: string;
  source: string;
  sender: string;
  hazard: string;
  severity: string;
  urgency: string;
  certainty: string;
  area: {
    type: string;
    coordinates: number[][][];
  };
  instruction_keys: string[];
  params: Record<string, unknown>;
  sent_at: string;
  expires_at: string;
  supersedes?: string | null;
  published_by: string;
  is_replay: boolean;
}

export interface RenderedInstruction {
  key: string;
  text: string;
  reviewed: boolean;
  original_en?: string | null;
}

export interface EvidenceItem {
  type: 'official' | 'rain' | 'crowd';
  summary: string;
  age_s: number;
  weight: number;
}

export interface Shelter {
  id: string;
  name: string;
  name_local: string;
  lat: number;
  lng: number;
  open: boolean;
  is_demo: boolean;
  capacity?: number | null;
  distance_m?: number | null;
}

export interface HealthResponse {
  status: string;
  mode: 'live' | 'replay' | 'mock' | string;
  is_replay: boolean;
  version: string;
  server_time: string;
}

export interface StateResponse {
  cell: string;
  status: CellStatus;
  p_hazard: number;
  headline_key: string;
  alerts: Alert[];
  instructions: RenderedInstruction[];
  evidence: EvidenceItem[];
  nearest_shelters: Shelter[];
  is_replay: boolean;
  generated_at: string;
  server_time: string;
}

export interface CheckInRequest {
  device_id: string;
  lat: number;
  lng: number;
  state: CheckInState;
  language?: string;
  group_size?: number;
  note?: string;
}

export interface CheckInResponse {
  id: string;
  recorded_at: string;
}

export interface ReportRequest {
  device_id: string;
  lat: number;
  lng: number;
  claim: ClaimType;
  text?: string;
}

export interface ReportResponse {
  accepted: boolean;
  cell: string;
  status: string;
}

export interface TemplatesResponse {
  lang: string;
  reviewed: boolean;
  templates: Record<string, string>;
}

export interface ShelterListResponse {
  shelters: Shelter[];
  total: number;
}

export interface CellProperties {
  cell: string;
  status: CellStatus;
  p_hazard: number;
  updated_at: string;
}

export interface GeoJSONPolygonGeometry {
  type: 'Polygon';
  coordinates: number[][][];
}

export interface CellFeature {
  type: 'Feature';
  geometry: GeoJSONPolygonGeometry;
  properties: CellProperties;
}

export interface CellFeatureCollection {
  type: 'FeatureCollection';
  features: CellFeature[];
}
