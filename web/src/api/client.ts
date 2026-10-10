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
    try {
      const errorData = (await response.json()) as { message?: string; detail?: string | unknown };
      if (errorData.message) {
        errorMessage = errorData.message;
      } else if (errorData.detail) {
        errorMessage = typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail);
      }
    } catch {
      // Ignore JSON parse errors for non-JSON error responses
    }
    throw new Error(errorMessage);
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

export async function getCells(): Promise<CellFeatureCollection> {
  return request<CellFeatureCollection>('/cells', {
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
