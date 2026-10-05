# 语音面试设置

核对日期：2026-09-27。下面是官方文档描述的入口；具体是否可用取决于客户端、账号开放状态和工作区设置。本机入口与麦克风尚未实测。

## 1. 开启实时语音

1. 在桌面应用中打开 `mock_interview` 项目下的聊天。
2. 找到 **Start voice chat**。新聊天可能显示 **Start new voice chat**。
3. 首次使用时允许麦克风权限，并选择声音。
4. 可在 **Settings → Voice → Voice chat hotkey** 配置快捷键。
5. 结束时选择 **Stop voice chat**。

要选择实时 **Voice Chat**。**Voice dictation** 只将讲话转成待发送文字，不是实时双向通话。

如果已有聊天没有入口，官方建议更新桌面应用与运行任务的 Codex host，并检查账号/工作区是否开放。支持的情况下可从新语音聊天开始；否则先使用文字模式。官方列出的订阅包括 Plus、Pro、Business、Edu、Enterprise；不要仅凭订阅就假定所有入口都已开放。同时只能有一个活动语音聊天。

## 2. 让面试官看到代码

推荐使用本地文件：

1. 面试开始后，在编辑器打开该 session 的 `solution.py`。
2. 关闭 AI 补全，自己写代码；在需要检查时保存。
3. 说：**“Please read my saved code.”**

面试官会按需读取已保存文件；不会自动看到未保存修改，也不会持续监看每次输入。

可选开启屏幕上下文：

1. 在 macOS 的 **Settings → Voice → Screen context** 开启功能。
2. 按系统提示完成屏幕录制及辅助功能权限。
3. 把代码编辑器放到前台，说 **“Take a look at this.”**

屏幕上下文通过前台窗口 appshot 提供截图和可访问文字，是按需捕获。Appshot 可能包含窗口滚动区域以外的文字。分享前把需要讨论的编辑器窗口放到前台。

## 3. 面试前做一个简短检查

- 戴耳机，确认输入设备正确。
- 说：**“This is an audio check. Please repeat: hash map, deque, and O of n log n.”**
- 请求读取一个已保存文件，确认代码交流顺畅。
- 如果打算使用屏幕上下文，说 **“Take a look at this and tell me which window you can see.”** 验证实际捕获结果。
- 自己设好 45 分钟倒计时，准备好后再开始。

## 4. 开场指令

> Start an LC mock interview using this hub's defaults: English, Python, Medium, 45 minutes. Follow AGENTS.md and the LC mode instructions. Ask one question at a time. Do not edit my solution or reveal hints unless I request them. Let me think when I ask for time. Confirm readiness before presenting the problem and starting the interview. Debrief in Chinese after we finish.

思考时说 **“Let me think for a moment; I'll tell you when I'm ready.”**；暂停说 **“Pause the interview.”**；结束说 **“End the interview and debrief.”**。语音系统可能仍会误判停顿，这些约定不能保证完全控制其轮次检测。

## 官方来源

- [ChatGPT Voice：开启方式、可用性、快捷键和屏幕上下文](https://learn.chatgpt.com/docs/features/voice)
- [Appshots：窗口捕获范围与权限](https://learn.chatgpt.com/docs/appshots)
