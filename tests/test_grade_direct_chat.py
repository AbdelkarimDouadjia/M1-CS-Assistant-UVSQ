from chatbot_core.grade_calculator import calculate_grade_response, is_grade_query


def test_direct_grade_query_accepts_short_labels_without_tool_call() -> None:
    question = (
        "Calcule ma moyenne S1 AMIS avec "
        "bd 12, reseaux 13, crypto 14, graphes 15, maths 16, "
        "complexite 17, complement prog 18, ro 11"
    )

    assert is_grade_query(question)

    response, details = calculate_grade_response(question)

    assert "Moyenne S1 (AMIS)" in response
    assert "Bases de données avancées" in response
    assert "Réseaux et systèmes" in response
    assert "Cryptographie" in response
    assert "UEs renseignées: 8/8" in details
