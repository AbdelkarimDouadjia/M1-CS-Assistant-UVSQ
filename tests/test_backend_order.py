from chatbot_core.llm_backends import generation_llm_order


def test_generation_order_is_gemini_first_then_server_backup() -> None:
    gemini = object()
    compat = object()
    server = object()

    order = generation_llm_order(
        vllm_reachable=True,
        vllm_llm=server,
        openai_compat_llms=[compat],
        tertiary_llm=gemini,
    )

    assert order == [gemini, compat, server]


def test_generation_order_keeps_server_as_last_resort_when_probe_fails() -> None:
    server = object()

    order = generation_llm_order(
        vllm_reachable=False,
        vllm_llm=server,
        openai_compat_llms=[],
        tertiary_llm=None,
    )

    assert order == [server]
