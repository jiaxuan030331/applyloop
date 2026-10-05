# Interview Hub

你的模拟面试工作区。默认 **英文面试 / Python / LeetCode / 45 分钟**，面试结束后用中文复盘。

## 开始使用

1. 在 Codex 中打开这个目录，并在该项目内开启聊天。
2. 按 [语音设置](docs/voice-setup.md) 开启 Voice Chat。
3. 说或输入：`Start an LC mock interview.`
4. 面试官创建一个独立 session，给出题目和代码文件位置；你在编辑器中写代码并保存。
5. 说 `Please read my saved code.` 请求检查；说 `End the interview and debrief.` 结束并复盘。

不必开启语音也能使用，文字聊天遵循同样的面试规则。关掉编辑器的 AI 补全，自己设置一个 45 分钟倒计时。

## Modes

| ID | 内容 | 状态 |
| --- | --- | --- |
| `lc` | 算法与数据结构，默认 Python、Medium、一题加 follow-up | Ready |
| `dl` | 深度学习手撕实现 | Planned |
| `bq` | 行为与业务情景题；支持用户提供的 PDF 题库 | Ready |
| `system-design` | 系统设计 | Planned |
| `company` | 公司专项；可组合多个 mode | Planned |

配置入口是 [hub.json](hub.json)，全局面试行为在 [AGENTS.md](AGENTS.md)，每个 mode 有自己的说明。Planned 项只预留结构，不会自动开始面试。

## 常用指令

- `Start an LC mock interview.` — 按默认配置开始。
- `Start a 30-minute LC interview in Python, difficulty Easy.` — 覆盖本场设置。
- `I have seen this problem before. Please replace it.` — 换题。
- `Give me a small hint.` — 获得一级提示，记入复盘。
- `Let me think.` — 留出思考空间。
- `Pause the interview.` / `Resume the interview.` — 暂停 / 恢复。
- `End the interview and debrief.` — 结束、检查代码并复盘。
- `Add the DL mode to this hub.` — 进入 hub 开发流程，不会误启动面试。

## 目录

```text
hub.json                  默认参数和 mode 注册表
AGENTS.md                 面试官行为及 session 流程
docs/voice-setup.md        语音与屏幕设置
modes/<mode>/MODE.md       每种面试的规则
templates/                Session 和复盘模板
modes/lc/sessions/        每次 LC 面试的题目、代码、记录和反馈
```

这是文件驱动的 hub，由项目内的 Codex 聊天执行流程；不需要服务、API key 或额外依赖。增加 mode 时填写对应 MODE.md，再更新 hub.json 中的状态即可。

## 每题归档与面评

每次做题使用独立 session 文件夹；wrap-up 后保留题目、最终代码、过程记录和面评。默认直接编辑该文件夹内的 solution.py；指定其他位置时在结束后归档快照。面评采用六项 1–4 分，加具体证据和最多三条建议，详见 [评分标准](docs/evaluation.md)。

## 总览与 Skill

[LC PROGRESS.md](modes/lc/PROGRESS.md) 记录做过的题、各次面评和粗略总体水平，每次 wrap-up 自动更新。

- `$lc-interview`：准备一道未做过的新题。
- `$lc-interview 239`：准备指定的 LeetCode 239，核实官方题面。
- `$lc-interview resume`：继续未结束的面试。
- `wrap up`：结束本场，归档代码、写面评并更新总览。

Skill 源码保留在 [skills/lc-interview/SKILL.md](skills/lc-interview/SKILL.md)，个人安装副本在 ~/.codex/skills/lc-interview。修改源码后需同步安装副本。

LC 所有题目归档位于 `modes/lc/sessions/`，LC 总体水平与做题索引位于 `modes/lc/PROGRESS.md`。项目根目录继续作为多 mode hub。
