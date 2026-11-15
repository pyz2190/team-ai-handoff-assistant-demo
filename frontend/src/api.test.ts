import { afterEach, describe, expect, it, vi } from "vitest";

import { api, ApiError, setApiMember } from "./api";


afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});


describe("api client", () => {
  it("sends the selected demo identity", async () => {
    setApiMember("member-b");
    const mocked = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      })
    );
    await api("/projects");
    const headers = new Headers(mocked.mock.calls[0][1]?.headers);
    expect(headers.get("X-Demo-Member-ID")).toBe("member-b");
  });

  it("returns structured server errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ error: { code: "STALE_REVISION", message: "请刷新" } }),
        { status: 409, headers: { "Content-Type": "application/json" } }
      )
    );
    await expect(api("/tasks/1")).rejects.toMatchObject({
      code: "STALE_REVISION",
      status: 409
    } satisfies Partial<ApiError>);
  });
});
