import { createClient, type SupabaseClient } from '@supabase/supabase-js';

export type Config = { auth_configured: boolean; supabase_url: string; supabase_anon_key: string; ai_available: boolean; voice_available: boolean; payment_provider: string };
export let auth: SupabaseClient | null = null;
export function configureAuth(config: Config) {
  if (config.auth_configured && !auth) auth = createClient(config.supabase_url, config.supabase_anon_key, { auth: { detectSessionInUrl: true, persistSession: true, autoRefreshToken: true } });
}
export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}
export async function api<T = any>(path: string, options: RequestInit = {}): Promise<T> {
  const session = auth ? (await auth.auth.getSession()).data.session : null;
  const headers = new Headers(options.headers);
  if (session) headers.set('Authorization', `Bearer ${session.access_token}`);
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  if (options.method === 'POST' && !headers.has('Idempotency-Key')) headers.set('Idempotency-Key', crypto.randomUUID());
  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const fields = error.field_errors?.map((e: any) => e.message).join(' ');
    throw new ApiError(fields || error.message || `Request failed (${response.status}).`, response.status);
  }
  return response.json();
}
export const post = <T = any>(path: string, body: unknown = {}) => api<T>(path, { method: 'POST', body: JSON.stringify(body) });
export async function downloadQuote(id: string) {
  const session = auth ? (await auth.auth.getSession()).data.session : null;
  const response = await fetch(`/api/quotes/${id}/download`, { headers: session ? { Authorization: `Bearer ${session.access_token}` } : {} });
  if (!response.ok) throw new Error('The PDF could not be downloaded. Please retry.');
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement('a'); link.href = url; link.download = `helm-quote-${id}.pdf`; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export const aed = (fils: number) => new Intl.NumberFormat('en-AE', { style: 'currency', currency: 'AED', maximumFractionDigits: 2 }).format(fils / 100);
