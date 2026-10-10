/**
 * Authority Console API Client.
 * Communicates with administrative StreetVerism endpoints using X-Authority-Key.
 */

export interface CheckinItem {
  id: string;
  lat: number;
  lng: number;
  cell7: string;
  state: 'safe' | 'need_help';
  language: string;
  group_size: number;
  note?: string | null;
  handled: boolean;
  created_at: string;
  is_replay: boolean;
}

export interface CheckinCluster {
  cell7: string;
  count: number;
  need_help: number;
  languages: Record<string, number>;
  unhandled_need_help: number;
}

export interface CheckinListResponse {
  items: CheckinItem[];
  clusters: CheckinCluster[];
}

export interface ConsoleAlert {
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

export interface ConsoleAlertsResponse {
  alerts: ConsoleAlert[];
  total: number;
}

export interface ScenarioStatusResponse {
  name: string;
  mode: string;
  is_running: boolean;
  paused: boolean;
  speed: number;
  current_time?: string | null;
  elapsed_s: number;
  scenario_start?: string | null;
  scenario_end?: string | null;
  is_replay: boolean;
  label?: string | null;
  disclaimer?: string | null;
  bookmarks?: Array<{ name: string; t_offset_s: number; description: string }> | null;
}

const getApiBase = (): string => {
  const envBase = import.meta.env.VITE_API_BASE;
  if (envBase && typeof envBase === 'string' && envBase.trim() !== '') {
    return envBase.replace(/\/+$/, '');
  }
  return 'http://localhost:8000';
};

export function getStoredAuthorityKey(): string {
  try {
    return sessionStorage.getItem('streetverism_authority_key') || '';
  } catch {
    return '';
  }
}

export function setStoredAuthorityKey(key: string): void {
  try {
    if (key) {
      sessionStorage.setItem('streetverism_authority_key', key);
    } else {
      sessionStorage.removeItem('streetverism_authority_key');
    }
  } catch {
    // SessionStorage unavailable
  }
}

async function consoleFetch<T>(
  endpoint: string,
  options?: RequestInit,
  authorityKey?: string
): Promise<T> {
  const baseUrl = getApiBase();
  const url = `${baseUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  };

  const key = authorityKey || getStoredAuthorityKey();
  if (key) {
    headers['X-Authority-Key'] = key;
  }

  const response = await fetch(url, {
    ...options,
    headers: {
      ...headers,
      ...options?.headers,
    },
  });

  if (!response.ok) {
    let msg = `HTTP error ${response.status} ${response.statusText}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) {
        msg = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
      } else if (errJson.message) {
        msg = errJson.message;
      }
    } catch {
      // Ignore parse failure
    }
    const err = new Error(msg);
    (err as any).status = response.status;
    throw err;
  }

  return (await response.json()) as T;
}

// 1. Check-ins
export async function getConsoleCheckins(authorityKey?: string): Promise<CheckinListResponse> {
  return consoleFetch<CheckinListResponse>('/api/checkins', { method: 'GET' }, authorityKey);
}

export async function patchCheckinHandled(
  checkinId: string,
  handled: boolean,
  authorityKey?: string
): Promise<CheckinItem> {
  return consoleFetch<CheckinItem>(
    `/api/checkins/${checkinId}`,
    {
      method: 'PATCH',
      body: JSON.stringify({ handled }),
    },
    authorityKey
  );
}

// 2. Alerts
export async function getActiveAlerts(authorityKey?: string): Promise<ConsoleAlertsResponse> {
  return consoleFetch<ConsoleAlertsResponse>('/api/alerts?active=true', { method: 'GET' }, authorityKey);
}

export async function expireAlert(alertId: string, authorityKey?: string): Promise<{ ok: boolean }> {
  return consoleFetch<{ ok: boolean }>(`/api/alerts/${alertId}`, { method: 'DELETE' }, authorityKey);
}

export interface PublishAlertPayload {
  hazard: string;
  severity: string;
  urgency: string;
  certainty: string;
  area: {
    type: 'Polygon';
    coordinates: number[][][];
  };
  instruction_keys: string[];
  params?: Record<string, unknown>;
  expires_in_hours?: number;
}

export async function publishAlert(
  payload: PublishAlertPayload,
  authorityKey?: string
): Promise<ConsoleAlert> {
  return consoleFetch<ConsoleAlert>(
    '/api/alerts',
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
    authorityKey
  );
}

// 3. Scenario & Replay
export async function getScenarioStatus(): Promise<ScenarioStatusResponse> {
  return consoleFetch<ScenarioStatusResponse>('/api/scenario/status', { method: 'GET' });
}

export async function seekScenario(
  bookmark?: string,
  offset_s?: number
): Promise<ScenarioStatusResponse> {
  const body: Record<string, unknown> = {};
  if (bookmark) body.bookmark = bookmark;
  else if (offset_s !== undefined) body.offset_s = offset_s;
  return consoleFetch<ScenarioStatusResponse>('/api/scenario/seek', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function startOrResumeScenario(
  name: string = 'michaung_replay',
  speed: number = 1.0
): Promise<ScenarioStatusResponse> {
  return consoleFetch<ScenarioStatusResponse>('/api/scenario/start', {
    method: 'POST',
    body: JSON.stringify({ name, speed }),
  });
}

export async function resetScenario(): Promise<{ ok: boolean; mode: string; is_replay: boolean }> {
  return consoleFetch<{ ok: boolean; mode: string; is_replay: boolean }>('/api/scenario/reset', {
    method: 'POST',
  });
}

// 4. Metadata
export async function getEnglishTemplates(): Promise<{
  lang: string;
  reviewed: boolean;
  templates: Record<string, string>;
}> {
  return consoleFetch<{ lang: string; reviewed: boolean; templates: Record<string, string> }>(
    '/api/templates/en',
    { method: 'GET' }
  );
}
