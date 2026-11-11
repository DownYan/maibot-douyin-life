# MaiBot 刷抖音插件

将 [cixinshang/dsh-douyin-life-plus](https://github.com/cixinshang/dsh-douyin-life-plus) 的浏览器与视频理解内核移植为独立 MaiBot SDK 插件。宿主层不再依赖 DSH、Harness、Node.js 或独立人设文件。

## 功能

- 35 个 `dy_*` 工具：推荐流、热榜、搜索、视频信息、评论、看片、私信、登录、环境自检等。
- 自动刷视频：过滤直播和超长视频，转写、抽帧、写日报，并按授权进行一种主要互动。
- 私信与评论巡检：白名单、只回名单、每日/每轮限额、消息去重。
- 续火花、表情包、转发附言、ComfyUI 工作流出片与投稿。
- 配置页提供二维码、自检和立即运行控件。
- 本地原子账本记录真实回执；`pending` / `unknown` 不算成功，也不会被自动重发。

## 人设行为

评论、私信和转发附言在**每次生成前**调用 `ctx.personality.get_current()`，读取 MaiBot 当前人设；私聊还会使用当前人设的私聊字段。插件不会缓存或切换人设，也不会创建 `persona.md` 或提供 `personaPrompt` 配置。

视频、评论和私信正文均作为不可信素材放入提示词，不能修改人设或指示插件绕过安全闸门。

## 环境与安装

要求：

- Python 3.10+。
- MaiBot SDK 2.20+（离线开发测试使用 2.22.1）。
- 支持 Manifest v2 和配置页控件的 MaiBot Host。
- Google Chrome；视频理解需要 `ffmpeg` 与 `ffprobe` 在 PATH 中。
- 首次语音转写可能需要联网下载 faster-whisper 模型。

将整个 `maibot-douyin-life` 文件夹复制到 MaiBot 的 `plugins/` 目录，然后给**高级设置中 `advanced.python_path` 指向的 Python**安装依赖：

```powershell
python -m pip install -r plugins/maibot-douyin-life/requirements.txt
```

如果 MaiBot Runner 使用另一个虚拟环境，还需要在该环境安装 `maibot-plugin-sdk>=2.20,<3`。无需安装原项目的 npm 依赖，也不要启动 DSH CLI。

重启或热重载插件。首次运行由 Host 生成 `config.toml`；也可以在 WebUI 修改配置。本源码包不包含任何账号、二维码或配置文件。

## 登录与首次检查

1. 在配置页点击“生成登录二维码”，或调用 `dy_login_start`。
2. 用抖音 App 扫码，再调用 `dy_login_poll` 确认。
3. 调用 `dy_whoami` 检查账号，`dy_selfcheck` 检查环境。
4. 先使用 `dy_feed`、`dy_search` 和 `dy_watch` 验证只读链路。

默认使用插件独立浏览器登录态。高级设置可指定 `chrome_path`，或填写已有 Chrome 的 `cdp_url`；`dy_chrome_open` 可启动带调试端口的 Chrome。不要同时使用多个程序写同一个浏览器 profile。

## 安全默认值

以下写操作默认关闭：

- 自动点赞：`interaction.auto_like`
- @ 评论：`interaction.auto_comment`，同时必须设置 `mention_name`
- 普通评论：`interaction.auto_comment_plain`
- 自己作品的评论回复：`interaction.auto_reply`
- 自动投稿：`publish.auto_publish`，且 `publish.publish_draft` 默认为 `true`

主动私信、表情和转发要求联系人精确包含在 `interaction.msg_allow_to`。白名单私信回复由 `dm.dm_auto_reply` 控制；陌生人回复必须另行开启 `dm.dm_reply`，也可通过 `dm.dm_reply_only_to` 限定范围。

手动写工具中的 `force=true` 仅表示用户当次明确授权，后台任务始终忽略 force。请谨慎开启，自行遵守平台规则并控制频率。

`dy_reconcile_pending` 只核对已有未知评论回执，不会重新发送。`dy_cleanup` 只清理临时媒体、过期缩略图、日报和日志，不删除浏览器登录态、账本或事实记忆。

## 自动任务

- `daily.per_day=0` 关闭自动刷视频；手动 `dy_run` 仍可进行只读浏览。
- 开启 `daily.peak_valley` 后，仅在启用的中午或夜间窗口刷视频。
- 私信、评论、续火花和刷视频使用异步任务与随机间隔；卸载或配置更新会取消旧任务。
- 日报写入插件数据目录的 `out/YYYY-MM-DD.md`，事实记忆写入 `memory/YYYY-MM.md`。
- `daily.report_level=off` 可关闭日报，`daily.memory=false` 可关闭事实记忆。

## ComfyUI 与投稿

在高级设置填写：

- `comfy_url`，默认 `http://127.0.0.1:8188`
- `comfy_output_dir`，即 ComfyUI 的 output 目录
- 可选 `comfy_workflow`：工作流 JSON 文本或 JSON 文件路径

`dy_comfy_list` 只列真实存在的 `.mp4`。配置工作流后，`dy_publish(latest=true)` 会提交 `/prompt` 并轮询本次 `prompt_id` 的 `/history/<id>`；只接受本次工作流唯一、有效的 MP4，不会把其他旧成片当成结果。输出路径必须位于配置的 output 目录内。

## 数据位置

长期数据写入 `ctx.paths.data_dir`，进程临时目录写入 `ctx.paths.runtime_dir`。浏览器登录态、账本和记忆由 Host 管理路径，不写入源码包。

## 测试与验收边界

在仓库工作区运行：

```powershell
.venv/Scripts/python -m pytest maibot-douyin-life/tests -v
.venv/Scripts/python -m compileall -q maibot-douyin-life
```

测试使用假 MCP、假 LLM 和临时目录，不需要真实抖音账号。当前交付仅通过离线单元测试与语法检查；**尚未在真实 MaiBot Host 中加载，也未使用真实抖音账号验证登录、点赞、评论、私信或投稿**。Manifest 已按官方 Manifest v2 文档整理，但仍需以实际 Host 校验结果为准。

## 来源与许可

原项目：TiAmoSS；改版来源：cixinshang。保留 MIT License，详见 `LICENSE`。浏览器内核及视频理解原型来自上述仓库，MaiBot 宿主层为本次移植实现。
