/** Own the active chat, saved history, and cancellable Agent stream. */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  createMessage,
  findLastUserMessage,
  normalizeAttachments,
  restoreMessage,
} from '../models/chatMessage.js';
import {
  createConversation,
  getConversation,
  listConversations,
  streamChat,
} from '../services/chatApi.js';
import { createId } from '../utils/createId.js';

function readableError(error) {
  return error.message === 'Failed to fetch'
    ? '目前無法連線至診斷服務，請確認後端已啟動。'
    : error.message;
}

function mergeConversations(previous, incoming) {
  const byId = new Map(previous.map((item) => [item.id, item]));
  for (const item of incoming) {
    const stored = byId.get(item.id);
    if (!stored || Date.parse(item.updated_at) >= Date.parse(stored.updated_at)) {
      byId.set(item.id, item);
    }
  }
  return [...byId.values()].sort(
    (a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at),
  );
}

export function useChat(inferenceModel = 'ridge_direct') {
  const [messages, setMessages] = useState([]);
  const [conversations, setConversations] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [historyReady, setHistoryReady] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const activeRequestRef = useRef(null);
  const currentConversationRef = useRef(null);
  const selectionVersionRef = useRef(0);
  const mountedRef = useRef(false);

  useEffect(() => {
    mountedRef.current = true;
    const version = ++selectionVersionRef.current;
    const controller = new AbortController();

    async function loadHistory() {
      try {
        const items = await listConversations({ signal: controller.signal });
        if (!mountedRef.current) return;
        if (version !== selectionVersionRef.current) {
          setConversations((previous) => mergeConversations(previous, items));
          return;
        }
        setConversations(items);
        setHistoryError('');
      } catch (error) {
        if (error.name !== 'AbortError' && mountedRef.current
          && version === selectionVersionRef.current) {
          setHistoryError('載入聊天紀錄失敗：' + readableError(error));
        }
      } finally {
        if (mountedRef.current && version === selectionVersionRef.current) {
          setHistoryReady(true);
        }
      }
    }

    loadHistory();
    return () => {
      mountedRef.current = false;
      controller.abort();
      activeRequestRef.current?.controller.abort();
      activeRequestRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!historyReady) return undefined;
    let cancelled = false;
    let refreshing = false;

    async function refreshHistory() {
      if (refreshing || !mountedRef.current) return;
      refreshing = true;
      const version = selectionVersionRef.current;
      try {
        const items = await listConversations();
        if (cancelled || !mountedRef.current) return;
        setConversations((previous) => mergeConversations(previous, items));
        setHistoryError('');
        const activeId = currentConversationRef.current;
        if (!activeId || activeRequestRef.current || version !== selectionVersionRef.current) {
          return;
        }
        const conversation = await getConversation(activeId);
        if (cancelled || !mountedRef.current || activeRequestRef.current
          || activeId !== currentConversationRef.current
          || version !== selectionVersionRef.current) return;
        const restored = conversation.messages.map(restoreMessage);
        setMessages((previous) => (
          previous.length === restored.length
          && previous.every((item, index) => (
            item.id === restored[index].id
            && item.content === restored[index].content
          ))
            ? previous : restored
        ));
        setHistoryError('');
      } catch (error) {
        if (!cancelled && mountedRef.current) {
          setHistoryError('更新聊天紀錄失敗：' + readableError(error));
        }
      } finally {
        refreshing = false;
      }
    }

    function onVisibilityChange() {
      if (document.visibilityState === 'visible') refreshHistory();
    }
    window.addEventListener('focus', refreshHistory);
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => {
      cancelled = true;
      window.removeEventListener('focus', refreshHistory);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [historyReady]);

  const lastUserMessage = useMemo(
    () => findLastUserMessage(messages),
    [messages],
  );

  const stopResponse = useCallback(() => {
    activeRequestRef.current?.controller.abort();
    activeRequestRef.current = null;
    setIsLoading(false);
  }, []);

  const newChat = useCallback(() => {
    stopResponse();
    selectionVersionRef.current += 1;
    currentConversationRef.current = null;
    setConversationId(null);
    setMessages([]);
    setInput('');
    setHistoryReady(true);
    setHistoryError('');
  }, [stopResponse]);

  const openChat = useCallback(async (id) => {
    if (id === currentConversationRef.current) return;
    stopResponse();
    const version = ++selectionVersionRef.current;
    setHistoryReady(false);
    setHistoryError('');
    try {
      const conversation = await getConversation(id);
      if (!mountedRef.current || version !== selectionVersionRef.current) return;
      currentConversationRef.current = id;
      setConversationId(id);
      setMessages(conversation.messages.map(restoreMessage));
      setInput('');
    } catch (error) {
      if (mountedRef.current && version === selectionVersionRef.current) {
        setHistoryError('載入聊天紀錄失敗：' + readableError(error));
      }
    } finally {
      if (mountedRef.current && version === selectionVersionRef.current) {
        setHistoryReady(true);
      }
    }
  }, [stopResponse]);

  const sendMessage = useCallback(async (overrideMessage) => {
    const userMessage = (
      typeof overrideMessage === 'string' ? overrideMessage : input
    ).trim();
    if (!userMessage || !historyReady || activeRequestRef.current) return;

    const requestId = createId();
    const controller = new AbortController();
    activeRequestRef.current = { requestId, controller };
    setIsLoading(true);
    let targetId = currentConversationRef.current;

    try {
      if (!targetId) {
        const created = await createConversation(userMessage, { signal: controller.signal });
        if (!mountedRef.current || activeRequestRef.current?.requestId !== requestId) return;
        targetId = created.id;
        currentConversationRef.current = targetId;
        setConversationId(targetId);
        setConversations((previous) => mergeConversations(previous, [created]));
      }

      setHistoryError('');
      setInput('');
      setMessages((previous) => [...previous, createMessage('user', userMessage)]);
      await streamChat(userMessage, {
        signal: controller.signal,
        inferenceModel,
        conversationId: targetId,
        onEvent: (event) => {
          if (!mountedRef.current || activeRequestRef.current?.requestId !== requestId) {
            return;
          }
          setMessages((previous) => [
            ...previous,
            createMessage(
              'agent', event.content, event.status,
              normalizeAttachments(event.attachments), event.token_usage,
            ),
          ]);
        },
      });
      if (mountedRef.current && activeRequestRef.current?.requestId === requestId) {
        const updatedAt = new Date().toISOString();
        setConversations((previous) => previous.map((item) => (
          item.id === targetId ? { ...item, updated_at: updatedAt } : item
        )).sort((a, b) => b.updated_at.localeCompare(a.updated_at)));
      }
    } catch (error) {
      if (error.name !== 'AbortError' && mountedRef.current
        && activeRequestRef.current?.requestId === requestId) {
        if (!targetId) {
          setHistoryError('無法建立聊天紀錄，訊息尚未送出：' + readableError(error));
        } else {
          setMessages((previous) => [
            ...previous,
            createMessage('agent', readableError(error), 'error'),
          ]);
        }
      }
    } finally {
      if (activeRequestRef.current?.requestId === requestId) {
        activeRequestRef.current = null;
        if (mountedRef.current) setIsLoading(false);
      }
    }
  }, [historyReady, inferenceModel, input]);

  const retryLastMessage = useCallback(() => {
    if (lastUserMessage && !activeRequestRef.current) {
      sendMessage(lastUserMessage);
    }
  }, [lastUserMessage, sendMessage]);

  return {
    messages,
    conversations,
    conversationId,
    input,
    isLoading,
    historyReady,
    historyError,
    hasMessages: messages.length > 0,
    setInput,
    sendMessage,
    stopResponse,
    newChat,
    openChat,
    retryLastMessage,
  };
}
