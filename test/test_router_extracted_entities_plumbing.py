import unittest


class TestRouterExtractedEntitiesPlumbing(unittest.TestCase):
    def test_invoke_router_graph_preserves_extracted_entities(self) -> None:
        # Regression: router LLM may extract entities, but the orchestrator state graph
        # must not drop them (downstream enrichment relies on this).
        import infrastructure.routing.orchestrator.router_graph as router_graph

        class _DummyRoutingInfo:
            confidence = 0.9
            method = "llm"
            reason = "dummy"
            extracted_entities = {"low_level": ["喜宴"], "high_level": ["电影", "导演信息"]}

        def _dummy_route_kb_prefix(message: str, requested_kb_prefix=None):
            _ = (message, requested_kb_prefix)
            return "movie", _DummyRoutingInfo()

        old = router_graph.route_kb_prefix
        try:
            router_graph.KB_AUTO_ROUTE = True
            router_graph.route_kb_prefix = _dummy_route_kb_prefix
            decision = router_graph.invoke_router_graph(
                message="喜宴 导演是谁？",
                session_id="s1",
                requested_kb_prefix=None,
            )
            self.assertEqual(
                decision.extracted_entities,
                {"low_level": ["喜宴"], "high_level": ["电影", "导演信息"]},
            )
        finally:
            router_graph.route_kb_prefix = old
