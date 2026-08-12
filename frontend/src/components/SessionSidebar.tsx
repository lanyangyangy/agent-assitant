import { Plus, Trash2 } from "lucide-react";

import type { SessionRecord } from "../api/types";

interface SessionSidebarProps {
  sessions: SessionRecord[];
  selectedSessionId: string | null;
  isLoading: boolean;
  onCreateSession: () => void;
  onSelectSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string) => void;
}

export function SessionSidebar({
  sessions,
  selectedSessionId,
  isLoading,
  onCreateSession,
  onSelectSession,
  onDeleteSession,
}: SessionSidebarProps) {
  return (
    <aside className="session-sidebar">
      <div className="panel-heading">
        <div>
          <h2>会话</h2>
          <p>{isLoading ? "正在加载会话" : `共 ${sessions.length} 个会话`}</p>
        </div>
        <button type="button" className="primary-button" onClick={onCreateSession}>
          <Plus size={16} />
          <span>新建会话</span>
        </button>
      </div>

      {sessions.length === 0 ? (
        <div className="empty-state">暂无会话</div>
      ) : (
        <div className="session-list">
          {sessions.map((session) => (
            <div
              key={session.session_id}
              className={session.session_id === selectedSessionId ? "session-row selected" : "session-row"}
            >
              <button type="button" onClick={() => onSelectSession(session.session_id)}>
                <span>当前会话</span>
                <strong>{shortSessionId(session.session_id)}</strong>
              </button>
              <button
                type="button"
                className="icon-only danger"
                aria-label={`删除会话 ${shortSessionId(session.session_id)}`}
                onClick={() => onDeleteSession(session.session_id)}
              >
                <Trash2 size={15} />
              </button>
            </div>
          ))}
        </div>
      )}
    </aside>
  );
}

function shortSessionId(sessionId: string): string {
  return sessionId.slice(0, 8);
}
