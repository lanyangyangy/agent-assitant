import { Send } from "lucide-react";
import type { FormEvent } from "react";

import type { ChatMessage } from "../state/types";

interface ChatPanelProps {
  selectedSessionId: string | null;
  messages: ChatMessage[];
  inputValue: string;
  isStreaming: boolean;
  onInputChange: (value: string) => void;
  onSubmit: () => void;
}

export function ChatPanel({
  selectedSessionId,
  messages,
  inputValue,
  isStreaming,
  onInputChange,
  onSubmit,
}: ChatPanelProps) {
  const canSend = Boolean(selectedSessionId && inputValue.trim() && !isStreaming);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (canSend) {
      onSubmit();
    }
  }

  return (
    <section className="chat-panel">
      <div className="panel-heading">
        <div>
          <h2>聊天流</h2>
          <p>{selectedSessionId ? `当前会话 ${selectedSessionId.slice(0, 8)}` : "请先创建或选择会话"}</p>
        </div>
        {isStreaming ? <span className="status-dot">正在生成</span> : <span>空闲</span>}
      </div>

      <div className="message-list" aria-live="polite">
        {messages.length === 0 ? (
          <div className="empty-state">发送一条消息，观察 Agent 如何调用工具并整合结果。</div>
        ) : (
          messages.map((message) => (
            <article key={message.id} className={`message-bubble ${message.role}`}>
              <span>{message.role === "user" ? "你" : "助手"}</span>
              <p>{message.content || "正在接收回答..."}</p>
            </article>
          ))
        )}
      </div>

      <form className="composer" onSubmit={handleSubmit}>
        <label className="sr-only" htmlFor="chat-input">
          聊天输入
        </label>
        <textarea
          id="chat-input"
          aria-label="聊天输入"
          value={inputValue}
          placeholder="请计算 19 * 23 并解释结果"
          onChange={(event) => onInputChange(event.target.value)}
          rows={3}
        />
        <button type="submit" className="primary-button" disabled={!canSend}>
          <Send size={16} />
          <span>发送</span>
        </button>
      </form>
    </section>
  );
}
