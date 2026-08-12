import { useCallback, useEffect, useRef, useState } from "react";

import type { BackendClient } from "../api/backendClient";
import type { HealthResponse, SessionRecord, ToolSchema } from "../api/types";
import { chatReducer, createInitialChatState } from "../state/chatReducer";
import type { ChatAction, ChatState } from "../state/types";
import { ChatPanel } from "./ChatPanel";
import { ErrorBanner } from "./ErrorBanner";
import { EventPanel } from "./EventPanel";
import { SessionSidebar } from "./SessionSidebar";
import { StatusBar } from "./StatusBar";

interface AgentConsoleProps {
  api: BackendClient;
  apiBaseUrl: string;
  defaultUserId: string;
}

export function AgentConsole({ api, apiBaseUrl, defaultUserId }: AgentConsoleProps) {
  const [userId, setUserId] = useState(defaultUserId);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [tools, setTools] = useState<ToolSchema[]>([]);
  const [sessions, setSessions] = useState<SessionRecord[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [inputValue, setInputValue] = useState("");
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [chatStatesBySession, setChatStatesBySession] = useState<Record<string, ChatState>>({});
  const sessionsRef = useRef<SessionRecord[]>([]);
  const sessionRequestIdRef = useRef(0);
  const activeUserIdRef = useRef(defaultUserId.trim());
  const historyRequestVersionsRef = useRef<Record<string, number>>({});
  const selectedChatState = selectedSessionId ? chatStatesBySession[selectedSessionId] : undefined;
  const chatState = selectedSessionId
    ? (selectedChatState ?? createInitialChatState())
    : createInitialChatState();

  const dispatchToSession = useCallback((sessionId: string, action: ChatAction) => {
    setChatStatesBySession((current) => ({
      ...current,
      [sessionId]: chatReducer(current[sessionId] ?? createInitialChatState(), action),
    }));
  }, []);

  const nextHistoryRequestVersion = useCallback((nextUserId: string, sessionId: string) => {
    const requestKey = createHistoryRequestKey(nextUserId, sessionId);
    const nextVersion = (historyRequestVersionsRef.current[requestKey] ?? 0) + 1;
    historyRequestVersionsRef.current[requestKey] = nextVersion;
    return { requestKey, requestVersion: nextVersion };
  }, []);

  const invalidateHistoryRequest = useCallback((nextUserId: string, sessionId: string) => {
    const requestKey = createHistoryRequestKey(nextUserId, sessionId);
    historyRequestVersionsRef.current[requestKey] = (historyRequestVersionsRef.current[requestKey] ?? 0) + 1;
  }, []);

  const refreshStatus = useCallback(async () => {
    try {
      const [nextHealth, nextTools] = await Promise.all([api.getHealth(), api.listTools()]);
      setHealth(nextHealth);
      setTools(nextTools);
      setLocalError(null);
    } catch (error) {
      setLocalError(error instanceof Error ? error.message : "无法连接后端，请确认服务已启动。");
    }
  }, [api]);

  const loadSessions = useCallback(
    async (nextUserId: string) => {
      const requestId = ++sessionRequestIdRef.current;
      const trimmedUserId = nextUserId.trim();
      if (!trimmedUserId) {
        sessionsRef.current = [];
        setSessions([]);
        setSelectedSessionId(null);
        setChatStatesBySession({});
        historyRequestVersionsRef.current = {};
        setLocalError("请输入用户 ID。");
        return;
      }

      setIsLoadingSessions(true);
      try {
        const result = await api.listSessions(trimmedUserId);
        if (requestId !== sessionRequestIdRef.current) {
          return;
        }
        sessionsRef.current = result.sessions;
        setSessions(result.sessions);
        setSelectedSessionId(result.sessions[0]?.session_id ?? null);
        setChatStatesBySession({});
        historyRequestVersionsRef.current = {};
        setLocalError(null);
      } catch (error) {
        if (requestId !== sessionRequestIdRef.current) {
          return;
        }
        setLocalError(error instanceof Error ? error.message : "加载会话失败。");
      } finally {
        if (requestId === sessionRequestIdRef.current) {
          setIsLoadingSessions(false);
        }
      }
    },
    [api],
  );

  useEffect(() => {
    void refreshStatus();
  }, [refreshStatus]);

  useEffect(() => {
    void loadSessions(userId);
  }, [loadSessions, userId]);

  useEffect(() => {
    const trimmedUserId = userId.trim();
    if (!trimmedUserId || !selectedSessionId) {
      return;
    }
    if (selectedChatState !== undefined) {
      return;
    }

    const { requestKey, requestVersion } = nextHistoryRequestVersion(trimmedUserId, selectedSessionId);
    api
      .listMessages(trimmedUserId, selectedSessionId)
      .then((result) => {
        if (
          activeUserIdRef.current === trimmedUserId &&
          historyRequestVersionsRef.current[requestKey] === requestVersion
        ) {
          dispatchToSession(selectedSessionId, { type: "load_messages", messages: result.messages });
          setLocalError(null);
        }
      })
      .catch((error) => {
        if (
          activeUserIdRef.current === trimmedUserId &&
          historyRequestVersionsRef.current[requestKey] === requestVersion
        ) {
          setLocalError(error instanceof Error ? error.message : "加载聊天记录失败。");
        }
      });
  }, [api, dispatchToSession, nextHistoryRequestVersion, selectedChatState, selectedSessionId, userId]);

  function handleUserIdChange(nextUserId: string) {
    activeUserIdRef.current = nextUserId.trim();
    sessionRequestIdRef.current += 1;
    historyRequestVersionsRef.current = {};
    setUserId(nextUserId);
    sessionsRef.current = [];
    setSessions([]);
    setSelectedSessionId(null);
    setChatStatesBySession({});
    setInputValue("");
    setLocalError(null);
  }

  async function handleCreateSession() {
    const trimmedUserId = userId.trim();
    if (!trimmedUserId) {
      setLocalError("请输入用户 ID。");
      return;
    }

    sessionRequestIdRef.current += 1;
    try {
      const session = await api.createSession(trimmedUserId);
      if (activeUserIdRef.current !== trimmedUserId) {
        return;
      }
      setSessions((current) => {
        const nextSessions = [...current, session];
        sessionsRef.current = nextSessions;
        return nextSessions;
      });
      setSelectedSessionId(session.session_id);
      dispatchToSession(session.session_id, { type: "reset_for_session" });
      setLocalError(null);
    } catch (error) {
      if (activeUserIdRef.current !== trimmedUserId) {
        return;
      }
      setLocalError(error instanceof Error ? error.message : "创建会话失败。");
    }
  }

  async function handleDeleteSession(sessionId: string) {
    sessionRequestIdRef.current += 1;
    const trimmedUserId = userId.trim();
    try {
      await api.deleteSession(trimmedUserId, sessionId);
      if (activeUserIdRef.current !== trimmedUserId) {
        return;
      }
      invalidateHistoryRequest(trimmedUserId, sessionId);
      const nextSessions = sessionsRef.current.filter((session) => session.session_id !== sessionId);
      sessionsRef.current = nextSessions;
      setSessions(nextSessions);
      setSelectedSessionId((currentSelectedSessionId) =>
        currentSelectedSessionId === sessionId ? (nextSessions[0]?.session_id ?? null) : currentSelectedSessionId,
      );
      setChatStatesBySession((current) => {
        const { [sessionId]: _deletedSession, ...remaining } = current;
        return remaining;
      });
      setLocalError(null);
    } catch {
      if (activeUserIdRef.current !== trimmedUserId) {
        return;
      }
      setLocalError("删除会话失败，请刷新后重试。");
    }
  }

  function handleSelectSession(sessionId: string) {
    setSelectedSessionId(sessionId);
  }

  async function handleSubmitMessage() {
    const trimmedMessage = inputValue.trim();
    const trimmedUserId = userId.trim();
    if (!trimmedUserId) {
      setLocalError("请输入用户 ID。");
      return;
    }
    if (!selectedSessionId) {
      setLocalError("请先创建或选择会话。");
      return;
    }
    if (!trimmedMessage) {
      return;
    }

    const requestSessionId = selectedSessionId;
    invalidateHistoryRequest(trimmedUserId, requestSessionId);
    dispatchToSession(requestSessionId, { type: "user_message", content: trimmedMessage });
    dispatchToSession(requestSessionId, { type: "start_stream" });
    setInputValue("");
    setLocalError(null);

    try {
      for await (const event of api.streamChat(trimmedUserId, {
        session_id: requestSessionId,
        message: trimmedMessage,
      })) {
        dispatchToSession(requestSessionId, { type: "stream_event", event });
      }
    } catch (error) {
      dispatchToSession(requestSessionId, {
        type: "stream_event",
        event: {
          event: "error",
          data: { message: error instanceof Error ? error.message : "聊天流中断，请重试。" },
        },
      });
    }
  }

  return (
    <main className="console-root">
      <StatusBar
        apiBaseUrl={apiBaseUrl}
        userId={userId}
        healthLabel={health?.status === "ok" ? "后端正常" : "后端未知"}
        modelLabel={health?.model_configured ? "模型已配置" : "模型未配置"}
        sqliteLabel={health?.sqlite_available ? "SQLite 可用" : "SQLite 异常"}
        searchLabel={health?.search_available ? "搜索可用" : "搜索不可用"}
        onUserIdChange={handleUserIdChange}
        onRefresh={refreshStatus}
      />
      <ErrorBanner message={localError ?? chatState.error} />
      <div className="console-layout">
        <SessionSidebar
          sessions={sessions}
          selectedSessionId={selectedSessionId}
          isLoading={isLoadingSessions}
          onCreateSession={handleCreateSession}
          onSelectSession={handleSelectSession}
          onDeleteSession={handleDeleteSession}
        />
        <ChatPanel
          selectedSessionId={selectedSessionId}
          messages={chatState.messages}
          inputValue={inputValue}
          isStreaming={chatState.isStreaming}
          onInputChange={setInputValue}
          onSubmit={handleSubmitMessage}
        />
        <EventPanel events={chatState.events} tools={tools} />
      </div>
    </main>
  );
}

function createHistoryRequestKey(userId: string, sessionId: string): string {
  return `${userId}:${sessionId}`;
}
