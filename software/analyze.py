#!/usr/bin/env python3
"""Analyse one LC-RV run: CSV in, viscosity out.

    python analyze.py run.csv --plot flow.png
    python analyze.py ../data/reference/mineral-oil-gap-study.csv \
            --select bob_diameter_mm=42.5

    omega = 2*pi*rpm/60     gdot = omega*R_b/G
    A     = 2*pi*R_c*h      tau  = F/A        mu = tau/gdot

Two layouts, auto-detected. "firmware" is the serial log
(t_s,rpm,force_g,shear_rate_1s,stress_Pa,viscosity_Pas); "reference" is
data/reference/, which carries a raw load_cell_g and states its own geometry.
Only speed and force are read from either; shear rate, stress and viscosity
are recomputed from R_c, R_b, G and h.
"""

import argparse
import csv
import math

import numpy as np

G_STD = 9.80665       # m/s^2
TA_CRIT = 1708.0      # Taylor number at which Couette flow goes unstable

def geometry(cup_id_mm, bob_dia_mm, height_mm):
    """Constants of the model: gdot = c*omega, tau = F/A."""
    R_c, R_b, h = cup_id_mm / 2e3, bob_dia_mm / 2e3, height_mm / 1e3
    if not 0 < R_b < R_c:
        raise SystemExit("bob %.1f does not fit cup %.1f" % (bob_dia_mm, cup_id_mm))
    gap = R_c - R_b
    return {"R_c": R_c, "R_b": R_b, "gap": gap, "h": h,
            "c": R_b / gap, "A": 2 * math.pi * R_c * h}

def read_rows(path):
    """Read a CSV, dropping the '#' comment block the reference files carry."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader([ln for ln in fh if ln.lstrip()[:1] != "#"]))
    if not rows:
        raise SystemExit("%s has no data rows" % path)
    return rows

def num(row, key):
    try:
        return float((row.get(key) or "").strip())
    except ValueError:
        return None

def select(rows, specs):
    """Apply repeatable --select COL=VALUE row filters."""
    for spec in specs or ():
        col, _, want = (s.strip() for s in spec.partition("="))
        if col not in rows[0]:
            raise SystemExit("--select %s: no such column" % spec)
        try:
            keep = [r for r in rows if num(r, col) == float(want)]
        except ValueError:
            keep = [r for r in rows if r[col].strip().lower() == want.lower()]
        if not keep:
            raise SystemExit("--select %s left no rows. Present: %s"
                             % (spec, sorted({r[col] for r in rows})[:12]))
        rows = keep
    return rows

def flow_curve(rows, fmt, geom, rho, bin_rpm, settle):
    """Bin by set speed, drop the unsettled head of each dwell, average."""
    col, bins = "force_g" if fmt == "firmware" else "load_cell_g", {}
    for row in rows:
        rpm, grams = num(row, "rpm"), num(row, col)
        if rpm and rpm > 0 and grams is not None:
            bins.setdefault(round(rpm / bin_rpm) * bin_rpm, []).append(
                (rpm, grams * 1e-3 * G_STD))
    table = []
    for key in sorted(bins):
        block = np.array(bins[key][int(len(bins[key]) * settle):])
        if not len(block):
            continue
        n = len(block)
        omega = 2 * math.pi * block[:, 0] / 60.0
        gdot = geom["c"] * omega
        stress = block[:, 1] / geom["A"]
        mu = stress / gdot
        nu = mu.mean() / rho
        table.append({
            "rpm": key, "n": n, "gdot": gdot.mean(), "stress": stress.mean(),
            "stress_sd": stress.std(ddof=1) if n > 1 else 0.0,
            "mu": mu.mean(), "mu_sd": mu.std(ddof=1) if n > 1 else 0.0,
            "Ta": omega.mean() ** 2 * geom["R_b"] * geom["gap"] ** 3 / nu ** 2
                  if nu > 0 else float("nan")})
    if not table:
        raise SystemExit("no usable rows (need a positive rpm and a force)")
    return table

def fit(table):
    """Least squares stress = mu*gdot + c over the laminar points."""
    ok = [p for p in table if math.isnan(p["Ta"]) or p["Ta"] < TA_CRIT]
    if len(ok) < 2:
        return None
    x, y = (np.array([p[c] for p in ok]) for c in ("gdot", "stress"))
    slope, intercept = np.polyfit(x, y, 1)
    resid = y - (slope * x + intercept)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    return {"mu": slope, "c": intercept, "n": len(ok),
            "r2": 1.0 - resid.dot(resid) / ss_tot if ss_tot else float("nan")}

def report(table, model, geom, path, fmt, rho):
    per_gram = 1e-3 * G_STD / (geom["A"] * geom["c"])
    print("%s  [%s]\ncup R_c %.2f mm, bob R_b %.2f mm, gap %.2f mm, wetted h "
          "%.1f mm\ngdot = %.4f*omega, A = %.4e m^2, mu = %.6f*F_g/omega, "
          "rho = %.0f kg/m^3\n\n"
          "  rpm    n  shear rate      shear stress           viscosity"
          "         Ta\n            1/s              Pa                 Pa.s"
          % (path, fmt, geom["R_c"] * 1e3, geom["R_b"] * 1e3,
             geom["gap"] * 1e3, geom["h"] * 1e3, geom["c"], geom["A"],
             per_gram, rho))
    for p in table:
        print("%5.0f %4d %9.2f  %9.4f +/- %-7.4f %8.5f +/- %-8.5f %7.1f%s"
              % (p["rpm"], p["n"], p["gdot"], p["stress"], p["stress_sd"],
                 p["mu"], p["mu_sd"], p["Ta"],
                 " *" if p["Ta"] >= TA_CRIT else ""))
    flagged = ", ".join("%.0f" % p["rpm"] for p in table if p["Ta"] >= TA_CRIT)
    if flagged:
        print("\n* Ta >= %.0f, no longer laminar Couette: %s rpm. Left out of "
              "the fit." % (TA_CRIT, flagged))
    if model is None:
        return print("\nFewer than two laminar points; no fit.")
    print("\nstress = %.6g*gdot %+.4g   (n = %d, R^2 = %.5f)"
          "\nviscosity from the slope: %.6g Pa.s (%.4g mPa.s)"
          % (model["mu"], model["c"], model["n"], model["r2"],
             model["mu"], model["mu"] * 1e3))
    if model["mu"] < 5e-3:
        print("At or under the bearing-friction floor: treat this as an upper bound.")

def save_plot(table, model, path, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    x = np.array([p["gdot"] for p in table])
    fig, ax = plt.subplots(figsize=(5.2, 4.0))
    ax.errorbar(x, [p["stress"] for p in table], fmt="o", ms=5, capsize=3,
                yerr=[p["stress_sd"] for p in table], label="measured")
    if model is not None:
        xs = np.linspace(0.0, x.max() * 1.05, 50)
        ax.plot(xs, model["mu"] * xs + model["c"], "-", label="fit: %.4g Pa.s "
                "(R2 = %.4f)" % (model["mu"], model["r2"]))
    ax.set(xlabel="shear rate  [1/s]", ylabel="shear stress  [Pa]", title=title)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    print("wrote %s" % path)

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("csv")
    ap.add_argument("--format", default="auto",
                    choices=("auto", "firmware", "reference"))
    ap.add_argument("--select", action="append", metavar="COL=VALUE",
                    help="row filter for the reference files; repeatable")
    ap.add_argument("--cup-id", type=float, metavar="MM", help="cup inner dia")
    ap.add_argument("--bob", type=float, metavar="MM", help="bob diameter")
    ap.add_argument("--height", type=float, metavar="MM", help="wetted height")
    ap.add_argument("--rho", type=float, default=1000.0, metavar="KG_M3",
                    help="sample density, for the Taylor number; glycerol 1260")
    ap.add_argument("--bin", type=float, default=5.0, metavar="RPM",
                    help="width of the speed bins (default 5)")
    ap.add_argument("--settle", type=float, metavar="FRAC",
                    help="unsettled head of each dwell to discard "
                         "(default 0.5 firmware, 0 reference)")
    ap.add_argument("--plot", metavar="PNG", help="save a flow curve here")
    ap.add_argument("--no-plot", action="store_true", help="never plot")
    args = ap.parse_args(argv)

    rows = read_rows(args.csv)
    fmt = args.format
    if fmt == "auto":
        fmt = "reference" if "load_cell_g" in rows[0] else "firmware"
    cup, bob, height = 46.0, 43.0, 30.0
    if fmt == "reference":
        rows = select(rows, args.select)
        seen = sorted({(num(r, "cup_id_mm"), num(r, "bob_diameter_mm"),
                        num(r, "wetted_height_mm")) for r in rows})
        if len(seen) != 1:
            raise SystemExit("%d geometries here (cup, bob, height mm): %s\n"
                             "narrow it, e.g. --select bob_diameter_mm=43"
                             % (len(seen), seen))
        cup, bob, height = seen[0]
    geom = geometry(args.cup_id or cup, args.bob or bob, args.height or height)
    settle = args.settle if args.settle is not None else (
        0.5 if fmt == "firmware" else 0.0)
    table = flow_curve(rows, fmt, geom, args.rho, args.bin, settle)
    model = fit(table)
    report(table, model, geom, args.csv, fmt, args.rho)
    if args.plot and not args.no_plot:
        save_plot(table, model, args.plot,
                  args.csv.replace("\\", "/").rsplit("/", 1)[-1])

if __name__ == "__main__":
    main()
