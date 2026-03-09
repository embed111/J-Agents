# WeChat 低风险自动模式（Ever）

## 目录
- `config.json`：目标联系人、自动回复模板、轮询间隔、冷却时间
- `wechat_low_risk_watcher.py`：通知监听 + 固定模板自动回复
- `state.json`：运行状态（已处理通知 ID、上次发送时间）
- `watcher.log`：运行日志
- `STOP`：停止信号（创建此文件即可停止）

## 启动
```powershell
.\.venv\Scripts\python .\wechat_low_risk_watcher.py
```

## 停止
```powershell
New-Item -ItemType File -Path .\STOP -Force
```

## 约束
- 仅对 `target_contact` 生效
- 只发固定模板，不做自由生成
- 冷却时间内不重复发送
- 监听命中不确定时不发送（宁漏勿错）
