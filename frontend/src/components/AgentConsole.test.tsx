import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { createFakeApi } from "../test/fakeApi";
import { AgentConsole } from "./AgentConsole";

describe("Agent 控制台", () => {
  it("加载健康状态、工具和会话", async () => {
    const api = createFakeApi({
      sessions: {
        alice: [
          {
            session_id: "alice-history-1",
            user_id: "alice",
            created_at: "2026-08-12T00:00:00.000Z",
          },
        ],
      },
    });

    render(<AgentConsole api={api} apiBaseUrl="/api" defaultUserId="alice" />);

    expect(await screen.findByText("Agent 控制台")).toBeInTheDocument();
    expect(await screen.findByText("后端正常")).toBeInTheDocument();
    expect(await screen.findByText("calculator")).toBeInTheDocument();
    expect(await screen.findByText("当前会话 alice-hi")).toBeInTheDocument();
    expect(api.calls.listSessions).toEqual(["alice"]);
  });

  it("创建会话后自动选中新会话", async () => {
    const user = userEvent.setup();
    const api = createFakeApi();

    render(<AgentConsole api={api} apiBaseUrl="/api" defaultUserId="alice" />);
    await user.click(await screen.findByRole("button", { name: "新建会话" }));

    expect(await screen.findByText("当前会话 alice-se")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "发送" })).toBeDisabled();
  });

  it("发送消息后展示工具调用、工具结果和流式回答", async () => {
    const user = userEvent.setup();
    const api = createFakeApi();

    render(<AgentConsole api={api} apiBaseUrl="/api" defaultUserId="alice" />);
    await user.click(await screen.findByRole("button", { name: "新建会话" }));
    await user.type(screen.getByLabelText("聊天输入"), "请计算 19 * 23 并解释结果");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("调用工具：calculator")).toBeInTheDocument();
    expect(await screen.findByText(/"result": 437/)).toBeInTheDocument();
    expect(await screen.findByText(/19 × 23 = 437/)).toBeInTheDocument();
  });

  it("切换用户后不展示原用户会话", async () => {
    const user = userEvent.setup();
    const api = createFakeApi();

    render(<AgentConsole api={api} apiBaseUrl="/api" defaultUserId="alice" />);
    await user.click(await screen.findByRole("button", { name: "新建会话" }));
    await user.clear(screen.getByLabelText("用户 ID"));
    await user.type(screen.getByLabelText("用户 ID"), "bob");

    await waitFor(() => {
      expect(screen.getByText("暂无会话")).toBeInTheDocument();
    });
  });

  it("忽略晚返回的旧用户会话列表", async () => {
    const user = userEvent.setup();
    const api = createFakeApi({
      sessions: {
        alice: [
          {
            session_id: "alice-history-1",
            user_id: "alice",
            created_at: "2026-08-12T00:00:00.000Z",
          },
        ],
      },
    });
    const originalListSessions = api.listSessions.bind(api);
    let releaseAliceRequest: (() => void) | null = null;
    api.listSessions = async (nextUserId) => {
      if (nextUserId === "alice") {
        await new Promise<void>((resolve) => {
          releaseAliceRequest = resolve;
        });
      }
      return originalListSessions(nextUserId);
    };

    render(<AgentConsole api={api} apiBaseUrl="/api" defaultUserId="alice" />);
    await user.clear(screen.getByLabelText("用户 ID"));
    await user.type(screen.getByLabelText("用户 ID"), "bob");

    await waitFor(() => {
      expect(screen.getByText("暂无会话")).toBeInTheDocument();
    });
    await act(async () => {
      releaseAliceRequest?.();
    });

    expect(screen.getByText("暂无会话")).toBeInTheDocument();
    expect(screen.queryByText("当前会话 alice-hi")).not.toBeInTheDocument();
  });
});
