import pytest

from maibot_sdk.config_widgets import ConfigWidgetSnapshot
from plugin import DouyinLifePlugin


@pytest.mark.asyncio
async def test_config_widgets_have_complete_state():
    plugin = DouyinLifePlugin()
    states = await plugin.get_config_widget_state()
    snapshot = ConfigWidgetSnapshot(widgets=plugin.config_widgets, states=states)
    assert {widget.id for widget in snapshot.widgets} == {"login", "qr", "selfcheck", "run"}
    assert set(states) == {"login", "qr", "selfcheck", "run"}


@pytest.mark.asyncio
async def test_unknown_widget_action_is_rejected():
    plugin = DouyinLifePlugin()
    with pytest.raises(ValueError):
        await plugin.on_config_widget_action("unknown")
