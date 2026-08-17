/* LC-RV configuration -- this is the only file you should need to edit.
   Change CALIBRATION_FACTOR to the number printed by
   firmware/calibration/calibrate, and BOB_DIAMETER_MM if you installed one
   of the other bobs. */

#ifndef LCRV_CONFIG_H
#define LCRV_CONFIG_H

/* ---- Pins (Arduino Nano) ------------------------------------------- */
#define PIN_TACHO      2      /* IR sensor OUT, INT0                    */
#define PIN_HX711_DT   3
#define PIN_HX711_SCK  4
#define PIN_DIR        8      /* A4988 DIR                              */
#define PIN_STEP       9      /* A4988 STEP -- must be D9, it is OC1A   */
#define PIN_POT       A0      /* speed potentiometer wiper              */
#define OLED_ADDR   0x3C      /* SSD1306 on A4/A5, fixed by the TWI pins */

/* ---- Geometry, millimetres ----------------------------------------- */
/* 43.0 gives the 1.5 mm gap; the spare bobs are 40.0 / 37.0 / 34.0.    */
#define BOB_DIAMETER_MM   43.0
#define CUP_RADIUS_MM     23.0
#define WETTED_HEIGHT_MM  30.0
/* Annular gap G = R_c - R_b, so 1.5 mm with the 43 mm bob.            */
#define GAP_MM   (CUP_RADIUS_MM - 0.5 * BOB_DIAMETER_MM)

/* ---- Calibration ---------------------------------------------------- */
/* Raw HX711 counts per gram, from calibrate.ino.  A 100 g cell at
   1 mV/V on 5 V lands near 2e4; the value below is a placeholder,
   replace it with your own.                                           */
#define CALIBRATION_FACTOR  21000.0

/* ---- Hardware ------------------------------------------------------- */
#define LOADCELL_CAPACITY_G 100.0  /* printed rating of the cell        */
#define STEPS_PER_REV       3200   /* 200 full steps x 1/16 microstep   */
#define IR_PULSES_PER_REV   20     /* slots in the printed encoder disc */

#endif /* LCRV_CONFIG_H */
