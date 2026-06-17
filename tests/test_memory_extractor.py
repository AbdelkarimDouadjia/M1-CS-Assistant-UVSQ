from chatbot_core.memory_extractor import _apply_facts, extract_facts


def test_name_memory_can_be_overridden() -> None:
    profile = _apply_facts("", extract_facts("my name is Abdelkarim"))

    facts = extract_facts("my new name is Riadh", existing_profile=profile)
    updated = _apply_facts(profile, facts)

    assert "Nom : Riadh" in updated
    assert "Nom : Abdelkarim" not in updated


def test_french_name_memory_can_be_overridden() -> None:
    profile = _apply_facts("", extract_facts("je m'appelle Abdelkarim"))

    facts = extract_facts("mon nouveau nom est Riadh", existing_profile=profile)
    updated = _apply_facts(profile, facts)

    assert "Nom : Riadh" in updated
    assert "Nom : Abdelkarim" not in updated
