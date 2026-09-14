import json
import sys
import unittest
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parents[1]))

from incident_lens.config import Settings
from incident_lens.provider import (
    DeterministicFallbackGenerator,
    OpenAICompatibleProvider,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderValidationError,
    UnknownCitationError,
    build_answer_generator,
)


PASSAGES = [
    {"source_id": "source-a", "source_version": "docs@1", "text": "Compare traces and metrics in the same window."},
    {"source_id": "source-b", "source_version": "docs@1", "text": "Use logs to correlate a trace context."},
]


def settings(**overrides):
    values = dict(
        provider_api_key="unit-test-secret",
        provider_base_url="https://provider.example",
        provider_model="test-model",
        provider_timeout_seconds=0.2,
        provider_max_input_tokens=120,
        provider_max_context_tokens=60,
        provider_max_output_tokens=40,
        provider_max_retries=1,
    )
    values.update(overrides)
    return Settings(**values)


class Phase4ProviderTests(unittest.TestCase):
    def test_valid_grounding_is_structured_and_bounded(self):
        seen = {}

        def handler(request):
            seen["url"] = str(request.url)
            seen["headers"] = dict(request.headers)
            seen["payload"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {
                                "content": json.dumps(
                                    {
                                        "claim": "The cited guidance supports checking correlated signals.",
                                        "uncertainty": "This does not establish a root cause.",
                                        "citation_source_ids": ["source-a"],
                                        "next_checks": ["Inspect the matching trace."],
                                    }
                                )
                            }
                        }
                    ]
                },
                request=request,
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        answer = OpenAICompatibleProvider(settings(), http_client=client).generate("What should I check?", PASSAGES)
        self.assertEqual(answer.mode, "provider")
        self.assertEqual(answer.citation_source_ids, ["source-a"])
        self.assertEqual(seen["url"], "https://provider.example/chat/completions")
        self.assertEqual(seen["payload"]["max_tokens"], 40)
        self.assertEqual(seen["payload"]["thinking"], {"type": "disabled"})
        self.assertNotIn("unit-test-secret", seen["payload"].__repr__())
        self.assertEqual(seen["headers"]["authorization"], "Bearer unit-test-secret")

    def test_thinking_option_can_be_omitted_for_another_compatible_provider(self):
        seen = {}

        def handler(request):
            seen["payload"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({
                    "claim": "The passage supports a bounded check.",
                    "uncertainty": "This is not causal proof.",
                    "citation_source_ids": ["source-a"],
                    "next_checks": [],
                })}}]},
                request=request,
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        OpenAICompatibleProvider(settings(provider_disable_thinking=False), http_client=client).generate("question", PASSAGES)
        self.assertNotIn("thinking", seen["payload"])

    def test_unknown_citation_is_rejected(self):
        def handler(request):
            return httpx.Response(
                200,
                json={
                    "choices": [{"finish_reason": "stop", "message": {"content": json.dumps({
                        "claim": "A claim",
                        "uncertainty": "Uncertain",
                        "citation_source_ids": ["not-retrieved"],
                        "next_checks": [],
                    })}}]
                },
                request=request,
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        with self.assertRaises(UnknownCitationError):
            OpenAICompatibleProvider(settings(), http_client=client).generate("question", PASSAGES)

    def test_empty_citations_are_rejected(self):
        def handler(request):
            return httpx.Response(
                200,
                json={"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({
                    "claim": "A claim",
                    "uncertainty": "Uncertain",
                    "citation_source_ids": [],
                    "next_checks": [],
                })}}]},
                request=request,
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        with self.assertRaises(ProviderValidationError):
            OpenAICompatibleProvider(settings(), http_client=client).generate("question", PASSAGES)

    def test_non_stop_termination_is_rejected(self):
        def handler(request):
            return httpx.Response(
                200,
                json={"choices": [{"finish_reason": "length", "message": {"content": json.dumps({
                    "claim": "A claim",
                    "uncertainty": "Uncertain",
                    "citation_source_ids": ["source-a"],
                    "next_checks": [],
                })}}]},
                request=request,
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        with self.assertRaises(ProviderValidationError):
            OpenAICompatibleProvider(settings(), http_client=client).generate("question", PASSAGES)

    def test_response_tool_call_is_rejected(self):
        def handler(request):
            return httpx.Response(
                200,
                json={"choices": [{"finish_reason": "stop", "message": {
                    "content": json.dumps({
                        "claim": "A claim",
                        "uncertainty": "Uncertain",
                        "citation_source_ids": ["source-a"],
                        "next_checks": [],
                    }),
                    "tool_calls": [{"id": "tool-1"}],
                }}]},
                request=request,
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        with self.assertRaises(ProviderValidationError):
            OpenAICompatibleProvider(settings(), http_client=client).generate("question", PASSAGES)

    def test_empty_or_truncated_structured_response_fails(self):
        def handler(request):
            return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": "{"}}]}, request=request)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        with self.assertRaises(ProviderValidationError):
            OpenAICompatibleProvider(settings(), http_client=client).generate("question", PASSAGES)

    def test_timeout_retries_are_bounded_and_safe(self):
        class TimeoutClient:
            calls = 0

            def post(self, *args, **kwargs):
                self.calls += 1
                raise httpx.ReadTimeout("contains-unit-test-secret", request=httpx.Request("POST", args[0]))

        client = TimeoutClient()
        with self.assertRaises(ProviderTimeoutError) as caught:
            OpenAICompatibleProvider(settings(), http_client=client).generate("question", PASSAGES)
        self.assertEqual(client.calls, 2)
        self.assertNotIn("unit-test-secret", str(caught.exception))

    def test_provider_error_retries_transient_status_and_fails_without_fallback(self):
        class ErrorClient:
            calls = 0

            def post(self, *args, **kwargs):
                self.calls += 1
                return httpx.Response(503, request=httpx.Request("POST", args[0]))

        client = ErrorClient()
        with self.assertRaises(ProviderResponseError):
            OpenAICompatibleProvider(settings(), http_client=client).generate("question", PASSAGES)
        self.assertEqual(client.calls, 2)

    def test_no_key_uses_explicit_non_provider_fallback(self):
        generator = build_answer_generator(Settings())
        self.assertIsInstance(generator, DeterministicFallbackGenerator)
        answer = generator.generate("question", PASSAGES)
        self.assertEqual(answer.mode, "deterministic_non_provider_fallback")
        self.assertEqual(answer.provider_status, "not_configured")
        self.assertIn("not fresh AI inference", answer.claim)

    def test_forbidden_tool_shape_is_not_accepted(self):
        def handler(request):
            return httpx.Response(
                200,
                json={"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({
                    "claim": "A claim",
                    "uncertainty": "Uncertain",
                    "citation_source_ids": ["source-a"],
                    "next_checks": [],
                    "tool_calls": [{"name": "shell"}],
                })}}]},
                request=request,
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        with self.assertRaises(ProviderValidationError):
            OpenAICompatibleProvider(settings(), http_client=client).generate("question", PASSAGES)


if __name__ == "__main__":
    unittest.main()
