import json

with open('config/futures_symbols.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

lines = ['{']
keys = list(data.keys())
for i, k in enumerate(keys):
    v = data[k]
    lines.append(f'    "{k}": {{')
    lines.append(f'        "description": "{v["description"]}",')
    lines.append('        "symbols": {')
    sym_keys = list(v['symbols'].keys())
    for j, sk in enumerate(sym_keys):
        sv = v['symbols'][sk]
        sv['continuous'] = ["88", "888", "99"]
        line = f'            "{sk}": {json.dumps(sv, ensure_ascii=False)}'
        if j < len(sym_keys) - 1:
            line += ','
        lines.append(line)
    lines.append('        }')
    if i < len(keys) - 1:
        lines.append('    },')
    else:
        lines.append('    }')
lines.append('}')

with open('config/futures_symbols.json', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
