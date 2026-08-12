import { RefreshCw } from "lucide-react";

interface StatusBarProps {
  apiBaseUrl: string;
  userId: string;
  healthLabel: string;
  modelLabel: string;
  searchLabel: string;
  sqliteLabel: string;
  onUserIdChange: (value: string) => void;
  onRefresh: () => void;
}

export function StatusBar({
  apiBaseUrl,
  userId,
  healthLabel,
  modelLabel,
  searchLabel,
  sqliteLabel,
  onUserIdChange,
  onRefresh,
}: StatusBarProps) {
  return (
    <header className="status-bar">
      <div className="status-brand">
        <strong>Agent 控制台</strong>
        <span>{apiBaseUrl}</span>
      </div>
      <div className="status-chips">
        <span>{healthLabel}</span>
        <span>{modelLabel}</span>
        <span>{sqliteLabel}</span>
        <span>{searchLabel}</span>
      </div>
      <label className="status-user">
        <span>用户 ID</span>
        <input
          aria-label="用户 ID"
          value={userId}
          onChange={(event) => onUserIdChange(event.target.value)}
        />
      </label>
      <button type="button" className="icon-button" onClick={onRefresh} aria-label="刷新状态">
        <RefreshCw size={16} />
        <span>刷新</span>
      </button>
    </header>
  );
}
