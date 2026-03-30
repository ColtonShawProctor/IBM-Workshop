import axios from 'axios';
import type { AuthResponse, User, Preferences, BidPeriod, Sequence, Bid, BidProperty, BidPropertyInput, Bookmark, FilterPreset, FilterSet, LayerSummary, PaginatedResponse, ProjectedScheduleResponse } from '../types/api';
import { isOnline, cacheData, getCachedData, queueMutation } from './offline';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Token refresh state — prevents concurrent refresh attempts
let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

function onTokenRefreshed(token: string) {
  refreshSubscribers.forEach(cb => cb(token));
  refreshSubscribers = [];
}

function addRefreshSubscriber(cb: (token: string) => void) {
  refreshSubscribers.push(cb);
}

// Cache successful GET responses for offline use
api.interceptors.response.use(
  (response) => {
    if (response.config.method === 'get' && response.config.url) {
      const cacheKey = response.config.url + (response.config.params ? JSON.stringify(response.config.params) : '');
      cacheData(cacheKey, response.data);
    }
    return response;
  },
  async (error) => {
    const originalRequest = error.config;

    // Handle 401 responses — attempt token refresh before redirecting
    if (error.response?.status === 401 && !originalRequest._retry) {
      // Don't retry refresh requests themselves
      if (originalRequest.url?.includes('/auth/refresh') || originalRequest.url?.includes('/auth/login')) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
        return Promise.reject(error);
      }

      const refreshToken = localStorage.getItem('refresh_token');
      if (!refreshToken) {
        localStorage.removeItem('access_token');
        window.location.href = '/login';
        return Promise.reject(error);
      }

      if (isRefreshing) {
        // Another refresh is in progress — queue this request
        return new Promise((resolve) => {
          addRefreshSubscriber((newToken: string) => {
            originalRequest.headers.Authorization = `Bearer ${newToken}`;
            originalRequest._retry = true;
            resolve(api(originalRequest));
          });
        });
      }

      isRefreshing = true;
      originalRequest._retry = true;

      try {
        const res = await axios.post('/api/auth/refresh', { refresh_token: refreshToken });
        const { access_token, refresh_token: newRefresh } = res.data;
        localStorage.setItem('access_token', access_token);
        if (newRefresh) localStorage.setItem('refresh_token', newRefresh);
        api.defaults.headers.common.Authorization = `Bearer ${access_token}`;
        onTokenRefreshed(access_token);
        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return api(originalRequest);
      } catch {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
        return Promise.reject(error);
      } finally {
        isRefreshing = false;
      }
    }

    // When offline and a GET fails, try to serve from cache
    if (!isOnline() && error.config?.method === 'get' && error.config?.url) {
      const cacheKey = error.config.url + (error.config.params ? JSON.stringify(error.config.params) : '');
      const cached = getCachedData(cacheKey);
      if (cached) {
        return { data: cached, status: 200, statusText: 'OK (cached)', headers: {}, config: error.config };
      }
    }
    // When offline and a mutation fails, queue it for replay
    if (!isOnline() && error.config && ['post', 'put', 'delete'].includes(error.config.method)) {
      const method = error.config.method.toUpperCase() as 'POST' | 'PUT' | 'DELETE';
      queueMutation(method, error.config.url || '', error.config.data ? JSON.parse(error.config.data) : undefined);
    }
    return Promise.reject(error);
  }
);

// ── Auth ────────────────────────────────────────────────────────────────

export async function register(data: {
  email: string;
  password: string;
  profile: {
    display_name: string;
    base_city: string;
    commute_from?: string;
    seniority_percentage?: number;
    seniority_number?: number;
    total_base_fas?: number;
    position_min: number;
    position_max: number;
    language_qualifications: string[];
  };
}): Promise<AuthResponse> {
  const res = await api.post('/auth/register', data);
  return res.data;
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const res = await api.post('/auth/login', { email, password });
  return res.data;
}

// ── Users ───────────────────────────────────────────────────────────────

export async function getMe(): Promise<User> {
  const res = await api.get('/users/me');
  return res.data;
}

export async function updateMe(data: Partial<{ profile: Partial<User['profile']>; default_preferences: Partial<Preferences> }>): Promise<User> {
  const res = await api.put('/users/me', data);
  return res.data;
}

export async function updatePreferences(prefs: Partial<Preferences>): Promise<Preferences> {
  const res = await api.put('/users/me/preferences', prefs);
  return res.data;
}

// ── Bid Periods ─────────────────────────────────────────────────────────

export async function createBidPeriod(formData: FormData): Promise<BidPeriod> {
  const res = await api.post('/bid-periods', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}

export async function listBidPeriods(): Promise<PaginatedResponse<BidPeriod>> {
  const res = await api.get('/bid-periods');
  return res.data;
}

export async function getBidPeriod(id: string): Promise<BidPeriod> {
  const res = await api.get(`/bid-periods/${id}`);
  return res.data;
}

export async function deleteBidPeriod(id: string): Promise<void> {
  await api.delete(`/bid-periods/${id}`);
}

export async function updateTargetCredit(
  bidPeriodId: string,
  minMinutes: number,
  maxMinutes: number,
): Promise<BidPeriod> {
  const res = await api.put(`/bid-periods/${bidPeriodId}/target-credit`, {
    target_credit_min_minutes: minMinutes,
    target_credit_max_minutes: maxMinutes,
  });
  return res.data;
}

// ── Sequences ───────────────────────────────────────────────────────────

export async function listSequences(
  bidPeriodId: string,
  params?: Record<string, string | number | boolean>
): Promise<PaginatedResponse<Sequence>> {
  const res = await api.get(`/bid-periods/${bidPeriodId}/sequences`, { params });
  return res.data;
}

export async function getSequence(bidPeriodId: string, sequenceId: string): Promise<Sequence> {
  const res = await api.get(`/bid-periods/${bidPeriodId}/sequences/${sequenceId}`);
  return res.data;
}

export async function compareSequences(bidPeriodId: string, sequenceIds: string[]): Promise<{ sequences: Sequence[]; differences: { attribute: string; values: Record<string, unknown> }[] }> {
  const res = await api.post(`/bid-periods/${bidPeriodId}/sequences/compare`, { sequence_ids: sequenceIds });
  return res.data;
}

// ── Bids ────────────────────────────────────────────────────────────────

export async function createBid(bidPeriodId: string, name: string, entries?: { sequence_id: string }[]): Promise<Bid> {
  const res = await api.post(`/bid-periods/${bidPeriodId}/bids`, { name, entries: entries ?? [] });
  return res.data;
}

export async function listBids(bidPeriodId: string): Promise<PaginatedResponse<Bid>> {
  const res = await api.get(`/bid-periods/${bidPeriodId}/bids`);
  return res.data;
}

export async function getBid(bidPeriodId: string, bidId: string): Promise<Bid> {
  const res = await api.get(`/bid-periods/${bidPeriodId}/bids/${bidId}`);
  return res.data;
}

export async function updateBid(bidPeriodId: string, bidId: string, data: Partial<Bid>): Promise<Bid> {
  const res = await api.put(`/bid-periods/${bidPeriodId}/bids/${bidId}`, data);
  return res.data;
}

export async function optimizeBid(bidPeriodId: string, bidId: string, preferences?: Partial<Preferences>): Promise<Bid> {
  const res = await api.post(`/bid-periods/${bidPeriodId}/bids/${bidId}/optimize`, preferences ? { preferences } : {});
  return res.data;
}

export async function exportBid(bidPeriodId: string, bidId: string, format: 'txt' | 'csv' = 'txt'): Promise<Blob> {
  const res = await api.post(`/bid-periods/${bidPeriodId}/bids/${bidId}/export`, { format }, {
    responseType: 'blob',
  });
  return res.data;
}

// ── PBS Properties ─────────────────────────────────────────────────────

export async function listBidProperties(bidPeriodId: string, bidId: string): Promise<BidProperty[]> {
  const res = await api.get(`/bid-periods/${bidPeriodId}/bids/${bidId}/properties`);
  return res.data;
}

export async function addBidProperty(bidPeriodId: string, bidId: string, property: BidPropertyInput): Promise<BidProperty> {
  const res = await api.post(`/bid-periods/${bidPeriodId}/bids/${bidId}/properties`, property);
  return res.data;
}

export async function updateBidProperty(
  bidPeriodId: string,
  bidId: string,
  propertyId: string,
  updates: BidPropertyInput,
): Promise<BidProperty> {
  const res = await api.put(`/bid-periods/${bidPeriodId}/bids/${bidId}/properties/${propertyId}`, updates);
  return res.data;
}

export async function deleteBidProperty(bidPeriodId: string, bidId: string, propertyId: string): Promise<void> {
  await api.delete(`/bid-periods/${bidPeriodId}/bids/${bidId}/properties/${propertyId}`);
}

export async function getLayerSummaries(bidPeriodId: string, bidId: string): Promise<LayerSummary[]> {
  const res = await api.get(`/bid-periods/${bidPeriodId}/bids/${bidId}/layers`);
  return res.data;
}

export async function getProjectedSchedule(bidPeriodId: string, bidId: string): Promise<ProjectedScheduleResponse> {
  const res = await api.get(`/bid-periods/${bidPeriodId}/bids/${bidId}/projected`);
  return res.data;
}

// ── Bookmarks ───────────────────────────────────────────────────────────

export async function createBookmark(bidPeriodId: string, sequenceId: string): Promise<Bookmark> {
  const res = await api.post(`/bid-periods/${bidPeriodId}/bookmarks`, { sequence_id: sequenceId });
  return res.data;
}

export async function listBookmarks(bidPeriodId: string): Promise<PaginatedResponse<Bookmark>> {
  const res = await api.get(`/bid-periods/${bidPeriodId}/bookmarks`);
  return res.data;
}

export async function deleteBookmark(bidPeriodId: string, bookmarkId: string): Promise<void> {
  await api.delete(`/bid-periods/${bidPeriodId}/bookmarks/${bookmarkId}`);
}

// ── Filter Presets ──────────────────────────────────────────────────────

export async function createFilterPreset(bidPeriodId: string, name: string, filters: FilterSet): Promise<FilterPreset> {
  const res = await api.post(`/bid-periods/${bidPeriodId}/filter-presets`, { name, filters });
  return res.data;
}

export async function listFilterPresets(bidPeriodId: string): Promise<PaginatedResponse<FilterPreset>> {
  const res = await api.get(`/bid-periods/${bidPeriodId}/filter-presets`);
  return res.data;
}

export async function deleteFilterPreset(bidPeriodId: string, presetId: string): Promise<void> {
  await api.delete(`/bid-periods/${bidPeriodId}/filter-presets/${presetId}`);
}

export default api;
