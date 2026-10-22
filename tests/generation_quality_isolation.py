"""Fixtures for lower-level generation guards, independently of the retrieval gate.

The strict gate itself is exercised without these mocks in test_response_evidence.
These older unit tests intentionally inject drafts to exercise repetition,
persona and prompt formatting even though factual drafts no longer reach them
in a normal request.
"""
from unittest.mock import patch


class GenerationQualityIsolation:
    def setUp(self):
        super().setUp()
        for target, value in [('response_evidence.retrieve', None),
                              ('response_evidence.medium_conversation', False),
                              ('response_evidence.generated_reply_allowed', True),
                              ('response_evidence.strict_answer', None)]:
            item=patch(target,return_value=value)
            item.start()
            self.addCleanup(item.stop)
