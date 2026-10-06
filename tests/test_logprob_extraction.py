from __future__ import annotations

import math
import unittest

from backend.engines import _top_boolean_logprobs


class LogprobExtractionTests(unittest.TestCase):
    def test_prefers_boolean_tokens_with_the_sampled_json_whitespace(self) -> None:
        entry = {
            "token": " false",
            "top_logprobs": [
                {"token": " false", "logprob": -0.11050731688737869},
                {"token": " true", "logprob": -2.259719133377075},
                {"token": "false", "logprob": -11.322657585144043},
            ],
        }

        lp_true, lp_false = _top_boolean_logprobs(entry)
        self.assertAlmostEqual(lp_true, -2.259719133377075)
        self.assertAlmostEqual(lp_false, -0.11050731688737869)
        p_true = math.exp(lp_true) / (math.exp(lp_true) + math.exp(lp_false))
        self.assertLess(p_true, 0.5)


if __name__ == "__main__":
    unittest.main()
