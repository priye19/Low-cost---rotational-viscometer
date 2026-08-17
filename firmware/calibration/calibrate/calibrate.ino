/* LC-RV load-cell calibration.  Arduino Nano, same wiring as the main
   sketch; only the HX711 has to be connected.

   Tare the cell empty, rest a known mass on it: this sketch divides the
   change in raw HX711 counts by the mass to get CALIBRATION_FACTOR in
   counts per gram, the one value config.h needs.  A second, different
   mass checks that the cell is linear. */

#include <HX711.h>
#define PIN_HX711_DT   3
#define PIN_HX711_SCK  4
#define N_AVERAGE      20       /* raw counts averaged per reading */

HX711 scale;
static float g_tare = 0.0f;
static float g_first = 0.0f;    /* counts per gram from the first mass */

/* Read one line from the serial port, blocking. */
static void readLine(char *buf, uint8_t len)
{
  uint8_t i = 0;
  for (;;) {
    while (!Serial.available())
      ;
    const char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (i > 0) {
        buf[i] = '\0';
        return;
      }
    } else if (i < len - 1) {
      buf[i++] = c;
    }
  }
}

static void tareNow()
{
  g_tare = (float)scale.read_average(N_AVERAGE);
  g_first = 0.0f;
  Serial.print(F("tare "));
  Serial.println(g_tare, 0);
}

static void measure(float massG)
{
  if (massG <= 0.0f) {
    Serial.println(F("type the mass in grams, as a positive number"));
    return;
  }
  const float counts = (float)scale.read_average(N_AVERAGE) - g_tare;
  const float k = counts / massG;
  Serial.print(massG, 3);
  Serial.print(F(" g -> "));
  Serial.print(counts, 0);
  Serial.print(F(" counts, CALIBRATION_FACTOR "));
  Serial.println(k, 1);
  Serial.println(F("Paste that into firmware/LC-RV/config.h."));
  if (g_first == 0.0f) {
    g_first = k;
    Serial.println(F("Now try a second, different mass."));
  } else {
    Serial.print(F("differs from the first mass by "));
    Serial.print((k - g_first) / g_first * 100.0f, 1);
    Serial.println(F(" %"));
  }
}

void setup()
{
  Serial.begin(115200);
  scale.begin(PIN_HX711_DT, PIN_HX711_SCK);
  if (!scale.wait_ready_timeout(1000)) {
    Serial.println(F("no HX711 on D3/D4"));
  }
  Serial.println(F("LC-RV load-cell calibration"));
  Serial.println(F("t tares the empty cell; a number is a mass in grams."));
  tareNow();
}

void loop()
{
  char line[16];
  readLine(line, sizeof(line));
  if (line[0] == 't' || line[0] == 'T') {
    tareNow();
  } else {
    measure(atof(line));
  }
}
