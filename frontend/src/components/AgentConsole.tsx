import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import type { BackendClient } from "../api/backendClient";
import type { HealthResponse, SessionRecord, ToolSchema } from "../api/types";
import { chatReducer, createInitialChatState } from "../state/chatReducer";
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
  const [chatState, dispatch] = useReducer(chatReducer, undefined, createInitialChatState);
  const sessionRequestIdRef = useRef(0);

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
        setSessions([]);
        setSelectedSessionId(null);
        setLocalError("请输入用户 ID。");
        return;
      }

      setIsLoadingSessions(true);
      try {
        const result = await api.listSessions(trimmedUserId);
        if (requestId !== sessionRequestIdRef.current) {
          return;
        }
        setSessions(result.sessions);
        setSelectedSessionId(result.sessions[0]?.session_id ?? null);
        dispatch({ type: "reset_for_session" });
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

  async function handleCreateSession() {
    const trimmedUserId = userId.trim();
    if (!trimmedUserId) {
      setLocalError("请输入用户 ID。");
      return;
    }

    sessionRequestIdRef.current += 1;
    try {
      const session = await api.createSession(trimmedUserId);
      setSessions((current) => [...current, session]);
      setSelectedSessionId(session.session_id);
      dispatch({ type: "reset_for_session" });
      setLocalError(null);
    } catch (error) {
      setLocalError(error instanceof Error ? error.message : "创建会话失败。");
    }
  }

  async function handleDeleteSession(sessionId: string) {
    sessionRequestIdRef.current += 1;
    try {
      await api.deleteSession(userId.trim(), sessionId);
      setSessions((current) => {
        const nextSessions = current.filter((session) => session.session_id !== sessionId);
        if (selectedSessionId === sessionId) {
          setSelectedSessionId(nextSessions[0]?.session_id ?? null);
          dispatch({ type: "reset_for_session" });
        }
        return nextSessions;
      });
      setLocalError(null);
    } catch {
      setLocalError("删除会话失败，请刷新后重试。");
    }
  }

  function handleSelectSession(sessionId: string) {
    setSelectedSessionId(sessionId);
    dispatch({ type: "reset_for_session" });
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

    dispatch({ type: "user_message", content: trimmedMessage });
    dispatch({ type: "start_stream" });
    setInputValue("");
    setLocalError(null);

    try {
      for await (const event of api.streamChat(trimmedUserId, {
        session_id: selectedSessionId,
        message: trimmedMessage,
      })) {
        dispatch({ type: "stream_event", event });
      }
    } catch (error) {
      dispatch({
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
        onUserIdChange={setUserId}
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
