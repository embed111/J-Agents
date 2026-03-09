import { chromium } from "playwright-core";
import { loadEdgeSessionCookies } from "./edgeCookieSession.js";

function resolveChannel(browser) {
  return browser === "chrome" ? "chrome" : "msedge";
}

function sanitizeSessionMeta(options) {
  return {
    browser: options.browser,
    sessionMode: options.sessionMode,
    cdpUrl: options.sessionMode === "cdp" ? options.cdpUrl : "",
    profileDirectory: options.sessionMode === "profile" ? options.profileDirectory : ""
  };
}

export async function createBrowserSession(options, logger) {
  const sessionMeta = sanitizeSessionMeta(options);

  if (options.sessionMode === "cookie") {
    const cookies = await loadEdgeSessionCookies({
      browser: options.browser,
      profileDirectory: options.profileDirectory
    });

    if (cookies.length === 0) {
      throw new Error("未从本机 Edge 读取到可用的飞书登录 Cookie。");
    }

    const browser = await chromium.launch({
      channel: resolveChannel(options.browser),
      headless: options.headless,
      timeout: options.timeoutMs
    });
    const context = await browser.newContext({
      viewport: null
    });

    await context.addCookies(cookies);
    const page = await context.newPage();

    await logger.appendAudit("session_cookie_injected", {
      ...sessionMeta,
      cookieCount: cookies.length
    });

    return {
      browser,
      context,
      page,
      async close() {
        await context.close().catch(() => undefined);
        await browser.close().catch(() => undefined);
      }
    };
  }

  if (options.sessionMode === "cdp") {
    if (!options.cdpUrl) {
      throw new Error("CDP 模式缺少 --cdp-url。");
    }

    const browser = await chromium.connectOverCDP(options.cdpUrl, {
      timeout: options.timeoutMs
    });
    const context = browser.contexts()[0];

    if (!context) {
      throw new Error(
        "已连接到浏览器，但未发现可用上下文。请先在调试浏览器中打开一个窗口。"
      );
    }

    let page = context.pages().find((item) => !item.isClosed());
    let createdByAgent = false;

    if (!page) {
      page = await context.newPage();
      createdByAgent = true;
    }

    await logger.appendAudit("session_attached", sessionMeta);

    return {
      browser,
      context,
      page,
      async close() {
        if (createdByAgent && !page.isClosed()) {
          await page.close().catch(() => undefined);
        }

        await browser.close().catch(() => undefined);
      }
    };
  }

  if (!options.userDataDir) {
    throw new Error("profile 模式缺少 --user-data-dir。");
  }

  const context = await chromium.launchPersistentContext(options.userDataDir, {
    channel: resolveChannel(options.browser),
    headless: options.headless,
    timeout: options.timeoutMs,
    viewport: null,
    args: [`--profile-directory=${options.profileDirectory}`]
  });
  const page = context.pages()[0] ?? (await context.newPage());

  await logger.appendAudit("session_launched", sessionMeta);

  return {
    context,
    page,
    async close() {
      await context.close().catch(() => undefined);
    }
  };
}
