"""Every printed part of the LC-RV, as a function returning a Trimesh.

Each function is pure: it takes only optional overrides, reads its dimensions
from :mod:`params`, and returns a closed solid modelled with ``z = 0`` on the
print bed, already in its recommended print orientation.  The physics behind
the geometry is in ``docs/theory.md``; the matching firmware constants are in
``firmware/LC-RV/config.h``.

Design intent
-------------
* The cup is **not** bolted down.  ``cup_bottom`` carries a 22.0 mm bore for a
  608-2RS pressed onto an M8x40 post rising from ``base_plate``, so the cup is
  free to rotate, and is restrained only by an integral arm whose flexure-link
  hole sits at ``r = 40.000 mm``.
* Each bob has a 120 deg included-angle conical recess 6.0 mm deep in its
  bottom face and a stepped shank 10 mm smaller in diameter than its working
  cylinder.
* ``motor_plate`` rides on the two M8 threaded rods, so bob immersion is set by
  sliding the plate and locked with nuts -- adjustable and repeatable.

Print orientation notes
-----------------------
* ``bob_*`` is modelled **hub down**.  In that orientation the conical recess
  opens upward, which is fully self-supporting (each layer removes material
  rather than adding an unsupported roof).  The only overhang is the 5 mm
  annular shoulder under the working cylinder.
* ``cup_bottom`` is modelled with the arm flat on the bed and the bearing
  pocket opening downward.
"""

from __future__ import annotations

import math

import numpy as np
import trimesh

import params as p
import primitives as P

EPS = P.EPS


# --------------------------------------------------------------------------
# local helpers for horizontal features
# --------------------------------------------------------------------------
def _xbore(radius, x_start, x_end, y, z, sections=P.SEG_FUNCTIONAL):
    """Cylindrical cutter running along x from ``x_start`` to ``x_end``."""
    length = abs(float(x_end) - float(x_start))
    direction = (1.0, 0.0, 0.0) if x_end > x_start else (-1.0, 0.0, 0.0)
    tool = P.cylinder(radius, 0.0, length, sections)
    return P.orient(tool, (x_start, y, z), direction)


# ==========================================================================
# 1.  base_plate  -- 150 x 110 x 10 mm; pivot post, load cell, uprights
# ==========================================================================
def base_plate() -> trimesh.Trimesh:
    """Instrument base: 150 x 110 x 10 mm slab, cup axis at local (0, 0)."""
    solid = P.rounded_box(p.BASE_X0, p.BASE_X1, p.BASE_Y0, p.BASE_Y1,
                          0.0, p.BASE_PLATE_T_MM, p.BASE_CORNER_R_MM)

    z0, z1 = -EPS, p.BASE_PLATE_T_MM + EPS
    cuts = []

    # M8x40 cup pivot post, head + washer recessed into the underside.
    cuts.append(P.counterbore(p.M8_CLEAR_DIA_MM, p.M8_WASHER_DIA_MM, 5.0,
                              z0, z1, z_face=0.0, center=(0.0, 0.0)))

    # Two M8 threaded-rod uprights; nut + washer recessed into the underside.
    for cx, cy in p.ROD_POS:
        cuts.append(P.counterbore(p.M8_CLEAR_DIA_MM, p.M8_WASHER_DIA_MM, 4.0,
                                  z0, z1, z_face=0.0, center=(cx, cy)))

    # Four M3 bolts for loadcell_mount, heads recessed into the underside.
    mx, my = p.LOADCELL_MOUNT_CENTRE
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            c = (mx + sx * p.LOADCELL_MOUNT_BOLT_DX,
                 my + sy * p.LOADCELL_MOUNT_BOLT_DY)
            cuts.append(P.counterbore(p.M3_CLEAR_DIA_MM, p.M3_HEAD_DIA_MM,
                                      4.0, z0, z1, z_face=0.0, center=c))

    # Corner holes for rubber feet / bench mounting.
    for c in p.BASE_FOOT_HOLES:
        cuts.append(P.cylinder(0.5 * p.BASE_FOOT_DIA_MM, z0, z1,
                               P.SEG_FUNCTIONAL, center=c))

    mesh = P.difference(solid, cuts)
    return P.assert_solid(mesh, "base_plate")


# ==========================================================================
# 2.  motor_plate -- 100 x 90 x 8 mm; NEMA 17, 22 mm bore, opto, 2x M8
# ==========================================================================
def motor_plate() -> trimesh.Trimesh:
    """Motor carrier that slides on the two M8 rods to set bob immersion."""
    t = p.MOTOR_PLATE_T_MM
    boss_top = t + p.ROD_BOSS_H_MM

    solid = [P.rounded_box(p.MOTOR_X0, p.MOTOR_X1, p.MOTOR_Y0, p.MOTOR_Y1,
                           0.0, t, p.MOTOR_CORNER_R_MM)]
    # Tall guide bosses double the bearing length on the M8 rods, which is what
    # stops the plate from tilting about the line joining the two rods.
    for cx, cy in p.ROD_POS:
        solid.append(P.cylinder(0.5 * p.ROD_BOSS_DIA_MM, 0.0, boss_top,
                                P.SEG_FUNCTIONAL, center=(cx, cy)))
    body = P.union(solid)

    cuts = []
    # 22.0 mm bore for the NEMA 17 pilot boss and the 5 mm shaft.
    cuts.append(P.cylinder(0.5 * p.NEMA17_REGISTER_DIA_MM, -EPS, t + EPS,
                           P.SEG_SMOOTH))
    # Recess the motor face 3 mm to recover shaft length for the encoder disc.
    cuts.append(P.cylinder(0.5 * p.MOTOR_FACE_RECESS_DIA_MM,
                           t - p.MOTOR_FACE_RECESS_DEPTH_MM, t + EPS,
                           P.SEG_FUNCTIONAL))
    # NEMA 17 bolt pattern: 31.0 mm square, M3 from below into the motor.
    half = 0.5 * p.NEMA17_BOLT_SQUARE_MM
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            cuts.append(P.counterbore(p.M3_CLEAR_DIA_MM, p.M3_HEAD_DIA_MM,
                                      p.M3_HEAD_H_MM, -EPS, t + EPS,
                                      z_face=0.0, center=(sx * half, sy * half)))
    # M8 rod bores through plate and boss.
    for cx, cy in p.ROD_POS:
        cuts.append(P.cylinder(0.5 * p.M8_CLEAR_DIA_MM, -EPS, boss_top + EPS,
                               P.SEG_FUNCTIONAL, center=(cx, cy)))
    # Slotted opto sensor: radial slots so the slot can be centred on the disc.
    for cx, cy in p.OPTO_SLOT_CENTRES:
        half_len = 0.5 * p.OPTO_SLOT_LEN_MM
        cuts.append(P.slot(cx - half_len, cx + half_len, cy,
                           p.M3_CLEAR_DIA_MM, -EPS, t + EPS))
    # Motor / opto cable pass-through.
    cuts.append(P.slot(-44.0, -36.0, 0.0, 8.0, -EPS, t + EPS))

    mesh = P.difference(body, cuts)
    return P.assert_solid(mesh, "motor_plate")


# ==========================================================================
# 3.  cup_bottom -- Ø68; epoxy socket, 22 mm bearing bore, arm
# ==========================================================================
def cup_bottom() -> trimesh.Trimesh:
    """Cup base: bearing hub and restraining arm.

    The cup is the STATIONARY member -- it is free to pivot on the 608-2RS
    but is held against the sample's viscous drag by the arm and the load
    cell.  The bob rotates.
    """
    r_flange = 0.5 * p.CUP_BOTTOM_DIA_MM          # 34.0
    r_hub = 0.5 * p.CUP_HUB_DIA_MM                # 26.5
    z_hub = p.CUP_HUB_TOP_Z                       # 8.0
    z_cone = p.CUP_CONE_TOP_Z                     # 15.5
    z_top = p.CUP_FLANGE_TOP_Z                    # 24.0

    r_socket_in = p.R_C_MM                                        # 23.000
    r_socket_out = 0.5 * p.TUBE_OD_MM + p.CLR_EPOXY               # 25.200
    z_socket = z_top - p.CUP_SOCKET_DEPTH_MM                      # 18.0

    arm_hw = 0.5 * p.CUP_ARM_W_MM
    arm_tip_r = 0.5 * p.CUP_ARM_TIP_DIA_MM

    body = P.union([
        # bearing hub
        P.cylinder(r_hub, 0.0, z_hub, P.SEG_SMOOTH),
        # 45 deg transition so the Ø68 flange needs no support
        P.frustum(r_hub, r_flange, z_hub, z_cone, P.SEG_SMOOTH),
        # flange carrying the acrylic-tube socket and the cup floor
        P.cylinder(r_flange, z_cone, z_top, P.SEG_SMOOTH),
        # integral arm, flat on the bed, reaching past the link hole
        P.box(20.0, p.CUP_ARM_HOLE_R_MM + arm_tip_r - 1.0, -arm_hw, arm_hw,
              0.0, p.CUP_ARM_T_MM),
        P.cylinder(arm_tip_r, 0.0, p.CUP_ARM_T_MM, P.SEG_FUNCTIONAL,
                   center=(p.CUP_ARM_HOLE_R_MM, 0.0)),
    ])

    cuts = [
        # 608-2RS press-fit pocket, opening downward onto the bed
        P.cylinder(0.5 * p.BEARING_608_OD_MM, -EPS,
                   p.CUP_BEARING_POCKET_DEPTH_MM, P.SEG_FUNCTIONAL),
        P.chamfer_bore(0.5 * p.BEARING_608_OD_MM, p.CHAMFER_MM, 0.0,
                       downward=False),
        # relief above the bearing for the M8 nyloc; the step between this and
        # the 22.0 mm pocket is the shoulder the outer race seats against
        P.cylinder(0.5 * p.CUP_NUT_RELIEF_DIA_MM,
                   p.CUP_BEARING_POCKET_DEPTH_MM - 0.1,
                   p.CUP_NUT_RELIEF_TOP_Z, P.SEG_FUNCTIONAL),
        # epoxy socket for the 50/46 mm acrylic tube
        P.tube(r_socket_out, r_socket_in, z_socket, z_top + EPS, P.SEG_SMOOTH),
        P.chamfer_bore(r_socket_out, p.CHAMFER_MM, z_top, downward=True),
        P.chamfer_outer(r_socket_in, p.CHAMFER_MM, z_top, upward=True),
        # M3 hole for the flexure link, at r = 40.000 mm
        P.cylinder(0.5 * p.M3_CLEAR_DIA_MM, -EPS, p.CUP_ARM_T_MM + EPS,
                   P.SEG_FUNCTIONAL, center=(p.CUP_ARM_HOLE_R_MM, 0.0)),
    ]

    mesh = P.difference(body, cuts)
    return P.assert_solid(mesh, "cup_bottom")


# ==========================================================================
# 4.  bob (parameterised over the four canonical diameters)
# ==========================================================================
def bob(working_dia: float = None, name: str = None) -> trimesh.Trimesh:
    """Rotating bob, modelled hub-down in its print orientation.

    ``working_dia`` selects the variant; the shank is always 10.0 mm smaller in
    diameter, and the bottom face always carries the 120 deg / 6.0 mm conical
    recess.
    """
    if name is not None:
        spec = p.BOBS[name]
        working_dia = spec["working_dia"]
    elif working_dia is None:
        working_dia = p.BOBS[p.DEFAULT_BOB]["working_dia"]
    working_dia = float(working_dia)
    shank_dia = working_dia - p.BOB_SHANK_DIA_OFFSET_MM
    r_w = 0.5 * working_dia
    r_s = 0.5 * shank_dia

    # z = 0 is the hub face (on the bed); z = 70 is the wetted bottom face.
    z_step = p.BOB_HUB_LENGTH_MM + p.BOB_SHANK_LENGTH_MM       # 40.0
    z_end = p.BOB_TOTAL_LENGTH_MM                              # 70.0

    body = P.union([
        P.cylinder(r_s, 0.0, z_step, P.SEG_SMOOTH),            # hub + shank
        P.cylinder(r_w, z_step, z_end, P.SEG_SMOOTH),          # working cylinder
    ])

    # 120 deg included-angle conical recess, 6.0 mm deep, in the bottom face.
    half_angle = math.radians(0.5 * p.BOB_CONE_INCLUDED_ANGLE_DEG)
    over = 0.5
    z_apex = z_end - p.BOB_CONE_DEPTH_MM
    r_base = math.tan(half_angle) * (p.BOB_CONE_DEPTH_MM + over)
    recess = P.cone(r_base, z_end + over, z_apex, P.SEG_SMOOTH)

    # 5 mm D-bore, 20 mm deep, in the hub end; flat faces +x.
    dbore = P.d_shaft_bore(p.BOB_DBORE_DIA_MM, p.BOB_DBORE_FLAT_DEPTH_MM,
                           -EPS, p.BOB_DBORE_DEPTH_MM, clearance=0.2,
                           flat_dir="+x")

    # M3 brass heat-set insert for the grub screw that bears on the shaft flat.
    z_grub = 10.0
    grub = P.union([
        _xbore(0.5 * p.M3_HEATSET_DIA_MM, r_s + EPS,
               r_s - p.M3_HEATSET_DEPTH_MM, 0.0, z_grub),
        _xbore(0.5 * p.M3_HEATSET_THRU_DIA_MM, r_s + EPS, 1.5, 0.0, z_grub),
    ])

    mesh = P.difference(body, [recess, dbore, grub])
    label = name or f"bob_{working_dia:g}mm"
    return P.assert_solid(mesh, label)


def bob_43mm():
    return bob(name="bob_43mm")


def bob_40mm():
    return bob(name="bob_40mm")


def bob_37mm():
    return bob(name="bob_37mm")


def bob_34mm():
    return bob(name="bob_34mm")


# ==========================================================================
# 5.  encoder_disc -- Ø40, 20 slots, 5 mm D-bore + M3 grub screw
# ==========================================================================
def encoder_disc() -> trimesh.Trimesh:
    """Tachometer chopper disc for the LM393 slotted opto (TACHO_SLOTS = 20)."""
    r_disc = 0.5 * p.ENCODER_DISC_DIA_MM
    t = p.ENCODER_DISC_T_MM
    z_boss = t + p.ENCODER_BOSS_H_MM

    body = P.union([
        P.cylinder(r_disc, 0.0, t, P.SEG_SMOOTH),
        P.cylinder(0.5 * p.ENCODER_BOSS_DIA_MM, t, z_boss, P.SEG_FUNCTIONAL),
    ])

    cuts = [
        P.slot_ring(p.ENCODER_SLOTS, p.ENCODER_SLOT_R_IN_MM,
                    p.ENCODER_SLOT_R_OUT_MM, p.ENCODER_SLOT_DUTY,
                    -EPS, t + EPS, segs=6),
        P.d_shaft_bore(p.BOB_DBORE_DIA_MM, p.BOB_DBORE_FLAT_DEPTH_MM,
                       -EPS, z_boss + EPS, clearance=0.2, flat_dir="+x"),
        # self-tapping M3 grub screw, radial, bearing on the shaft flat
        _xbore(0.5 * p.M3_TAP_DIA_MM, 0.5 * p.ENCODER_BOSS_DIA_MM + EPS,
               1.5, 0.0, t + 0.5 * p.ENCODER_BOSS_H_MM),
    ]

    mesh = P.difference(body, cuts)
    return P.assert_solid(mesh, "encoder_disc")


# ==========================================================================
# 6.  loadcell_mount -- pedestal that clamps the fixed end of the bar cell
# ==========================================================================
def loadcell_mount() -> trimesh.Trimesh:
    """Pedestal for a 12.7 mm square straight-bar cell (TAL221 class).

    The bar passes right through a 12.9 mm square channel and is pinched by two
    M3 screws in heat-set inserts in the roof, so no assumption is made about
    the cell's own hole pattern.  The cell is installed rotated 90 deg about its
    own axis so that its sensing direction is horizontal and tangential.
    """
    fx = 0.5 * p.LCM_FLANGE_X_MM
    fy = 0.5 * p.LCM_FLANGE_Y_MM
    bt = p.LCM_FLANGE_T_MM
    by = 0.5 * p.LCM_BLOCK_Y_MM
    top = p.LCM_BLOCK_TOP_Z

    pocket = p.LOADCELL_BAR_MM + p.LCM_POCKET_CLR_MM        # 12.9
    pz0 = p.LCM_POCKET_FLOOR_Z
    pz1 = pz0 + pocket

    body = P.union([
        P.rounded_box(-fx, fx, -fy, fy, 0.0, bt, 4.0),
        P.box(-fx, fx, -by, by, 0.0, top),
    ])

    cuts = [
        # through channel for the load-cell bar
        P.box(-fx - EPS, fx + EPS, -0.5 * pocket, 0.5 * pocket, pz0, pz1),
    ]
    # four M3 bolts down into base_plate, clear of the block footprint
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            cuts.append(P.cylinder(0.5 * p.M3_CLEAR_DIA_MM, -EPS, bt + EPS,
                                   P.SEG_FUNCTIONAL,
                                   center=(sx * p.LOADCELL_MOUNT_BOLT_DX,
                                           sy * p.LOADCELL_MOUNT_BOLT_DY)))
    # two M3 heat-set clamp screws in the channel roof
    for cx in (-9.0, 9.0):
        cuts.append(P.cylinder(0.5 * p.M3_HEATSET_DIA_MM,
                               top - p.M3_HEATSET_DEPTH_MM, top + EPS,
                               P.SEG_FUNCTIONAL, center=(cx, 0.0)))
        cuts.append(P.cylinder(0.5 * p.M3_HEATSET_THRU_DIA_MM, pz1 - EPS,
                               top + EPS, P.SEG_FUNCTIONAL, center=(cx, 0.0)))

    mesh = P.difference(body, cuts)
    return P.assert_solid(mesh, "loadcell_mount")


# ==========================================================================
# 7.  flexure_link -- 0.8 x 10 x 25 mm strap
# ==========================================================================
def flexure_link() -> trimesh.Trimesh:
    """Strap between the cup arm and the load cell.

    Stiff along its length (tangential, the measured direction) and compliant
    in bending about that length (vertical), so cup height and bearing runout
    do not load the cell.
    """
    hx = 0.5 * p.FLEXURE_L_MM
    hy = 0.5 * p.FLEXURE_W_MM
    body = P.rounded_box(-hx, hx, -hy, hy, 0.0, p.FLEXURE_T_MM,
                         p.FLEXURE_CORNER_R_MM)
    half_pitch = 0.5 * p.FLEXURE_HOLE_PITCH_MM
    cuts = [P.cylinder(0.5 * p.M3_CLEAR_DIA_MM, -EPS, p.FLEXURE_T_MM + EPS,
                       P.SEG_FUNCTIONAL, center=(sx * half_pitch, 0.0))
            for sx in (-1.0, 1.0)]
    mesh = P.difference(body, cuts)
    return P.assert_solid(mesh, "flexure_link")


# ==========================================================================
# registry
# ==========================================================================
BUILDERS = {
    "base_plate": base_plate,
    "motor_plate": motor_plate,
    "cup_bottom": cup_bottom,
    "bob_43mm": bob_43mm,
    "bob_40mm": bob_40mm,
    "bob_37mm": bob_37mm,
    "bob_34mm": bob_34mm,
    "encoder_disc": encoder_disc,
    "loadcell_mount": loadcell_mount,
    "flexure_link": flexure_link,
}

DESCRIPTIONS = {
    "base_plate": "150 x 110 x 10 mm base; M8x40 pivot post, 2x M8 uprights, "
                  "load-cell pedestal bolt pattern",
    "motor_plate": "100 x 90 x 8 mm motor carrier; 22.0 mm bore, NEMA 17 "
                   "31.0 mm square bolt pattern, opto slots, 2x Ø8.4 rod bores",
    "cup_bottom": "Ø68 cup base (stationary member); Ø46.0 epoxy socket, Ø22.0 bearing "
                  "bore, arm to r=40.000",
    "bob_43mm": "default bob, 43.0 mm working Ø, 1.5 mm gap, 33.0 mm shank",
    "bob_40mm": "bob, 40.0 mm working Ø, 3.0 mm gap, 30.0 mm shank",
    "bob_37mm": "bob, 37.0 mm working Ø, 4.5 mm gap, 27.0 mm shank",
    "bob_34mm": "bob, 34.0 mm working Ø, 6.0 mm gap, 24.0 mm shank",
    "encoder_disc": "Ø40 tachometer disc, 20 slots, 5 mm D-bore, M3 grub screw",
    "loadcell_mount": "pedestal clamping the fixed end of a 12.7 mm bar cell",
    "flexure_link": "0.8 x 10 x 25 mm strap, M3 holes at 17.0 mm pitch",
}


def build(name: str) -> trimesh.Trimesh:
    """Build a single named part."""
    try:
        return BUILDERS[name]()
    except KeyError:
        raise KeyError(f"unknown part {name!r}; known: {sorted(BUILDERS)}")


def build_all() -> dict:
    """Build every part in canonical order."""
    return {name: BUILDERS[name]() for name in p.part_names()}
