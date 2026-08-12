import { Activity } from "lucide-react";

import type { TimelineEvent } from "../state/types";
import { ToolCatalog } from "./ToolCatalog";
import type { ToolSchema } from "../api/types";

interface EventPanelProps {
  events: TimelineEvent[];
  tools: ToolSchema[];
}

export function EventPanel({ events, tools }: EventPanelProps) {
  return (
    <aside className="event-panel">
      <div className="panel-heading">
        <div>
          <h2>工具事件</h2>
          <p>当前请求时间线</p>
        </div>
        <Activity size={18} />
      </div>

      <div className="event-list">
        {events.length === 0 ? (
          <div className="empty-state">还没有工具事件</div>
        ) : (
          events.map((event) => (
            <article key={event.id} className={`event-item event-${eventKindClass(event.kind)}`}>
              <h3>{event.title}</h3>
              <pre>{event.summary}</pre>
            </article>
          ))
        )}
      </div>

      <ToolCatalog tools={tools} />
    </aside>
  );
}

function eventKindClass(kind: string): string {
  if (kind === "tool_call") return "tool-call";
  if (kind === "tool_result") return "tool-result";
  if (kind === "error") return "error";
  if (kind === "message_start") return "start";
  return "info";
}
