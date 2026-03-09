# Startup Checklist

## 启动前必查
1. [x] 当前主题限定为“单篇飞书文档优化”
2. [x] 不修改 `C:\work\agents\Analyst` 与 `C:\work\agents\workflow`
3. [x] 已读取需求文档：
   1. [x] `docs/agents/README.md`
   2. [x] `docs/agents/feishu-doc-optimizer/需求概述.md`
   3. [x] `docs/agents/feishu-doc-optimizer/需求详情-单篇飞书文档优化闭环.md`
   4. [x] `docs/agents/feishu-doc-optimizer/需求详情-浏览器自动化与写回安全.md`
4. [x] 已建立治理基线：
   1. [x] `AGENTS.md`
   2. [x] `workspace_state/目录导读.md`
   3. [x] `workspace_state/core/session-snapshot.md`
   4. [x] `user_profile/目录导读.md`

## 运行前检查
1. [x] Node.js 依赖已安装：`npm install`
2. [ ] 已准备 Edge / Chrome 已登录飞书会话
3. [ ] 若使用 CDP 模式，浏览器已通过 `--remote-debugging-port` 启动
4. [ ] 若使用 profile 模式，目标浏览器实例已关闭，避免 profile 锁冲突
5. [ ] 已确认本轮目标文档为单篇 Wiki / Doc 链接

## 首轮闭环完成标准
1. [ ] `doctor` 能附着到浏览器会话
2. [ ] `optimize` 能成功输出标题、结构化抽取和诊断结果
3. [x] `workspace_state/runs/` 下生成运行留痕
4. [x] `--writeback` 路径具备人工确认门禁
5. [x] 复杂结构、登录失效、页面切换会阻断写回

## 当前验证结果
1. [x] `npm run help` 可正常输出命令说明
2. [x] `npm run doctor -- --browser edge --session-mode cdp --cdp-url http://127.0.0.1:9222` 在未启动调试浏览器时能明确返回 `ECONNREFUSED`
3. [x] 优化层本地 smoke test 已通过，能生成建议与草稿
4. [x] 已通过 UI fallback 成功读取真实飞书单篇文档正文
5. [ ] 待把真实读取结果接回结构化抽取与优化链路，完成自动化闭环验证
