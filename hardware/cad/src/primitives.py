"""Solid-modelling helpers for the LC-RV parametric CAD source.

Everything here returns a :class:`trimesh.Trimesh`.  Constructive solid
geometry is done with the ``manifold`` engine, which is exact and guarantees a
watertight, winding-consistent result for watertight inputs -- that property is
what lets ``assert_solid`` make hard assertions about the output.

Segment-count policy
--------------------
``SEG_FUNCTIONAL`` (64) is used for bolt holes, bearing bores and other
features whose *fit* matters but whose faceting does not.  ``SEG_SMOOTH``
(128) is used for the cup bore and the bob working cylinders, where the
surface finish is part of the measurement: at r = 23 mm a 128-gon is inside
the true circle by only r*(1-cos(pi/128)) = 0.0069 mm, which is an order of
magnitude below the print tolerance.

All builders take absolute ``z0``/``z1`` planes rather than a height plus a
centre, because every part is modelled with ``z = 0`` on the print bed.
"""

from __future__ import annotations

import math

import numpy as np
import trimesh

# --------------------------------------------------------------------------
# Tessellation defaults
# --------------------------------------------------------------------------
SEG_FUNCTIONAL = 64     # bolt holes, bores, bosses
SEG_SMOOTH = 128        # cup bore, bob working cylinders
SEG_COARSE = 32         # cosmetic corner rounds

ENGINE = "manifold"

# A small overshoot applied to cutting tools so that coincident faces never
# occur in a boolean.  Coincident faces are legal for manifold but they make
# the result ambiguous to read back numerically.
EPS = 0.01


def _finalize(verts, faces, name: str) -> trimesh.Trimesh:
    """Build a Trimesh from hand-written topology and normalise its winding.

    ``Trimesh.fix_normals`` is deliberately not used: it goes through
    ``scipy.sparse.csgraph``, which is not importable in every environment this
    file has to run in.  Instead the topology below is written closed by
    construction, so the only ambiguity is a global inside/outside flip, which
    a negative signed volume detects exactly.
    """
    m = trimesh.Trimesh(vertices=np.asarray(verts, dtype=float),
                        faces=np.asarray(faces, dtype=np.int64),
                        process=True)
    if not m.is_watertight:
        raise ValueError(f"{name}: hand-built mesh is not watertight")
    if m.volume < 0:
        m.invert()
    if not m.is_winding_consistent:
        raise ValueError(f"{name}: hand-built mesh has inconsistent winding")
    return m


# --------------------------------------------------------------------------
# Boolean wrappers
# --------------------------------------------------------------------------
def union(meshes) -> trimesh.Trimesh:
    """Boolean union of an iterable of meshes."""
    meshes = [m for m in meshes if m is not None]
    if len(meshes) == 1:
        return meshes[0].copy()
    return trimesh.boolean.union(meshes, engine=ENGINE)


def difference(base: trimesh.Trimesh, cutters) -> trimesh.Trimesh:
    """Subtract one or many cutters from ``base``."""
    if isinstance(cutters, trimesh.Trimesh):
        cutters = [cutters]
    cutters = [c for c in cutters if c is not None]
    if not cutters:
        return base.copy()
    return trimesh.boolean.difference([base] + list(cutters), engine=ENGINE)


def intersection(meshes) -> trimesh.Trimesh:
    """Boolean intersection of an iterable of meshes."""
    return trimesh.boolean.intersection(list(meshes), engine=ENGINE)


def combine(meshes) -> trimesh.Trimesh:
    """Concatenate meshes *without* a boolean.

    Only valid for provably disjoint solids (for example the 20 slot cutters of
    the encoder disc).  Much faster than a 20-way union and exactly equivalent
    as a cutting tool.
    """
    return trimesh.util.concatenate([m for m in meshes if m is not None])


# --------------------------------------------------------------------------
# Elementary solids
# --------------------------------------------------------------------------
def cylinder(radius: float, z0: float, z1: float,
             sections: int = SEG_FUNCTIONAL,
             center=(0.0, 0.0)) -> trimesh.Trimesh:
    """Right circular cylinder spanning ``z0..z1`` about ``center``."""
    height = float(z1) - float(z0)
    if height <= 0:
        raise ValueError("cylinder needs z1 > z0")
    m = trimesh.creation.cylinder(radius=float(radius), height=height,
                                  sections=int(sections))
    m.apply_translation([center[0], center[1], 0.5 * (z0 + z1)])
    return m


def tube(r_outer: float, r_inner: float, z0: float, z1: float,
         sections: int = SEG_FUNCTIONAL,
         center=(0.0, 0.0)) -> trimesh.Trimesh:
    """Annular solid (a hollow cylinder) spanning ``z0..z1``."""
    if r_inner <= 0:
        return cylinder(r_outer, z0, z1, sections, center)
    outer = cylinder(r_outer, z0, z1, sections, center)
    inner = cylinder(r_inner, z0 - EPS, z1 + EPS, sections, center)
    return difference(outer, inner)


def box(x0: float, x1: float, y0: float, y1: float,
        z0: float, z1: float) -> trimesh.Trimesh:
    """Axis-aligned box given by its two opposite corners."""
    m = trimesh.creation.box(extents=[x1 - x0, y1 - y0, z1 - z0])
    m.apply_translation([0.5 * (x0 + x1), 0.5 * (y0 + y1), 0.5 * (z0 + z1)])
    return m


def frustum(r0: float, r1: float, z0: float, z1: float,
            sections: int = SEG_FUNCTIONAL,
            center=(0.0, 0.0)) -> trimesh.Trimesh:
    """Circular frustum: radius ``r0`` at ``z0`` blending to ``r1`` at ``z1``.

    Used for 45 degree print-support transitions and for chamfer cutters.
    Built by hand rather than via a revolve so the vertex ring lies exactly on
    the nominal radius.
    """
    n = int(sections)
    ang = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
    cx, cy = float(center[0]), float(center[1])
    ring0 = np.column_stack([cx + r0 * np.cos(ang), cy + r0 * np.sin(ang),
                             np.full(n, float(z0))])
    ring1 = np.column_stack([cx + r1 * np.cos(ang), cy + r1 * np.sin(ang),
                             np.full(n, float(z1))])
    verts = np.vstack([ring0, ring1,
                       [[cx, cy, float(z0)]], [[cx, cy, float(z1)]]])
    c0, c1 = 2 * n, 2 * n + 1
    faces = []
    for k in range(n):
        k2 = (k + 1) % n
        faces.append([k, k2, n + k2])
        faces.append([k, n + k2, n + k])
        faces.append([c0, k2, k])
        faces.append([c1, n + k, n + k2])
    return _finalize(verts, faces, "frustum")


def cone(radius: float, z_base: float, z_apex: float,
         sections: int = SEG_FUNCTIONAL,
         center=(0.0, 0.0)) -> trimesh.Trimesh:
    """Cone with a circular base at ``z_base`` and its apex at ``z_apex``."""
    height = float(z_apex) - float(z_base)
    m = trimesh.creation.cone(radius=float(radius), height=abs(height),
                              sections=int(sections))
    if height < 0:
        m.apply_transform(trimesh.transformations.rotation_matrix(
            math.pi, [1, 0, 0]))
    m.apply_translation([center[0], center[1], float(z_base)])
    return m


def convex_prism(profile_xz, y0: float, y1: float) -> trimesh.Trimesh:
    """Extrude a **convex** polygon given in the XZ plane along ``y``.

    ``profile_xz`` is an ordered sequence of ``(x, z)`` pairs.  Convexity lets
    the end caps be fan-triangulated exactly, so the result is watertight by
    construction with no dependency on a polygon triangulator.
    """
    pts = np.asarray(profile_xz, dtype=float)
    n = len(pts)
    if n < 3:
        raise ValueError("convex_prism needs at least 3 profile points")
    v0 = np.column_stack([pts[:, 0], np.full(n, float(y0)), pts[:, 1]])
    v1 = np.column_stack([pts[:, 0], np.full(n, float(y1)), pts[:, 1]])
    verts = np.vstack([v0, v1])
    faces = []
    for k in range(1, n - 1):          # fan-triangulated caps
        faces.append([0, k, k + 1])
        faces.append([n, n + k + 1, n + k])
    for k in range(n):                 # side walls
        k2 = (k + 1) % n
        faces.append([k, n + k, n + k2])
        faces.append([k, n + k2, k2])
    return _finalize(verts, faces, "convex_prism")


def annular_sector(r_in: float, r_out: float, a0: float, a1: float,
                   z0: float, z1: float, segs: int = 12,
                   center=(0.0, 0.0)) -> trimesh.Trimesh:
    """A pie-slice of an annulus, ``a0..a1`` in radians, extruded ``z0..z1``.

    Built as a quad strip between the inner and outer arcs, so no general
    polygon triangulation is needed and the arcs stay exactly on radius.
    """
    n = int(segs) + 1
    ang = np.linspace(float(a0), float(a1), n)
    cx, cy = float(center[0]), float(center[1])
    ox = cx + r_out * np.cos(ang)
    oy = cy + r_out * np.sin(ang)
    ix = cx + r_in * np.cos(ang)
    iy = cy + r_in * np.sin(ang)
    verts = np.vstack([
        np.column_stack([ox, oy, np.full(n, float(z0))]),   # O0  : 0*n
        np.column_stack([ox, oy, np.full(n, float(z1))]),   # O1  : 1*n
        np.column_stack([ix, iy, np.full(n, float(z0))]),   # I0  : 2*n
        np.column_stack([ix, iy, np.full(n, float(z1))]),   # I1  : 3*n
    ])
    O0, O1, I0, I1 = 0, n, 2 * n, 3 * n
    faces = []

    def quad(a, b, c, d):
        faces.append([a, b, c])
        faces.append([a, c, d])

    for k in range(n - 1):
        quad(O0 + k, O0 + k + 1, O1 + k + 1, O1 + k)     # outer wall
        quad(I0 + k, I1 + k, I1 + k + 1, I0 + k + 1)     # inner wall
        quad(O1 + k, O1 + k + 1, I1 + k + 1, I1 + k)     # top
        quad(O0 + k, I0 + k, I0 + k + 1, O0 + k + 1)     # bottom
    quad(O0, O1, I1, I0)                                  # start cap
    quad(O0 + n - 1, I0 + n - 1, I1 + n - 1, O1 + n - 1)  # end cap
    return _finalize(verts, faces, "annular_sector")


# --------------------------------------------------------------------------
# Compound helpers
# --------------------------------------------------------------------------
def rounded_box(x0: float, x1: float, y0: float, y1: float,
                z0: float, z1: float, radius: float,
                sections: int = SEG_COARSE) -> trimesh.Trimesh:
    """Rectangular slab with vertical corner rounds of ``radius``."""
    r = float(radius)
    if r <= 0:
        return box(x0, x1, y0, y1, z0, z1)
    parts = [box(x0 + r, x1 - r, y0, y1, z0, z1),
             box(x0, x1, y0 + r, y1 - r, z0, z1)]
    for cx in (x0 + r, x1 - r):
        for cy in (y0 + r, y1 - r):
            parts.append(cylinder(r, z0, z1, sections, center=(cx, cy)))
    return union(parts)


def slot(x0: float, x1: float, y: float, width: float,
         z0: float, z1: float, sections: int = SEG_COARSE) -> trimesh.Trimesh:
    """Obround slot along x, centred on ``y``, of the given ``width``."""
    r = 0.5 * float(width)
    parts = [box(x0, x1, y - r, y + r, z0, z1),
             cylinder(r, z0, z1, sections, center=(x0, y)),
             cylinder(r, z0, z1, sections, center=(x1, y))]
    return union(parts)


def counterbore(hole_d: float, cbore_d: float, cbore_depth: float,
                z_thru0: float, z_thru1: float, z_face: float,
                center=(0.0, 0.0), sections: int = SEG_FUNCTIONAL,
                from_top: bool = False) -> trimesh.Trimesh:
    """Cutting tool for a counterbored screw hole.

    ``z_thru0..z_thru1`` is the through-hole extent (already overshot by the
    caller if desired); ``z_face`` is the plane the screw head sits in.  With
    ``from_top=False`` the counterbore is cut upward from ``z_face`` (a head
    recess in the underside of a plate).
    """
    thru = cylinder(0.5 * hole_d, z_thru0, z_thru1, sections, center)
    if from_top:
        cb = cylinder(0.5 * cbore_d, z_face - cbore_depth, z_face + EPS,
                      sections, center)
    else:
        cb = cylinder(0.5 * cbore_d, z_face - EPS, z_face + cbore_depth,
                      sections, center)
    return union([thru, cb])


def m3_hole(z0: float, z1: float, center=(0.0, 0.0), kind: str = "clear",
            sections: int = SEG_FUNCTIONAL) -> trimesh.Trimesh:
    """Cutting tool for an M3 hole.

    ``kind`` is ``"clear"`` (3.4 mm), ``"tap"`` (2.6 mm self-tapping into PLA)
    or ``"heatset_thru"`` (3.2 mm shank behind a heat-set insert).
    """
    d = {"clear": 3.4, "tap": 2.6, "heatset_thru": 3.2}[kind]
    return cylinder(0.5 * d, z0, z1, sections, center)


def heatset_boss(boss_d: float, z0: float, z1: float, center=(0.0, 0.0),
                 insert_d: float = 4.2, insert_depth: float = 5.5,
                 thru_d: float = 3.2, thru_z: float = None,
                 sections: int = SEG_FUNCTIONAL):
    """Boss + cutter pair for an M3 brass heat-set insert.

    Returns ``(boss_solid, cutter)``.  The insert is melted in from ``z1``
    downward; the 3.2 mm shank continues to ``thru_z`` (default ``z0``).
    """
    boss = cylinder(0.5 * boss_d, z0, z1, sections, center)
    if thru_z is None:
        thru_z = z0 - EPS
    cutter = union([
        cylinder(0.5 * insert_d, z1 - insert_depth, z1 + EPS, sections, center),
        cylinder(0.5 * thru_d, thru_z, z1 + EPS, sections, center),
    ])
    return boss, cutter


def d_shaft_bore(shaft_d: float, flat_depth: float, z0: float, z1: float,
                 clearance: float = 0.2, center=(0.0, 0.0),
                 flat_dir: str = "+x",
                 sections: int = SEG_FUNCTIONAL) -> trimesh.Trimesh:
    """Cutting tool for a D-shaped motor-shaft bore.

    ``shaft_d`` is the nominal round diameter and ``flat_depth`` how far the
    flat is machined in from that circle (0.5 mm on a standard 5 mm NEMA 17
    shaft).  ``clearance`` is added diametrically for a slide fit.
    """
    r = 0.5 * (shaft_d + clearance)
    flat_offset = 0.5 * shaft_d - flat_depth + 0.5 * clearance
    bore = cylinder(r, z0, z1, sections, center)
    big = 10.0 * r
    cx, cy = center
    if flat_dir == "+x":
        keep = box(cx + flat_offset, cx + big, cy - big, cy + big,
                   z0 - EPS, z1 + EPS)
    elif flat_dir == "-x":
        keep = box(cx - big, cx - flat_offset, cy - big, cy + big,
                   z0 - EPS, z1 + EPS)
    elif flat_dir == "+y":
        keep = box(cx - big, cx + big, cy + flat_offset, cy + big,
                   z0 - EPS, z1 + EPS)
    else:
        keep = box(cx - big, cx + big, cy - big, cy - flat_offset,
                   z0 - EPS, z1 + EPS)
    return difference(bore, keep)


def slot_ring(n_slots: int, r_in: float, r_out: float, duty: float,
              z0: float, z1: float, phase: float = 0.0,
              segs: int = 8, center=(0.0, 0.0)) -> trimesh.Trimesh:
    """``n_slots`` equally spaced radial slots on a ring -- the encoder pattern.

    Returned as one concatenated (non-boolean) cutting tool; the sectors are
    provably disjoint because ``duty < 1``.
    """
    pitch = 2.0 * math.pi / int(n_slots)
    half = 0.5 * duty * pitch
    sectors = []
    for k in range(int(n_slots)):
        a = phase + k * pitch
        sectors.append(annular_sector(r_in, r_out, a - half, a + half,
                                      z0, z1, segs=segs, center=center))
    return combine(sectors)


def chamfer_outer(radius: float, size: float, z_edge: float, upward: bool,
                  sections: int = SEG_FUNCTIONAL,
                  center=(0.0, 0.0)) -> trimesh.Trimesh:
    """Cutter that breaks the outside edge of a cylinder of ``radius``.

    ``upward=True`` chamfers the top edge (material removed above ``z_edge``).
    """
    big = radius + size + 5.0
    if upward:
        ring = frustum(radius - size, radius + size, z_edge - size,
                       z_edge + size, sections, center)
        outer = cylinder(big, z_edge - size, z_edge + size, sections, center)
        return difference(outer, ring)
    ring = frustum(radius + size, radius - size, z_edge - size,
                   z_edge + size, sections, center)
    outer = cylinder(big, z_edge - size, z_edge + size, sections, center)
    return difference(outer, ring)


def chamfer_bore(radius: float, size: float, z_edge: float, downward: bool,
                 sections: int = SEG_FUNCTIONAL,
                 center=(0.0, 0.0)) -> trimesh.Trimesh:
    """Cutter that breaks the mouth of a bore of ``radius`` as a lead-in.

    ``downward=True`` puts the lead-in on the top face of the part (the bore
    opens upward and the chamfer widens as z increases).
    """
    if downward:
        return frustum(radius, radius + size, z_edge - size, z_edge + size,
                       sections, center)
    return frustum(radius + size, radius, z_edge - size, z_edge + size,
                   sections, center)


# --------------------------------------------------------------------------
# Placement + inspection helpers
# --------------------------------------------------------------------------
def orient(mesh: trimesh.Trimesh, origin, direction) -> trimesh.Trimesh:
    """Rotate a +z-aligned tool onto ``direction`` and move it to ``origin``."""
    direction = np.asarray(direction, dtype=float)
    direction = direction / np.linalg.norm(direction)
    T = trimesh.geometry.align_vectors([0.0, 0.0, 1.0], direction)
    out = mesh.copy()
    out.apply_transform(T)
    out.apply_translation(np.asarray(origin, dtype=float))
    return out


def clean_solid(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Strip export artefacts from a boolean result, in place.

    The boolean engine occasionally emits a triangle whose three vertices are
    collinear to within float noise -- a zero-area face.  In float64 such a
    face is harmless: the mesh is still closed, because the sliver's two
    near-coincident vertices are distinct numbers.  Binary STL, however, stores
    vertices as **float32**.  The quantisation collapses those two vertices
    onto one, the sliver collapses onto its own longest edge, and that edge
    ends up referenced by four faces instead of two.  The *exported file* is
    then not watertight even though the in-memory mesh was.

    Dropping the degenerate faces and re-merging vertices before export makes
    the shipped STL byte-for-byte equivalent to the validated model.  It cannot
    change the geometry: a zero-area triangle contributes nothing to the
    surface, and ``merge_vertices`` works at ``tol.merge`` (1e-8 mm), seven
    orders of magnitude below print tolerance.
    """
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.merge_vertices()
    mesh.remove_unreferenced_vertices()
    return mesh


def assert_solid(mesh: trimesh.Trimesh, name: str) -> trimesh.Trimesh:
    """Clean the mesh, then raise unless it is a single, closed, positive-volume solid.

    The cleaning pass (``clean_solid``) runs first so that the assertions below
    describe the solid that will actually be written to ``hardware/cad/stl/``,
    not a float64-only idealisation of it.
    """
    clean_solid(mesh)
    if not mesh.is_watertight:
        raise ValueError(f"{name}: mesh is not watertight")
    if not mesh.is_winding_consistent:
        raise ValueError(f"{name}: winding is not consistent")
    if mesh.volume <= 0:
        raise ValueError(f"{name}: volume is {mesh.volume}")
    return mesh


def chord_error(radius: float, sections: int) -> float:
    """Inscribed-polygon sagitta, i.e. how far a facet sits inside true radius."""
    return radius * (1.0 - math.cos(math.pi / sections))
