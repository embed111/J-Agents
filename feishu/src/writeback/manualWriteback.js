import readline from "node:readline/promises";
import { stdin as input, stdout as output } from "node:process";

import { assertStillOnDocument, getDocumentFingerprint } from "../browser/feishuDoc.js";
import { extractStructuredDocument } from "../extract/structuredExtractor.js";

async function tryEnterEditMode(page) {
  const editButton = page.getByRole("button", { name: /编辑|edit/i }).first();
  const visible = await editButton.isVisible({ timeout: 2000 }).catch(() => false);

  if (visible) {
    await editButton.click();
    await page.waitForTimeout(1000);
    return "button";
  }

  return "already_editable";
}

async function locateEditableAreas(page, expectedTitle) {
  const handles = await page.$$("[contenteditable='true']");

  if (handles.length === 0) {
    throw new Error("未找到可编辑区域，可能当前文档为只读或页面结构已变更。");
  }

  const descriptors = await Promise.all(
    handles.map(async (handle, index) => {
      const box = await handle.boundingBox();
      const text = ((await handle.textContent()) || "").replace(/\s+/g, " ").trim();

      return {
        index,
        text,
        textLength: text.length,
        y: box?.y ?? Number.MAX_SAFE_INTEGER,
        area: (box?.width ?? 0) * (box?.height ?? 0)
      };
    })
  );

  const titleCandidate =
    descriptors
      .filter(
        (item) =>
          item.y < 260 &&
          (item.text.includes(expectedTitle.slice(0, 4)) || item.textLength <= 80)
      )
      .sort((left, right) => left.y - right.y || left.textLength - right.textLength)[0] ||
    null;
  const bodyCandidate =
    descriptors
      .filter((item) => !titleCandidate || item.index !== titleCandidate.index)
      .sort((left, right) => right.textLength - left.textLength || right.area - left.area)[0] ||
    descriptors[0];

  return {
    descriptors,
    titleHandle: titleCandidate ? handles[titleCandidate.index] : null,
    bodyHandle: handles[bodyCandidate.index]
  };
}

async function replaceEditableContent(page, handle, text) {
  await handle.click();
  await page.keyboard.press("Control+A");
  await page.keyboard.press("Backspace");

  const chunks = text.match(/[\s\S]{1,1500}/g) || [];
  for (const chunk of chunks) {
    await page.keyboard.insertText(chunk);
  }
}

function confirmationToken(documentUrl) {
  const fingerprint = getDocumentFingerprint(documentUrl);
  return `WRITEBACK ${fingerprint.token}`;
}

export async function requestWritebackConfirmation({
  title,
  documentUrl,
  replacementScope
}) {
  if (!input.isTTY || !output.isTTY) {
    return {
      confirmed: false,
      reason: "当前终端不是交互模式，无法执行人工确认。"
    };
  }

  const expectedTitle = title.slice(0, Math.min(title.length, 8));
  const token = confirmationToken(documentUrl);
  const rl = readline.createInterface({ input, output });

  try {
    output.write(`\n准备写回飞书文档：\n`);
    output.write(`- 标题：${title}\n`);
    output.write(`- 链接：${documentUrl}\n`);
    output.write(`- 替换范围：${replacementScope}\n`);

    const titleAnswer = (
      await rl.question(`请输入文档标题前 ${expectedTitle.length} 个字确认目标：`)
    ).trim();

    if (titleAnswer !== expectedTitle) {
      return {
        confirmed: false,
        reason: "标题确认失败，已取消写回。"
      };
    }

    const tokenAnswer = (await rl.question(`请输入 ${token} 执行写回：`)).trim();

    if (tokenAnswer !== token) {
      return {
        confirmed: false,
        reason: "写回确认口令不匹配，已取消写回。"
      };
    }

    return {
      confirmed: true,
      replacementScope,
      token
    };
  } finally {
    rl.close();
  }
}

export async function applyWriteback(page, payload, logger) {
  await assertStillOnDocument(page, payload.sourceUrl);
  const editMode = await tryEnterEditMode(page);
  const areas = await locateEditableAreas(page, payload.currentTitle);

  if (!areas.bodyHandle) {
    throw new Error("未定位到正文编辑区域，写回已中止。");
  }

  let titleUpdated = false;

  if (areas.titleHandle && payload.recommendedTitle) {
    await replaceEditableContent(page, areas.titleHandle, payload.recommendedTitle);
    titleUpdated = true;
  }

  await replaceEditableContent(page, areas.bodyHandle, payload.bodyPlainText);
  await page.waitForTimeout(2000);

  const latest = await extractStructuredDocument(page);
  const probe = payload.bodyPlainText
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 48);
  const verified = latest.plainText.replace(/\s+/g, " ").includes(probe);
  const result = {
    status: verified ? "success" : "warning",
    editMode,
    titleUpdated,
    verified,
    currentUrl: page.url(),
    replacementScope: "正文主体整篇替换，标题最佳努力更新"
  };

  await logger.appendAudit("writeback_completed", result);
  return result;
}
