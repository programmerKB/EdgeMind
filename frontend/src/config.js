/** @file Browser-visible API configuration and artifact URL resolution. */

// A relative default keeps chat and images same-origin; Vite proxies /api in
// development while a production reverse proxy can expose the same contract.
export const API_URL =
  import.meta.env.VITE_API_URL || '/api/chat_utf8';

/** Keep conversation requests on the same API origin and path prefix as chat. */
export const CONVERSATIONS_URL = new URL(
  'conversations',
  new URL(API_URL, window.location.href),
).toString();

/** Resolve a backend-relative artifact against the configured API origin. */
export function resolveApiUrl(path) {
  const apiEndpoint = new URL(API_URL, window.location.href);
  return new URL(path, apiEndpoint.origin).toString();
}
