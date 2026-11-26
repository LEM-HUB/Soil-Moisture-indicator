# Berechnungsgrundlagen

Diese Seite beschreibt die Rechenwege hinter den Sensoren: wie Messpunkte
entstehen, wie der Trend gefittet wird, wie das Wettermodell die Trocknung
skaliert und welche Grenzwerte gelten. Die Formeln sind aus
`predict.py`, `weather.py` und `coordinator.py` übernommen; die Konstanten
stehen am Ende tabellarisch.

## 1. Messpunkte

Der Coordinator fragt den Quellsensor alle **5 Minuten** ab
(`DEFAULT_UPDATE_INTERVAL_MINUTES`) und legt jeden Wert als Paar
`(Zeitstempel in Epochensekunden, Feuchte in %)` ab. Der Puffer fasst maximal
**5000** Punkte.

Beim ersten Durchlauf nach dem Start lädt die Integration zusätzlich die letzten
`history_hours` (Standard 24 h, einstellbar 2–168 h) aus dem Home-Assistant-
Recorder. Damit steht die Prognose sofort nach einem Neustart, statt bei null zu
beginnen. Ist der Recorder nicht aktiv, startet der Puffer leer.

Vor jedem Fit werden Punkte verworfen, die älter als das Historienfenster sind.
Beim Fit selbst gilt zusätzlich:

- nicht numerische Werte (`unknown`, `unavailable`, `NaN`) werden ignoriert,
- doppelte Zeitstempel werden zusammengefasst (der letzte Wert gewinnt),
- die Punkte werden nach Zeit sortiert.

## 2. Trendfit

Über alle verbleibenden Punkte wird eine Gerade nach der Methode der kleinsten
Quadrate gelegt. `x` ist die Zeit in Stunden relativ zum ersten Punkt, `y` die
Feuchte in Prozent:

```
n     = Anzahl Punkte
x̄, ȳ  = Mittelwerte
Sxx   = Σ (xᵢ − x̄)²
Sxy   = Σ (xᵢ − x̄)(yᵢ − ȳ)
Syy   = Σ (yᵢ − ȳ)²

Steigung   slope = Sxy / Sxx        [Prozentpunkte pro Stunde]
Achsenabs. b     = ȳ − slope × x̄
Bestimmth. R²    = Sxy² / (Sxx × Syy)     (auf 0…1 begrenzt)
```

**Mindestanforderungen:** mindestens **3** Punkte und eine Spannweite von
mindestens **30 Minuten** (`MIN_SPAN_HOURS = 0.5`). Sonst gibt es keinen Trend,
und alle Prognosen fallen auf den aktuellen Wert zurück.

**R² (`confidence`)** sagt, wie gut eine Gerade zu den Punkten passt: 1,0 heißt
perfekt linear, kleine Werte heißen verrauscht (Bewölkung, Gießen, Sensorrauschen).
Bei einer völlig konstanten Reihe ist `Syy = 0`; R² wird dann als 0,0 gemeldet.
R² beeinflusst die Rechnung nicht, sondern dient der Einschätzung.

**Richtung (`trend_direction`)** aus der Steigung:

| Steigung | Richtung |
| --- | --- |
| `slope ≤ −0,05 %/h` | `falling` |
| `−0,05 < slope < 0,05 %/h` | `stable` |
| `slope ≥ 0,05 %/h` | `rising` |
| kein Fit möglich | `unknown` |

Der Schwellwert `FLAT_SLOPE = 0.05` verhindert, dass minimales Sensorrauschen als
Trocknung gilt. Er wirkt auch in der Terminrechnung: Ein Trend mit −0,04 %/h
gilt als stabil, und `Tage bis zur Mindestfeuchtigkeit` bleibt `unknown`.

## 3. Gieß-Erkennung

Eine Wassergabe ist kein Trocknungsprozess. Würde sie in den Fit eingehen,
kippte die Steigung nach oben und alle Prognosen wären für Stunden unbrauchbar.
Deshalb prüft der Coordinator vor jedem neuen Punkt:

```
neuer Wert − letzter Wert ≥ 5 Prozentpunkte   und
Abstand zum letzten Punkt   ≤ 30 Minuten
    ⇒  Puffer leeren, last_watering = jetzt
```

Die Bedingungen stammen aus `WATERING_JUMP_PERCENT = 5.0` und
`WATERING_MAX_GAP_MINUTES = 30`. Der Zeitabstand verhindert Fehlalarme, wenn die
Integration nach einer Pause (Neustart, Recorder-Lücke) einen alten Wert mit
einem neuen vergleicht. Nach dem Leeren beginnt der Trend beim nächsten Punkt
von vorn – die Prognose ist erst nach 3 Punkten bzw. 30 Minuten wieder belastbar.

Ein sehr langsames Gießen (Tropfbewässerung) löst die Erkennung nicht aus, weil
der Sprung unter 5 Prozentpunkten bleibt. Dann geht das Gießen als Anstieg in
den Trend ein und die Prognose beruhigt sich entsprechend langsamer.

## 4. Lineare Projektion

Alle Vorhersagen ohne Wetter rechnen mit derselben Formel:

```
wert(t) = clamp(current + slope × t, 0, 100)
```

`current` ist der aktuelle Messwert (nicht der Fit-Wert), `t` die Zeit in
Stunden. Die Begrenzung auf 0–100 % entspricht dem Messbereich eines
Bodenfeuchtesensors.

## 5. Wettermodell

### Datenquelle

Die Integration ruft `weather.get_forecasts` auf und bevorzugt **stündliche**
Daten, weil damit Tag/Nacht-Verlauf und Regenstunden abgebildet werden. Kann die
Wetterentität nur Tageswerte, wird auf `daily` zurückgegriffen; `forecast_kind`
zeigt, was verwendet wurde. Die Antwort wird **30 Minuten** zwischengespeichert
(`WEATHER_FORECAST_CACHE_MINUTES`), damit nicht bei jedem 5-Minuten-Update ein
Dienst aufgerufen wird.

Ohne konfigurierte Entität nutzt die Integration die einzige Wetterentität der
Instanz. Gibt es keine oder mehrere, bleibt die Wetterprognose aus und
`forecast_error` nennt den Grund.

### Faktoren

Jeder Faktor ist 1,0 bei „durchschnittlichem" Wetter und wird auf einen
sinnvollen Bereich begrenzt, damit einzelne Ausreißer das Modell nicht kippen.

| Größe | Formel | Grenzen | Bezug |
| --- | --- | --- | --- |
| Temperatur | `1 + 0,03 × (T − 20)` | 0,5–2,0 | Tageshöchstwert bzw. Stundentemperatur in °C, Bezug 20 °C |
| Bewölkung | `1 − 0,3 × c/100` | 0,7–1,0 | c in %, volle Bewölkung bremst auf 0,7 |
| Luftfeuchte | `1 + (50 − RH) × 0,008` | 0,6–1,4 | RH in %, trockene Luft trocknet schneller |
| Globalstrahlung | `1 + (G − 300) × 0,0005` | 0,8–1,5 | G in W/m², Bezug 300 W/m² |
| Verdunstung | `E / 0,05` | 0,3–3,0 | E in mm/h, Bezug 0,05 mm/h |
| Regen | `2,0 × mm`, höchstens 40 pro Tag | 0–40 | 1 mm Regen ≈ 2 Prozentpunkte Feuchte |

### Kombination pro Stunde

```
faktor = temperaturfaktor

falls verdunstung gemeldet:
    faktor ×= verdunstungsfaktor                 # ersetzt Strahlung und Luftfeuchte
sonst:
    falls globalstrahlung gemeldet: faktor ×= strahlungsfaktor
    sonst:                          faktor ×= wolkenfaktor
    faktor ×= luftfeuchtefaktor

änderung = slope × faktor + regen
```

Die Reihenfolge ist bewusst: Eine gemeldete Verdunstung fasst Temperatur, Wind
und Luftfeuchte bereits zusammen. Würden Strahlung oder Luftfeuchte zusätzlich
multipliziert, würde die Trocknung doppelt gezählt. Fehlt die Verdunstung,
vertritt die Strahlung Sonne und Wolken; ohne Strahlung bleibt die Bewölkung.

### Kombination pro Tag

```
änderung = slope × 24 × temperaturfaktor × wolkenfaktor + regen
```

Tagesdaten liefern nur Temperatur, Bewölkung und Niederschlag, deshalb entfallen
Strahlung, Luftfeuchte und Verdunstung.

### Regen

Regen erhöht die Feuchte um `2,0` Prozentpunkte pro Millimeter, begrenzt auf
**40 Prozentpunkte pro Kalendertag**. Die Tagesgrenze verhindert, dass eine
einzelne Starkregenstunde den Boden rechnerisch „überflutet". Bei Stundendaten
wird der Zuschlag über den Kalendertag mitgezählt; sobald die 40 Punkte erreicht
sind, bringen weitere Regenstunden desselben Tages nichts mehr.

### Projektion über 7 Tage

Beide Projektionen laufen über **168 Stunden** (`WEATHER_FORECAST_DAYS = 7`).
Jeder Schritt addiert die wettergewichtete Änderung und begrenzt das Ergebnis
auf 0–100 %. Reicht die Vorhersage nicht bis 168 h, wird der Rest mit der
linearen Steigung fortgeschrieben:

```
wert = current
für jede Stunde/Tag der Vorhersage (bis 168 h):
    wert = clamp(wert + änderung, 0, 100)
restliche Zeit linear: wert = clamp(wert + slope × reststunden, 0, 100)
```

### Termin mit Wetter (`Tage bis zur Mindestfeuchtigkeit (Wettervorhersage)`)

Statt zu projizieren, sucht die Rechnung den ersten Schritt, der die Schwelle
unterschreitet, und interpoliert innerhalb dieses Schritts:

```
anteil  = (wert_vorher − schwelle) / (wert_vorher − wert_nachher)
stunden = vergangene_schritte + anteil × schrittweite     (1 h bzw. 24 h)
```

Danach wird mit dem linearen Trend weitergezählt, falls die Vorhersage vorher
endet. Voraussetzungen: `current > optimal_min` und eine fallende Steigung;
sonst ist das Ergebnis `0.0` bzw. `unknown`. Der Termin wird nur berechnet, wenn
auch der lineare Termin existiert – so sind beide Sensoren immer vergleichbar.

## 6. Schwellen und Sensortyp

Der Optimalbereich eines Pflanzentyps wird beim Laden der Optionen kalibriert
(`calibrate_profile`):

```
offset = 0        für kapazitive Sensoren
offset = −8,0     für resistive Sensoren

optimal_min = max(0,   optimal_min + offset)
optimal_max = min(100, optimal_max + offset)

falls optimal_max − optimal_min < 15:
    optimal_max = min(100, optimal_min + 15)
```

Alle abgeleiteten Größen benutzen diese kalibrierten Grenzen – deshalb wirkt eine
Änderung des Sensortyps gleichzeitig auf `Gießen nötig`, beide Terminsensoren,
die Gießmenge und die Attribute. Da die Verschiebung die Breite des Bereichs
nicht ändert und alle Profile mindestens 15 Prozentpunkte breit sind, greift die
Mindestbreite derzeit nur als Sicherheitsnetz für künftige Profile.

## 7. Gießmenge

```
ml = max(0, optimal_target − current) × volume × 10
```

`optimal_target` ist die Mitte des kalibrierten Bereichs, `volume` das
Substratvolumen in Litern. Die 10 ml pro Prozentpunkt und Liter sind eine
Faustregel: 1 % Volumenwasser in 1 l Substrat entspricht 10 ml Wasser. Nur die
Differenz bis zur Mitte wird berechnet; ist der Boden feuchter als die Mitte,
ergibt sich 0.

## 8. Veraltete Daten

```
veraltet ⇔ now − source_last_updated > 480 Minuten
           oder das letzte Update ist fehlgeschlagen
```

`source_last_updated` ist die letzte Zustandsänderung des Quellsensors. Acht
Stunden sind bewusst großzügig, damit langsam meldende Sensoren und die Nacht
keinen Fehlalarm auslösen.

## 9. Konstanten

### Integration (`const.py`, `coordinator.py`)

| Konstante | Wert | Wirkung |
| --- | --- | --- |
| `DEFAULT_UPDATE_INTERVAL_MINUTES` | 5 | Abfrageintervall des Quellsensors |
| `MAX_SAMPLES` | 5000 | Obergrenze des Messpunktpuffers |
| `DEFAULT_HISTORY_HOURS` | 24 | Standard-Historienfenster |
| `MIN_HISTORY_HOURS` / `MAX_HISTORY_HOURS` | 2 / 168 | Grenzen der Option |
| `DEFAULT_PREDICTION_HORIZON` | 12 | Standard-Horizont der Vorhersage |
| `MIN_PREDICTION_HORIZON` / `MAX_PREDICTION_HORIZON` | 1 / 72 | Grenzen der Option |
| `WATERING_JUMP_PERCENT` | 5,0 | Mindestsprung für Gieß-Erkennung |
| `WATERING_MAX_GAP_MINUTES` | 30 | Maximaler Abstand für Gieß-Erkennung |
| `STALE_AFTER_MINUTES` | 480 | Schwelle für „Daten veraltet" |
| `ML_PER_PERCENT_LITRE` | 10,0 | ml Wasser je Prozentpunkt und Liter |
| `SENSOR_TYPE_THRESHOLD_OFFSET` | 0 / −8 | Verschiebung je Sensortyp |
| `MIN_OPTIMAL_RANGE_WIDTH` | 15,0 | Mindestbreite des Optimalbereichs |
| `FORECAST_SENSORS` | 1, 5, 7 | Tage der festen Prognosesensoren |
| `WEATHER_FORECAST_DAYS` | 7 | Reichweite der Wetterprognose |
| `WEATHER_FORECAST_CACHE_MINUTES` | 30 | Cache der Wettervorhersage |
| `MAX_CONTAINER_VOLUME` | 1000 | Obergrenze des Substratvolumens |

### Trend (`predict.py`)

| Konstante | Wert | Wirkung |
| --- | --- | --- |
| `MIN_SAMPLES` | 3 | Mindestanzahl Punkte für einen Fit |
| `MIN_SPAN_HOURS` | 0,5 | Mindestspannweite für einen Fit |
| `FLAT_SLOPE` | 0,05 | Grenze zwischen stabil und fallend/steigend (%/h) |
| `MIN_MOISTURE` / `MAX_MOISTURE` | 0 / 100 | Klammer aller Prognosen |

### Wetter (`weather.py`)

| Konstante | Wert | Wirkung |
| --- | --- | --- |
| `TEMP_REFERENCE_C` | 20 | Bezugstemperatur |
| `TEMP_FACTOR_PER_C` | 0,03 | Zuschlag je Grad |
| `MIN_TEMP_FACTOR` / `MAX_TEMP_FACTOR` | 0,5 / 2,0 | Grenzen des Temperaturfaktors |
| `CLOUD_FACTOR_AT_FULL_COVER` | 0,7 | Faktor bei voller Bewölkung |
| `HUMIDITY_REFERENCE` | 50 | Bezugsluftfeuchte in % |
| `HUMIDITY_FACTOR_PER_PERCENT` | 0,008 | Änderung je Prozentpunkt Luftfeuchte |
| `MIN_HUMIDITY_FACTOR` / `MAX_HUMIDITY_FACTOR` | 0,6 / 1,4 | Grenzen des Luftfeuchtefaktors |
| `RADIATION_REFERENCE_W` | 300 | Bezugsstrahlung in W/m² |
| `RADIATION_FACTOR_PER_W` | 0,0005 | Änderung je W/m² |
| `MIN_RADIATION_FACTOR` / `MAX_RADIATION_FACTOR` | 0,8 / 1,5 | Grenzen des Strahlungsfaktors |
| `EVAPORATION_REFERENCE_MM_H` | 0,05 | Bezugsverdunstung in mm/h |
| `MIN_EVAPORATION_FACTOR` / `MAX_EVAPORATION_FACTOR` | 0,3 / 3,0 | Grenzen des Verdunstungsfaktors |
| `RAIN_PERCENT_PER_MM` | 2,0 | Feuchtezuwachs je mm Regen |
| `MAX_DAILY_RAIN_PERCENT` | 40,0 | Tagesobergrenze des Regenzuschlags |

## 10. Durchgerechnetes Beispiel

**Annahme:** Tomate, kapazitiver Sensor, Optimalbereich 60–80 %, Ziel 70 %,
Substratvolumen 10 l, aktuelle Feuchte 64,3 %, Trend −0,1 %/h, 24 Messpunkte,
R² 0,86.

| Entität | Rechnung | Ergebnis |
| --- | --- | --- |
| Aktuelle Feuchtigkeit | Messwert | 64,3 % |
| Feuchtigkeitsvorhersage (12 h) | 64,3 − 0,1 × 12 | 63,1 % |
| Feuchtigkeit in 1 Tag | 64,3 − 0,1 × 24 | 61,9 % |
| Feuchtigkeit in 5 Tagen | 64,3 − 0,1 × 120 | 52,3 % |
| Feuchtigkeit in 7 Tagen | 64,3 − 0,1 × 168 | 47,5 % |
| Optimale Feuchtigkeit | (60 + 80) / 2 | 70,0 % |
| Benötigtes Wasser | (70 − 64,3) × 10 l × 10 | 570 ml |
| Tage bis zur Mindestfeuchtigkeit | (64,3 − 60) / 0,1 / 24 | 1,8 Tage |
| Gießen nötig | 64,3 < 60? | Nein |

**Mit Wetter:** 48 Stunden Vorhersage mit 22 °C, 400 W/m², 60 % Luftfeuchte und
ohne Regen:

```
Temperaturfaktor  = 1 + 0,03 × (22 − 20)        = 1,060
Strahlungsfaktor  = 1 + (400 − 300) × 0,0005    = 1,050
Luftfeuchtefaktor = 1 + (50 − 60) × 0,008       = 0,920
Stundenfaktor     = 1,060 × 1,050 × 0,920       = 1,024

Änderung je Stunde = −0,1 × 1,024                = −0,1024

48 h Vorhersage    : 64,3 − 4,92                 = 59,4
120 h linear       : 59,4 − 12,0                 = 47,4
```

Die 7-Tage-Wetterprognose liegt mit 47,4 % praktisch gleichauf mit der linearen
(47,5 %); bei warmem, sonnigem Wetter fällt sie deutlich niedriger aus, bei Regen
höher. Der wetterbasierte Gießtermin liegt mit 41,99 h ≈ 1,7 Tagen minimal vor
dem linearen Wert von 43 h.

## 11. Grenzen des Modells

- **Linearität:** Der Trend ist eine Gerade. Austrocknung verläuft real
  degressiv (der Boden trocknet langsamer, je trockener er ist). Für Zeiträume
  von ein bis zwei Tagen ist die Näherung brauchbar, für Wochen nicht.
- **Ein Punkt pro Sensor:** Verdunstung hängt von Topfgröße, Substrat, Wind und
  Pflanze ab; das Modell kennt nur die gemessene Steigung. Deshalb sind die
  Wetterfaktoren Multiplikatoren auf diese Steigung, keine physikalische
  Verdunstungsrechnung.
- **Wetterfaktoren sind Faustregeln:** Temperatur, Strahlung, Luftfeuchte und
  Regen sind grob kalibriert, nicht an einem Standort gemessen.
- **Regen im Topf:** Regen erreicht Zimmerpflanzen nicht. Für Indoor-Pflanzen
  sollte man die Wetterprognose daher als „was wäre draußen" lesen oder die
  Wetterentität weglassen.
- **Sensorkennlinie:** Kapazitive Sensoren sind substratabhängig und nicht
  absolut kalibriert. Die Prozentwerte sind relativ; die Profile gehen von einem
  üblichen DIY-Sensor in Blumenerde aus.
- **Gießmenge:** Die 10 ml je Prozentpunkt und Liter gelten für lockeres
  Substrat mit Ablauf. Verdichtete Erde braucht weniger, Tontöpfe und
  Untersetzer verändern das Bild.
- **Gieß-Erkennung:** Ein Sprung über 5 Prozentpunkte gilt als Gießen. Ein
  Sensor, der beim Bewegen oder Reinigen springt, wird ebenfalls so gewertet.
