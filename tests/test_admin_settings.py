import os

from chatbot_core.admin_settings import default_settings


def test_rerasker_env_alias_controls_query_expansion() -> None:
    old_query = os.environ.get("QUERY_EXPANSION_ENABLED")
    old_rerasker = os.environ.get("RERASKER_ENABLED")
    old_variants = os.environ.get("RERASKER_MAX_VARIANTS")
    try:
        os.environ.pop("QUERY_EXPANSION_ENABLED", None)
        os.environ["RERASKER_ENABLED"] = "true"
        os.environ["RERASKER_MAX_VARIANTS"] = "4"

        settings = default_settings()

        assert settings["query_expansion_enabled"] is True
        assert settings["query_expansion_max_variants"] == 4
    finally:
        if old_query is None:
            os.environ.pop("QUERY_EXPANSION_ENABLED", None)
        else:
            os.environ["QUERY_EXPANSION_ENABLED"] = old_query
        if old_rerasker is None:
            os.environ.pop("RERASKER_ENABLED", None)
        else:
            os.environ["RERASKER_ENABLED"] = old_rerasker
        if old_variants is None:
            os.environ.pop("RERASKER_MAX_VARIANTS", None)
        else:
            os.environ["RERASKER_MAX_VARIANTS"] = old_variants
