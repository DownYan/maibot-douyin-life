"""原 DSH 35 个工具的 MaiBot SDK 声明。"""

STRING = "string"
INTEGER = "integer"
BOOLEAN = "boolean"


def _schema(description, **parameters):
    return {"description": description, "parameters": parameters}


TOOL_SCHEMAS = {
    "dy_status": _schema("查看今日额度、任务、登录与报告状态"),
    "dy_config": _schema("读取 MaiBot 中的插件配置；修改请在 WebUI 完成"),
    "dy_whoami": _schema("查看当前抖音登录账号"),
    "dy_feed": _schema("读取抖音推荐流", num={"type": INTEGER}, scrolls={"type": INTEGER}),
    "dy_hot": _schema("读取抖音热榜", limit={"type": INTEGER}),
    "dy_hot_videos": _schema("读取热点下的视频", sentence_id={"type": STRING}, word={"type": STRING}, num={"type": INTEGER}),
    "dy_search": _schema("搜索抖音视频", keyword={"type": STRING}, num={"type": INTEGER}, order={"type": STRING}),
    "dy_video": _schema("读取单条视频信息", aweme_id={"type": STRING}),
    "dy_comments": _schema("读取视频评论", aweme_id={"type": STRING}, num={"type": INTEGER}),
    "dy_my_posts": _schema("读取自己最近投稿", days={"type": INTEGER}),
    "dy_my_videos": _schema("读取插件投稿账本"),
    "dy_thumb": _schema("截取视频缩略图", aweme_id={"type": STRING}),
    "dy_comfy_list": _schema("列出 ComfyUI 最近成片", limit={"type": INTEGER}),
    "dy_remember": _schema("写入一条本地事实记忆，不会修改人设", line={"type": STRING}),
    "dy_like": _schema("点赞或取消点赞；受安全闸门控制", aweme_id={"type": STRING}, undo={"type": BOOLEAN}, force={"type": BOOLEAN}),
    "dy_comment": _schema("发布评论或回复；受安全闸门与额度控制", aweme_id={"type": STRING}, text={"type": STRING}, reply_cid={"type": STRING}, force={"type": BOOLEAN}),
    "dy_share": _schema("转发视频给白名单联系人", aweme_id={"type": STRING}, to={"type": STRING}, title={"type": STRING}, force={"type": BOOLEAN}),
    "dy_chat_send": _schema("给白名单联系人发送私信", nickname={"type": STRING}, text={"type": STRING}, force={"type": BOOLEAN}),
    "dy_chat_sticker": _schema("给白名单联系人发送表情包", nickname={"type": STRING}, keyword={"type": STRING}, pick={"type": INTEGER}, flip={"type": INTEGER}, force={"type": BOOLEAN}),
    "dy_dm_inbox": _schema("只读私信收件箱", limit={"type": INTEGER}, nickname={"type": STRING}),
    "dy_dm_poll": _schema("立即巡检一次白名单私信"),
    "dy_dm_round": _schema("按陌生人私信设置巡检并回复"),
    "dy_reply_round": _schema("巡检并回复自己作品下的新评论", count={"type": INTEGER}, random={"type": BOOLEAN}),
    "dy_reply": _schema("回复自己作品下的一条评论", aweme_id={"type": STRING}, cid={"type": STRING}, text={"type": STRING}, comment={"type": STRING}, force={"type": BOOLEAN}),
    "dy_publish": _schema("投稿或保存草稿；默认草稿并受安全闸门控制", video_path={"type": STRING}, latest={"type": BOOLEAN}, title={"type": STRING}, tags={"type": STRING}, draft={"type": BOOLEAN}, force={"type": BOOLEAN}),
    "dy_run": _schema("立即刷一轮推荐、看片、按授权互动并写日报"),
    "dy_selfcheck": _schema("检查浏览器内核、登录和搜索环境"),
    "dy_cleanup": _schema("清理临时文件和过期缓存，不动登录态", thumbDays={"type": INTEGER}, reportDays={"type": INTEGER}),
    "dy_chrome_open": _schema("打开带 CDP 调试端口的 Chrome", port={"type": INTEGER}),
    "dy_login_start": _schema("生成抖音扫码登录二维码"),
    "dy_login_poll": _schema("查询扫码登录状态"),
    "dy_login_sms": _schema("向本人确认过的手机号发送登录验证码", phone={"type": STRING}),
    "dy_login_sms_submit": _schema("提交本人提供的短信验证码", code={"type": STRING}),
    "dy_watch": _schema("下载、抽帧并转写一条视频", aweme_id={"type": STRING}, seconds={"type": INTEGER}, frames={"type": INTEGER}),
    "dy_reconcile_pending": _schema("核对状态未知的评论回复回执，不重新发送", limit={"type": INTEGER}),
}
