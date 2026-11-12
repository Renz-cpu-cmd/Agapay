"""Render the AGAPAY OLED pages on the PC with the real firmware renderer (no ESP32, no upload).

  python tools/oled_preview.py --u8g2 <U8g2 Arduino library dir> [--cxx "python -m ziglang c++"]

Builds U8g2's C library + src/oled_render.cpp + tools/oled_preview.cpp, runs the display-model
host tests (tests/oled_model_test.cpp), and writes 4x-scale PNG mockups to docs/oled-mockups/.
"""
import argparse
import concurrent.futures
import os
import shlex
import struct
import subprocess
import sys
import zlib
from pathlib import Path

firmware = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--u8g2", required=True, type=Path, help="U8g2 library folder (contains src/clib)")
parser.add_argument("--cxx", default=os.environ.get("CXX", "c++"))
parser.add_argument("--cc", default=os.environ.get("CC"))
parser.add_argument("--out", type=Path, default=firmware / "docs/oled-mockups")
parser.add_argument("--arduinojson", type=Path)
args = parser.parse_args()
clib = args.u8g2 / "src" / "clib"
if not (clib / "u8g2.h").is_file():
    raise SystemExit("U8g2 clib not found under " + str(clib))
cxx = shlex.split(args.cxx)
cc = shlex.split(args.cc) if args.cc else [*cxx[:-1], cxx[-1].replace("c++", "cc")]
build = firmware / ".pio" / "oled-host"
(build / "obj").mkdir(parents=True, exist_ok=True)
exe = ".exe" if os.name == "nt" else ""


def run(command):
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise SystemExit("FAILED: " + " ".join(map(str, command[:6])) + "\n" + (result.stdout + result.stderr)[-4000:])


# 1. Display-model host tests (pure logic, strict warnings).
test = build / ("oled_model_test" + exe)
run([*cxx, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I" + str(firmware / "include"),
     str(firmware / "tests/oled_model_test.cpp"), "-o", str(test)])
result = subprocess.run([str(test)], capture_output=True, text=True)
print(result.stdout.strip() or result.stderr.strip())
if result.returncode:
    raise SystemExit(result.returncode)
json_include = args.arduinojson or firmware / ".pio/libdeps/esp32doit-devkit-v1/ArduinoJson/src"
if not json_include.is_dir():
    raise SystemExit("ArduinoJson not found: run python -m platformio run -d agapay-firmware first, or pass --arduinojson")
forecast_test = build / ("forecast_message_test" + exe)
run([*cxx, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I" + str(firmware / "include"), "-I" + str(json_include),
     str(firmware / "tests/forecast_message_test.cpp"), "-o", str(forecast_test)])
result = subprocess.run([str(forecast_test)], capture_output=True, text=True)
print(result.stdout.strip() or result.stderr.strip())
if result.returncode:
    raise SystemExit(result.returncode)

# 2. U8g2 C library objects (cached).
def compile_c(source):
    target = build / "obj" / (source.stem + ".o")
    if not target.exists() or target.stat().st_mtime < source.stat().st_mtime:
        run([*cc, "-c", "-O1", "-w", "-I" + str(clib), str(source), "-o", str(target)])
    return target
with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as pool:
    objects = list(pool.map(compile_c, sorted(clib.glob("*.c"))))

# 3. Real renderer + preview scenarios.
preview = build / ("oled_preview" + exe)
run([*cxx, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I" + str(firmware / "include"), "-I" + str(clib),
     str(firmware / "src/oled_render.cpp"), str(firmware / "tools/oled_preview.cpp"), *map(str, objects), "-o", str(preview)])
frames_file = build / "frames.bin"
run([str(preview), str(frames_file)])


def png(path, width, height, rows):
    raw = b"".join(b"\x00" + bytes(row) for row in rows)
    chunk = lambda tag, data: struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


SCALE, ON, OFF, GAP = 4, (205, 235, 255), (8, 10, 14), (2, 3, 5)


def pixels(buffer):  # SH1106 full buffer: 8 pages x 128 columns, LSB = top pixel
    return [[(buffer[(y // 8) * 128 + x] >> (y % 8)) & 1 for x in range(128)] for y in range(64)]


def scaled(grid, border=6):
    width, height = 128 * SCALE + 2 * border, 64 * SCALE + 2 * border
    rows = []
    for py in range(height):
        row = []
        for px in range(width):
            x, y = (px - border) // SCALE, (py - border) // SCALE
            if not (0 <= x < 128 and 0 <= y < 64):
                row.extend(OFF)
            elif (px - border) % SCALE == SCALE - 1 or (py - border) % SCALE == SCALE - 1:
                row.extend(GAP)  # subtle pixel grid, like a real OLED
            else:
                row.extend(ON if grid[y][x] else OFF)
        rows.append(row)
    return width, height, rows


data = frames_file.read_bytes()
args.out.mkdir(parents=True, exist_ok=True)
frames, offset = [], 0
while offset < len(data):
    end = data.index(b"\n", offset)
    name = data[offset:end].decode()
    frames.append((name, pixels(data[end + 1:end + 1025])))
    offset = end + 1025
for name, grid in frames:
    png(args.out / f"{name}.png", *scaled(grid))
# Contact sheet: 4 columns.
cell_w, cell_h = 128 * SCALE + 12, 64 * SCALE + 12
columns, pad = 4, 10
rows_n = (len(frames) + columns - 1) // columns
sheet_w, sheet_h = columns * cell_w + (columns + 1) * pad, rows_n * cell_h + (rows_n + 1) * pad
sheet = [[30, 32, 36] * sheet_w for _ in range(sheet_h)]
for index, (_, grid) in enumerate(frames):
    _, _, cell = scaled(grid)
    ox, oy = pad + (index % columns) * (cell_w + pad), pad + (index // columns) * (cell_h + pad)
    for y, row in enumerate(cell):
        sheet[oy + y][ox * 3:(ox + cell_w) * 3] = row
png(args.out / "contact-sheet.png", sheet_w, sheet_h, sheet)
print(f"rendered {len(frames)} frames -> {args.out}")
