import { appendFile, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

function slugifyUrl(url) {
  return String(url || "no-url")
    .replace(/^https?:\/\//, "")
    .replace(/[^\w.-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 48) || "no-url";
}

function nowStamp() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

export async function createRunLogger({ command, outputDir, url, browser, sessionMode }) {
  const runId = `${nowStamp()}-${command}`;
  const runDir = path.resolve(outputDir, `${runId}-${slugifyUrl(url)}`);
  const auditPath = path.join(runDir, "audit-log.jsonl");

  await mkdir(runDir, { recursive: true });

  const baseSummary = {
    runId,
    runDir,
    command,
    browser,
    sessionMode,
    sourceUrl: url || "",
    startedAt: new Date().toISOString()
  };

  async function appendAudit(event, detail = {}) {
    const record = {
      timestamp: new Date().toISOString(),
      event,
      detail
    };

    await appendFile(auditPath, `${JSON.stringify(record)}\n`, "utf8");
  }

  async function writeJson(filename, data) {
    await writeFile(
      path.join(runDir, filename),
      `${JSON.stringify(data, null, 2)}\n`,
      "utf8"
    );
  }

  async function writeText(filename, content) {
    await writeFile(path.join(runDir, filename), `${content}\n`, "utf8");
  }

  async function finalize(status, extra = {}) {
    const summary = {
      ...baseSummary,
      finishedAt: new Date().toISOString(),
      status,
      ...extra
    };

    await writeJson("run-summary.json", summary);
    await appendAudit("run_finalized", { status });
    return summary;
  }

  await appendAudit("run_started", {
    command,
    browser,
    sessionMode
  });

  return {
    runId,
    runDir,
    appendAudit,
    writeJson,
    writeText,
    finalize
  };
}
