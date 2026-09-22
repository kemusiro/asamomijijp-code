"""MicroPython-compatible RGB ray tracer for the Pico 2 W cluster.

The scene is intentionally fixed so every worker can render independent tiles
without receiving scene data.  It uses analytic sphere and plane intersections,
configurable anti-aliasing, an area light, hard specular highlights, and one
reflection bounce.  Only one RGB888 tile buffer is required on each Pico.
"""

import array
import math

try:
    import micropython
except ImportError:
    micropython = None


def _identity(function):
    return function


_native = getattr(micropython, "native", _identity) if micropython else _identity

ALGORITHM_VERSION = "showcase-raytracer-float-v1"
OUTPUT_VERSION = "rgb888-v1"
CHECKSUM_VERSION = "crc32-image-v1"

# cx, cy, cz, radius, red, green, blue, reflectivity, specular exponent
_SPHERES = (
    (-1.05, -0.18, 1.25, 0.82, 0.92, 0.16, 0.10, 0.24, 42),
    (0.95, -0.38, 0.65, 0.62, 0.08, 0.34, 0.95, 0.42, 80),
    (0.22, 0.52, 2.05, 0.66, 0.98, 0.66, 0.08, 0.18, 54),
    (1.55, 0.10, 2.65, 0.44, 0.16, 0.88, 0.52, 0.30, 64),
)

_AA_OFFSETS_4 = ((0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75))
_AA_OFFSETS_2 = ((0.25, 0.25), (0.75, 0.75))
_AA_OFFSETS_1 = ((0.5, 0.5),)
_LIGHT_OFFSETS_4 = ((-0.42, -0.30), (0.42, -0.30), (-0.42, 0.30), (0.42, 0.30))
_LIGHT_OFFSETS_2 = ((-0.36, -0.26), (0.36, 0.26))
_LIGHT_OFFSETS_1 = ((0.0, 0.0),)
_FAR = 1000000.0
_EPSILON = 0.002
_MAX_TILE_CHANNELS = 16 * 16 * 3
_LINEAR_RGB = array.array("f", [0.0] * _MAX_TILE_CHANNELS)


if micropython and hasattr(micropython, "asm_thumb"):

    @micropython.asm_thumb
    def _linear_to_srgb(r0, r1, r2):
        label(loop)
        cmp(r2, 0)
        beq(done)
        vldr(s0, [r0, 0])

        mov(r3, 0)
        vmov(s1, r3)
        vcmp(s0, s1)
        vmrs(APSR_nzcv, FPSCR)
        ble(store_zero)

        movwt(r3, 0x3F800000)
        vmov(s1, r3)
        vcmp(s0, s1)
        vmrs(APSR_nzcv, FPSCR)
        bge(store_one)

        vsqrt(s0, s0)
        movwt(r3, 0x437F0000)
        vmov(s1, r3)
        vmul(s0, s0, s1)
        movwt(r3, 0x3F000000)
        vmov(s1, r3)
        vadd(s0, s0, s1)
        vcvt_s32_f32(s0, s0)
        vmov(r3, s0)
        b(store)

        label(store_zero)
        mov(r3, 0)
        b(store)

        label(store_one)
        mov(r3, 255)

        label(store)
        strb(r3, [r1, 0])
        add(r0, 4)
        add(r1, 1)
        sub(r2, 1)
        b(loop)
        label(done)

else:

    def _linear_to_srgb(source, result, count):
        for index in range(count):
            result[index] = _to_srgb_u8(source[index])


def validate_job(job):
    required = ("width", "height", "samples", "shadow_samples", "max_bounces")
    for name in required:
        if name not in job:
            raise ValueError("missing job field: " + name)
    if type(job["width"]) is not int or type(job["height"]) is not int:
        raise ValueError("width and height must be integers")
    if job["width"] <= 0 or job["height"] <= 0:
        raise ValueError("width and height must be positive")
    if job["samples"] not in (1, 2, 4):
        raise ValueError("samples must be 1, 2, or 4")
    if job["shadow_samples"] not in (1, 2, 4):
        raise ValueError("shadow_samples must be 1, 2, or 4")
    if job["max_bounces"] not in (1, 2):
        raise ValueError("max_bounces must be 1 or 2")


def validate_tile(job, x0, y0, tile_width, tile_height):
    if x0 < 0 or y0 < 0 or tile_width <= 0 or tile_height <= 0:
        raise ValueError("tile origin and size are invalid")
    if x0 + tile_width > job["width"] or y0 + tile_height > job["height"]:
        raise ValueError("tile extends outside the job")


@_native
def _nearest_hit(ox, oy, oz, dx, dy, dz):
    nearest = _FAR
    object_id = -1

    if dy < -0.000001:
        plane_t = (-1.0 - oy) / dy
        if plane_t > _EPSILON:
            nearest = plane_t
            object_id = 0

    for index in range(len(_SPHERES)):
        sphere = _SPHERES[index]
        ocx = ox - sphere[0]
        ocy = oy - sphere[1]
        ocz = oz - sphere[2]
        b = ocx * dx + ocy * dy + ocz * dz
        c = ocx * ocx + ocy * ocy + ocz * ocz - sphere[3] * sphere[3]
        discriminant = b * b - c
        if discriminant > 0.0:
            root = math.sqrt(discriminant)
            distance = -b - root
            if distance <= _EPSILON:
                distance = -b + root
            if _EPSILON < distance < nearest:
                nearest = distance
                object_id = index + 1
    return nearest, object_id


@_native
def _sky(dy):
    blend = 0.5 * (dy + 1.0)
    if blend < 0.0:
        blend = 0.0
    elif blend > 1.0:
        blend = 1.0
    return (
        0.055 + 0.33 * blend,
        0.075 + 0.46 * blend,
        0.13 + 0.72 * blend,
    )


@_native
def _surface(object_id, hx, hz):
    if object_id == 0:
        checker = (int(math.floor(hx * 0.72)) + int(math.floor(hz * 0.72))) & 1
        if checker:
            return 0.055, 0.065, 0.085, 0.34, 72
        return 0.72, 0.74, 0.78, 0.18, 30
    sphere = _SPHERES[object_id - 1]
    return sphere[4], sphere[5], sphere[6], sphere[7], sphere[8]


@_native
def _normal(object_id, hx, hy, hz):
    if object_id == 0:
        return 0.0, 1.0, 0.0
    sphere = _SPHERES[object_id - 1]
    inverse_radius = 1.0 / sphere[3]
    return (
        (hx - sphere[0]) * inverse_radius,
        (hy - sphere[1]) * inverse_radius,
        (hz - sphere[2]) * inverse_radius,
    )


@_native
def _is_shadowed(ox, oy, oz, lx, ly, lz, light_distance):
    distance, object_id = _nearest_hit(ox, oy, oz, lx, ly, lz)
    return object_id >= 0 and distance < light_distance - _EPSILON


@_native
def _shade(ox, oy, oz, dx, dy, dz, object_id, distance, shadow_samples):
    hx = ox + dx * distance
    hy = oy + dy * distance
    hz = oz + dz * distance
    nx, ny, nz = _normal(object_id, hx, hy, hz)
    base_r, base_g, base_b, reflectivity, specular_power = _surface(
        object_id, hx, hz
    )

    diffuse = 0.0
    specular = 0.0
    if shadow_samples == 4:
        light_offsets = _LIGHT_OFFSETS_4
    elif shadow_samples == 2:
        light_offsets = _LIGHT_OFFSETS_2
    else:
        light_offsets = _LIGHT_OFFSETS_1
    for light_offset in light_offsets:
        light_x = -3.4 + light_offset[0]
        light_y = 5.2
        light_z = -2.0 + light_offset[1]
        lx = light_x - hx
        ly = light_y - hy
        lz = light_z - hz
        light_distance = math.sqrt(lx * lx + ly * ly + lz * lz)
        inverse_light_distance = 1.0 / light_distance
        lx *= inverse_light_distance
        ly *= inverse_light_distance
        lz *= inverse_light_distance
        shadow_origin_x = hx + nx * _EPSILON
        shadow_origin_y = hy + ny * _EPSILON
        shadow_origin_z = hz + nz * _EPSILON
        if not _is_shadowed(
            shadow_origin_x,
            shadow_origin_y,
            shadow_origin_z,
            lx,
            ly,
            lz,
            light_distance,
        ):
            ndotl = nx * lx + ny * ly + nz * lz
            if ndotl > 0.0:
                diffuse += ndotl
                view_x = -dx
                view_y = -dy
                view_z = -dz
                half_x = lx + view_x
                half_y = ly + view_y
                half_z = lz + view_z
                half_length = math.sqrt(
                    half_x * half_x + half_y * half_y + half_z * half_z
                )
                if half_length > 0.0:
                    inverse_half = 1.0 / half_length
                    ndoth = (
                        nx * half_x * inverse_half
                        + ny * half_y * inverse_half
                        + nz * half_z * inverse_half
                    )
                    if ndoth > 0.0:
                        specular += ndoth ** specular_power

    inverse_samples = 1.0 / len(light_offsets)
    diffuse *= inverse_samples
    specular *= inverse_samples
    ambient = 0.105
    light = ambient + 0.895 * diffuse
    red = base_r * light + 0.72 * specular
    green = base_g * light + 0.72 * specular
    blue = base_b * light + 0.72 * specular

    # Slight blue fill light keeps the shadow side readable on a display.
    fill = nx * 0.18 + ny * 0.34 - nz * 0.92
    if fill > 0.0:
        red += base_r * fill * 0.025
        green += base_g * fill * 0.045
        blue += base_b * fill * 0.10
    return red, green, blue, reflectivity, hx, hy, hz, nx, ny, nz


@_native
def _trace(ox, oy, oz, dx, dy, dz, shadow_samples, max_bounces):
    distance, object_id = _nearest_hit(ox, oy, oz, dx, dy, dz)
    if object_id < 0:
        return _sky(dy)

    red, green, blue, reflectivity, hx, hy, hz, nx, ny, nz = _shade(
        ox, oy, oz, dx, dy, dz, object_id, distance, shadow_samples
    )
    if max_bounces > 1 and reflectivity > 0.0:
        projection = dx * nx + dy * ny + dz * nz
        reflected_x = dx - 2.0 * projection * nx
        reflected_y = dy - 2.0 * projection * ny
        reflected_z = dz - 2.0 * projection * nz
        reflected_distance, reflected_object = _nearest_hit(
            hx + nx * _EPSILON,
            hy + ny * _EPSILON,
            hz + nz * _EPSILON,
            reflected_x,
            reflected_y,
            reflected_z,
        )
        if reflected_object < 0:
            reflected_red, reflected_green, reflected_blue = _sky(reflected_y)
        else:
            (
                reflected_red,
                reflected_green,
                reflected_blue,
                _unused_reflectivity,
                _unused_hx,
                _unused_hy,
                _unused_hz,
                _unused_nx,
                _unused_ny,
                _unused_nz,
            ) = _shade(
                hx + nx * _EPSILON,
                hy + ny * _EPSILON,
                hz + nz * _EPSILON,
                reflected_x,
                reflected_y,
                reflected_z,
                reflected_object,
                reflected_distance,
                1,
            )
        facing = -(dx * nx + dy * ny + dz * nz)
        fresnel = 1.0 - facing
        if fresnel < 0.0:
            fresnel = 0.0
        fresnel = reflectivity + (1.0 - reflectivity) * fresnel ** 5
        red = red * (1.0 - fresnel) + reflected_red * fresnel
        green = green * (1.0 - fresnel) + reflected_green * fresnel
        blue = blue * (1.0 - fresnel) + reflected_blue * fresnel
    return red, green, blue


def _to_srgb_u8(value):
    if value <= 0.0:
        return 0
    if value >= 1.0:
        return 255
    return int(math.sqrt(value) * 255.0 + 0.5)


@_native
def _compute_tile_into(job, x0, y0, tile_width, tile_height, result):
    width = job["width"]
    height = job["height"]
    sample_count = job["samples"]
    shadow_samples = job["shadow_samples"]
    max_bounces = job["max_bounces"]
    if sample_count == 4:
        aa_offsets = _AA_OFFSETS_4
    elif sample_count == 2:
        aa_offsets = _AA_OFFSETS_2
    else:
        aa_offsets = _AA_OFFSETS_1
    aspect = width / height
    camera_x = 0.0
    camera_y = 0.72
    camera_z = -4.2
    output_offset = 0

    for py in range(y0, y0 + tile_height):
        for px in range(x0, x0 + tile_width):
            accumulated_red = 0.0
            accumulated_green = 0.0
            accumulated_blue = 0.0
            for sample_offset in aa_offsets:
                screen_x = (
                    ((px + sample_offset[0]) / width) * 2.0 - 1.0
                ) * aspect * 0.64
                screen_y = (
                    1.0 - ((py + sample_offset[1]) / height) * 2.0
                ) * 0.64 - 0.055
                direction_x = screen_x
                direction_y = screen_y
                direction_z = 1.0
                direction_length = math.sqrt(
                    direction_x * direction_x
                    + direction_y * direction_y
                    + direction_z * direction_z
                )
                inverse_length = 1.0 / direction_length
                direction_x *= inverse_length
                direction_y *= inverse_length
                direction_z *= inverse_length
                red, green, blue = _trace(
                    camera_x,
                    camera_y,
                    camera_z,
                    direction_x,
                    direction_y,
                    direction_z,
                    shadow_samples,
                    max_bounces,
                )
                accumulated_red += red
                accumulated_green += green
                accumulated_blue += blue
            inverse_samples = 1.0 / sample_count
            _LINEAR_RGB[output_offset] = accumulated_red * inverse_samples
            _LINEAR_RGB[output_offset + 1] = accumulated_green * inverse_samples
            _LINEAR_RGB[output_offset + 2] = accumulated_blue * inverse_samples
            output_offset += 3
    _linear_to_srgb(_LINEAR_RGB, result, output_offset)


def compute_tile_into(job, x0, y0, tile_width, tile_height, result):
    validate_job(job)
    validate_tile(job, x0, y0, tile_width, tile_height)
    required = tile_width * tile_height * 3
    if len(result) < required:
        raise ValueError("result buffer is too small")
    if required > _MAX_TILE_CHANNELS:
        raise ValueError("optimized core supports tiles up to 16x16")
    _compute_tile_into(job, x0, y0, tile_width, tile_height, result)
    return result


def compute_tile(job, x0, y0, tile_width, tile_height):
    result = bytearray(tile_width * tile_height * 3)
    compute_tile_into(job, x0, y0, tile_width, tile_height, result)
    return result
