from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1]))
from live2d_expressions import discover_live2d_expressions


model = Path(__file__).parents[1] / "models" / "live2d" / "MIU2022_vts" / "miu2022.model3.json"
expressions = discover_live2d_expressions(model)
assert len(expressions) == 11, f"Expected all 11 MIU2022 expressions, got {len(expressions)}"
assert {item["Name"] for item in expressions} >= {"爱心眼", "黑化", "脸红", "流泪"}
assert all((model.parent / item["File"]).is_file() for item in expressions)
print("PASS: MIU2022's unreferenced VTube Studio expression files are discovered and labeled")
