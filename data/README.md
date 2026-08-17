# data/

Machine-readable form of the data behind the paper, transcribed from the source
workbook `Rotational Viscometer Data.xlsx`. Measured values are as published.
Where the workbook did not state a geometry or a label, it is inferred and the
inference is flagged in that file's header. Each file opens with `#` lines
giving its source sheet, geometry and caveats.

| File | Rows | What it is | Figure |
|---|---|---|---|
| `mineral-oil-gap-study.csv` | 852 | Mineral oil, 45 mm cup, bobs 39.5/40.5/41.5/42.5 mm, 140-400 rpm | none; recorded alongside Fig. 3 |
| `glycerol-80pct-gap-study.csv` | 3183 | 80 % glycerol. 45 mm cup with bobs 39.5-42.5 mm, and 46 mm cup with bobs 34/37/40/43 mm | Fig. 3 (45 mm cup), SFig. 2 (46 mm cup) |
| `glycerol-concentration-series.csv` | 2880 | Glycerol 20-100 % by mass, 46 mm cup, 43 mm bob, 120-400 rpm | Fig. 4A, 4B |
| `load-cell-response-timeseries.csv` | 193 | Load cell at 1 Hz, liquid soap at 125 rpm; rotation starts at t = 24 s | Fig. 2A |
| `stress-strain-summary.csv` | 27 | Per-speed summary for water, mineral oil and liquid soap | Fig. 2B, 2C |
| `glycerol-viscosity-reference.csv` | 22 | Literature glycerol viscosities at 20 and 25 C (Sheely 1932) | comparison bars in Fig. 4B |

## Columns

| Column | Unit | Meaning |
|---|---|---|
| `fluid`, `concentration_pct` | -, % by mass | sample identity |
| `cup_id_mm`, `bob_diameter_mm`, `gap_mm`, `wetted_height_mm` | mm | cell geometry for that row |
| `rpm`, `rpm_nominal` | rev/min | measured and set speed |
| `replicate` | - | index within one speed group |
| `time_s` | s | timeseries file only |
| `load_cell_g` | g | raw reading, and the only measured quantity |
| `wb_*` | as named | computed in the workbook and repeated on every row of a speed group, so not independent measurements |
| `source_sheet`, `source_column` | - | provenance in the workbook |

A `load_cell_g` of exactly 0, or slightly negative, in the dilute glycerol
columns is a genuine reading at or below the detection floor, not missing data.
An empty cell means no reading was taken.

The `wb_*` columns use the workbook's narrow-gap model, `gdot = omega*R_b/G`
and `tau = F/(2*pi*R_b*h)`. `software/analyze.py` ignores them and recomputes
shear rate and stress from the geometry each file states, using the cup-wall
area `A = 2*pi*R_c*h` rather than the workbook's bob area.
