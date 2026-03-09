# 长期偏好评审日志

## 规则
1. 触发条件：任一长期偏好文件超过 200 行。
2. 评审动作：
   1. 保留跨话题稳定偏好在长期主档；
   2. 将阶段性/主题性条目降级到短期偏好池。
3. 结果记录：
   1. 记录触发文件、评审结论、迁移文件、迁移原因。

## 2026-03-03 首次评审
1. 触发文件：
   1. `user_profile/core/thinking-patterns-domain-requirements.md`（276 行，超限）。
2. 评审结论：
   1. 保留“场景特征/决策偏好/对应执行策略/待验证问题”等长期稳定主干。
   2. 将四个增量专题块降级到短期偏好池。
3. 降级去向：
   1. `user_profile/core/thinking-patterns-short-term.md`（A/B/C/D 四个专题块）。
4. 评审后状态：
   1. `thinking-patterns-domain-requirements.md` 降至 200 行内。
5. 备注：
   1. 后续若短期条目跨 2 个独立话题复现，可按规则回升到长期主档。

