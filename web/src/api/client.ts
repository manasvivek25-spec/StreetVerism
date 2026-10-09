import type {
  CheckInRequest,
  CheckInResponse,
  ReportRequest,
  ReportResponse,
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
      const errorData = (await response.json()) as { message?: string; detail?: string };
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

export async function getState(language?: string, lat?: number, lng?: number): Promise<StateResponse> {
  const params = new URLSearchParams();
  if (language) params.append('lang', language);
  if (lat !== undefined) params.append('lat', String(lat));
  if (lng !== undefined) params.append('lng', String(lng));
  const queryString = params.toString();
  const query = queryString ? `?${queryString}` : '';
  return request<StateResponse>(`/state${query}`, {
    method: 'GET',
  });
}

export async function getTemplates(language?: string): Promise<TemplatesResponse> {
  const endpoint = language ? `/templates/${encodeURIComponent(language)}` : '/templates';
  return request<TemplatesResponse>(endpoint, {
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
  return request<ReportResponse>('/report', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
