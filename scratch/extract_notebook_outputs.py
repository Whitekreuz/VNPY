# -*- coding: utf-8 -*-
import json

with open("test_backtest_analysis.ipynb", "r", encoding="utf-8") as f:
    nb = json.load(f)

for idx, cell in enumerate(nb.get("cells", [])):
    if cell.get("cell_type") == "code":
        print(f"\n--- Cell {idx} ---")
        
        for output in cell.get("outputs", []):
            if output.get("output_type") == "stream":
                text = "".join(output.get("text", []))
                # replace checkmark emoji or cross emoji
                text_clean = text.replace("\u2705", "[OK]").replace("\u274c", "[FAIL]").replace("\u26a0\ufe0f", "[WARN]")
                try:
                    print(text_clean.strip())
                except Exception:
                    # absolute fallback for any other characters
                    print(text_clean.encode("ascii", errors="replace").decode("ascii"))
            elif output.get("output_type") == "display_data":
                data = output.get("data", {})
                if "image/png" in data:
                    print("[Image Output]")
                elif "text/plain" in data:
                    text_plain = "".join(data.get("text/plain", []))
                    print(text_plain.strip())
            elif output.get("output_type") == "execute_result":
                data = output.get("data", {})
                if "text/plain" in data:
                    text_plain = "".join(data.get("text/plain", []))
                    print(text_plain.strip())
