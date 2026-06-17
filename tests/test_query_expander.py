from chatbot_core.query_expander import parse_query_variants


def test_parse_query_variants_strips_numbering_and_dedupes() -> None:
    raw = """
    1. Quand a lieu le jury du S1 ?
    2) Date du jury du semestre 1
    - Quand a lieu le jury du S1 ?
    [3] Calendrier du jury S1
    """

    variants = parse_query_variants(raw, max_variants=5)

    assert variants == [
        "Quand a lieu le jury du S1 ?",
        "Date du jury du semestre 1",
        "Calendrier du jury S1",
    ]
