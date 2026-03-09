const DEFAULT_TIMEOUT_MS = 45000;

function toCamelCase(input) {
  return input.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
}

function parseBoolean(value, fallback = false) {
  if (value === undefined) {
    return fallback;
  }

  if (typeof value === "boolean") {
    return value;
  }

  const normalized = String(value).trim().toLowerCase();

  if (["1", "true", "yes", "y", "on"].includes(normalized)) {
    return true;
  }

  if (["0", "false", "no", "n", "off"].includes(normalized)) {
    return false;
  }

  return fallback;
}

function normalizeBrowser(value) {
  if (!value) {
    return "edge";
  }

  const normalized = String(value).trim().toLowerCase();
  return normalized === "chrome" ? "chrome" : "edge";
}

function normalizeSessionMode(value) {
  if (!value) {
    return "cdp";
  }

  const normalized = String(value).trim().toLowerCase();
  if (normalized === "profile") {
    return "profile";
  }

  if (normalized === "cookie") {
    return "cookie";
  }

  return "cdp";
}

function normalizeOutputDir(value) {
  return value ? String(value).trim() : "workspace_state/runs";
}

function normalizeTimeout(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULT_TIMEOUT_MS;
}

function parseTokens(tokens) {
  const flags = {};

  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];

    if (!token.startsWith("--")) {
      continue;
    }

    if (token === "--help") {
      flags.help = true;
      continue;
    }

    const rawKey = token.slice(2);

    if (rawKey.startsWith("no-")) {
      flags[toCamelCase(rawKey.slice(3))] = false;
      continue;
    }

    const next = tokens[index + 1];

    if (!next || next.startsWith("--")) {
      flags[toCamelCase(rawKey)] = true;
      continue;
    }

    flags[toCamelCase(rawKey)] = next;
    index += 1;
  }

  return { flags };
}

export function getUsageText() {
  return `
飞书文档优化 Agent

命令：
  npm run doctor -- --browser edge --session-mode cdp --cdp-url http://127.0.0.1:9222
  npm run optimize -- --browser edge --session-mode cdp --cdp-url http://127.0.0.1:9222 --url "https://xxx.feishu.cn/docx/xxxx"
  npm run optimize -- --browser edge --session-mode cdp --cdp-url http://127.0.0.1:9222 --url "https://xxx.feishu.cn/docx/xxxx" --writeback

常用参数：
  --url <飞书文档链接>
  --browser <edge|chrome>
  --session-mode <cdp|profile|cookie>
  --cdp-url <http://127.0.0.1:9222>
  --user-data-dir <浏览器 User Data 路径>
  --profile-directory <Default|Profile 1>
  --writeback
  --allow-unsupported-writeback
  --timeout-ms <毫秒>
  --output-dir <运行记录目录>
`.trim();
}

export function parseCli(argv, env = process.env) {
  const tokens = argv.slice(2);
  const command = tokens[0] && !tokens[0].startsWith("--") ? tokens[0] : "help";
  const remaining = command === "help" ? tokens : tokens.slice(1);
  const { flags } = parseTokens(remaining);

  if (command === "help" || flags.help) {
    return {
      command: "help",
      options: {}
    };
  }

  const options = {
    url: flags.url ?? env.FEISHU_DOC_URL ?? "",
    browser: normalizeBrowser(flags.browser ?? env.FEISHU_BROWSER ?? "edge"),
    sessionMode: normalizeSessionMode(flags.sessionMode ?? env.FEISHU_SESSION_MODE ?? "cdp"),
    cdpUrl: flags.cdpUrl ?? env.FEISHU_BROWSER_CDP_URL ?? "http://127.0.0.1:9222",
    userDataDir: flags.userDataDir ?? env.FEISHU_USER_DATA_DIR ?? "",
    profileDirectory: flags.profileDirectory ?? env.FEISHU_PROFILE_DIRECTORY ?? "Default",
    writeback: parseBoolean(flags.writeback, false),
    allowUnsupportedWriteback: parseBoolean(
      flags.allowUnsupportedWriteback,
      false
    ),
    headless: parseBoolean(flags.headless, false),
    timeoutMs: normalizeTimeout(flags.timeoutMs ?? env.FEISHU_TIMEOUT_MS),
    outputDir: normalizeOutputDir(flags.outputDir ?? env.FEISHU_OUTPUT_DIR)
  };

  return { command, options };
}
