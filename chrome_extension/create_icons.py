"""
Creates simple PNG icons for the Chrome extension.
Run once: python chrome_extension/create_icons.py
"""

import struct
import zlib
import os

def create_png(width, height, color=(96, 165, 250)):
    """Create a simple solid-color PNG."""
    def make_chunk(chunk_type, data):
        chunk = chunk_type + data
        return struct.pack('>I', len(data)) + chunk + struct.pack('>I', zlib.crc32(chunk) & 0xFFFFFFFF)

    # PNG signature
    signature = b'\x89PNG\r\n\x1a\n'

    # IHDR
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr = make_chunk(b'IHDR', ihdr_data)

    # IDAT — raw pixel data
    raw_data = b''
    for y in range(height):
        raw_data += b'\x00'  # filter byte
        for x in range(width):
            # Simple circle with background
            cx, cy = width // 2, height // 2
            r = min(width, height) // 2 - 1
            dx, dy = x - cx, y - cy
            if dx * dx + dy * dy <= r * r:
                raw_data += bytes(color)
            else:
                raw_data += b'\x00\x00\x00'  # transparent (black)

    compressed = zlib.compress(raw_data)
    idat = make_chunk(b'IDAT', compressed)

    # IEND
    iend = make_chunk(b'IEND', b'')

    return signature + ihdr + idat + iend

os.makedirs('chrome_extension', exist_ok=True)

for size in [16, 48, 128]:
    png_data = create_png(size, size, color=(96, 165, 250))  # Seven's accent blue
    path = os.path.join('chrome_extension', f'icon{size}.png')
    with open(path, 'wb') as f:
        f.write(png_data)
    print(f'Created {path} ({len(png_data)} bytes)')

print('Done. Icons created.')