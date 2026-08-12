import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
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

  it("创建会话未返回时切换用户会忽略旧用户新会话", async () => {
    const user = userEvent.setup();
    const api = createFakeApi();
    const originalCreateSession = api.createSession.bind(api);
    let releaseCreate: (() => void) | null = null;
    api.createSession = async (nextUserId) => {
      await new Promise<void>((resolve) => {
        releaseCreate = resolve;
      });
      return originalCreateSession(nextUserId);
    };

    render(<AgentConsole api={api} apiBaseUrl="/api" defaultUserId="alice" />);

    await user.click(await screen.findByRole("button", { name: "新建会话" }));
    fireEvent.change(screen.getByLabelText("用户 ID"), { target: { value: "bob" } });
    await act(async () => {
      releaseCreate?.();
    });

    await waitFor(() => {
      expect(screen.getByText("暂无会话")).toBeInTheDocument();
    });
    expect(screen.queryByText("alice-se")).not.toBeInTheDocument();
    expect(screen.queryByText("当前会话 alice-se")).not.toBeInTheDocument();
  });

  it("创建会话失败前切换用户不显示旧用户错误", async () => {
    const user = userEvent.setup();
    const api = createFakeApi();
    let releaseCreate: (() => void) | null = null;
    api.createSession = async () => {
      await new Promise<void>((resolve) => {
        releaseCreate = resolve;
      });
      throw new Error("旧用户创建失败");
    };

    render(<AgentConsole api={api} apiBaseUrl="/api" defaultUserId="alice" />);

    await user.click(await screen.findByRole("button", { name: "新建会话" }));
    fireEvent.change(screen.getByLabelText("用户 ID"), { target: { value: "bob" } });
    await act(async () => {
      releaseCreate?.();
    });

    expect(screen.queryByText("旧用户创建失败")).not.toBeInTheDocument();
    expect(screen.queryByText("创建会话失败。")).not.toBeInTheDocument();
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

  it("切换用户时立即清空旧会话并不读取旧会话消息", async () => {
    const api = createFakeApi({
      sessions: {
        alice: [
          {
            session_id: "alice-session-1",
            user_id: "alice",
            created_at: "2026-08-12T00:00:00.000Z",
          },
        ],
      },
    });

    let releaseAliceMessages: (() => void) | null = null;
    api.listMessages = async (nextUserId, sessionId) => {
      api.calls.listMessages.push({ userId: nextUserId, sessionId });
      if (nextUserId === "alice") {
        await new Promise<void>((resolve) => {
          releaseAliceMessages = resolve;
        });
      }
      return { messages: [] };
    };

    render(<AgentConsole api={api} apiBaseUrl="/api" defaultUserId="alice" />);

    await screen.findByText("alice-se", { selector: "strong" });
    fireEvent.change(screen.getByLabelText("用户 ID"), { target: { value: "bob" } });

    expect(screen.getByText("暂无会话")).toBeInTheDocument();
    expect(screen.queryByText("alice-se")).not.toBeInTheDocument();
    expect(api.calls.listMessages).not.toContainEqual({
      userId: "bob",
      sessionId: "alice-session-1",
    });

    await act(async () => {
      releaseAliceMessages?.();
    });
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

  it("切换会话后加载并展示对应历史消息", async () => {
    const user = userEvent.setup();
    const api = createFakeApi({
      sessions: {
        alice: [
          {
            session_id: "alpha-session-1",
            user_id: "alice",
            created_at: "2026-08-12T00:00:00.000Z",
          },
          {
            session_id: "bravo-session-2",
            user_id: "alice",
            created_at: "2026-08-12T00:01:00.000Z",
          },
        ],
      },
      messages: {
        "alpha-session-1": [
          {
            id: 1,
            role: "user",
            content: "第一条会话的问题",
            created_at: "2026-08-12T00:00:01.000Z",
          },
        ],
        "bravo-session-2": [
          {
            id: 2,
            role: "assistant",
            content: "第二条会话的回答",
            created_at: "2026-08-12T00:01:01.000Z",
          },
        ],
      },
    });

    render(<AgentConsole api={api} apiBaseUrl="/api" defaultUserId="alice" />);

    expect(await screen.findByText("第一条会话的问题")).toBeInTheDocument();
    await user.click(screen.getByText("bravo-se", { selector: "strong" }));

    expect(await screen.findByText("第二条会话的回答")).toBeInTheDocument();
    expect(screen.queryByText("第一条会话的问题")).not.toBeInTheDocument();
    expect(api.calls.listMessages).toEqual([
      { userId: "alice", sessionId: "alpha-session-1" },
      { userId: "alice", sessionId: "bravo-session-2" },
    ]);
  });

  it("切换离开后晚返回的历史消息会按原会话缓存", async () => {
    const user = userEvent.setup();
    const api = createFakeApi({
      sessions: {
        alice: [
          {
            session_id: "alpha-session-1",
            user_id: "alice",
            created_at: "2026-08-12T00:00:00.000Z",
          },
          {
            session_id: "bravo-session-2",
            user_id: "alice",
            created_at: "2026-08-12T00:01:00.000Z",
          },
        ],
      },
    });

    let releaseFirstAlphaRequest: (() => void) | null = null;
    let alphaRequestCount = 0;
    api.listMessages = async (nextUserId, sessionId) => {
      api.calls.listMessages.push({ userId: nextUserId, sessionId });
      if (sessionId === "alpha-session-1") {
        alphaRequestCount += 1;
        if (alphaRequestCount === 1) {
          await new Promise<void>((resolve) => {
            releaseFirstAlphaRequest = resolve;
          });
        }
        return {
          messages: [
            {
              id: 1,
              role: "user",
              content: "A 会话历史",
              created_at: "2026-08-12T00:00:01.000Z",
            },
          ],
        };
      }

      return {
        messages: [
          {
            id: 2,
            role: "assistant",
            content: "B 会话历史",
            created_at: "2026-08-12T00:01:01.000Z",
          },
        ],
      };
    };

    render(<AgentConsole api={api} apiBaseUrl="/api" defaultUserId="alice" />);

    await screen.findByText("alpha-se", { selector: "strong" });
    await user.click(screen.getByText("bravo-se", { selector: "strong" }));
    expect(await screen.findByText("B 会话历史")).toBeInTheDocument();

    await act(async () => {
      releaseFirstAlphaRequest?.();
    });

    await user.click(screen.getByText("alpha-se", { selector: "strong" }));
    expect(await screen.findByText("A 会话历史")).toBeInTheDocument();
    expect(api.calls.listMessages.filter(({ sessionId }) => sessionId === "alpha-session-1")).toHaveLength(1);
  });

  it("删除选中的 204 会话后更新列表并清空聊天记录", async () => {
    const user = userEvent.setup();
    const api = createFakeApi({
      sessions: {
        alice: [
          {
            session_id: "alice-session-1",
            user_id: "alice",
            created_at: "2026-08-12T00:00:00.000Z",
          },
        ],
      },
      messages: {
        "alice-session-1": [
          {
            id: 1,
            role: "user",
            content: "待删除会话里的消息",
            created_at: "2026-08-12T00:00:01.000Z",
          },
        ],
      },
    });

    render(<AgentConsole api={api} apiBaseUrl="/api" defaultUserId="alice" />);

    expect(await screen.findByText("待删除会话里的消息")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "删除会话 alice-se" }));

    await waitFor(() => {
      expect(screen.getByText("暂无会话")).toBeInTheDocument();
    });
    expect(screen.queryByText("待删除会话里的消息")).not.toBeInTheDocument();
    expect(screen.queryByText("删除会话失败，请刷新后重试。")).not.toBeInTheDocument();
    expect(api.calls.deleteSession).toEqual([{ userId: "alice", sessionId: "alice-session-1" }]);
  });

  it("发送消息后忽略晚返回的历史消息请求", async () => {
    const user = userEvent.setup();
    const api = createFakeApi({
      sessions: {
        alice: [
          {
            session_id: "alice-session-1",
            user_id: "alice",
            created_at: "2026-08-12T00:00:00.000Z",
          },
        ],
      },
    });
    let releaseHistoryRequest: (() => void) | null = null;
    api.listMessages = async (nextUserId, sessionId) => {
      api.calls.listMessages.push({ userId: nextUserId, sessionId });
      await new Promise<void>((resolve) => {
        releaseHistoryRequest = resolve;
      });
      return { messages: [] };
    };

    render(<AgentConsole api={api} apiBaseUrl="/api" defaultUserId="alice" />);

    await screen.findByText("当前会话 alice-se");
    await user.type(screen.getByLabelText("聊天输入"), "请计算 19 * 23 并解释结果");
    await user.click(screen.getByRole("button", { name: "发送" }));
    await act(async () => {
      releaseHistoryRequest?.();
    });

    expect(await screen.findByText("请计算 19 * 23 并解释结果")).toBeInTheDocument();
    expect(await screen.findByText(/19 × 23 = 437/)).toBeInTheDocument();
  });

  it("删除未选中的会话不打断当前会话历史加载", async () => {
    const user = userEvent.setup();
    const api = createFakeApi({
      sessions: {
        alice: [
          {
            session_id: "alpha-session-1",
            user_id: "alice",
            created_at: "2026-08-12T00:00:00.000Z",
          },
          {
            session_id: "bravo-session-2",
            user_id: "alice",
            created_at: "2026-08-12T00:01:00.000Z",
          },
        ],
      },
      messages: {
        "alpha-session-1": [
          {
            id: 1,
            role: "assistant",
            content: "当前会话历史",
            created_at: "2026-08-12T00:00:01.000Z",
          },
        ],
      },
    });
    const originalListMessages = api.listMessages.bind(api);
    let releaseHistoryRequest: (() => void) | null = null;
    api.listMessages = async (nextUserId, sessionId) => {
      api.calls.listMessages.push({ userId: nextUserId, sessionId });
      if (sessionId === "alpha-session-1") {
        await new Promise<void>((resolve) => {
          releaseHistoryRequest = resolve;
        });
      }
      return originalListMessages(nextUserId, sessionId);
    };

    render(<AgentConsole api={api} apiBaseUrl="/api" defaultUserId="alice" />);

    await screen.findByText("alpha-se", { selector: "strong" });
    await user.click(screen.getByRole("button", { name: "删除会话 bravo-se" }));
    await act(async () => {
      releaseHistoryRequest?.();
    });

    expect(await screen.findByText("当前会话历史")).toBeInTheDocument();
    expect(screen.queryByText("bravo-se")).not.toBeInTheDocument();
  });

  it("其他会话流式更新不会重启当前会话的历史加载", async () => {
    const user = userEvent.setup();
    const api = createFakeApi({
      sessions: {
        alice: [
          {
            session_id: "alpha-session-1",
            user_id: "alice",
            created_at: "2026-08-12T00:00:00.000Z",
          },
          {
            session_id: "bravo-session-2",
            user_id: "alice",
            created_at: "2026-08-12T00:01:00.000Z",
          },
        ],
      },
    });
    let releaseAlphaStream: (() => void) | null = null;
    let releaseFirstBravoHistory: (() => void) | null = null;
    let bravoHistoryRequests = 0;
    api.listMessages = async (nextUserId, sessionId) => {
      api.calls.listMessages.push({ userId: nextUserId, sessionId });
      if (sessionId === "bravo-session-2") {
        bravoHistoryRequests += 1;
        if (bravoHistoryRequests === 1) {
          await new Promise<void>((resolve) => {
            releaseFirstBravoHistory = resolve;
          });
        } else {
          await new Promise<void>(() => {});
        }
        return {
          messages: [
            {
              id: 2,
              role: "assistant",
              content: "B 会话历史",
              created_at: "2026-08-12T00:01:01.000Z",
            },
          ],
        };
      }

      return { messages: [] };
    };
    api.streamChat = async function* (nextUserId, request) {
      api.calls.streamChat.push({
        userId: nextUserId,
        sessionId: request.session_id,
        message: request.message,
      });
      yield { event: "message_start", data: { session_id: request.session_id } };
      await new Promise<void>((resolve) => {
        releaseAlphaStream = resolve;
      });
      yield { event: "token", data: { session_id: request.session_id, content: "A 会话回答" } };
      yield { event: "message_end", data: { session_id: request.session_id } };
    };

    render(<AgentConsole api={api} apiBaseUrl="/api" defaultUserId="alice" />);

    await screen.findByText("alpha-se", { selector: "strong" });
    await user.type(screen.getByLabelText("聊天输入"), "A 会话问题");
    await user.click(screen.getByRole("button", { name: "发送" }));
    await user.click(screen.getByText("bravo-se", { selector: "strong" }));
    await waitFor(() => {
      expect(api.calls.listMessages.filter(({ sessionId }) => sessionId === "bravo-session-2")).toHaveLength(1);
    });

    await act(async () => {
      releaseAlphaStream?.();
    });
    await act(async () => {
      releaseFirstBravoHistory?.();
    });

    expect(await screen.findByText("B 会话历史")).toBeInTheDocument();
    expect(api.calls.listMessages.filter(({ sessionId }) => sessionId === "bravo-session-2")).toHaveLength(1);
  });

  it("删除请求期间切到被删会话时删除完成后切回剩余会话", async () => {
    const user = userEvent.setup();
    const api = createFakeApi({
      sessions: {
        alice: [
          {
            session_id: "alpha-session-1",
            user_id: "alice",
            created_at: "2026-08-12T00:00:00.000Z",
          },
          {
            session_id: "bravo-session-2",
            user_id: "alice",
            created_at: "2026-08-12T00:01:00.000Z",
          },
        ],
      },
    });
    const originalDeleteSession = api.deleteSession.bind(api);
    let releaseDelete: (() => void) | null = null;
    api.deleteSession = async (nextUserId, sessionId) => {
      await new Promise<void>((resolve) => {
        releaseDelete = resolve;
      });
      await originalDeleteSession(nextUserId, sessionId);
    };

    render(<AgentConsole api={api} apiBaseUrl="/api" defaultUserId="alice" />);

    await screen.findByText("alpha-se", { selector: "strong" });
    await user.click(screen.getByRole("button", { name: "删除会话 bravo-se" }));
    await user.click(screen.getByText("bravo-se", { selector: "strong" }));
    expect(screen.getByText("当前会话 bravo-se")).toBeInTheDocument();

    await act(async () => {
      releaseDelete?.();
    });

    await waitFor(() => {
      expect(screen.queryByText("bravo-se")).not.toBeInTheDocument();
    });
    expect(screen.getByText("当前会话 alpha-se")).toBeInTheDocument();
  });

  it("删除会话未返回时切换用户会忽略旧用户删除结果", async () => {
    const user = userEvent.setup();
    const api = createFakeApi({
      sessions: {
        alice: [
          {
            session_id: "alice-session-1",
            user_id: "alice",
            created_at: "2026-08-12T00:00:00.000Z",
          },
        ],
        bob: [
          {
            session_id: "bob-session-1",
            user_id: "bob",
            created_at: "2026-08-12T00:00:00.000Z",
          },
        ],
      },
    });
    const originalDeleteSession = api.deleteSession.bind(api);
    let releaseDelete: (() => void) | null = null;
    api.deleteSession = async (nextUserId, sessionId) => {
      await new Promise<void>((resolve) => {
        releaseDelete = resolve;
      });
      await originalDeleteSession(nextUserId, sessionId);
    };

    render(<AgentConsole api={api} apiBaseUrl="/api" defaultUserId="alice" />);

    await screen.findByText("alice-se", { selector: "strong" });
    await user.click(screen.getByRole("button", { name: "删除会话 alice-se" }));
    fireEvent.change(screen.getByLabelText("用户 ID"), { target: { value: "bob" } });
    expect(await screen.findByText("bob-sess", { selector: "strong" })).toBeInTheDocument();

    await act(async () => {
      releaseDelete?.();
    });

    expect(await screen.findByText("bob-sess", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByText("当前会话 bob-sess")).toBeInTheDocument();
  });

  it("删除会话失败前切换用户不显示旧用户错误", async () => {
    const user = userEvent.setup();
    const api = createFakeApi({
      sessions: {
        alice: [
          {
            session_id: "alice-session-1",
            user_id: "alice",
            created_at: "2026-08-12T00:00:00.000Z",
          },
        ],
        bob: [
          {
            session_id: "bob-session-1",
            user_id: "bob",
            created_at: "2026-08-12T00:00:00.000Z",
          },
        ],
      },
    });
    let releaseDelete: (() => void) | null = null;
    api.deleteSession = async () => {
      await new Promise<void>((resolve) => {
        releaseDelete = resolve;
      });
      throw new Error("旧用户删除失败");
    };

    render(<AgentConsole api={api} apiBaseUrl="/api" defaultUserId="alice" />);

    await screen.findByText("alice-se", { selector: "strong" });
    await user.click(screen.getByRole("button", { name: "删除会话 alice-se" }));
    fireEvent.change(screen.getByLabelText("用户 ID"), { target: { value: "bob" } });
    expect(await screen.findByText("bob-sess", { selector: "strong" })).toBeInTheDocument();

    await act(async () => {
      releaseDelete?.();
    });

    expect(screen.queryByText("旧用户删除失败")).not.toBeInTheDocument();
    expect(screen.queryByText("删除会话失败，请刷新后重试。")).not.toBeInTheDocument();
  });

  it("切到其他会话后不展示原会话仍在流式生成的 token", async () => {
    const user = userEvent.setup();
    const api = createFakeApi({
      sessions: {
        alice: [
          {
            session_id: "alpha-session-1",
            user_id: "alice",
            created_at: "2026-08-12T00:00:00.000Z",
          },
          {
            session_id: "bravo-session-2",
            user_id: "alice",
            created_at: "2026-08-12T00:01:00.000Z",
          },
        ],
      },
    });
    let releaseAlphaStream: (() => void) | null = null;
    api.streamChat = async function* (nextUserId, request) {
      api.calls.streamChat.push({
        userId: nextUserId,
        sessionId: request.session_id,
        message: request.message,
      });
      if (request.session_id === "alpha-session-1") {
        yield { event: "message_start", data: { session_id: "alpha-session-1" } };
        await new Promise<void>((resolve) => {
          releaseAlphaStream = resolve;
        });
        yield { event: "token", data: { session_id: "alpha-session-1", content: "A 会话回答" } };
        yield { event: "message_end", data: { session_id: "alpha-session-1" } };
      }
    };

    render(<AgentConsole api={api} apiBaseUrl="/api" defaultUserId="alice" />);

    await screen.findByText("alpha-se", { selector: "strong" });
    await user.type(screen.getByLabelText("聊天输入"), "A 会话问题");
    await user.click(screen.getByRole("button", { name: "发送" }));
    await user.click(screen.getByText("bravo-se", { selector: "strong" }));

    await act(async () => {
      releaseAlphaStream?.();
    });

    expect(screen.queryByText("A 会话回答")).not.toBeInTheDocument();
    await user.click(screen.getByText("alpha-se", { selector: "strong" }));
    expect(await screen.findByText("A 会话回答")).toBeInTheDocument();
  });
});
