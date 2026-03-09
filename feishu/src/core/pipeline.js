import { createBrowserSession } from "../browser/browserSession.js";
import { openFeishuDocument } from "../browser/feishuDoc.js";
import { extractStructuredDocument } from "../extract/structuredExtractor.js";
import { createRunLogger } from "../logging/runLogger.js";
import {
  optimizeDocument,
  renderAnalysisReport
} from "../optimize/ruleBasedOptimizer.js";
import {
  applyWriteback,
  requestWritebackConfirmation
} from "../writeback/manualWriteback.js";

function serializeError(error) {
  return {
    message: error instanceof Error ? error.message : String(error),
    stack: error instanceof Error ? error.stack : ""
  };
}

function blockedByRisk(analysis) {
  return analysis.riskFlags.find((item) => item.blockWriteback);
}

export async function runDoctor(options) {
  const logger = await createRunLogger({
    command: "doctor",
    outputDir: options.outputDir,
    url: "",
    browser: options.browser,
    sessionMode: options.sessionMode
  });

  let session;

  try {
    session = await createBrowserSession(options, logger);
    const pageUrls = session.context
      .pages()
      .filter((page) => !page.isClosed())
      .map((page) => page.url())
      .filter(Boolean)
      .slice(0, 5);
    const diagnosis = {
      attached: true,
      browser: options.browser,
      sessionMode: options.sessionMode,
      pageCount: session.context.pages().length,
      samplePages: pageUrls,
      hint: pageUrls.some((item) => /feishu|larksuite/i.test(item))
        ? "已检测到飞书相关页面，可以直接进入 optimize。"
        : "已附着浏览器，但未检测到飞书页面；请确认你在该浏览器中已登录飞书。"
    };

    await logger.writeJson("doctor.json", diagnosis);
    await logger.finalize("success", diagnosis);

    return {
      logger,
      diagnosis
    };
  } catch (error) {
    const serialized = serializeError(error);
    await logger.writeJson("error.json", serialized).catch(() => undefined);
    await logger.finalize("failed", { error: serialized }).catch(() => undefined);
    throw error;
  } finally {
    await session?.close?.().catch(() => undefined);
  }
}

export async function runOptimize(options) {
  const logger = await createRunLogger({
    command: "optimize",
    outputDir: options.outputDir,
    url: options.url,
    browser: options.browser,
    sessionMode: options.sessionMode
  });

  let session;

  try {
    session = await createBrowserSession(options, logger);
    const openedDocument = await openFeishuDocument(session.page, options.url, options, logger);
    const documentData = await extractStructuredDocument(session.page);
    const analysis = optimizeDocument(documentData);

    await logger.writeJson("document.json", documentData);
    await logger.writeJson("analysis.json", analysis);
    await logger.writeText(
      "report.md",
      renderAnalysisReport(documentData, analysis, openedDocument)
    );
    await logger.writeText("draft.md", analysis.draft.markdown);

    let writeback = {
      status: "not_requested",
      reason: "未传入 --writeback，仅生成分析结果和草稿。"
    };

    if (options.writeback) {
      const blockingRisk = blockedByRisk(analysis);

      if (blockingRisk && !options.allowUnsupportedWriteback) {
        writeback = {
          status: "blocked",
          reason: blockingRisk.message
        };
      } else {
        const confirmation = await requestWritebackConfirmation({
          title: documentData.title,
          documentUrl: openedDocument.currentUrl,
          replacementScope: "正文主体整篇替换，标题最佳努力更新"
        });

        if (!confirmation.confirmed) {
          writeback = {
            status: "cancelled",
            reason: confirmation.reason
          };
        } else {
          writeback = await applyWriteback(
            session.page,
            {
              sourceUrl: openedDocument.currentUrl,
              currentTitle: documentData.title,
              recommendedTitle: analysis.recommendedTitle,
              bodyPlainText: analysis.draft.bodyPlainText
            },
            logger
          );
        }
      }
    }

    await logger.writeJson("writeback.json", writeback);
    await logger.finalize("success", {
      documentTitle: documentData.title,
      currentUrl: openedDocument.currentUrl,
      writebackStatus: writeback.status
    });

    return {
      logger,
      openedDocument,
      documentData,
      analysis,
      writeback
    };
  } catch (error) {
    const serialized = serializeError(error);
    await logger.writeJson("error.json", serialized).catch(() => undefined);
    await logger.finalize("failed", { error: serialized }).catch(() => undefined);
    throw error;
  } finally {
    await session?.close?.().catch(() => undefined);
  }
}
