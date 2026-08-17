"""Compare bytecode and native emitters with a small integer ray tracer."""

import gc
import machine
import micropython
import os
import sys
import time


WIDTH = 64
HEIGHT = 48
SAMPLES = 11
PRINT_FRAME = False
PRINT_PREVIEW = True


def render_bytecode(pixels, width, height):
    camera_z = 300
    sphere_radius = 120
    focal_length = 100
    sphere_term = camera_z * camera_z - sphere_radius * sphere_radius
    camera_focal = camera_z * focal_length
    camera_focal_squared = camera_focal * camera_focal
    index = 0
    hits = 0
    y = 0
    while y < height:
        ray_y = y * 2 - height
        x = 0
        while x < width:
            ray_x = x * 2 - width
            ray_length_squared = (
                ray_x * ray_x
                + ray_y * ray_y
                + focal_length * focal_length
            )
            discriminant = (
                camera_focal_squared - ray_length_squared * sphere_term
            )
            if discriminant > 0:
                remainder = discriminant
                root = 0
                bit = 1 << 30
                while bit > remainder:
                    bit >>= 2
                while bit:
                    trial = root + bit
                    if remainder >= trial:
                        remainder -= trial
                        root = (root >> 1) + bit
                    else:
                        root >>= 1
                    bit >>= 2

                distance_numerator = camera_focal - root
                surface_z_numerator = (
                    -camera_z * ray_length_squared
                    + focal_length * distance_numerator
                )
                shade = (
                    -surface_z_numerator * 220
                    // (ray_length_squared * sphere_radius)
                    + 25
                )
                if shade > 245:
                    shade = 245
                pixels[index] = shade
                hits += 1
            else:
                pixels[index] = 4 + y * 12 // height
            index += 1
            x += 1
        y += 1
    return hits


@micropython.native
def render_native(pixels, width, height):
    camera_z = 300
    sphere_radius = 120
    focal_length = 100
    sphere_term = camera_z * camera_z - sphere_radius * sphere_radius
    camera_focal = camera_z * focal_length
    camera_focal_squared = camera_focal * camera_focal
    index = 0
    hits = 0
    y = 0
    while y < height:
        ray_y = y * 2 - height
        x = 0
        while x < width:
            ray_x = x * 2 - width
            ray_length_squared = (
                ray_x * ray_x
                + ray_y * ray_y
                + focal_length * focal_length
            )
            discriminant = (
                camera_focal_squared - ray_length_squared * sphere_term
            )
            if discriminant > 0:
                remainder = discriminant
                root = 0
                bit = 1 << 30
                while bit > remainder:
                    bit >>= 2
                while bit:
                    trial = root + bit
                    if remainder >= trial:
                        remainder -= trial
                        root = (root >> 1) + bit
                    else:
                        root >>= 1
                    bit >>= 2

                distance_numerator = camera_focal - root
                surface_z_numerator = (
                    -camera_z * ray_length_squared
                    + focal_length * distance_numerator
                )
                shade = (
                    -surface_z_numerator * 220
                    // (ray_length_squared * sphere_radius)
                    + 25
                )
                if shade > 245:
                    shade = 245
                pixels[index] = shade
                hits += 1
            else:
                pixels[index] = 4 + y * 12 // height
            index += 1
            x += 1
        y += 1
    return hits


def median(values):
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def timed_render(function, pixels):
    gc.collect()
    started = time.ticks_us()
    hits = function(pixels, WIDTH, HEIGHT)
    elapsed = time.ticks_diff(time.ticks_us(), started)
    return elapsed, hits


def print_frame(pixels):
    for y in range(HEIGHT):
        start = y * WIDTH
        print("FRAME,%02d,%s" % (y, bytes(pixels[start : start + WIDTH]).hex()))


def print_preview(pixels):
    shades = " .:-=+*#%@"
    for y in range(0, HEIGHT, 2):
        line = ""
        for x in range(0, WIDTH, 2):
            value = pixels[y * WIDTH + x]
            line += shades[value * (len(shades) - 1) // 255]
        print("PREVIEW,%s" % line)


def main():
    bytecode_pixels = bytearray(WIDTH * HEIGHT)
    native_pixels = bytearray(WIDTH * HEIGHT)

    bytecode_hits = render_bytecode(bytecode_pixels, WIDTH, HEIGHT)
    native_hits = render_native(native_pixels, WIDTH, HEIGHT)
    if bytecode_pixels != native_pixels or bytecode_hits != native_hits:
        raise RuntimeError("bytecode and native images differ")

    print("META,implementation,%s" % (sys.implementation,))
    print("META,uname,%s" % (os.uname(),))
    print("META,cpu_hz,%d" % machine.freq())
    print("META,width,%d" % WIDTH)
    print("META,height,%d" % HEIGHT)
    print("META,samples,%d" % SAMPLES)
    print("VERIFY,hits,%d" % bytecode_hits)
    print("VERIFY,pixel_sum,%d" % sum(bytecode_pixels))

    timings = {"bytecode": [], "native": []}
    variants = (
        ("bytecode", render_bytecode, bytecode_pixels),
        ("native", render_native, native_pixels),
    )
    for sample in range(SAMPLES):
        for step in range(2):
            name, function, pixels = variants[(sample + step) % 2]
            elapsed, hits = timed_render(function, pixels)
            if hits != bytecode_hits:
                raise RuntimeError("hit count changed")
            timings[name].append(elapsed)
            print("RAW,raytrace,%s,%d,%d" % (name, sample + 1, elapsed))

    if bytecode_pixels != native_pixels:
        raise RuntimeError("images differ after measurement")

    baseline = median(timings["bytecode"])
    for name in ("bytecode", "native"):
        values = timings[name]
        middle = median(values)
        print(
            "SUMMARY,raytrace,%s,%d,%d,%d,%.3f"
            % (name, min(values), middle, max(values), baseline / middle)
        )
    if PRINT_FRAME:
        print_frame(native_pixels)
    if PRINT_PREVIEW:
        print_preview(native_pixels)


if __name__ == "__main__":
    main()
