import pytest

from services.persona import PersonaService


class Personality:
    def __init__(self, profile=None, error=None):
        self.profile = profile or {
            "personality": "温和",
            "behavior_style": "自然",
            "reply_style": "短句",
            "private_chat_prompts": "像朋友一样",
        }
        self.error = error
        self.calls = 0
        self.switched = False

    async def get_current(self):
        self.calls += 1
        if self.error:
            raise self.error
        return self.profile

    async def switch(self, name):
        self.switched = True


class Ctx:
    def __init__(self, personality):
        self.personality = personality


@pytest.mark.asyncio
async def test_persona_uses_current_maibot_profile_without_switching():
    personality = Personality()
    service = PersonaService(Ctx(personality))

    prompt = await service.prompt("private")

    assert "温和" in prompt
    assert "像朋友一样" in prompt
    assert not personality.switched


@pytest.mark.asyncio
async def test_persona_is_read_again_for_each_generation():
    personality = Personality()
    service = PersonaService(Ctx(personality))
    await service.prompt("comment")
    personality.profile["personality"] = "直率"
    prompt = await service.prompt("comment")

    assert personality.calls == 2
    assert "直率" in prompt
    assert "温和" not in prompt


@pytest.mark.asyncio
async def test_persona_failure_degrades_to_empty_prompt():
    service = PersonaService(Ctx(Personality(error=RuntimeError("unavailable"))))
    assert await service.prompt("private") == ""
