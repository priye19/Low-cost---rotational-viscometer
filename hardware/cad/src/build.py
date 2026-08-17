#!/usr/bin/env python3
"""Build every LC-RV printed part: export binary STLs into hardware/cad/stl/.

Geometry comes from ``params.py``, which mirrors ``firmware/LC-RV/config.h``.

Usage
-----
    python build.py                 # export every STL and print a mass table
    python build.py --part bob_43mm # a single part

Mass estimate
-------------
Printed parts are not solid, so mass is estimated as

    m = rho_PLA * V_solid * (SHELL_FRACTION + (1 - SHELL_FRACTION) * infill)

with ``rho_PLA = 1.24 g/cm^3`` and ``SHELL_FRACTION = 0.35``, i.e. perimeters and
top/bottom layers are treated as fully dense and account for about 35 % of the solid
volume of a part of this size. This is an approximation for planning filament use --
your slicer is authoritative. Print times are scaled from the same estimate through
``TIME_PER_CM3_MIN`` and are likewise indicative.
"""

from __future__ import annotations

import argparse
import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import trimesh  # noqa: E402

import parts as parts_mod  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CAD_DIR = os.path.dirname(HERE)
STL_DIR = os.path.join(CAD_DIR, "stl")

RHO_PLA_G_CM3 = 1.24
SHELL_FRACTION = 0.35
DEFAULT_INFILL = 0.20
# Rough FDM throughput at 0.2 mm layer / 0.4 mm nozzle, including travel and
# non-printing moves.
TIME_PER_CM3_MIN = 3.1

# Parts that are not needed for a default build (gap-study spares).
OPTIONAL = {"bob_34mm", "bob_37mm", "bob_40mm"}


def part_builders():
    """Return {name: callable} for every concrete printable part.

    Excludes the parameterised ``bob`` helper (its four concrete diameters are
    exported individually) and any non-part helper in the module.
    """
    out = {}
    for name, fn in inspect.getmembers(parts_mod, inspect.isfunction):
        if name.startswith("_"):
            continue
        if name in {"bob", "build", "build_all"}:
            continue
        if fn.__module__ != parts_mod.__name__:
            continue
        # Skip helpers that cannot be called with no arguments. Parameters that
        # have defaults are fine -- only a *required* parameter disqualifies a
        # function from being a concrete, directly printable part.
        if any(p.default is inspect.Parameter.empty
               and p.kind in (inspect.Parameter.POSITIONAL_ONLY,
                              inspect.Parameter.POSITIONAL_OR_KEYWORD,
                              inspect.Parameter.KEYWORD_ONLY)
               for p in inspect.signature(fn).parameters.values()):
            continue
        out[name] = fn
    return dict(sorted(out.items()))


def estimate(mesh, infill=DEFAULT_INFILL):
    """Return (volume_cm3, mass_g, time_min) for a printed part."""
    vol_cm3 = float(mesh.volume) / 1000.0
    mass = RHO_PLA_G_CM3 * vol_cm3 * (SHELL_FRACTION + (1.0 - SHELL_FRACTION) * infill)
    return vol_cm3, mass, mass / RHO_PLA_G_CM3 * TIME_PER_CM3_MIN


def main():
    ap = argparse.ArgumentParser(description="Build LC-RV printed parts.")
    ap.add_argument("--part", help="build only this part")
    ap.add_argument("--infill", type=float, default=DEFAULT_INFILL,
                    help="infill fraction used for the mass estimate (default 0.20)")
    args = ap.parse_args()

    os.makedirs(STL_DIR, exist_ok=True)

    builders = part_builders()
    if args.part:
        if args.part not in builders:
            sys.exit("unknown part %r; available: %s" % (args.part, ", ".join(builders)))
        builders = {args.part: builders[args.part]}

    rows = []
    failures = []
    for name, fn in builders.items():
        mesh = fn()
        if not mesh.is_watertight:
            failures.append("%s is not watertight" % name)
        stl_path = os.path.join(STL_DIR, name + ".stl")
        mesh.export(stl_path)
        # Re-open what we just wrote. Binary STL stores float32 vertices, so a
        # model that is watertight in float64 can still land on disk with a
        # hole in it; the file is the thing people print, so check the file.
        written = trimesh.load(stl_path, file_type="stl")
        if not written.is_watertight:
            failures.append("%s.stl is not watertight as exported" % name)
        if not written.is_winding_consistent:
            failures.append("%s.stl has inconsistent winding as exported" % name)
        if len(written.faces) != len(mesh.faces):
            failures.append("%s.stl has %d triangles, model has %d"
                            % (name, len(written.faces), len(mesh.faces)))
        vol, mass, minutes = estimate(mesh, args.infill)
        rows.append({
            "name": name,
            "bbox": mesh.extents,
            "tris": len(mesh.faces),
            "vol": vol,
            "mass": mass,
            "time": minutes,
            "kb": os.path.getsize(stl_path) / 1024.0,
            "optional": name in OPTIONAL,
        })

    hdr = ("%-18s %-22s %8s %8s %8s %9s"
           % ("part", "bbox mm (X x Y x Z)", "tris", "vol cm3", "mass g", "time min"))
    print(hdr)
    print("-" * len(hdr))
    core_mass = core_time = 0.0
    opt_mass = opt_time = 0.0
    for r in rows:
        bbox = "%.1f x %.1f x %.1f" % tuple(r["bbox"])
        print("%-18s %-22s %8d %8.2f %8.1f %9.0f"
              % (r["name"], bbox, r["tris"], r["vol"], r["mass"], r["time"]))
        if r["optional"]:
            opt_mass += r["mass"]
            opt_time += r["time"]
        else:
            core_mass += r["mass"]
            core_time += r["time"]

    print("-" * len(hdr))
    print("core build      : %6.1f g  %5.1f h" % (core_mass, core_time / 60.0))
    print("spare bobs      : %6.1f g  %5.1f h" % (opt_mass, opt_time / 60.0))
    print("everything      : %6.1f g  %5.1f h" % (core_mass + opt_mass, (core_time + opt_time) / 60.0))
    print("assumptions     : PLA %.2f g/cm3, %.0f%% infill, shell fraction %.2f, %.1f min/cm3"
          % (RHO_PLA_G_CM3, args.infill * 100, SHELL_FRACTION, TIME_PER_CM3_MIN))
    print("STLs written to : %s" % STL_DIR)

    if failures:
        print("\nFAILURES:")
        for f in failures:
            print("  " + f)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
