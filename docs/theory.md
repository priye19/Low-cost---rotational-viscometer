# Theory

A concentric-cylinder (Couette) viscometer. A bob of radius `R_b` spins at angular velocity
`omega` inside a stationary cup of inner radius `R_c`, with fluid filling the annulus over a
wetted height `h`. Viscous drag tries to turn the cup; a load cell holds it and reads the
restraining force `F`. As built: `R_c` = 23.0 mm, `R_b` = 21.5 mm (43 mm bob), gap
`G = R_c - R_b` = 1.5 mm, `h` = 30.0 mm.

## Shear in the annulus

The bob wall moves at `omega*R_b` and the cup wall is stationary, so the fluid between them
is sheared. When the gap is small next to the radii, the curvature of the annulus makes
little difference and the flow is effectively the flow between two flat plates `G` apart:
the velocity falls linearly across the gap and the shear rate is the same everywhere in it.
The fluid drags on the wetted band of cup wall, and the load cell reads that drag as a
force. Three lines then give the viscosity:

    omega = 2*pi*RPM/60           rad/s
    gdot  = omega*R_b/G           1/s     shear rate in the gap
    A     = 2*pi*R_c*h            m^2     wetted area of the cup wall
    tau   = F/A                   Pa      F in newtons
    mu    = tau/gdot              Pa.s

For the 43 mm bob, `gdot` = 14.3333*`omega` and `A` = 4.3354e-3 m^2, so 5-400 RPM spans
7.5-600 s^-1. With force read in grams that is `mu` = 0.157814*`F_g`/`omega`.

The linear profile is an assumption of the method, not a result. It holds while `G` is small
compared with `R_b`, which is why the default gap is 1.5 mm on a 21.5 mm bob. The 40, 37 and
34 mm bobs open it to 3.0, 4.5 and 6.0 mm; the wider the gap, the weaker the assumption, so
those results are less reliable than the default.

Laminar flow is the other assumption. With the inner cylinder turning, the flow breaks into
Taylor vortices above `Ta = omega^2*R_b*G^3/nu^2 = 1708`, which at 400 RPM and `G` = 1.5 mm
is `nu` = 8.6e-6 m^2/s; `analyze.py` computes `Ta` and leaves any point past it out of the
fit.

## Limits

- Friction in the cup bearing sets a floor near 3-5 mPa.s. Water, at 1 mPa.s, is below it
  and cannot be measured on this instrument.
- The 100 g load cell sets the ceiling, and since force grows with speed the ceiling falls
  as speed rises: about 6 Pa.s at 25 RPM, 1.5 Pa.s at 100 RPM, 0.5 Pa.s at 300 RPM. Thick
  fluids have to be run slowly.
- There is no temperature control and no temperature sensor. Viscosity is strongly
  temperature dependent (glycerol about 7 % per degC), so note the room temperature with a
  thermometer and let the sample sit until it has settled.
- For a non-Newtonian fluid the reported number is an apparent viscosity at the shear rate
  above, not a material constant.
- Absolute values run low against a commercial rheometer. Trends and orders of magnitude
  hold; individual numbers are not traceable.

Knutson et al., *J. Chem. Educ.* **2025**, *102* (3), 1138-1145.
https://doi.org/10.1021/acs.jchemed.4c01490
