from PIL import Image
from collections import Counter
import sys

try:
    img = Image.open('/Users/songxijun/workspace/otherProject/movie_agent/miniprogram/assets/scroll-to-bottom-icon.png')
    img = img.convert('RGBA')
    pixels = img.getdata()
    colors = []
    for r, g, b, a in pixels:
        if a > 50: # Ignore mostly transparent
            colors.append((r, g, b))

    if not colors:
        print("No opaque pixels found")
    else:
        most_common = Counter(colors).most_common(1)[0][0]
        hex_color = '#{:02x}{:02x}{:02x}'.format(*most_common).upper()
        print(f"Dominant Color: {hex_color}")
except Exception as e:
    print(f"Error: {e}")
