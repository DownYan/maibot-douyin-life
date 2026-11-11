from plugin import DouyinLifePlugin


EXPECTED = {
    "dy_status", "dy_config", "dy_whoami", "dy_feed", "dy_hot", "dy_hot_videos", "dy_search",
    "dy_video", "dy_comments", "dy_my_posts", "dy_my_videos", "dy_thumb", "dy_comfy_list",
    "dy_remember", "dy_like", "dy_comment", "dy_share", "dy_chat_send", "dy_chat_sticker",
    "dy_dm_inbox", "dy_dm_poll", "dy_dm_round", "dy_reply_round", "dy_reply", "dy_publish",
    "dy_run", "dy_selfcheck", "dy_cleanup", "dy_chrome_open", "dy_login_start", "dy_login_poll",
    "dy_login_sms", "dy_login_sms_submit", "dy_watch", "dy_reconcile_pending",
}


def test_all_35_original_tools_are_registered_once():
    plugin = DouyinLifePlugin()
    tools = [item for item in plugin.get_components() if item["type"].upper() == "TOOL"]
    names = [item["name"] for item in tools]

    assert len(names) == 35
    assert len(names) == len(set(names))
    assert set(names) == EXPECTED
