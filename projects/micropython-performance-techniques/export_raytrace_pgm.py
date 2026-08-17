"""Render the native sphere and export its pixels as a binary PGM file."""

from raytrace_native import HEIGHT, WIDTH, render_native


pixels = bytearray(WIDTH * HEIGHT)
hits = render_native(pixels, WIDTH, HEIGHT)
pixel_sum = sum(pixels)

if hits != 1481 or pixel_sum != 323731:
    raise RuntimeError("unexpected rendered image")

with open("/remote/results/raytrace-native-pico2w.pgm", "wb") as output:
    output.write(b"P5\n64 48\n255\n")
    output.write(pixels)

print("EXPORT,width,%d" % WIDTH)
print("EXPORT,height,%d" % HEIGHT)
print("EXPORT,hits,%d" % hits)
print("EXPORT,pixel_sum,%d" % pixel_sum)
