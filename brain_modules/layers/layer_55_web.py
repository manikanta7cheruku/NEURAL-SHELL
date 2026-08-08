"""
=============================================================================
LAYER 5.5: WEB SEARCH

Runs DuckDuckGo search for questions needing live data
(weather, news, prices, scores, current events).

Writes results to ctx.web_context. Sets ctx.web_searched = True
so LLM layer knows to trust web results over its training data.

Adds user's city to weather queries automatically.
=============================================================================
"""

from colorama import Fore
from brain_modules.layer_result import LayerResult


_WEATHER_WORDS = [
    "weather", "temperature", "forecast", "rain",
    "sunny", "cloudy", "humidity", "wind"
]

_NEWS_WORDS = ["news", "latest", "happened", "breaking", "update"]


def process(ctx, deps):
    if (ctx.is_command or ctx.is_greeting or ctx.is_action_cmd
            or "VISUAL_REPORT:" in ctx.prompt_text):
        return LayerResult.pass_through()

    config = deps.get("config")

    try:
        from web.classifier import needs_web_search
        from web.core       import web_search, web_news

        should_search, search_query = needs_web_search(ctx.prompt_text)

        if not (should_search and search_query):
            return LayerResult.pass_through()

        # Add location to weather queries
        _is_weather = any(w in search_query.lower() for w in _WEATHER_WORDS)
        if _is_weather and "in " not in search_query.lower():
            try:
                _city = config.KEY.get("identity", {}).get("city", "")
                if not _city:
                    _city = config.KEY.get("identity", {}).get("location", "")
                if _city:
                    search_query = f"weather in {_city} today"
                else:
                    search_query = "current weather today"
            except Exception:
                pass

        print(Fore.CYAN + f"[BRAIN] Web search: '{search_query}'")

        _timeout     = config.KEY.get("web", {}).get("timeout", 5)
        _max_results = config.KEY.get("web", {}).get("max_results", 2)
        _is_news     = any(w in ctx.clean_in for w in _NEWS_WORDS)

        # Weather needs only 1 result — the current conditions.
        # More results add noise and inflate response length.
        if _is_weather:
            _max_results = 1

        ctx.web_context = (
            web_news(search_query, max_results=_max_results, timeout=_timeout)
            if _is_news
            else web_search(search_query, max_results=_max_results, timeout=_timeout)
        )

        if ctx.web_context:
            ctx.web_searched = True
            print(Fore.GREEN + "[BRAIN] Web results injected.")

    except Exception:
        pass

    return LayerResult.pass_through()