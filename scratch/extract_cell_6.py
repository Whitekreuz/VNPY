# -*- coding: utf-8 -*-
import json

with open("test_backtest_analysis.ipynb", "r", encoding="utf-8") as f:
    nb = json.load(f)

# Find cell 6
for idx, cell in enumerate(nb.get("cells", [])):
    source_str = "".join(cell.get("source", ""))
    if "calculate_statistics" in source_str or idx == 6:
        print(f"--- Cell {idx} outputs ---")
        for output in cell.get("outputs", []):
            if output.get("output_type") == "stream":
                text = "".join(output.get("text", []))
                # strip non-ascii
                text_clean = text.encode("ascii", errors="replace").decode("ascii")
                print(text_clean)
