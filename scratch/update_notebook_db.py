# -*- coding: utf-8 -*-
import json

notebook_path = "test_comparison.ipynb"

with open(notebook_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

updated = False
for cell in nb.get("cells", []):
    if cell.get("cell_type") == "code":
        source = cell.get("source", [])
        new_source = []
        for line in source:
            if "PG_DBNAME_PROD" in line and "quant_db_prod" in line:
                line = line.replace("PG_DBNAME_PROD", "PG_DBNAME_TEST").replace("quant_db_prod", "quant_db_test")
                updated = True
            new_source.append(line)
        cell["source"] = new_source

if updated:
    with open(notebook_path, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
    print("Successfully updated test_comparison.ipynb to use quant_db_test!")
else:
    print("No matching lines found in test_comparison.ipynb.")
