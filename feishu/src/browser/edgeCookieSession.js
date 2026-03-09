import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";

import initSqlJs from "sql.js";

const EDGE_BASE_DIR = path.join(
  process.env.USERPROFILE || "",
  "AppData",
  "Local",
  "Microsoft",
  "Edge",
  "User Data"
);

function chromiumSameSiteToPlaywright(value) {
  if (value === 0) {
    return "None";
  }

  if (value === 1) {
    return "Lax";
  }

  if (value === 2) {
    return "Strict";
  }

  return undefined;
}

function chromiumExpiresToUnixSeconds(value) {
  const numeric = Number(value);

  if (!Number.isFinite(numeric) || numeric <= 0) {
    return undefined;
  }

  const seconds = Math.floor(numeric / 1_000_000 - 11644473600);
  return seconds > 0 ? seconds : undefined;
}

function dpapiUnprotectBase64(base64Value) {
  const script = [
    "Add-Type -AssemblyName System.Security;",
    "$plain=[System.Security.Cryptography.ProtectedData]::Unprotect(",
    "[Convert]::FromBase64String($env:COOKIE_B64),",
    "$null,",
    "[System.Security.Cryptography.DataProtectionScope]::CurrentUser",
    ");",
    "[Console]::Out.Write([Convert]::ToBase64String($plain));"
  ].join("");

  const output = execFileSync(
    "powershell.exe",
    ["-NoProfile", "-Command", script],
    {
      env: {
        ...process.env,
        COOKIE_B64: base64Value
      },
      encoding: "utf8"
    }
  ).trim();

  return Buffer.from(output, "base64");
}

function getEdgeMasterKey(edgeBaseDir) {
  const localStatePath = path.join(edgeBaseDir, "Local State");
  const localState = JSON.parse(readFileSync(localStatePath, "utf8"));
  const encryptedKey = localState.os_crypt?.encrypted_key;

  if (!encryptedKey) {
    throw new Error("Edge Local State 中缺少加密密钥。");
  }

  const keyBuffer = Buffer.from(encryptedKey, "base64");
  const dpapiBuffer =
    keyBuffer.slice(0, 5).toString("utf8") === "DPAPI" ? keyBuffer.slice(5) : keyBuffer;

  return dpapiUnprotectBase64(dpapiBuffer.toString("base64"));
}

function decryptChromiumCookie(encryptedValue, masterKey) {
  const buffer = Buffer.from(encryptedValue);

  if (buffer.length === 0) {
    return "";
  }

  const prefix = buffer.slice(0, 3).toString("utf8");

  if (prefix === "v10" || prefix === "v11" || prefix === "v20") {
    const iv = buffer.subarray(3, 15);
    const cipherText = buffer.subarray(15, buffer.length - 16);
    const authTag = buffer.subarray(buffer.length - 16);
    const decipher = crypto.createDecipheriv("aes-256-gcm", masterKey, iv);
    decipher.setAuthTag(authTag);
    return Buffer.concat([decipher.update(cipherText), decipher.final()]).toString("utf8");
  }

  return dpapiUnprotectBase64(buffer.toString("base64")).toString("utf8");
}

function resolveEdgePaths(profileDirectory) {
  return {
    edgeBaseDir: EDGE_BASE_DIR,
    cookieDbPath: path.join(EDGE_BASE_DIR, profileDirectory || "Default", "Network", "Cookies")
  };
}

async function queryCookies(cookieDbPath) {
  const tempDir = mkdtempSync(path.join(os.tmpdir(), "feishu-cookie-db-"));
  const tempDbPath = path.join(tempDir, "Cookies");

  try {
    try {
      execFileSync("esentutl.exe", ["/y", cookieDbPath, "/d", tempDbPath, "/o"], {
        stdio: "ignore"
      });
    } catch {
      execFileSync(
        "powershell.exe",
        [
          "-NoProfile",
          "-Command",
          [
            "$src=$env:COOKIE_SRC;",
            "$dst=$env:COOKIE_DST;",
            "$in=[System.IO.File]::Open($src,[System.IO.FileMode]::Open,[System.IO.FileAccess]::Read,[System.IO.FileShare]::ReadWrite);",
            "$out=[System.IO.File]::Open($dst,[System.IO.FileMode]::Create,[System.IO.FileAccess]::Write,[System.IO.FileShare]::None);",
            "try { $in.CopyTo($out) } finally { $out.Dispose(); $in.Dispose() }"
          ].join("")
        ],
        {
          stdio: "ignore",
          env: {
            ...process.env,
            COOKIE_SRC: cookieDbPath,
            COOKIE_DST: tempDbPath
          }
        }
      );
    }
    const SQL = await initSqlJs();
    const database = new SQL.Database(readFileSync(tempDbPath));
    const statement = database.prepare(`
      SELECT
        host_key,
        name,
        path,
        expires_utc,
        is_secure,
        is_httponly,
        samesite,
        encrypted_value
      FROM cookies
      WHERE host_key LIKE '%feishu.cn'
         OR host_key LIKE '%larksuite.com'
    `);
    const rows = [];

    while (statement.step()) {
      rows.push(statement.getAsObject());
    }

    statement.free();
    database.close();
    return rows;
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
}

export async function loadEdgeSessionCookies({
  browser,
  profileDirectory
}) {
  if (browser !== "edge") {
    throw new Error("cookie 模式当前仅支持 Edge。");
  }

  const { edgeBaseDir, cookieDbPath } = resolveEdgePaths(profileDirectory);
  const masterKey = getEdgeMasterKey(edgeBaseDir);
  const rows = await queryCookies(cookieDbPath);
  const cookies = [];

  for (const row of rows) {
    const encryptedValue = row.encrypted_value;
    const value = decryptChromiumCookie(encryptedValue, masterKey);

    if (!value) {
      continue;
    }

    cookies.push({
      name: row.name,
      value,
      domain: row.host_key,
      path: row.path || "/",
      httpOnly: Boolean(row.is_httponly),
      secure: Boolean(row.is_secure),
      expires: chromiumExpiresToUnixSeconds(row.expires_utc),
      sameSite: chromiumSameSiteToPlaywright(Number(row.samesite))
    });
  }

  return cookies;
}
