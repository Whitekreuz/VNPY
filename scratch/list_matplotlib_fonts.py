# -*- coding: utf-8 -*-
import matplotlib.font_manager as fm

# Find all installed fonts that might support Chinese
print("Searching for CJK/Chinese fonts in matplotlib font manager...")
available_fonts = []
for font in fm.fontManager.ttflist:
    name = font.name
    # Keep track of unique names
    if name not in available_fonts:
        available_fonts.append(name)

# Print fonts containing typical Chinese font names
keywords = ["hei", "yahei", "sim", "song", "kai", "ming", "st", "deng", "fang", "gothic", "yu", "ms"]
chinese_fonts = []
for f in available_fonts:
    if any(k in f.lower() for k in keywords):
        chinese_fonts.append(f)

print("Detected potential CJK/Chinese fonts:")
for cf in sorted(chinese_fonts):
    print(f" - {cf}")
