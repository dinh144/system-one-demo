from __future__ import annotations

import os
import sys
import types
import unittest
from unittest.mock import patch

from backend.engines import Engine


class CpuPrecisionTests(unittest.TestCase):
    def test_laya_cpu_load_disables_optional_bfloat16_environment_override(self) -> None:
        seen_environment: list[str | None] = []
        laya_module = types.ModuleType("laya")

        def fake_router(*, preload: bool, device: str):
            seen_environment.append(os.environ.get("LAYA_CPU_AMP"))
            self.assertTrue(preload)
            self.assertEqual(device, "cpu")
            return object()

        laya_module.Router = fake_router
        with patch.dict(os.environ, {"LAYA_CPU_AMP": "bf16"}), patch.dict(
            sys.modules,
            {"laya": laya_module},
        ):
            engine = Engine("laya")
            self.assertEqual(engine.device, "cpu")
            engine._load()

        self.assertEqual(seen_environment, [None])


if __name__ == "__main__":
    unittest.main()
