import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import unittest
from unittest.mock import patch


class _FakeSpan:
    def __init__(self) -> None:
        self.ended = False
        self.end_kwargs = None

    def end(self, **kwargs):
        self.ended = True
        self.end_kwargs = kwargs


class _FakeParent:
    def __init__(self) -> None:
        self.span_obj = _FakeSpan()

    def span(self, **_kwargs):
        return self.span_obj


class _FakeChain:
    def __or__(self, _other):
        # Ignore the output parser stage.
        return self

    async def astream_events(self, _payload, **_kwargs):
        # Match the on_parser_stream path used in completion.py.
        yield {"event": "on_parser_stream", "data": {"chunk": "OK"}}


class _FakePrompt:
    def __or__(self, _llm):
        return _FakeChain()


class TestGenerateGeneralAnswerStreamRegression(unittest.IsolatedAsyncioTestCase):
    async def test_success_path_does_not_raise_unboundlocal(self):
        # Regression test: `error_message` must be initialized even when the
        # stream succeeds, because Langfuse span finalization references it.
        from infrastructure.llm import completion as mod

        parent = _FakeParent()

        with patch.object(mod, "_build_general_prompt", return_value=_FakePrompt()), patch.object(
            mod, "get_stream_llm_model", return_value=object()
        ), patch.object(mod, "get_current_langfuse_stateful_client", return_value=parent), patch.object(
            mod, "get_langfuse_callback", return_value=None
        ):
            out = []
            async for chunk in mod.generate_general_answer_stream(question="hi"):
                out.append(chunk)

        self.assertEqual("".join(out), "OK")
        self.assertTrue(parent.span_obj.ended)
        # Success path should not mark the span as error.
        self.assertIsNone(parent.span_obj.end_kwargs.get("level"))

