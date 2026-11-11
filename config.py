"""MaiBot 配置模型。所有写操作保持默认安全。"""

from __future__ import annotations

from typing import Literal

from maibot_sdk import Field, PluginConfigBase


class PluginSection(PluginConfigBase):
    __ui_label__ = "插件"
    config_version: str = Field(default="1.0.0", description="配置版本")
    enabled: bool = Field(default=True, description="启用插件")


class DailySection(PluginConfigBase):
    __ui_label__ = "日常"
    per_day: int = Field(default=5, ge=0, le=50, description="每天最多挑选几条；0 关闭自动刷")
    pick_per_round: int = Field(default=2, ge=1, le=5, description="每轮最多挑选几条")
    peak_valley: bool = Field(default=False, description="启用时间窗口自动刷")
    noon: bool = Field(default=True, description="中午 12:00–14:00 窗口")
    night: bool = Field(default=True, description="夜间 00:30–08:30 窗口")
    keywords: list[str] = Field(default_factory=list, description="关注关键词")
    report_level: Literal["full", "brief", "off"] = Field(default="full", description="日报详细程度")
    memory: bool = Field(default=True, description="记录本地事实记忆；不会修改 MaiBot 人设")


class WatchSection(PluginConfigBase):
    __ui_label__ = "刷视频"
    skip_over_min: int = Field(default=60, ge=1, le=600, description="超过该分钟数直接跳过")
    skim_over_min: int = Field(default=5, ge=1, le=120, description="超过该分钟数标记为跳着看")
    watch_before_act: bool = Field(default=True, description="评论或转发前先转写视频")
    watch_seconds: int = Field(default=90, ge=15, le=600, description="最多分析视频前多少秒")
    watch_frames: int = Field(default=10, ge=3, le=48, description="看片抽帧数")


class InteractionSection(PluginConfigBase):
    __ui_label__ = "互动"
    auto_like: bool = Field(default=False, description="自动点赞")
    auto_comment: bool = Field(default=False, description="自动评论并 @ 指定用户")
    mention_name: str = Field(default="", description="评论中 @ 的抖音昵称")
    comment_per_round: int = Field(default=1, ge=0, le=20, description="每轮最多 @ 评论数")
    comment_per_day: int = Field(default=10, ge=0, le=50, description="每天最多 @ 评论数")
    auto_comment_plain: bool = Field(default=False, description="自动发布普通公开评论")
    plain_comment_per_day: int = Field(default=10, ge=0, le=30, description="每天最多普通评论数")
    auto_reply: bool = Field(default=False, description="自动回复自己作品下的评论")
    reply_per_run: int = Field(default=3, ge=0, le=20, description="每次最多回复评论数")
    reply_per_day: int = Field(default=10, ge=0, le=1000, description="每天最多回复评论数")
    reply_random: bool = Field(default=True, description="随机选择评论")
    reply_once_per_user: bool = Field(default=False, description="同一用户只回复一次")
    reply_interval_min: int = Field(default=30, ge=5, le=1440, description="评论与任务巡检间隔（分钟）")
    reply_video_ids: str = Field(default="", description="指定自己作品 ID，逗号分隔")
    reply_one_shot: bool = Field(default=True, description="指定作品回复完成后清空")
    reply_works_days: int = Field(default=3, ge=1, le=90, description="回复最近几天内作品的评论")
    skip_live: bool = Field(default=True, description="跳过直播")
    share_to_nick: str = Field(default="", description="转发视频给谁")
    share_per_day: int = Field(default=10, ge=0, le=50, description="每天最多转发数")
    share_with_note: bool = Field(default=True, description="转发后发送附言和表情包")
    share_note: str = Field(default="", description="固定转发附言；留空由 MaiBot 生成")
    msg_allow_to: str = Field(default="", description="允许主动发私信的昵称，逗号分隔；空为禁止")
    streak_nick: str = Field(default="", description="续火花联系人")
    streak_per_day: int = Field(default=1, ge=0, le=20, description="每天续火花次数")
    ask_doubao: bool = Field(default=False, description="遇到不懂的视频时 @ 豆包")
    my_nickname: str = Field(default="", description="自己的抖音昵称；留空自动识别")


class DmSection(PluginConfigBase):
    __ui_label__ = "私信"
    dm_reply: bool = Field(default=False, description="自动回复陌生人私信")
    dm_auto_reply: bool = Field(default=True, description="后台回复白名单私信；仍需配置允许联系人")
    dm_reply_only_to: str = Field(default="", description="只回复哪些联系人，逗号分隔；空不限")
    dm_auto_interval_sec: int = Field(default=15, ge=5, le=120, description="私信巡检间隔（秒）")
    dm_reply_per_contact: int = Field(default=1, ge=1, le=10, description="每个联系人每天最多回复数")
    dm_reply_per_day: int = Field(default=5, ge=0, le=100, description="每天私信回复总数")


class StickerSection(PluginConfigBase):
    __ui_label__ = "表情包"
    library_dirs: list[str] = Field(default_factory=list, description="本地表情图库目录")
    streak_sticker: str = Field(default="大肥鱼", description="续火花表情包关键词")
    fallback_keyword: str = Field(default="666", description="找不到表情时的兜底关键词")


class AdvancedSection(PluginConfigBase):
    __ui_label__ = "高级"
    python_path: str = Field(default="python", description="运行浏览器内核的 Python")
    cdp_url: str = Field(default="", description="留空使用插件独立浏览器 profile")
    cdp_port: int = Field(default=9222, ge=1024, le=65535, description="Chrome 调试端口")
    chrome_path: str = Field(default="", description="Chrome 可执行文件路径；留空自动探测")
    auto_clean: bool = Field(default=True, description="每天自动清理临时文件")
    comfy_url: str = Field(default="http://127.0.0.1:8188", description="ComfyUI 地址")
    comfy_output_dir: str = Field(default="", description="ComfyUI 输出目录")
    comfy_workflow: str = Field(default="", description="可选工作流 JSON 或文件路径")
    comfy_wait_seconds: int = Field(default=900, ge=30, le=7200, description="等待出片秒数")
    comfy_list_limit: int = Field(default=20, ge=1, le=200, description="成片列表条数")


class PublishSection(PluginConfigBase):
    __ui_label__ = "投稿"
    auto_publish: bool = Field(default=False, description="允许自动投稿")
    publish_per_day: int = Field(default=1, ge=0, le=20, description="每天最多投稿数")
    publish_draft: bool = Field(default=True, description="默认只保存草稿")
    publish_title: str = Field(default="", description="标题模板，可使用 {date}")
    publish_tags: str = Field(default="", description="默认话题")


class DouyinLifeConfig(PluginConfigBase):
    plugin: PluginSection = Field(default_factory=PluginSection)
    daily: DailySection = Field(default_factory=DailySection)
    watch: WatchSection = Field(default_factory=WatchSection)
    interaction: InteractionSection = Field(default_factory=InteractionSection)
    dm: DmSection = Field(default_factory=DmSection)
    sticker: StickerSection = Field(default_factory=StickerSection)
    advanced: AdvancedSection = Field(default_factory=AdvancedSection)
    publish: PublishSection = Field(default_factory=PublishSection)
