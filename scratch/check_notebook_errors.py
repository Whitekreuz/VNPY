# -*- coding: utf-8 -*-
import json

with open("test_backtest_analysis.ipynb", "r", encoding="utf-8") as f:
    nb = json.load(f)

has_error = False
for idx, cell in enumerate(nb.get("cells", [])):
    if cell.get("cell_type") == "code":
        # Check if there is any error in outputs
        for output in cell.get("outputs", []):
            if output.get("output_type") == "error":
                print(f"[ERROR] Cell {idx} failed: {output.get('ename')}: {output.get('evalue')}")
                # print lines safely
                for line in output.get("traceback", []):
                    try:
                        print(line)
                    except Exception:
                        pass
                has_error = True

if not has_error:
    print("[SUCCESS] All cells executed successfully with no errors!")
