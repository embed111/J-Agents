# workflow 文档目录说明

## 1. 目录分层
1. `overview/`
   1. 需求主索引与历史增量索引。
2. `requirements/`
   1. 需求详情文档（按主题拆分）。
3. `design/`
   1. 详细设计文档（与需求主题对应）。
4. `governance/`
   1. 执行门禁、验收证据、截图规范、启动留痕、治理清单。
5. `reports/`
   1. 重构映射与行数预算等分析报告。
6. `prompts/`
   1. 执行提示词与提示词管理说明。

## 2. 当前主入口
1. 主入口：`docs/workflow/overview/需求概述.md`
2. 历史增量：`docs/workflow/overview/需求概述-增量历史-20260225-20260304.md`

## 3. 命名与治理约束
1. 新增需求文档优先放入 `requirements/` 或 `design/`，禁止再回到根目录扁平堆叠。
2. `Phase0` 类历史文件保留为 `legacy_keep`，不直接删除。
3. 所有活动文档必须在 `docs/workflow/overview/需求概述.md` 中有可追溯索引。

