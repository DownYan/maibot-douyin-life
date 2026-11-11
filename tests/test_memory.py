from services.memory import MemoryStore


def test_memory_appends_facts_without_creating_persona_file(tmp_path):
    store = MemoryStore(tmp_path)
    store.add("视频 v1：作者分享了猫")
    store.add("私信：对方说晚安")

    assert store.recent(1) == ["私信：对方说晚安"]
    assert len(list((tmp_path / "memory").glob("*.md"))) == 1
    assert not (tmp_path / "persona.md").exists()
