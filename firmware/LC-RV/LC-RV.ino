/* LC-RV -- low-cost rotational viscometer.  Arduino Nano (ATmega328P).

   A stepper spins a bob inside a cup of sample fluid.  The cup turns on
   a bearing and is held back by a load cell, so viscous drag in the
   annulus appears as a force at the cup wall.  Force, speed and
   geometry give shear rate, shear stress and viscosity; all three are
   computed here and streamed as CSV at 115200 baud.

   Step pulses come out of Timer1 in hardware on D9, so nothing this
   sketch does in software can disturb the rotation.  Nothing in loop()
   blocks either: the HX711 is polled with is_ready(), never through
   get_units(n), which averages n conversions and stalls for roughly
   half a second per call.

   Everything you may want to change lives in config.h.

   Knutson, M.; Weerakoon, S. P.; Ticknor, C. J.; Yavitt, B. M.;
   Priye, A. J. Chem. Educ. 2025, 102 (3), 1138-1145.
   https://doi.org/10.1021/acs.jchemed.4c01490 */

#include <util/atomic.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <HX711.h>
#include "config.h"

/* SRAM: the statics below plus the 1024-byte frame buffer that
   Adafruit_SSD1306::begin() malloc's take most of the Nano's 2 KB.
   That leaves a few hundred bytes of stack -- enough here, but it is
   why there is no String and no second buffer anywhere below. */

/* ---- Geometry, folded to SI at compile time ------------------------ */
/* K_SHEAR: narrow-gap shear rate, gdot = K_SHEAR*w, with R_b/G = 14.333
            for the 43 mm bob.
   AREA:    wetted area of the cup wall, 2*pi*Rc*h = 4.3354e-3 m^2 at
            h = 30 mm.  The load-cell force acts over it: tau = F/A. */
static const float R_B     = BOB_DIAMETER_MM * 0.0005f;
static const float R_C     = CUP_RADIUS_MM * 0.001f;
static const float G_STD   = 9.80665f;
static const float K_SHEAR = R_B / (GAP_MM * 0.001f);
static const float AREA    = 6.283185f * R_C * (WETTED_HEIGHT_MM * 0.001f);

/* ---- Speed --------------------------------------------------------- */
/* Timer1 runs CTC with prescaler 1 and toggles OC1A, so one step pulse
   is two compare matches:  OCR1A = F_CPU/2 * 60 / (STEPS_PER_REV*RPM) - 1
   = 150000/RPM - 1.  400 RPM -> 374, 5 RPM -> 29999.  Below 5 RPM the
   bearing friction dominates, above 400 the motor loses steps. */
static const float    MIN_RPM = 5.0f;
static const float    MAX_RPM = 400.0f;
static const uint32_t OCR_NUM = (F_CPU / 2UL) * 60UL / STEPS_PER_REV;

/* ---- State --------------------------------------------------------- */
HX711 scale;
Adafruit_SSD1306 oled(128, 64, &Wire, -1);

static float g_rpmSet  = MIN_RPM;   /* what Timer1 is doing now         */
static float g_rpmMeas = 0.0f;      /* what the IR sensor sees          */
static bool  g_tachoOk = false;
static float g_counts  = 0.0f;      /* filtered load-cell counts        */
static float g_zero    = 0.0f;      /* counts with the cup unloaded     */
static bool  g_cellOk  = false;
static bool  g_oledOk  = false;
static float g_stress  = 0.0f;      /* kept for the display             */
static float g_visc    = 0.0f;

static volatile uint32_t g_sumUs  = 0;   /* written by the INT0 handler */
static volatile uint32_t g_lastUs = 0;
static volatile uint16_t g_nPulse = 0;
static volatile bool     g_havePulse = false;

static uint32_t g_tSpeed = 0, g_tTacho = 0, g_tRow = 0, g_tOled = 0;
static uint32_t g_tWarn = 0;

/* True once every `period` ms.  millis() differences are unsigned, so
   this stays correct across the 49-day rollover. */
static bool due(uint32_t *t, uint16_t period)
{
  const uint32_t now = millis();
  if (now - *t < period) {
    return false;
  }
  *t = now;
  return true;
}

/* ---- Motor --------------------------------------------------------- */
static void motorSetRpm(float rpm)
{
  if (rpm < MIN_RPM) rpm = MIN_RPM;
  if (rpm > MAX_RPM) rpm = MAX_RPM;
  const uint16_t ocr = (uint16_t)((float)OCR_NUM / rpm + 0.5f) - 1;
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) {
    OCR1A = ocr;
    /* Rewind if the counter has already run past the new TOP; otherwise
       a slow-down leaves a gap of up to 4 ms in the step train. */
    if (TCNT1 > ocr) {
      TCNT1 = 0;
    }
  }
  g_rpmSet = rpm;
}

/* Follow the knob, but slew at 400 RPM/s: a stepper commanded from 5 to
   400 RPM in one step just stalls.  The 1 RPM deadband also absorbs the
   ADC jitter on A0. */
static void speedTick()
{
  const float want = MIN_RPM +
                     analogRead(PIN_POT) * ((MAX_RPM - MIN_RPM) / 1023.0f);
  float d = want - g_rpmSet;
  if (fabs(d) < 1.0f) {
    return;
  }
  if (d >  20.0f) d =  20.0f;
  if (d < -20.0f) d = -20.0f;
  motorSetRpm(g_rpmSet + d);
}

/* ---- Tachometer ---------------------------------------------------- */
static void tachoIsr()
{
  const uint32_t now = micros();
  if (g_havePulse) {
    g_sumUs += now - g_lastUs;
    g_nPulse++;
  }
  g_lastUs = now;
  g_havePulse = true;
}

static void tachoUpdate()
{
  uint32_t sum, last;
  uint16_t n;
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) {
    sum = g_sumUs;
    n = g_nPulse;
    last = g_lastUs;
    g_sumUs = 0;
    g_nPulse = 0;
  }
  if (n > 0) {
    g_rpmMeas = 60000000.0f / (((float)sum / n) * IR_PULSES_PER_REV);
    g_tachoOk = true;
  } else if (micros() - last > 3000000UL) {
    /* At 5 RPM the pulses are 600 ms apart, so an empty window is not
       yet evidence of a stall; three seconds of silence is. */
    g_rpmMeas = 0.0f;
    g_tachoOk = false;
  }
}

/* ---- Load cell ----------------------------------------------------- */
/* is_ready() is a single digitalRead of DOUT; read() then takes about
   0.3 ms.  The HX711 delivers 10 samples per second, so this smooths
   with a light exponential average rather than a long block average. */
static void loadCellPoll()
{
  if (!scale.is_ready()) {
    return;
  }
  const float raw = (float)scale.read();
  g_counts = g_cellOk ? g_counts + 0.25f * (raw - g_counts) : raw;
  g_cellOk = true;
}

/* ---- Output -------------------------------------------------------- */
static void emitRow()
{
  const float rpm = g_tachoOk ? g_rpmMeas : g_rpmSet;
  const float w = rpm * 0.10471976f;              /* 2*pi*RPM/60 [rad/s] */
  const float force_g = (g_counts - g_zero) / CALIBRATION_FACTOR;
  const float gdot = K_SHEAR * w;
  /* tau = F/A, with F = force_g grams weight on the cell. */
  g_stress = force_g * G_STD * 0.001f / AREA;
  g_visc = (gdot > 0.0f) ? g_stress / gdot : 0.0f;

  Serial.print(millis() * 0.001f, 2);
  Serial.print(',');
  Serial.print(rpm, 1);
  Serial.print(',');
  Serial.print(force_g, 3);
  Serial.print(',');
  Serial.print(gdot, 2);
  Serial.print(',');
  Serial.print(g_stress, 4);
  Serial.print(',');
  Serial.println(g_visc, 5);

  if (fabs(force_g) > LOADCELL_CAPACITY_G && due(&g_tWarn, 5000)) {
    Serial.println(F("# load cell near or past full scale"));
  }
}

static void oledUpdate()
{
  oled.clearDisplay();
  oled.setCursor(0, 0);
  oled.print(F("RPM     "));
  oled.print(g_tachoOk ? g_rpmMeas : g_rpmSet, 1);
  oled.setCursor(0, 16);
  oled.print(F("stress  "));
  oled.print(g_stress, 3);
  oled.print(F(" Pa"));
  oled.setCursor(0, 32);
  oled.print(F("visc    "));
  oled.print(g_visc, 4);
  oled.print(F(" Pas"));
  oled.display();
}

/* ---- Setup and loop ------------------------------------------------ */
void setup()
{
  Serial.begin(115200);

  pinMode(PIN_DIR, OUTPUT);
  digitalWrite(PIN_DIR, HIGH);
  pinMode(PIN_STEP, OUTPUT);
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) {
    TCCR1A = _BV(COM1A0);               /* toggle OC1A (D9) on match     */
    TCCR1B = _BV(WGM12) | _BV(CS10);    /* CTC, prescaler 1              */
    TIMSK1 = 0;                         /* no Timer1 interrupt needed    */
    TCNT1 = 0;
  }
  motorSetRpm(MIN_RPM);

  pinMode(PIN_TACHO, INPUT);
  attachInterrupt(digitalPinToInterrupt(PIN_TACHO), tachoIsr, RISING);

  /* Zero the load cell once, before anything turns.  Averaging blocks
     for about a second here, which is harmless with the motor idle. */
  scale.begin(PIN_HX711_DT, PIN_HX711_SCK);
  if (scale.wait_ready_timeout(1000)) {
    g_zero = (float)scale.read_average(10);
    g_counts = g_zero;
    g_cellOk = true;
  } else {
    Serial.println(F("# no HX711 on D3/D4"));
  }

  g_oledOk = oled.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR);
  if (g_oledOk) {
    oled.setTextColor(SSD1306_WHITE);
    oled.setTextSize(1);
  } else {
    Serial.println(F("# no SSD1306 at 0x3C"));
  }

  Serial.println(
      F("t_s,rpm,force_g,shear_rate_1s,stress_Pa,viscosity_Pas"));
}

void loop()
{
  loadCellPoll();
  if (due(&g_tSpeed, 50)) {
    speedTick();
  }
  if (due(&g_tTacho, 1000)) {
    tachoUpdate();
  }
  if (due(&g_tRow, 250)) {
    emitRow();
  }
  if (g_oledOk && due(&g_tOled, 500)) {
    oledUpdate();
  }
}
