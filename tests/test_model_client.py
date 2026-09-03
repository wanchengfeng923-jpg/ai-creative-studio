import unittest
from dataclasses import is_dataclass, FrozenInstanceError
from types import SimpleNamespace

from creative_studio.model_client import (
    HttpModelClient,
    ModelClient,
    ModelRequest,
    ModelResponse,
)


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


class ModelClientTests(unittest.TestCase):
    def test_model_request_and_response_are_frozen_and_generic(self) -> None:
        self.assertTrue(is_dataclass(ModelRequest))
        self.assertTrue(ModelRequest.__dataclass_params__.frozen)
        self.assertTrue(is_dataclass(ModelResponse))
        self.assertTrue(ModelResponse.__dataclass_params__.frozen)

        request_fields = set(ModelRequest.__dataclass_fields__)
        response_fields = set(ModelResponse.__dataclass_fields__)
        self.assertEqual(
            request_fields,
            {"model", "messages", "response_format", "max_tokens", "conversation_id", "parent_message_id"},
        )
        self.assertEqual(
            response_fields,
            {
                "content",
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "conversation_id",
                "assistant_message_id",
                "latency_ms",
            },
        )

        with self.assertRaises(FrozenInstanceError):
            ModelRequest(model="x", messages=[], response_format=None, max_tokens=1, conversation_id="", parent_message_id="").model = "y"

    def test_http_client_builds_generic_payload_and_maps_response(self) -> None:
        response = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "choices": [
                    {
                        "message": {"content": "hello"},
                    }
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
                "conversation_id": "conv-1",
                "assistant_message_id": "msg-2",
            },
        )
        transport = FakeTransport([response])
        client = HttpModelClient(
            api_url="https://example.com/v1/chat/completions",
            api_key="secret",
            transport=transport,
        )
        result = client.generate(
            ModelRequest(
                model="gpt-test",
                messages=[{"role": "user", "content": "hi"}],
                response_format={"type": "json_object"},
                max_tokens=99,
                conversation_id="conv-1",
                parent_message_id="msg-0",
            )
        )

        self.assertIsInstance(result, ModelResponse)
        self.assertEqual(result.content, "hello")
        self.assertEqual(result.input_tokens, 3)
        self.assertEqual(result.output_tokens, 5)
        self.assertEqual(result.total_tokens, 8)
        self.assertEqual(result.conversation_id, "conv-1")
        self.assertEqual(result.assistant_message_id, "msg-2")
        self.assertGreaterEqual(result.latency_ms, 0)
        self.assertEqual(len(transport.calls), 1)
        url, kwargs = transport.calls[0]
        self.assertEqual(url, "https://example.com/v1/chat/completions")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer secret")
        self.assertEqual(
            kwargs["json"],
            {
                "model": "gpt-test",
                "messages": [{"role": "user", "content": "hi"}],
                "response_format": {"type": "json_object"},
                "max_tokens": 99,
                "conversation_id": "conv-1",
                "parent_message_id": "msg-0",
            },
        )

    def test_http_client_rejects_malformed_choices_with_exact_field_path(self) -> None:
        cases = (
            ({"choices": []}, "choices"),
            ({"choices": [{}]}, "choices[0].message.content"),
        )

        for payload, expected_path in cases:
            with self.subTest(expected_path=expected_path):
                response = SimpleNamespace(
                    raise_for_status=lambda: None,
                    json=lambda: payload,
                )
                client = HttpModelClient(
                    api_url="https://example.invalid/v1/chat/completions",
                    api_key="fake-test-key",
                    transport=FakeTransport([response]),
                )

                with self.assertRaises(Exception) as raised:
                    client.generate(
                        ModelRequest(
                            model="fake-test-model",
                            messages=[{"role": "user", "content": "test"}],
                            response_format={"type": "json_object"},
                            max_tokens=10,
                        )
                    )

                self.assertEqual(type(raised.exception).__name__, "ModelResponseFormatError")
                self.assertEqual(raised.exception.field_path, expected_path)


if __name__ == "__main__":
    unittest.main()
