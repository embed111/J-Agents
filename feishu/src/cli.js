#!/usr/bin/env node

import { runDoctor, runOptimize } from "./core/pipeline.js";
import { getUsageText, parseCli } from "./utils/args.js";

function printDoctorResult(result) {
  console.log("浏览器会话检查完成。");
  console.log(`运行目录：${result.logger.runDir}`);
  console.log(`附着状态：${result.diagnosis.attached ? "成功" : "失败"}`);
  console.log(`页面数量：${result.diagnosis.pageCount}`);
  console.log(`提示：${result.diagnosis.hint}`);
}

function printOptimizeResult(result) {
  console.log("飞书文档优化完成。");
  console.log(`运行目录：${result.logger.runDir}`);
  console.log(`文档标题：${result.documentData.title}`);
  console.log(`当前链接：${result.openedDocument.currentUrl}`);
  console.log(`推荐标题：${result.analysis.recommendedTitle}`);
  console.log("结构诊断：");
  for (const item of result.analysis.diagnostics.structure) {
    console.log(`- ${item}`);
  }
  console.log("表达诊断：");
  for (const item of result.analysis.diagnostics.expression) {
    console.log(`- ${item}`);
  }
  console.log("信息密度诊断：");
  for (const item of result.analysis.diagnostics.density) {
    console.log(`- ${item}`);
  }
  console.log(`写回状态：${result.writeback.status}`);
  if (result.writeback.reason) {
    console.log(`写回说明：${result.writeback.reason}`);
  }
}

async function main() {
  const parsed = parseCli(process.argv, process.env);

  if (parsed.command === "help") {
    console.log(getUsageText());
    return;
  }

  try {
    if (parsed.command === "doctor") {
      const result = await runDoctor(parsed.options);
      printDoctorResult(result);
      return;
    }

    if (parsed.command === "optimize") {
      if (!parsed.options.url) {
        throw new Error("optimize 命令缺少 --url。");
      }

      const result = await runOptimize(parsed.options);
      printOptimizeResult(result);
      return;
    }

    throw new Error(`未知命令：${parsed.command}`);
  } catch (error) {
    console.error(
      error instanceof Error ? `执行失败：${error.message}` : `执行失败：${String(error)}`
    );
    process.exitCode = 1;
  }
}

await main();
