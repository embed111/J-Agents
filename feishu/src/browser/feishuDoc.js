const SUPPORTED_HOST_SUFFIXES = ["feishu.cn", "larksuite.com"];
const SUPPORTED_PATH_MARKERS = ["docx", "docs", "wiki", "base"];

function isSupportedHost(hostname) {
  return SUPPORTED_HOST_SUFFIXES.some((suffix) => hostname.endsWith(suffix));
}

function getTokenFromUrl(url) {
  const parsed = new URL(url);
  const segments = parsed.pathname.split("/").filter(Boolean);
  const markerIndex = segments.findIndex((segment) =>
    SUPPORTED_PATH_MARKERS.includes(segment.toLowerCase())
  );

  if (markerIndex >= 0 && segments[markerIndex + 1]) {
    return segments[markerIndex + 1];
  }

  return segments[segments.length - 1] || "";
}

function loginLikeText(text) {
  return /登录|登入|扫码登录|继续登录|验证码|verification|sign in/i.test(text);
}

function sameDocument(targetUrl, currentUrl) {
  return (
    isSupportedHost(currentUrl.hostname) &&
    currentUrl.hostname.endsWith(targetUrl.hostname.split(".").slice(-2).join(".")) &&
    getTokenFromUrl(targetUrl.href) &&
    getTokenFromUrl(targetUrl.href) === getTokenFromUrl(currentUrl.href)
  );
}

export function assertFeishuDocumentUrl(input) {
  let parsed;

  try {
    parsed = new URL(input);
  } catch {
    throw new Error("输入链接不是合法 URL。");
  }

  if (!isSupportedHost(parsed.hostname)) {
    throw new Error("当前仅支持飞书 / LarkSuite 文档链接。");
  }

  if (!SUPPORTED_PATH_MARKERS.some((marker) => parsed.pathname.includes(`/${marker}/`))) {
    throw new Error("链接不是受支持的飞书 Wiki / Doc 文档路径。");
  }

  return parsed.href;
}

export function getDocumentFingerprint(url) {
  const parsed = new URL(url);
  return {
    host: parsed.host,
    pathname: parsed.pathname,
    token: getTokenFromUrl(parsed.href)
  };
}

export async function openFeishuDocument(page, inputUrl, options, logger) {
  const targetUrl = assertFeishuDocumentUrl(inputUrl);
  const targetFingerprint = getDocumentFingerprint(targetUrl);

  await logger.appendAudit("navigate_started", {
    url: targetUrl,
    token: targetFingerprint.token
  });

  await page.goto(targetUrl, {
    waitUntil: "domcontentloaded",
    timeout: options.timeoutMs
  });
  await page.waitForLoadState("networkidle", { timeout: options.timeoutMs }).catch(() => undefined);
  await page.waitForTimeout(1500);

  const currentUrl = new URL(page.url());
  const bodyText = await page.evaluate(() => document.body?.innerText?.trim() || "");

  if (currentUrl.href !== targetUrl && !sameDocument(new URL(targetUrl), currentUrl)) {
    throw new Error(
      `页面已跳转到非目标文档：${currentUrl.href}。为避免误写，流程已中断。`
    );
  }

  if (loginLikeText(`${currentUrl.href}\n${bodyText}`)) {
    throw new Error("检测到登录页或二次验证页面，请先在浏览器中完成登录。");
  }

  if (bodyText.length < 20) {
    throw new Error("页面正文过短，可能没有成功打开文档或没有读取权限。");
  }

  const pageTitle = (await page.title()).trim();

  await logger.appendAudit("navigate_completed", {
    title: pageTitle,
    currentUrl: currentUrl.href
  });

  return {
    targetUrl,
    currentUrl: currentUrl.href,
    title: pageTitle,
    fingerprint: targetFingerprint
  };
}

export async function assertStillOnDocument(page, targetUrl) {
  const current = new URL(page.url());
  const target = new URL(targetUrl);

  if (!sameDocument(target, current)) {
    throw new Error(`目标页面已变化：当前页面为 ${current.href}。`);
  }
}
