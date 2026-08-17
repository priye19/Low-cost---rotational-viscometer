"""Parametric dimensions for the LC-RV printed parts.

The dimensions here mirror ``firmware/LC-RV/config.h``; keep them in step by
hand.

UNITS
-----
Everything in this file is millimetres, degrees, or dimensionless.

COORDINATE CONVENTIONS
----------------------
* Every part is modelled in its own local frame with ``z = 0`` on the print bed
  and the part already in its recommended print orientation, so the exported
  STL can be dropped straight into a slicer with no rotation.
* For the parts that sit on the instrument axis (``base_plate``,
  ``motor_plate``, ``cup_bottom``) the local ``x = y = 0`` line is the cup /
  bob rotation axis, so the parts stack by simple translation in ``z``.
* ``+x`` points from the cup axis toward the load cell (the arm
  direction).  ``+y`` is the tangential direction in which the load cell is
  loaded.
"""

from __future__ import annotations

import math

# --------------------------------------------------------------------------
# 0.  Identity
# --------------------------------------------------------------------------
PROJECT = "Low-Cost Rotational Viscometer (LC-RV)"

# --------------------------------------------------------------------------
# 1.  GEOMETRY
# --------------------------------------------------------------------------
R_C_MM = 23.000            # cup inner radius
CUP_ID_MM = 46.000         # cup inner diameter (= 2 * R_C_MM)
R_B_MM = 21.500            # default bob working radius (43 mm bob)
GAP_MM = 1.500             # default annular gap
R_S_MM = 16.500            # default bob shank radius
H_W_MM = 30.000            # bob working-cylinder height (wetted)
BOB_FLOOR_CLEARANCE_MM = 5.000   # bob underside -> cup floor clearance (c)
H_FILL_MM = 35.000         # fill height above cup floor (= c + h_w)
CUP_ARM_HOLE_R_MM = 40.000  # cup axis -> M3 flexure-link hole

# Acrylic cup tube (bought part, not printed)
TUBE_OD_MM = 50.0
TUBE_ID_MM = 46.0
TUBE_WALL_MM = 2.0
TUBE_LENGTH_MM = 100.0

# Bob bottom feature: 120 deg included-angle conical recess, 6.0 mm deep.
BOB_CONE_INCLUDED_ANGLE_DEG = 120.0
BOB_CONE_DEPTH_MM = 6.0
BOB_CONE_MOUTH_RADIUS_MM = 10.39   # canonical; = 6.0 * tan(60 deg) = 10.3923

# Bob envelope: total length 70 mm = 5 mm blind hub + 35 mm shank + 30 mm
# working cylinder (working cylinder at the bottom in use).
BOB_TOTAL_LENGTH_MM = 70.0
BOB_HUB_LENGTH_MM = 5.0
BOB_SHANK_LENGTH_MM = 35.0
BOB_WORKING_LENGTH_MM = 30.0       # == H_W_MM
BOB_SHANK_DIA_OFFSET_MM = 10.0     # shank dia = working dia - 10.0, every variant

# Motor coupling in the bob hub end
BOB_DBORE_DIA_MM = 5.0             # 5 mm D-bore for the NEMA 17 shaft
BOB_DBORE_DEPTH_MM = 20.0
BOB_DBORE_FLAT_DEPTH_MM = 0.5      # standard flat on a 5 mm NEMA 17 shaft

# The four printable bobs: working_dia_mm, R_b, gap, shank_dia_mm, R_s, and
# the shear-rate factor k = R_b/gap, so that gdot = k * omega.
BOBS = {
    "bob_43mm": dict(working_dia=43.0, R_b=21.5, gap=1.5, shank_dia=33.0,
                     R_s=16.5, k=14.3333, default=True),
    "bob_40mm": dict(working_dia=40.0, R_b=20.0, gap=3.0, shank_dia=30.0,
                     R_s=15.0, k=6.6667, default=False),
    "bob_37mm": dict(working_dia=37.0, R_b=18.5, gap=4.5, shank_dia=27.0,
                     R_s=13.5, k=4.1111, default=False),
    "bob_34mm": dict(working_dia=34.0, R_b=17.0, gap=6.0, shank_dia=24.0,
                     R_s=12.0, k=2.8333, default=False),
}
DEFAULT_BOB = "bob_43mm"
K_DEFAULT = 14.3333

# --------------------------------------------------------------------------
# 2.  PRINTED-PART ENVELOPES
# --------------------------------------------------------------------------
BASE_PLATE_X_MM = 150.0
BASE_PLATE_Y_MM = 110.0
BASE_PLATE_T_MM = 10.0

MOTOR_PLATE_X_MM = 100.0
MOTOR_PLATE_Y_MM = 90.0
MOTOR_PLATE_T_MM = 8.0

CUP_BOTTOM_DIA_MM = 68.0

ENCODER_DISC_DIA_MM = 40.0
ENCODER_SLOTS = 20                 # == IR_PULSES_PER_REV in config.h

FLEXURE_T_MM = 0.8
FLEXURE_W_MM = 10.0
FLEXURE_L_MM = 25.0

# Printer envelope. Every part must fit inside it.
BED_X_MM = 200.0
BED_Y_MM = 200.0
BED_Z_MM = 200.0

# --------------------------------------------------------------------------
# 3.  BOUGHT HARDWARE
# --------------------------------------------------------------------------
BEARING_608_ID_MM = 8.0
BEARING_608_OD_MM = 22.0
BEARING_608_W_MM = 7.0
BEARING_608_INNER_RACE_FACE_R_MM = 6.0   # safe clamp radius, clears the 2RS seal

NEMA17_BOLT_SQUARE_MM = 31.0       # bolt circle is a 31.0 mm square
NEMA17_BODY_MM = 42.0
NEMA17_REGISTER_DIA_MM = 22.0      # pilot boss -> motor_plate bore
NEMA17_SHAFT_DIA_MM = 5.0
NEMA17_SHAFT_LENGTH_MM = 24.0      # typical; see docs for the stack-up note

M3_CLEAR_DIA_MM = 3.4
M3_TAP_DIA_MM = 2.6
M3_HEAD_DIA_MM = 6.5
M3_HEAD_H_MM = 3.5
M3_NUT_AF_MM = 5.5
M3_HEATSET_DIA_MM = 4.2            # brass heat-set insert, M3 x 5.0 mm long
M3_HEATSET_DEPTH_MM = 5.5
M3_HEATSET_THRU_DIA_MM = 3.2

M8_CLEAR_DIA_MM = 8.4              # M8 threaded rod / M8x40 pivot bolt clearance
M8_WASHER_DIA_MM = 17.0
M8_NUT_H_MM = 6.5

LOADCELL_BAR_MM = 12.7             # TAL221-class straight bar cross-section
LOADCELL_LENGTH_MM = 80.0
LOADCELL_CAPACITY_G = 100.0

# --------------------------------------------------------------------------
# 4.  PRINT CLEARANCES  (fabrication choices, tuned for 0.4 mm nozzle / PLA)
# --------------------------------------------------------------------------
CLR_SLIP = 0.30        # part must slide freely
CLR_FREE = 0.40        # generous running clearance
CLR_PRESS = 0.00       # press fit -- print nominal, bearings press straight in
CLR_BOLT = 0.40        # added to a bolt shank diameter for a clearance hole
CLR_EPOXY = 0.20       # bond-line gap for the acrylic tube in its socket
WALL_MIN_MM = 1.6      # 4 perimeters at 0.4 mm
FLOOR_MIN_MM = 1.2     # 6 layers at 0.2 mm
CHAMFER_MM = 0.6       # standard lead-in chamfer on bores and spigots

# --------------------------------------------------------------------------
# 5.  cup_bottom -- derived section heights (local frame, z=0 on the bed)
# --------------------------------------------------------------------------
CUP_HUB_DIA_MM = 53.0              # bearing hub OD
CUP_HUB_TOP_Z = 8.0
CUP_CONE_TOP_Z = 15.5              # 45 deg transition hub -> Ø68 flange
CUP_FLANGE_TOP_Z = 24.0            # cup floor plane
CUP_SOCKET_DEPTH_MM = 6.0          # epoxy socket depth for the acrylic tube
CUP_BEARING_POCKET_DEPTH_MM = 7.5  # 7.0 mm bearing + 0.5 mm relief
CUP_NUT_RELIEF_DIA_MM = 19.0       # clears the M8 nyloc; leaves an outer-race shoulder
CUP_NUT_RELIEF_TOP_Z = 15.0
CUP_ARM_T_MM = 8.0                 # arm thickness (z 0 .. 8, prints on the bed)
CUP_ARM_W_MM = 14.0                # arm width
CUP_ARM_TIP_DIA_MM = 14.0

# --------------------------------------------------------------------------
# 6.  base_plate / motor_plate -- derived hole positions (cup axis at 0,0)
# --------------------------------------------------------------------------
BASE_X0, BASE_X1 = -45.0, 105.0    # 150.0 mm
BASE_Y0, BASE_Y1 = -55.0, 55.0     # 110.0 mm
BASE_CORNER_R_MM = 6.0

ROD_POS = ((-31.0, 31.0), (-31.0, -31.0))   # the two M8 uprights, r = 43.84 mm
ROD_BOSS_DIA_MM = 18.0
ROD_BOSS_H_MM = 12.0               # extra guide length on motor_plate

LOADCELL_AXIS_Y_MM = 17.0          # load-cell centreline, = flexure hole spacing
LOADCELL_MOUNT_CENTRE = (86.0, 17.0)
LOADCELL_MOUNT_BOLT_DX = 12.0
LOADCELL_MOUNT_BOLT_DY = 19.0      # outside the pedestal block, so a driver fits

BASE_FOOT_HOLES = ((-35.0, 45.0), (-35.0, -45.0), (95.0, 45.0), (95.0, -45.0))
BASE_FOOT_DIA_MM = 4.5

MOTOR_X0, MOTOR_X1 = -50.0, 50.0   # 100.0 mm
MOTOR_Y0, MOTOR_Y1 = -45.0, 45.0   # 90.0 mm
MOTOR_CORNER_R_MM = 5.0
MOTOR_FACE_RECESS_DIA_MM = 34.0    # sinks the motor 3 mm to recover shaft length
MOTOR_FACE_RECESS_DEPTH_MM = 3.0
OPTO_SLOT_CENTRES = ((28.0, 8.0), (28.0, -8.0))
OPTO_SLOT_LEN_MM = 8.0             # radial adjustment travel

# --------------------------------------------------------------------------
# 7.  encoder_disc / flexure_link / loadcell_mount
# --------------------------------------------------------------------------
ENCODER_DISC_T_MM = 3.0
ENCODER_SLOT_R_IN_MM = 12.0
ENCODER_SLOT_R_OUT_MM = 18.0
ENCODER_SLOT_DUTY = 0.5            # 9 deg slot on an 18 deg pitch
ENCODER_BOSS_DIA_MM = 18.0
ENCODER_BOSS_H_MM = 5.0

FLEXURE_HOLE_PITCH_MM = 17.0       # = FLEXURE_L_MM - 2 * 4.0 mm edge distance
FLEXURE_EDGE_MM = 4.0
FLEXURE_CORNER_R_MM = 2.0

LCM_FLANGE_X_MM = 34.0
LCM_FLANGE_Y_MM = 46.0             # wider than the block so the bolts are reachable
LCM_FLANGE_T_MM = 6.0
LCM_BLOCK_Y_MM = 26.0
LCM_BLOCK_TOP_Z = 36.0
LCM_POCKET_FLOOR_Z = 13.5          # puts the cell top face level with the arm
LCM_POCKET_CLR_MM = 0.2            # 12.7 mm bar -> 12.9 mm pocket

# --------------------------------------------------------------------------
# 8.  Nominal assembly stack (documentation only; z = 0 is the underside of
#     the base plate).  Users trim the exact heights with the M8 nuts and
#     washers on the pivot post.
# --------------------------------------------------------------------------
ASSEMBLY_Z = {
    "base_plate_bottom": 0.0,
    "base_plate_top": 10.0,
    "cup_bottom_z0": 28.0,          # set by the nut/washer stack on the M8 post
    "arm_top": 36.0,                # = cup_bottom_z0 + CUP_ARM_T_MM
    "cup_floor": 52.0,              # = cup_bottom_z0 + CUP_FLANGE_TOP_Z
    "fill_line": 87.0,              # = cup_floor + H_FILL_MM
    "bob_bottom": 57.0,             # = cup_floor + BOB_FLOOR_CLEARANCE_MM
    "bob_top": 127.0,               # = bob_bottom + BOB_TOTAL_LENGTH_MM
    "tube_top": 146.0,              # socket floor + TUBE_LENGTH_MM
    "motor_plate_bottom": 145.0,
    "motor_plate_top": 153.0,
}

def part_names() -> list:
    """Ordered list of the printed parts."""
    return [
        "base_plate",
        "motor_plate",
        "cup_bottom",
        "bob_43mm",
        "bob_40mm",
        "bob_37mm",
        "bob_34mm",
        "encoder_disc",
        "loadcell_mount",
        "flexure_link",
    ]


# --------------------------------------------------------------------------
# 10.  Cheap identities that must hold for this file to be internally
#      consistent.  They run on import so a bad edit is caught immediately.
# --------------------------------------------------------------------------
def _self_check() -> None:
    assert abs(CUP_ID_MM - 2.0 * R_C_MM) < 1e-9, "cup ID must be 2*R_c"
    assert abs(H_FILL_MM - (BOB_FLOOR_CLEARANCE_MM + H_W_MM)) < 1e-9
    assert abs(BOB_TOTAL_LENGTH_MM - (BOB_HUB_LENGTH_MM + BOB_SHANK_LENGTH_MM
                                      + BOB_WORKING_LENGTH_MM)) < 1e-9
    mouth = BOB_CONE_DEPTH_MM * math.tan(
        math.radians(BOB_CONE_INCLUDED_ANGLE_DEG / 2.0))
    assert abs(mouth - BOB_CONE_MOUTH_RADIUS_MM) < 0.005, (
        f"120 deg cone 6 mm deep gives mouth radius {mouth:.4f}, "
        f"file says {BOB_CONE_MOUTH_RADIUS_MM}")
    for name, b in BOBS.items():
        assert abs(b["working_dia"] / 2.0 - b["R_b"]) < 1e-9, name
        assert abs(b["shank_dia"] / 2.0 - b["R_s"]) < 1e-9, name
        assert abs(b["working_dia"] - b["shank_dia"]
                   - BOB_SHANK_DIA_OFFSET_MM) < 1e-9, name
        assert abs(R_C_MM - b["R_b"] - b["gap"]) < 1e-9, name
        k = b["R_b"] / b["gap"]
        assert abs(k - b["k"]) < 5e-4, (name, k, b["k"])


_self_check()
