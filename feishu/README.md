# 飞书文档优化 Agent

面向“单篇飞书文档优化”的最小可跑通实现，主链路固定为浏览器自动化，并复用本机已登录飞书会话。

## 首轮收敛结果
1. 目标范围：单篇飞书 Wiki / Doc 文档读取、分析、优化稿生成、人工确认后写回。
2. 主链路：Node.js + `playwright-core`，优先通过 CDP 附着到已登录的 Edge / Chrome 会话。
3. 风险门禁：
   1. 不保存账号密码。
   2. 未确认不写回。
   3. 检测到复杂结构、登录失效、页面切换或 DOM 异常时中断写回。
4. 首轮策略：先支持“整篇正文替换”的最小闭环，复杂块默认只读分析，不自动改写。

## 目录规划
1. `docs/agents/feishu-doc-optimizer/`：需求输入，不直接改写其主题边界。
2. `src/`：运行时代码。
3. `workspace_state/`：阶段状态、运行日志、单次执行留痕。
4. `user_profile/`：本地使用偏好与稳定假设。
5. `scripts/`：后续如需补充本机辅助脚本，统一放在这里。

## 首轮实现覆盖
1. 文档链接输入与页面打开
2. 已登录浏览器会话复用
3. 正文抓取与结构化提取
4. 优化建议生成层
5. 人工确认后写回
6. 日志与风险保护

## 环境要求
1. Node.js 24+
2. 本机已安装 Edge 或 Chrome
3. 飞书登录态已存在于本机浏览器

## 安装
```bash
npm install
```

## 推荐运行方式
第一轮推荐使用 CDP 模式，先手动启动一个带远程调试端口的浏览器窗口，然后让 agent 附着：

```powershell
msedge.exe --remote-debugging-port=9222
```

如果使用 Chrome：

```powershell
chrome.exe --remote-debugging-port=9222
```

随后在该浏览器窗口中完成飞书登录，再运行：

```bash
npm run doctor -- --browser edge --session-mode cdp --cdp-url http://127.0.0.1:9222
npm run optimize -- --browser edge --session-mode cdp --cdp-url http://127.0.0.1:9222 --url "https://xxx.feishu.cn/docx/xxxx"
```

如果你明确要尝试直接使用本地 profile，并且该浏览器实例已关闭，可用：

```bash
npm run optimize -- --browser edge --session-mode profile --user-data-dir "C:\Users\<you>\AppData\Local\Microsoft\Edge\User Data" --profile-directory "Default" --url "https://xxx.feishu.cn/docx/xxxx"
```

## 写回执行
默认只执行读取、分析和生成草稿。

需要写回时，增加 `--writeback`：

```bash
npm run optimize -- --browser edge --session-mode cdp --cdp-url http://127.0.0.1:9222 --url "https://xxx.feishu.cn/docx/xxxx" --writeback
```

写回前会：
1. 再次展示目标文档标题与链接
2. 明确提示替换范围为“正文主体整篇替换”
3. 要求人工在命令行输入确认信息

## 如何验证“单篇飞书文档优化闭环”已跑通
1. 启动已登录飞书的 Edge / Chrome 调试窗口。
2. 运行 `doctor`，确认 agent 能附着到浏览器会话。
3. 运行 `optimize` 并传入一篇你有权限的飞书文档链接。
4. 检查 `workspace_state/runs/<run-id>/` 中是否生成：
   1. `document.json`
   2. `analysis.json`
   3. `report.md`
   4. `draft.md`
5. 终端中应看到：
   1. 页面标题
   2. 结构 / 表达 / 信息密度三类诊断
   3. 优化建议
   4. 草稿输出路径
6. 追加 `--writeback` 后再次运行：
   1. 若未输入确认信息，不发生写回
   2. 若输入确认信息且页面结构安全，正文被替换，`writeback.json` 记录结果

## 当前已知限制
1. 表格、折叠块、嵌入内容、图片与代码块默认视为复杂结构；出现时允许分析，但默认阻断自动写回。
2. 写回策略当前是“正文主体整篇替换”，不是块级精确 patch。
3. 标题写回为最佳努力；若定位不到标题编辑区域，会保留原始标题并在日志中提示。
4. 首轮优化层为规则驱动，不依赖外部 LLM。
