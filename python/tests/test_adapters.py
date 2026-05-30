from __future__ import annotations

import httpx
import respx

from cryptomem.adapters.ollama_adapter import OllamaAdapter


@respx.mock
def test_ollama_adapter_complete_parses_response():
    route = respx.post("http://localhost:11434/api/generate").mock(
        return_value=httpx.Response(200, json={"response": "Budget was $4.2M.", "done": True})
    )
    adapter = OllamaAdapter(base_url="http://localhost:11434", model="qwen2.5:0.5b")
    out = adapter.complete("What was the budget?")
    assert route.called
    assert out == "Budget was $4.2M."


@respx.mock
def test_ollama_adapter_is_alive():
    respx.get("http://localhost:11434/api/tags").mock(
        return_value=httpx.Response(200, json={"models": []})
    )
    assert OllamaAdapter().is_alive() is True


@respx.mock
def test_ollama_adapter_is_alive_false_on_error():
    respx.get("http://localhost:11434/api/tags").mock(side_effect=httpx.ConnectError("down"))
    assert OllamaAdapter().is_alive() is False
