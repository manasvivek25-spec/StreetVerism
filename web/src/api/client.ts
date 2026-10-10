import type {
  CellFeatureCollection,
  CheckInRequest,
  CheckInResponse,
  HealthResponse,
  ReportRequest,
  ReportResponse,
  ShelterListResponse,
  StateResponse,
  TemplatesResponse,
} from './types';

const getApiBase = (): string => {
  const envBase = import.meta.env.VITE_API_BASE;
  if (envBase && typeof envBase === 'string' && envBase.trim() !== '') {
    return envBase.replace(/\/+$/, '');
  }
  return 'http://localhost:8000';
};

export class ApiError extends Error {
  status: number;
  retryAfter?: number;
  data?: unknown;

  constructor(message: string, status: number, retryAfter?: number, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.retryAfter = retryAfter;
    this.data = data;
  }
}

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const baseUrl = getApiBase();
  const url = `${baseUrl}/api${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

  const defaultHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  };

  const config: RequestInit = {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options?.headers,
    },
  };

  const response = await fetch(url, config);

  if (!response.ok) {
    let errorMessage = `API request failed with status ${response.status} ${response.statusText}`;
    let errorData: unknown = null;
    try {
      errorData = await response.json();
      const parsed = errorData as { message?: string; detail?: string | unknown };
      if (parsed.message) {
        errorMessage = parsed.message;
      } else if (parsed.detail) {
        errorMessage = typeof parsed.detail === 'string' ? parsed.detail : JSON.stringify(parsed.detail);
      }
    } catch {
      // Ignore JSON parse errors for non-JSON error responses
    }

    const retryAfterHeader = response.headers.get('Retry-After');
    const retryAfter = retryAfterHeader ? parseInt(retryAfterHeader, 10) : undefined;
    if (response.status === 429) {
      const waitMsg = retryAfter ? ` Please wait ${retryAfter} seconds before trying again.` : '';
      errorMessage = `Rate limit exceeded.${waitMsg}`;
    }

    throw new ApiError(errorMessage, response.status, retryAfter, errorData);
  }

  return (await response.json()) as T;
}

export async function getHealth(): Promise<HealthResponse> {
  const baseUrl = getApiBase();
  const response = await fetch(`${baseUrl}/health`, {
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`);
  }
  return (await response.json()) as HealthResponse;
}

export async function getState(lat: number, lng: number, language?: string): Promise<StateResponse> {
  const params = new URLSearchParams({
    lat: String(lat),
    lng: String(lng),
  });
  if (language) {
    params.append('lang', language);
  }
  return request<StateResponse>(`/state?${params.toString()}`, {
    method: 'GET',
  });
}

export async function getTemplates(language: string): Promise<TemplatesResponse> {
  return request<TemplatesResponse>(`/templates/${encodeURIComponent(language)}`, {
    method: 'GET',
  });
}

export async function createCheckIn(payload: CheckInRequest): Promise<CheckInResponse> {
  return request<CheckInResponse>('/checkin', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function createReport(payload: ReportRequest): Promise<ReportResponse> {
  return request<ReportResponse>('/reports', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getCells(bbox?: string): Promise<CellFeatureCollection> {
  const query = bbox ? `?bbox=${encodeURIComponent(bbox)}` : '';
  return request<CellFeatureCollection>(`/cells${query}`, {
    method: 'GET',
  });
}

export async function getShelters(lat?: number, lng?: number, openOnly: boolean = true): Promise<ShelterListResponse> {
  const params = new URLSearchParams();
  if (lat !== undefined) params.append('lat', String(lat));
  if (lng !== undefined) params.append('lng', String(lng));
  params.append('open_only', String(openOnly));
  const queryString = params.toString();
  return request<ShelterListResponse>(`/shelters${queryString ? `?${queryString}` : ''}`, {
    method: 'GET',
  });
}
