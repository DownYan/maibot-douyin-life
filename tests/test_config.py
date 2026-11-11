from config import DouyinLifeConfig


def test_safe_defaults_and_no_plugin_persona_field():
    config = DouyinLifeConfig()

    assert config.plugin.config_version == "1.0.0"
    assert config.interaction.auto_like is False
    assert config.interaction.auto_comment is False
    assert config.interaction.auto_comment_plain is False
    assert config.interaction.auto_reply is False
    assert config.publish.auto_publish is False
    assert config.publish.publish_draft is True
    assert "personaPrompt" not in type(config.daily).model_fields


def test_dsh_only_fields_are_not_exposed():
    fields = set(DouyinLifeConfig().model_dump().get("advanced", {}))
    assert not {"dshBin", "headlessProfile", "headlessModel", "overlayMcp", "workspace", "localRound"} & fields
