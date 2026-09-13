"""MicroPython-compatible Mandelbrot tile calculation core.

The core allocates only one tile result buffer. It deliberately contains no
network, display, or board-specific code so the same functions can be checked
on CPython before they are copied to a Pico 2 W.
"""

try:
    import micropython

    _IS_MICROPYTHON = True
except ImportError:
    _IS_MICROPYTHON = False
    micropython = None


def _identity(function):
    return function


_native = getattr(micropython, "native", _identity) if micropython else _identity
_HAS_VIPER = bool(micropython and hasattr(micropython, "viper"))

ALGORITHM_VERSION = "mandelbrot-tile-float32-v2"
OUTPUT_VERSION = "iterations-u8-v1"
CHECKSUM_VERSION = "row-crc32-mix-v1"
DEFAULT_Q_BITS = 20
_UINT32_MASK = 0xFFFFFFFF


def validate_job(job):
    required = ("xmin", "xmax", "ymin", "ymax", "width", "height", "max_iter")
    for name in required:
        if name not in job:
            raise ValueError("missing job field: " + name)
    if job["width"] <= 0 or job["height"] <= 0:
        raise ValueError("width and height must be positive")
    if job["xmax"] <= job["xmin"] or job["ymax"] <= job["ymin"]:
        raise ValueError("coordinate range must be increasing")
    if job["max_iter"] <= 0 or job["max_iter"] > 255:
        raise ValueError("max_iter must be between 1 and 255 for u8 output")


def validate_tile(job, x0, y0, tile_width, tile_height):
    if x0 < 0 or y0 < 0 or tile_width <= 0 or tile_height <= 0:
        raise ValueError("tile origin and size are invalid")
    if x0 + tile_width > job["width"] or y0 + tile_height > job["height"]:
        raise ValueError("tile extends outside the job")


def iterate_float(cr, ci, max_iter):
    x = cr - 0.25
    q = x * x + ci * ci
    if q * (q + x) <= 0.25 * ci * ci:
        return max_iter
    x = cr + 1.0
    if x * x + ci * ci <= 0.0625:
        return max_iter

    zr = 0.0
    zi = 0.0
    count = 0
    while count < max_iter:
        zr2 = zr * zr
        zi2 = zi * zi
        if zr2 + zi2 > 4.0:
            break
        zi = 2.0 * zr * zi + ci
        zr = zr2 - zi2 + cr
        count += 1
    return count


@_native
def _compute_tile_float_into(job, x0, y0, tile_width, tile_height, result):
    xmin = job["xmin"]
    ymin = job["ymin"]
    dx = (job["xmax"] - xmin) / job["width"]
    dy = (job["ymax"] - ymin) / job["height"]
    max_iter = job["max_iter"]
    offset = 0

    for py in range(y0, y0 + tile_height):
        ci = ymin + (py + 0.5) * dy
        ci2 = ci * ci
        quarter_ci2 = 0.25 * ci2
        cr = xmin + (x0 + 0.5) * dx
        for px in range(x0, x0 + tile_width):
            x = cr - 0.25
            q = x * x + ci2
            if q * (q + x) <= quarter_ci2:
                result[offset] = max_iter
            else:
                x = cr + 1.0
                if x * x + ci2 <= 0.0625:
                    result[offset] = max_iter
                else:
                    zr = 0.0
                    zi = 0.0
                    count = 0
                    while count < max_iter:
                        zr2 = zr * zr
                        zi2 = zi * zi
                        if zr2 + zi2 > 4.0:
                            break
                        zi = 2.0 * zr * zi + ci
                        zr = zr2 - zi2 + cr
                        count += 1
                    result[offset] = count
            offset += 1
            cr += dx


def compute_tile_float_into(job, x0, y0, tile_width, tile_height, result):
    validate_job(job)
    validate_tile(job, x0, y0, tile_width, tile_height)
    if len(result) < tile_width * tile_height:
        raise ValueError("result buffer is too small")
    _compute_tile_float_into(job, x0, y0, tile_width, tile_height, result)
    return result


def compute_tile_float(job, x0, y0, tile_width, tile_height):
    result = bytearray(tile_width * tile_height)
    compute_tile_float_into(job, x0, y0, tile_width, tile_height, result)
    return result


def _to_fixed(value, scale):
    scaled = value * scale
    if scaled >= 0:
        return int(scaled + 0.5)
    return int(scaled - 0.5)


def iterate_fixed(cr, ci, max_iter, q_bits=DEFAULT_Q_BITS):
    scale = 1 << q_bits
    escape_squared = 4 * scale
    zr = 0
    zi = 0
    count = 0
    while count < max_iter:
        zr2 = (zr * zr) >> q_bits
        zi2 = (zi * zi) >> q_bits
        if zr2 + zi2 > escape_squared:
            break
        zi = ((2 * zr * zi) >> q_bits) + ci
        zr = zr2 - zi2 + cr
        count += 1
    return count


def compute_tile_fixed(job, x0, y0, tile_width, tile_height, q_bits=DEFAULT_Q_BITS):
    validate_job(job)
    validate_tile(job, x0, y0, tile_width, tile_height)
    if q_bits < 8 or q_bits > 24:
        raise ValueError("q_bits must be between 8 and 24")

    scale = 1 << q_bits
    xmin = _to_fixed(job["xmin"], scale)
    xmax = _to_fixed(job["xmax"], scale)
    ymin = _to_fixed(job["ymin"], scale)
    ymax = _to_fixed(job["ymax"], scale)
    x_span = xmax - xmin
    y_span = ymax - ymin
    width = job["width"]
    height = job["height"]
    max_iter = job["max_iter"]
    result = bytearray(tile_width * tile_height)
    offset = 0

    for py in range(y0, y0 + tile_height):
        ci = ymin + ((2 * py + 1) * y_span) // (2 * height)
        for px in range(x0, x0 + tile_width):
            cr = xmin + ((2 * px + 1) * x_span) // (2 * width)
            result[offset] = iterate_fixed(cr, ci, max_iter, q_bits)
            offset += 1
    return result


def compute_tile(job, x0, y0, tile_width, tile_height, method="float", q_bits=DEFAULT_Q_BITS):
    if method == "float":
        return compute_tile_float(job, x0, y0, tile_width, tile_height)
    if method == "fixed_q20" or method == "fixed":
        return compute_tile_fixed(job, x0, y0, tile_width, tile_height, q_bits)
    raise ValueError("unsupported method: " + method)


def compute_tile_into(
    job, x0, y0, tile_width, tile_height, result, method="float", q_bits=DEFAULT_Q_BITS
):
    if method == "float":
        return compute_tile_float_into(job, x0, y0, tile_width, tile_height, result)
    computed = compute_tile_fixed(job, x0, y0, tile_width, tile_height, q_bits)
    required = tile_width * tile_height
    if len(result) < required:
        raise ValueError("result buffer is too small")
    result[0:required] = computed
    return result


def checksum_update(checksum, global_pixel_index, value):
    """Return a tile-order-independent, position-aware 32-bit checksum."""
    term = ((global_pixel_index + 1) * 0x045D9F3B) & _UINT32_MASK
    term ^= ((value + 1) * 0x27D4EB2D) & _UINT32_MASK
    term ^= term >> 16
    term = (term * 0x119DE1F3) & _UINT32_MASK
    term ^= term >> 16
    return (checksum + term) & _UINT32_MASK


if _IS_MICROPYTHON and _HAS_VIPER:

    @micropython.viper
    def update_checksum_for_tile(
        checksum: uint,
        tile,
        job_width: int,
        x0: int,
        y0: int,
        tile_width: int,
        tile_height: int,
    ) -> uint:
        data = ptr8(tile)
        current = uint(checksum)
        offset = 0
        for local_y in range(tile_height):
            global_index = (y0 + local_y) * job_width + x0
            for local_x in range(tile_width):
                term = uint(global_index + local_x + 1) * uint(0x045D9F3B)
                term ^= uint(data[offset] + 1) * uint(0x27D4EB2D)
                term ^= term >> 16
                term *= uint(0x119DE1F3)
                term ^= term >> 16
                current += term
                offset += 1
        return current

else:

    def update_checksum_for_tile(checksum, tile, job_width, x0, y0, tile_width, tile_height):
        offset = 0
        for local_y in range(tile_height):
            global_index = (y0 + local_y) * job_width + x0
            for local_x in range(tile_width):
                checksum = checksum_update(checksum, global_index + local_x, tile[offset])
                offset += 1
        return checksum
