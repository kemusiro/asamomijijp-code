"""MicroPython-compatible extruded vehicle renderer, separate from gallery v2.

13 genes and optional bounded course points travel in a job. Geometry is
prepared once, then shared by all its tiles. No per-pixel mesh, external files, or scene mutation during a job.
"""
import math

try:
    import micropython
except ImportError:
    micropython = None


def _identity(function):
    return function


_native = getattr(micropython, "native", _identity) if micropython else _identity
ALGORITHM_VERSION = "vehicle-extrusion-raytracer-v2"
OUTPUT_VERSION = "rgb888-v1"
CHECKSUM_VERSION = "crc32-image-v1"
MODEL_VERSION = "vehicle-extrusion-v1"
BOUNDS = ((.3, 1.65),) * 8 + ((.18, .95), (.18, .95), (.65, 1.45), (-.8, -.25), (2, 7))
HALF_WIDTH = .48
TIRE_WIDTH = .30
FLOOR = -1.0
_EPS = .002
_FAR = 1000000.0
_signature = None
_parts = ()
_wheels = ()
_camera = ()
_terrain = ()
_terrain_enabled = False


def validate_genome(genome):
    if not isinstance(genome, (tuple, list)) or len(genome) != 13:
        raise ValueError("vehicle must contain exactly 13 genes")
    for i in range(13):
        value = genome[i]
        if type(value) not in (int, float) or not math.isfinite(value) or not BOUNDS[i][0] <= value <= BOUNDS[i][1]:
            raise ValueError("vehicle gene out of range: %d" % i)


def validate_job(job):
    if not isinstance(job, dict):
        raise ValueError("vehicle job must be an object")
    if job.get("model_version") != MODEL_VERSION:
        raise ValueError("unsupported vehicle model_version")
    for key in ("width", "height"):
        if type(job.get(key)) is not int or not 1 <= job[key] <= 640:
            raise ValueError(key + " must be an integer between 1 and 640")
    for key in ("samples", "shadow_samples"):
        if type(job.get(key)) is not int or job[key] not in (1, 2, 4):
            raise ValueError(key + " must be 1, 2, or 4")
    if type(job.get("max_bounces")) is not int or job["max_bounces"] not in (1, 2):
        raise ValueError("max_bounces must be 1 or 2")
    validate_genome(job.get("vehicle"))
    terrain = job.get("terrain")
    if terrain is not None:
        if not isinstance(terrain, dict) or terrain.get("version") != "course-diorama-v1":
            raise ValueError("unsupported terrain version")
        points = terrain.get("points")
        if not isinstance(points, (list, tuple)) or not 2 <= len(points) <= 24:
            raise ValueError("terrain requires 2..24 points")
        last = -100.0
        for p in points:
            if not isinstance(p, (list, tuple)) or len(p) != 2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in p):
                raise ValueError("invalid terrain point")
            if not last < p[0] <= 30 or p[0] < -30 or not -12 <= p[1] <= 6:
                raise ValueError("terrain point bounds/order")
            last=p[0]


def body_vertices(genome):
    return tuple((genome[i] * math.cos(i * math.pi / 4), genome[i] * math.sin(i * math.pi / 4)) for i in range(8))


def geometry(genome):
    """Return model-space polygons and wheels; keep original side-view genes."""
    validate_genome(genome)
    outline = body_vertices(genome)
    # 2D has no width: use a constant width and mirrored pairs of tires.
    # Lift without changing the side-view geometry so nothing penetrates floor.
    lift = FLOOR - min(min(y for x, y in outline), genome[11] - max(genome[8:10]))
    body = tuple((x, y + lift) for x, y in outline)
    parts = [(body, -HALF_WIDTH, HALF_WIDTH, 0)]
    for side in (-1, 1):
        ax, ay = side * genome[10], genome[11]
        length = math.sqrt(ax * ax + ay * ay)
        nx, ny = -ay / length * .055, ax / length * .055
        rod = ((nx, ny + lift), (-nx, -ny + lift), (ax - nx, ay - ny + lift), (ax + nx, ay + ny + lift))
        parts.append((rod, -.56, .56, 1))
    wheels = []
    for index in range(2):
        for side in (-1, 1):
            z0, z1 = sorted((side * (HALF_WIDTH + .06), side * (HALF_WIDTH + .06 + TIRE_WIDTH)))
            wheels.append(((index * 2 - 1) * genome[10], genome[11] + lift, genome[8 + index], z0, z1))
    return tuple(parts), tuple(wheels)


def _prepare(genome, terrain=None):
    global _signature, _parts, _wheels, _camera, _terrain, _terrain_enabled
    points=tuple(tuple(p) for p in terrain['points']) if terrain else ()
    signature = (tuple(genome), points)
    if signature == _signature:
        return
    _terrain_enabled = bool(points)
    segments=[]
    if points:
        expanded=points
        for i in range(len(expanded)-1):
            x,y=expanded[i];ex,ey=expanded[i+1]
            slope=(ey-y)/(ex-x);normal=1/math.sqrt(1+slope*slope)
            segments.append((x,ex,slope,y-slope*x,-slope*normal,normal))
    _terrain=tuple(segments)
    parts, wheels = geometry(genome)
    prepared = []
    for vertices, z0, z1, material in parts:
        edges = []
        for i in range(len(vertices)):
            x, y = vertices[i]
            ex, ey = vertices[(i + 1) % len(vertices)]
            ex, ey = ex - x, ey - y
            length = math.sqrt(ex * ex + ey * ey)
            edges.append((x, y, ex, ey, ey / length, -ex / length))
        prepared.append((tuple(edges), z0, z1, material,
                         min(x for x, y in vertices), max(x for x, y in vertices),
                         min(y for x, y in vertices), max(y for x, y in vertices)))
    _parts, _wheels = tuple(prepared), wheels
    # Fixed oblique camera; frame using actual body/wheel extents.
    xmin = min(min(p[4] for p in _parts), min(w[0] - w[2] for w in wheels))
    xmax = max(max(p[5] for p in _parts), max(w[0] + w[2] for w in wheels))
    ymin = min(FLOOR, min(p[6] for p in _parts))
    ymax = max(max(p[7] for p in _parts), max(w[1] + w[2] for w in wheels))
    target_x, target_y = (xmin + xmax) / 2, (ymin + ymax) / 2
    scale = max(1.0, (xmax - xmin) / 4.8, (ymax - ymin) / 2.6)
    ox, oy, oz = target_x + 3.8 * scale, target_y + 2.4 * scale, -6.4 * scale
    if terrain:
        ox,oy,oz=target_x+5.0*scale,target_y+3.4*scale,-8.3*scale
        target_x+=.7*scale;target_y-=.35*scale
    fx, fy, fz = target_x - ox, target_y - oy, -oz
    inverse = 1 / math.sqrt(fx * fx + fy * fy + fz * fz)
    fx, fy, fz = fx * inverse, fy * inverse, fz * inverse
    inverse = 1 / math.sqrt(fz * fz + fx * fx)
    rx, rz = fz * inverse, -fx * inverse
    ux, uy, uz = -fy * rz, fz * rx - fx * rz, fy * rx
    _camera = (ox, oy, oz, fx, fy, fz, rx, rz, ux, uy, uz)
    _signature = signature


@_native
def _inside(edges, x, y):
    inside = False
    for edge in edges:
        vx, vy, ex, ey = edge[0], edge[1], edge[2], edge[3]
        if (vy > y) != (vy + ey > y) and x < vx + (y - vy) * ex / ey:
            inside = not inside
    return inside


@_native
def _box(ox, oy, oz, dx, dy, dz, xmin, xmax, ymin, ymax, zmin, zmax, limit):
    lower, upper = _EPS, limit
    for origin, direction, low, high in ((ox, dx, xmin, xmax), (oy, dy, ymin, ymax), (oz, dz, zmin, zmax)):
        if abs(direction) < .0000001:
            if origin < low or origin > high:
                return False
        else:
            a, b = (low - origin) / direction, (high - origin) / direction
            if a > b:
                a, b = b, a
            lower, upper = max(lower, a), min(upper, b)
            if upper < lower:
                return False
    return True


@_native
def _nearest_hit(ox, oy, oz, dx, dy, dz):
    nearest, object_id, nx, ny, nz = _FAR, -1, 0.0, 0.0, 0.0
    if _terrain_enabled:
        if dy < -.000001:
            t=(-5.2-oy)/dy
            if t>_EPS:nearest,object_id,ny=t,20,1.0
        for seg in _terrain:
            denom=dy-seg[2]*dx
            if abs(denom)<.000001:
                continue
            t=(seg[2]*ox+seg[3]-oy)/denom
            if _EPS<t<nearest and seg[0]<=ox+t*dx<=seg[1] and abs(oz+t*dz)<=1.65:
                nearest,object_id,nx,ny,nz=t,0,seg[4],seg[5],0.0
        if abs(dz)>.000001:
            for z,normal in ((-1.65,-1.0),(1.65,1.0)):
                t=(z-oz)/dz
                if not _EPS<t<nearest or oy+t*dy< -5.2:continue
                x,y=ox+t*dx,oy+t*dy
                for seg in _terrain:
                    if seg[0]<=x<=seg[1] and y<=seg[2]*x+seg[3]:
                        nearest,object_id,nx,ny,nz=t,21,0.0,0.0,normal
                        break
        if abs(dx)>.000001:
            for x,top,normal in ((_terrain[0][0],_terrain[0][2]*_terrain[0][0]+_terrain[0][3],-1.0),(_terrain[-1][1],_terrain[-1][2]*_terrain[-1][1]+_terrain[-1][3],1.0)):
                t=(x-ox)/dx
                if _EPS<t<nearest and abs(oz+t*dz)<=1.65 and -5.2<=oy+t*dy<=top:
                    nearest,object_id,nx,ny,nz=t,21,normal,0.0,0.0
    elif dy < -.000001:
        t = (FLOOR - oy) / dy
        if t > _EPS:
            nearest, object_id, ny = t, 0, 1.0
    for index in range(len(_parts)):
        p = _parts[index]
        edges, z0, z1 = p[0], p[1], p[2]
        if not _box(ox, oy, oz, dx, dy, dz, p[4], p[5], p[6], p[7], z0, z1, nearest):
            continue
        if abs(dz) > .0000001:
            for z, normal in ((z0, -1.0), (z1, 1.0)):
                t = (z - oz) / dz
                if _EPS < t < nearest and _inside(edges, ox + t * dx, oy + t * dy):
                    nearest, object_id, nx, ny, nz = t, 1 + index, 0.0, 0.0, normal
        for e in edges:
            denom = dx * e[3] - dy * e[2]
            if abs(denom) < .0000001:
                continue
            qx, qy = e[0] - ox, e[1] - oy
            t = (qx * e[3] - qy * e[2]) / denom
            if not _EPS < t < nearest or not z0 <= oz + t * dz <= z1:
                continue
            u = (qx * dy - qy * dx) / denom
            if 0 <= u <= 1:
                nearest, object_id, nx, ny, nz = t, 1 + index, e[4], e[5], 0.0
    for index in range(len(_wheels)):
        cx, cy, radius, z0, z1 = _wheels[index]
        if not _box(ox, oy, oz, dx, dy, dz, cx-radius, cx+radius, cy-radius, cy+radius, z0, z1, nearest):
            continue
        qx, qy = ox - cx, oy - cy
        if abs(dz) > .0000001:
            for z, normal in ((z0, -1.0), (z1, 1.0)):
                t = (z - oz) / dz
                hx, hy = qx + t * dx, qy + t * dy
                if _EPS < t < nearest and hx * hx + hy * hy <= radius * radius:
                    nearest, object_id, nx, ny, nz = t, 10 + index, 0.0, 0.0, normal
        a, b = dx * dx + dy * dy, qx * dx + qy * dy
        c = qx * qx + qy * qy - radius * radius
        disc = b * b - a * c
        if a > .0000001 and disc > 0:
            root = math.sqrt(disc)
            for t in ((-b - root) / a, (-b + root) / a):
                if _EPS < t < nearest and z0 <= oz + t * dz <= z1:
                    nearest, object_id = t, 10 + index
                    nx, ny, nz = (qx + t * dx) / radius, (qy + t * dy) / radius, 0.0
    return nearest, object_id, nx, ny, nz


@_native
def _sky(dy):
    blend = max(0.0, min(1.0, .5 * (dy + 1)))
    return .045 + .20 * blend, .065 + .28 * blend, .10 + .40 * blend


@_native
def _material(object_id, x, y, z, nz):
    if object_id == 20:
        return .035,.050,.075,.08,32
    if object_id == 21:
        band=.035*math.sin(y*9)
        return .26+band,.16+band,.07,.02,24
    if object_id == 0:
        if _terrain_enabled:
            # 道路と草地。遠方の細かい市松模様によるモアレを避ける。
            if abs(z)<1.05:
                return .38,.29,.16,.02,24
            if 1.05<=abs(z)<1.12:
                return .69,.60,.33,.02,24
            band=.025*math.sin(y*5)
            return .12+band,.25+band,.075,.02,24
        if (int(math.floor(x)) + int(math.floor(z))) & 1:
            return .10, .14, .19, .12, 48
        return .38, .44, .50, .16, 48
    if object_id == 1:
        return .05, .78, .54, .22, 70
    if object_id < 10:
        return .58, .65, .72, .32, 88
    wheel = _wheels[object_id - 10]
    qx, qy, radius = x - wheel[0], y - wheel[1], wheel[2]
    distance = (qx * qx + qy * qy) / (radius * radius)
    if abs(nz) > .5 and distance < .55:
        if distance < .06 or abs(qx) < .055 * radius or abs(qy) < .055 * radius or abs(qx-qy) < .055 * radius:
            return .67, .75, .81, .40, 100
        return .13, .20, .24, .20, 60
    return .025, .032, .04, .06, 24


@_native
def _shade(ox, oy, oz, dx, dy, dz, hit, shadow_samples):
    t, obj, nx, ny, nz = hit
    hx, hy, hz = ox + t * dx, oy + t * dy, oz + t * dz
    r, g, b, reflection, power = _material(obj, hx, hy, hz, nz)
    diffuse, specular = 0.0, 0.0
    offsets = ((0.0, 0.0),)
    if shadow_samples == 2:
        offsets = ((-.35, -.25), (.35, .25))
    elif shadow_samples == 4:
        offsets = ((-.35, -.25), (.35, -.25), (-.35, .25), (.35, .25))
    for a, c in offsets:
        lx, ly, lz = -3.5 + a - hx, 6.5 - hy, -4.0 + c - hz
        length = math.sqrt(lx * lx + ly * ly + lz * lz)
        lx, ly, lz = lx / length, ly / length, lz / length
        dot = nx * lx + ny * ly + nz * lz
        if dot <= 0:
            continue
        shadow = _nearest_hit(hx + nx * _EPS, hy + ny * _EPS, hz + nz * _EPS, lx, ly, lz)
        if shadow[1] >= 0 and shadow[0] < length - _EPS:
            continue
        diffuse += dot
        vx, vy, vz = lx - dx, ly - dy, lz - dz
        length = math.sqrt(vx * vx + vy * vy + vz * vz)
        specular += max(0.0, (nx * vx + ny * vy + nz * vz) / length) ** power
    light = .22 + .78 * diffuse / len(offsets)
    highlight = .65 * specular / len(offsets)
    return r * light + highlight, g * light + highlight, b * light + highlight, reflection


@_native
def _trace(ox, oy, oz, dx, dy, dz, shadows, bounces):
    hit = _nearest_hit(ox, oy, oz, dx, dy, dz)
    if hit[1] < 0:
        return _sky(dy)
    r, g, b, reflection = _shade(ox, oy, oz, dx, dy, dz, hit, shadows)
    if bounces == 2:
        t, obj, nx, ny, nz = hit
        x, y, z = ox + t * dx + nx * _EPS, oy + t * dy + ny * _EPS, oz + t * dz + nz * _EPS
        dot = dx * nx + dy * ny + dz * nz
        rx, ry, rz = dx - 2 * dot * nx, dy - 2 * dot * ny, dz - 2 * dot * nz
        other = _nearest_hit(x, y, z, rx, ry, rz)
        if other[1] < 0:
            rr, rg, rb = _sky(ry)
        else:
            rr, rg, rb, unused = _shade(x, y, z, rx, ry, rz, other, 1)
        r, g, b = r * (1-reflection) + rr * reflection, g * (1-reflection) + rg * reflection, b * (1-reflection) + rb * reflection
    return r, g, b


@_native
def _compute_tile_into(job, x0, y0, width, height, result):
    ox, oy, oz, fx, fy, fz, rx, rz, ux, uy, uz = _camera
    offsets = ((.5, .5),)
    if job["samples"] == 2:
        offsets = ((.25, .25), (.75, .75))
    elif job["samples"] == 4:
        offsets = ((.25, .25), (.75, .25), (.25, .75), (.75, .75))
    aspect = job["width"] / job["height"]
    position = 0
    for py in range(y0, y0 + height):
        for px in range(x0, x0 + width):
            r, g, b = 0.0, 0.0, 0.0
            for a, c in offsets:
                sx = ((px+a) / job["width"] * 2 - 1) * aspect * .36
                sy = (1 - (py+c) / job["height"] * 2) * .36
                dx, dy, dz = fx + sx * rx + sy * ux, fy + sy * uy, fz + sx * rz + sy * uz
                length = math.sqrt(dx*dx + dy*dy + dz*dz)
                cr, cg, cb = _trace(ox, oy, oz, dx/length, dy/length, dz/length, job["shadow_samples"], job["max_bounces"])
                r, g, b = r + cr, g + cg, b + cb
            for color in (r, g, b):
                value = max(0.0, min(1.0, color / len(offsets)))
                result[position] = int(math.sqrt(value) * 255 + .5)
                position += 1


def compute_tile_into(job, x0, y0, width, height, result):
    validate_job(job)
    if x0 < 0 or y0 < 0 or width <= 0 or height <= 0 or x0+width > job["width"] or y0+height > job["height"]:
        raise ValueError("tile extends outside the job")
    if len(result) < width * height * 3:
        raise ValueError("result buffer is too small")
    _prepare(job["vehicle"],job.get("terrain"))
    _compute_tile_into(job, x0, y0, width, height, result)
    return result


def compute_tile(job, x0, y0, width, height):
    result = bytearray(width * height * 3)
    compute_tile_into(job, x0, y0, width, height, result)
    return result
