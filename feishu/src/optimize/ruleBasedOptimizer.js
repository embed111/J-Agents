function splitSentences(text) {
  return text
    .split(/(?<=[。！？!?；;])/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeLine(text) {
  return String(text || "")
    .replace(/\s+/g, " ")
    .trim();
}

function buildSummary(plainText) {
  const normalized = normalizeLine(plainText);
  if (!normalized) {
    return "未能抽取到足够正文，建议先确认页面是否已完整加载。";
  }

  const sentences = splitSentences(normalized);
  return sentences.slice(0, 3).join(" ").slice(0, 180) || normalized.slice(0, 180);
}

function buildRecommendedTitle(originalTitle, summary) {
  const cleanTitle = normalizeLine(originalTitle);

  if (cleanTitle && cleanTitle.length <= 28) {
    return cleanTitle;
  }

  return (
    splitSentences(summary)[0]
      ?.replace(/[：:，,。.!！？?；;].*$/, "")
      .trim()
      .slice(0, 28) || cleanTitle || "优化后文档"
  );
}

function createDiagnostics(documentData) {
  const headings = documentData.blocks.filter((block) => block.type === "heading");
  const paragraphs = documentData.blocks.filter((block) => block.type === "paragraph");
  const listItems = documentData.blocks.filter((block) => block.type === "list_item");
  const longParagraphs = paragraphs.filter((block) => normalizeLine(block.text).length >= 120);
  const duplicateCounter = new Map();

  for (const block of documentData.blocks) {
    const line = normalizeLine(block.text);
    duplicateCounter.set(line, (duplicateCounter.get(line) || 0) + 1);
  }

  const duplicateLines = Array.from(duplicateCounter.entries()).filter(
    ([line, count]) => line.length >= 12 && count > 1
  );
  const structure = [];
  const expression = [];
  const density = [];

  if (headings.length === 0 && paragraphs.length >= 3) {
    structure.push("正文缺少稳定标题层级，阅读路径不够清晰。");
  }

  if (longParagraphs.length >= 1) {
    structure.push("存在长段落，建议拆分成二级标题或要点列表。");
  }

  if (listItems.length === 0 && longParagraphs.length >= 2) {
    structure.push("信息主要堆在段落里，缺少可扫读的列表结构。");
  }

  if (paragraphs.some((block) => /我们|需要|应该/.test(block.text) && block.text.length > 100)) {
    expression.push("部分段落偏口语化，建议改成结论先行的书面表达。");
  }

  if (longParagraphs.some((block) => splitSentences(block.text).length >= 4)) {
    expression.push("长句较多，建议拆成短句并前置动作或结论。");
  }

  if (paragraphs.some((block) => /非常|比较|很多|等等|以及相关/.test(block.text))) {
    expression.push("出现模糊修饰词，建议替换为具体动作、范围或数据。");
  }

  if (duplicateLines.length > 0) {
    density.push("检测到重复或高度相似表达，建议合并重复信息。");
  }

  if (paragraphs.length > 0 && paragraphs.length / Math.max(headings.length, 1) >= 4) {
    density.push("平均每个结构段下的正文较密，建议增加小标题或列表断点。");
  }

  if (documentData.plainText.length > 4000) {
    density.push("正文整体较长，建议为摘要、结论和行动项预留独立位置。");
  }

  if (structure.length === 0) {
    structure.push("结构层级基本可读，但仍建议补充摘要提升进入速度。");
  }

  if (expression.length === 0) {
    expression.push("表达整体稳定，可重点压缩长段落和空泛修饰。");
  }

  if (density.length === 0) {
    density.push("信息密度整体可控，可进一步突出结论与行动项。");
  }

  return {
    structure,
    expression,
    density,
    stats: {
      headings: headings.length,
      paragraphs: paragraphs.length,
      listItems: listItems.length,
      longParagraphs: longParagraphs.length,
      duplicateLines: duplicateLines.length
    }
  };
}

function createSuggestions(documentData, diagnostics, summary) {
  const suggestions = [
    `在文档开头补一段 2~3 句摘要，帮助读者快速进入主题：${summary}`,
    "把超过 120 字的段落拆成短句，并优先改成列表或分点表达。",
    "对每个核心主题增加小标题，保证读者能通过扫读定位信息。"
  ];

  if (documentData.unsupportedElements.length > 0) {
    suggestions.push(
      `文档包含复杂结构：${documentData.unsupportedElements
        .map((item) => `${item.type}×${item.count}`)
        .join("，")}。首轮建议先人工复核这些区域。`
    );
  }

  if (diagnostics.stats.duplicateLines > 0) {
    suggestions.push("合并重复表述，并将相似结论集中到一个段落或列表下。");
  }

  return suggestions;
}

function transformBodyBlocks(documentData) {
  const output = [];

  for (const block of documentData.blocks) {
    if (block.type === "heading") {
      output.push({ type: "heading", text: normalizeLine(block.text) });
      continue;
    }

    if (block.type === "list_item") {
      output.push({
        type: "list_item",
        text: normalizeLine(block.text).replace(/^[-*•]\s*/, "")
      });
      continue;
    }

    if (block.type === "paragraph") {
      const normalized = normalizeLine(block.text);
      const sentences = splitSentences(normalized);

      if (normalized.length >= 140 && sentences.length >= 3) {
        for (const sentence of sentences) {
          output.push({
            type: "list_item",
            text: sentence
          });
        }
        continue;
      }

      output.push({ type: "paragraph", text: normalized });
      continue;
    }

    output.push({ type: "paragraph", text: normalizeLine(block.text) });
  }

  return output;
}

function buildDraft(documentData, recommendedTitle, summary) {
  const transformed = transformBodyBlocks(documentData);
  const markdownLines = [`# ${recommendedTitle}`, "", "## 摘要", summary, "", "## 优化稿", ""];
  const writebackLines = ["摘要", summary, ""];

  for (const block of transformed) {
    if (!block.text) {
      continue;
    }

    if (block.type === "heading") {
      markdownLines.push(`## ${block.text}`, "");
      writebackLines.push(block.text, "");
      continue;
    }

    if (block.type === "list_item") {
      markdownLines.push(`- ${block.text}`);
      writebackLines.push(`- ${block.text}`);
      continue;
    }

    markdownLines.push(block.text, "");
    writebackLines.push(block.text, "");
  }

  return {
    markdown: markdownLines.join("\n").replace(/\n{3,}/g, "\n\n").trim(),
    bodyPlainText: writebackLines.join("\n").replace(/\n{3,}/g, "\n\n").trim()
  };
}

export function optimizeDocument(documentData) {
  const summary = buildSummary(documentData.plainText);
  const recommendedTitle = buildRecommendedTitle(documentData.title, summary);
  const diagnostics = createDiagnostics(documentData);
  const suggestions = createSuggestions(documentData, diagnostics, summary);
  const riskFlags = [];

  if (documentData.unsupportedElements.length > 0) {
    riskFlags.push({
      code: "UNSUPPORTED_BLOCKS",
      severity: "high",
      blockWriteback: true,
      message: `检测到复杂结构：${documentData.unsupportedElements
        .map((item) => `${item.type}×${item.count}`)
        .join("，")}。默认阻断自动写回。`
    });
  }

  if (documentData.plainText.length > 12000) {
    riskFlags.push({
      code: "LONG_DOCUMENT",
      severity: "medium",
      blockWriteback: true,
      message: "文档正文较长，首轮整篇写回风险较高，默认阻断自动写回。"
    });
  }

  if (documentData.stats.blockCount < 3) {
    riskFlags.push({
      code: "LOW_CONFIDENCE_EXTRACTION",
      severity: "high",
      blockWriteback: true,
      message: "抽取块数过少，说明页面结构可能未正确识别，默认阻断自动写回。"
    });
  }

  return {
    recommendedTitle,
    summary,
    diagnostics,
    suggestions,
    riskFlags,
    draft: buildDraft(documentData, recommendedTitle, summary)
  };
}

export function renderAnalysisReport(documentData, analysis, openedDocument) {
  const lines = [
    "# 飞书文档优化报告",
    "",
    `- 标题：${documentData.title}`,
    `- 当前链接：${openedDocument.currentUrl}`,
    `- 推荐标题：${analysis.recommendedTitle}`,
    `- 抽取块数：${documentData.stats.blockCount}`,
    ""
  ];

  lines.push("## 结构诊断", "");
  for (const item of analysis.diagnostics.structure) {
    lines.push(`- ${item}`);
  }

  lines.push("", "## 表达诊断", "");
  for (const item of analysis.diagnostics.expression) {
    lines.push(`- ${item}`);
  }

  lines.push("", "## 信息密度诊断", "");
  for (const item of analysis.diagnostics.density) {
    lines.push(`- ${item}`);
  }

  lines.push("", "## 优化建议", "");
  for (const item of analysis.suggestions) {
    lines.push(`- ${item}`);
  }

  if (analysis.riskFlags.length > 0) {
    lines.push("", "## 风险提示", "");
    for (const item of analysis.riskFlags) {
      lines.push(`- ${item.message}`);
    }
  }

  lines.push("", "## 摘要", "", analysis.summary);
  return lines.join("\n");
}
