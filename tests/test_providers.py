from kira.providers import OnlineMangaProvider

def test_search_manga_metadata_online():
    meta = OnlineMangaProvider.search_manga_metadata("Monster")
    assert meta is not None
    assert meta["title"] == "Monster"
    assert "Urasawa" in meta["author"]
    assert meta["cover_url"] is not None


def test_fetch_volume_chapter_mapping_online():
    mapping = OnlineMangaProvider.fetch_volume_chapter_mapping("Fullmetal Alchemist")
    assert mapping is not None
    assert 1 in mapping
    assert len(mapping[1]) > 0
