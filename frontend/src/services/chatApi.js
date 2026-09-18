/** @file Fetch and incrementally decode the backend's SSE chat protocol. */

import { API_URL, CONVERSATIONS_URL } from '../config.js';
import { createId } from '../utils/createId.js';

const CLIENT_ID_KEY = 'edgemind.clientId.v1';
let clientId;

/** A random browser identifier keeps anonymous histories separated. */
function getClientId() {
  if (clientId) return clientId;
  try {
    const stored = window.localStorage.getItem(CLIENT_ID_KEY);
    if (stored && /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(stored)) {
      clientId = stored;
      return clientId;
    }
    clientId = createId();
    window.localStorage.setItem(CLIENT_ID_KEY, clientId);
  } catch {
    clientId = createId();
  }
  return clientId;
}

async function checkResponse(response) {
  if (response.ok) return response;
  const body = await response.json().catch(() => null);
  throw new Error(typeof body?.detail === 'string'
    ? body.detail
    : `伺服器回應錯誤 (${response.status})`);
}

export async function listConversations({ signal } = {}) {
  const response = await fetch(CONVERSATIONS_URL, {
    headers: { 'X-Client-ID': getClientId() }, signal,
  });
  return (await checkResponse(response)).json();
}

export async function getConversation(id, { signal } = {}) {
  const response = await fetch(`${CONVERSATIONS_URL}/${encodeURIComponent(id)}`, {
    headers: { 'X-Client-ID': getClientId() }, signal,
  });
  return (await checkResponse(response)).json();
}

export async function createConversation(title, { signal } = {}) {
  const response = await fetch(CONVERSATIONS_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Client-ID': getClientId() },
    body: JSON.stringify({ title }), signal,
  });
  return (await checkResponse(response)).json();
}

/** Convert one SSE block into its JSON data payload. */
function parseEvent(rawEvent) {
  const dataText = rawEvent
    .split('\n')
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart())
    .join('\n');
  return dataText ? JSON.parse(dataText) : null;
}

/**
 * Stream one Agent request without waiting for the complete response body.
 * @param {string} message
 * @param {{signal: AbortSignal, onEvent: (event: object) => void, inferenceModel: string, conversationId: string}} options
 */
export async function streamChat(message, { signal, onEvent, inferenceModel, conversationId }) {
  const response = await fetch(API_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Client-ID': getClientId() },
    body: JSON.stringify({
      message,
      inference_model: inferenceModel,
      conversation_id: conversationId,
    }),
    signal,
  });

  await checkResponse(response);
  if (!response.body) throw new Error('伺服器未提供串流回應');

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (value) {
        // Normalize line endings per chunk so the accumulated buffer is not
        // repeatedly copied as a response grows.
        buffer += decoder.decode(value, { stream: true }).replaceAll('\r\n', '\n');
      }
      if (done) buffer += decoder.decode();
      const events = buffer.split('\n\n');
      buffer = events.pop() || '';

      for (const rawEvent of events) {
        const event = parseEvent(rawEvent);
        if (event) onEvent(event);
      }
      if (done) break;
    }

    const finalEvent = parseEvent(buffer);
    if (finalEvent) onEvent(finalEvent);
  } finally {
    reader.releaseLock();
  }
}
