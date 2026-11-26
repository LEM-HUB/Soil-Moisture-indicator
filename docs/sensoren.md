# Sensoren und ihre Berechnung

Diese Seite beschreibt jede Entität der Integration einzeln: was sie misst,
wie sie rechnet, welche Eingangswerte eingehen, was in Sonderfällen
herauskommt und welche Attribute sie trägt. Die gemeinsamen Grundlagen der
Rechnung stehen in
[berechnungsgrundlagen.md](berechnungsgrundlagen.md).

Alle Werte werden mit einer Nachkommastelle ausgegeben, die Gießmenge ohne
Nachkommastelle. Entitäten, deren Eingangswerte nicht vorliegen, melden
`unknown`; Entitäten, deren Abhängigkeit fehlt (Quellsensor weg, Update
fehlgeschlagen), melden `unavailable`.

## Gemeinsame Eingangswerte

| Größe | Herkunft | Standard | Bereich |
| --- | --- | --- | --- |
| `current` | Zustand des Quellsensors, auf eine Nachkommastelle gerundet | – | 0–100 % |
| `slope` | Steigung der Trendgeraden in Prozentpunkten pro Stunde | – | beliebig, negativ = trocknet |
| `optimal_min` | Untergrenze des Pflanzentyps, sensortyp-kalibriert | 40 % (Zimmerpflanze) | 0–100 % |
| `optimal_max` | Obergrenze, sensortyp-kalibriert | 60 % (Zimmerpflanze) | 0–100 % |
| `optimal_target` | Mitte des Bereichs | 50 % | zwischen den Grenzen |
| `horizon` | Vorhersagehorizont aus den Optionen | 12 h | 1–72 h |
| `history_hours` | Historienfenster aus den Optionen | 24 h | 2–168 h |
| `volume` | Substratvolumen aus den Optionen | 0 L | 0–1000 L |

`slope` und `confidence` stammen aus dem Trendfit über alle Messpunkte im
Historienfenster. Hat der Fit zu wenig Material (unter 3 Messpunkten oder unter
30 Minuten Spannweite), gibt es keinen Trend. Dann rechnen alle Prognosen mit
`slope = 0`, `trend_direction` steht auf `unknown` und `confidence` ist leer.

## Übersicht

| Entität (deutsch) | Einheit | `device_class` | `state_class` |
| --- | --- | --- | --- |
| Aktuelle Feuchtigkeit | % | `moisture` | `measurement` |
| Feuchtigkeitsvorhersage | % | `moisture` | `measurement` |
| Feuchtigkeit in 1/5/7 Tagen | % | `moisture` | `measurement` |
| Feuchtigkeit in 7 Tagen (Wettervorhersage) | % | `moisture` | `measurement` |
| Optimale Feuchtigkeit | % | `moisture` | – |
| Benötigtes Wasser | mL | `volume` | – |
| Tage bis zur Mindestfeuchtigkeit | Tage | `duration` | – |
| Tage bis zur Mindestfeuchtigkeit (Wettervorhersage) | Tage | `duration` | – |
| Gießen nötig | – | – | – |
| Sensordaten veraltet | – | `problem` | – |

Die `unique_id` jeder Entität setzt sich aus der `entry_id` der Einrichtung und
dem Übersetzungsschlüssel zusammen und bleibt deshalb über Umbenennungen und
Optionsänderungen stabil.

---

## 1. Aktuelle Feuchtigkeit

**Schlüssel:** `current` · **Einheit:** % · **Icon:** `mdi:water-percent`

Der unveränderte Messwert des Quellsensors, auf eine Nachkommastelle gerundet –
der einzige Sensor, der keine eigene Rechnung anstellt. Er ist die Basis aller
anderen Entitäten und dient in Dashboards als Messreihe.

**Eingang:** Zustand des konfigurierten `sensor.*`. Nicht numerische Zustände
(`unknown`, `unavailable`, leer, `none`) führen zu einem fehlgeschlagenen
Update und damit zu `unavailable` für alle Entitäten des Geräts.

**Attribute**

| Attribut | Bedeutung |
| --- | --- |
| `source_entity` | Ausgewerteter Quellsensor |
| `plant_type` | Gewählter Pflanzentyp (Schlüssel, z. B. `tomato`) |
| `sensor_type` | `capacitive` oder `resistive` |
| `optimal_min` / `optimal_max` | Kalibrierter Optimalbereich |
| `moisture_status` | `below_optimal`, `optimal` oder `above_optimal` |
| `trend_per_hour` | Steigung in %/h, drei Nachkommastellen |
| `trend_direction` | `falling`, `stable`, `rising` oder `unknown` |
| `confidence` | R² des Fits, zwei Nachkommastellen |
| `samples` | Anzahl der Messpunkte im Fit |
| `last_reading` | Zeitpunkt der letzten Auswertung (UTC, ISO 8601) |
| `last_watering` | Zeitpunkt des zuletzt erkannten Gießens |
| `minutes_since_watering` | Minuten seit dem letzten Gießen |
| `source_last_updated` | Letzte Zustandsänderung des Quellsensors |
| `source_battery` | Batteriestand des Quellsensors, falls gemeldet |

`moisture_status` entsteht aus `classify(current, optimal_min, optimal_max)`:
unter der Untergrenze `below_optimal`, über der Obergrenze `above_optimal`,
sonst `optimal`. Die Grenzen selbst zählen als optimal.

**Beispiel:** `64.3` bei Tomate (60–80 %) → `moisture_status: optimal`.

---

## 2. Feuchtigkeitsvorhersage

**Schlüssel:** `prediction` · **Einheit:** % · **Icon:** `mdi:chart-timeline-variant`

Extrapoliert die aktuelle Feuchtigkeit um den eingestellten Horizont:

```
vorhersage = clamp(current + slope × horizon, 0, 100)
```

`clamp` begrenzt das Ergebnis auf den Sensorbereich 0–100 %, weil ein
Bodenfeuchtesensor nicht negativ und nicht über 100 % messen kann. Ohne
brauchbaren Trend (`slope = 0`) entspricht der Sensor dem aktuellen Wert.

Bewusst wird `current` als Startpunkt verwendet und nicht der Achsenabschnitt
der Regressionsgeraden: Der Sensor springt damit nach jeder neuen Messung auf
den tatsächlichen Wert, statt auf der alten Geraden zu bleiben.

| Horizont | Rechnung | Beispiel (64,3 %, −0,1 %/h) |
| --- | --- | --- |
| 1 h | 64,3 − 0,1 | 64,2 |
| 6 h | 64,3 − 0,6 | 63,7 |
| 12 h (Standard) | 64,3 − 1,2 | 63,1 |
| 72 h (Maximum) | 64,3 − 7,2 | 57,1 |

**Attribute:** `source_entity`, `current_moisture`,
`prediction_horizon_hours`, `history_hours`, `moisture_status`,
`hours_until_optimal_min` (nur bei fallendem Trend), `last_reading`, sowie
`trend_per_hour`, `trend_direction`, `confidence`, `samples`.

---

## 3. Feuchtigkeit in 1, 5 und 7 Tagen

**Schlüssel:** `moisture_1d`, `moisture_5d`, `moisture_7d` · **Einheit:** % ·
**Icon:** `mdi:chart-timeline-variant`

Reine lineare Trocknung ohne Wettereinfluss:

```
wert = clamp(current + slope × 24 × tage, 0, 100)
```

Die drei Sensoren unterscheiden sich nur im Faktor `tage` (1, 5, 7). Sie sind
gedacht als „Was passiert ohne mein Eingreifen?" – eine Aussage, die bewusst
keine Wetterdaten einbezieht und damit auch ohne Wetterentität funktioniert.

| Sensor | Faktor | Beispiel (64,3 %, −0,1 %/h) |
| --- | --- | --- |
| Feuchtigkeit in 1 Tag | 24 h | 61,9 |
| Feuchtigkeit in 5 Tagen | 120 h | 52,3 |
| Feuchtigkeit in 7 Tagen | 168 h | 47,5 |

Bei stärkerer Trocknung greift die untere Grenze: −0,42 %/h ergibt nach 7 Tagen
64,3 − 70,6 = −6,3 und wird als `0.0` ausgegeben.

**Attribute:** `days` (1, 5 bzw. 7), `hours` (24, 120 bzw. 168),
`basis: linear_drying`, `current_moisture`, `trend_per_hour`,
`trend_direction`, `confidence`, `samples`.

---

## 4. Feuchtigkeit in 7 Tagen (Wettervorhersage)

**Schlüssel:** `weather_forecast` · **Einheit:** % · **Icon:**
`mdi:weather-partly-rainy`

Dieselbe 7-Tage-Prognose, aber mit Wettermodell: Statt einer konstanten
Steigung wird jede Stunde (oder jeder Tag) mit Temperatur, Strahlung bzw.
Bewölkung, Luftfeuchte und Regen gewichtet.

```
stündlich:  wert += slope × stundenfaktor + regen
täglich:    wert += slope × 24 × temperaturfaktor × wolkenfaktor + regen
```

Das Modell rechnet bis 168 h (7 Tage). Liefert die Wetterentität weniger
Stunden oder Tage, wird der Rest linear fortgeschrieben. Fehlt die Vorhersage
ganz, bleibt der Sensor `unknown`.

Wie die Faktoren im Einzelnen entstehen, steht in
[berechnungsgrundlagen.md](berechnungsgrundlagen.md#5-wettermodell).

**Beispiel:** 64,3 %, −0,1 %/h, 48 Stunden Vorhersage mit 22 °C, 400 W/m² und
60 % Luftfeuchte (Faktor 1,024), danach linear:

```
48 h × (−0,1 × 1,024)  = −4,92  →  59,4
120 h linear × (−0,1)  = −12,0  →  47,4
```

**Attribute**

| Attribut | Bedeutung |
| --- | --- |
| `days` | Immer `7.0` |
| `basis` | `weather_forecast` |
| `weather_entity` | Ausgewertete Wetterentität |
| `forecast_days_used` | Abgedeckte Tage der Vorhersage (Stunden ÷ 24 bzw. Anzahl Tage, höchstens 7, eine Nachkommastelle) |
| `forecast_kind` | `hourly` oder `daily` |
| `forecast_error` | Grund, falls keine Vorhersage vorliegt (`no_weather_entity`, `multiple_weather_entities`, `empty_forecast`, `service_error: …`) |
| `current_moisture` | Ausgangswert |
| `trend_per_hour`, `trend_direction`, `confidence`, `samples` | Trenddaten des Fits |

---

## 5. Optimale Feuchtigkeit

**Schlüssel:** `optimal` · **Einheit:** % · **dynamisches Icon**

Der Zielwert der Pflanze – die Mitte des kalibrierten Optimalbereichs:

```
optimal = round((optimal_min + optimal_max) / 2, 1)
```

Der Sensor ist damit der einzige, dessen Wert nicht vom Messwert abhängt,
sondern ausschließlich von Pflanzentyp und Sensortyp. Er eignet sich als
Referenzlinie im Verlaufsgraphen und als Zielwert für die Gießmenge.

| Pflanze | Kapazitiv | Resistiv |
| --- | --- | --- |
| Zimmerpflanze | 50,0 | 42,0 |
| Tomate | 70,0 | 62,0 |
| Salat | 67,5 | 59,5 |
| Sukkulente | 25,0 | 17,0 |

Das Icon kommt aus dem Pflanzenprofil (`mdi:potted-plant`, `mdi:grass`,
`mdi:cactus` …) und wechselt mit dem Pflanzentyp.

**Attribute:** `plant_type`, `sensor_type`, `optimal_min`, `optimal_max`,
`current_moisture`, `moisture_status`, `source_entity`.

---

## 6. Benötigtes Wasser

**Schlüssel:** `water_needed` · **Einheit:** mL · **Icon:** `mdi:watering-can`

Wassermenge, um vom aktuellen Wert die **Mitte** des Optimalbereichs zu
erreichen:

```
ml = round(max(0, optimal_target − current) × volume × 10, 0)
```

Die Faustregel dahinter: 1 Prozentpunkt Feuchte in 1 Liter Substrat entspricht
rund 10 ml Wasser (`ML_PER_PERCENT_LITRE`); 1 % von 1 l sind 10 ml.

| Fall | Ergebnis |
| --- | --- |
| `volume = 0` (nicht eingetragen) | `unknown` |
| Feuchte bereits über dem Zielwert | `0` |
| Feuchte genau im Ziel | `0` |
| Feuchte unter dem Ziel | positive Menge |

**Beispiel:** Tomate, Ziel 70 %, aktuell 64,3 %, 10-l-Topf →
`(70 − 64,3) × 10 × 10 = 570 ml`.

Achtung: Der Sensor rechnet auf die **Mitte** des Bereichs, nicht auf den
unteren Rand. Wer nur bis `optimal_min` gießen möchte, nimmt den Differenzwert
selbst vor. Die Menge ist eine Faustregel für lockeres Substrat; verdichtete
Erde, Tontöpfe und Drainage verändern den tatsächlichen Bedarf.

**Attribute:** `container_volume_litres`, `target_moisture`,
`current_moisture`, `water_needed_litres` (gerundet auf zwei Stellen).

---

## 7. Tage bis zur Mindestfeuchtigkeit

**Schlüssel:** `days_until_min` · **Einheit:** Tage · **Icon:** `mdi:timer-sand`

Abstand bis zum unteren Rand des Optimalbereichs auf der Trendgeraden:

```
stunden = (current − optimal_min) / (−slope)
tage    = round(stunden / 24, 1)
```

| Fall | Ergebnis |
| --- | --- |
| `current ≤ optimal_min` | `0.0` (Schwelle erreicht) |
| `slope > −0,05 %/h` (flach oder steigend) | `unknown` |
| fallender Trend | Anzahl Tage |

`0` und `unknown` sind bewusst unterschiedliche Aussagen: „jetzt gießen" bzw.
„nicht absehbar". Der Wert ist eine Extrapolation der aktuellen Steigung – nach
dem Gießen, einem Regenschauer oder bei Temperaturwechsel ändert er sich mit
den nächsten Messungen.

**Beispiel:** 64,3 %, Schwelle 60 %, −0,1 %/h →
`(64,3 − 60) / 0,1 = 43 h → 1,8 Tage`.

**Rundung beachten:** Ausgegeben wird auf eine Nachkommastelle in Tagen. Werte
unter 0,05 Tagen (72 Minuten) runden dadurch auf `0.0` und sind rechnerisch
nicht von „Schwelle bereits erreicht“ zu unterscheiden. Für kurze Vorwarnzeiten
ist das Attribut `hours_until_optimal_min` am Sensor
`Feuchtigkeitsvorhersage` genauer (Stunden, eine Nachkommastelle).

**Attribute:** `basis: linear_drying`, `optimal_min`, `current_moisture`,
`trend_per_hour`, `trend_direction`, `confidence`, `samples`.

---

## 8. Tage bis zur Mindestfeuchtigkeit (Wettervorhersage)

**Schlüssel:** `days_until_min_weather` · **Einheit:** Tage · **Icon:**
`mdi:weather-partly-rainy`

Derselbe Termin, aber mit Wettermodell: Die Feuchte wird Stunde für Stunde (bzw.
Tag für Tag) fortgeschrieben, bis sie `optimal_min` erreicht. Der Bruchteil der
letzten Stunde wird linear interpoliert:

```
anteil = (wert_vor_schritt − schwelle) / (wert_vor_schritt − wert_nach_schritt)
stunden = vergangene_schritte + anteil × schrittweite
```

Die Rechnung nutzt höchstens die ersten 7 Tage (168 h) der Vorhersage – dieselbe
Grenze wie die 7-Tage-Prognose, damit beide Sensoren zusammenpassen. Danach
rechnet sie mit der linearen Steigung weiter, sodass auch Termine jenseits der
Vorhersage beantwortet werden. Regen im Vorhersagezeitraum verschiebt den Termin
nach hinten.

| Fall | Ergebnis |
| --- | --- |
| `current ≤ optimal_min` | `0.0` |
| linearer Trend nicht fallend | `unknown` |
| keine Wettervorhersage | `unknown` |
| Vorhersage vorhanden | Tage, ggf. über die Vorhersage hinaus extrapoliert |

**Beispiel:** 64,3 %, Schwelle 60 %, −0,1 %/h, 48 Stunden mit Faktor 1,024 →
`41,99 h → 1,7 Tage` (linear wären es 1,8 Tage; die Trocknung ist minimal
schneller als der Bezugstag).

Die Rundung auf eine Nachkommastelle in Tagen gilt hier genauso; kurze
Restzeiten unter 72 Minuten erscheinen als `0.0`.

**Attribute:** `basis: weather_forecast`, `optimal_min`, `current_moisture`,
`weather_entity`, `forecast_days_used`, `forecast_kind`, `forecast_error`,
`trend_per_hour`, `trend_direction`, `confidence`, `samples`.

Dieser Sensor ist die Grundlage für das Datum in der Verlaufs-Karte: Datum =
`jetzt + Tage × 86400`.

---

## 9. Gießen nötig

**Schlüssel:** `watering_required` · **Binärsensor** · **Icon:**
`mdi:watering-can`

```
on  ⇔  current < optimal_min
```

Der Sensor schaltet also nicht bei Annäherung, sondern erst beim Unterschreiten
des Optimalbereichs. Wer früher gewarnt werden will, nutzt `days_until_min` in
einer Automation (siehe README).

Die Zustände werden übersetzt angezeigt: `Ja`/`Nein` (englisch `Yes`/`No`).
Bewusst ohne `moisture`-Zustandsklasse, weil diese `on` als „nass" beschriften
würde.

**Attribute:** `current_moisture`, `optimal_min`, `optimal_max`,
`hours_until_optimal_min` (bei fallendem Trend), dazu – sofern vorhanden –
`last_watering`, `minutes_since_watering` und `water_needed_ml`.

---

## 10. Sensordaten veraltet

**Schlüssel:** `data_stale` · **Binärsensor** · **Gerätekategorie:**
Diagnose · **`device_class`:** `problem`

```
on  ⇔  now − source_last_updated > 480 min
       oder das letzte Coordinator-Update ist fehlgeschlagen
       oder es liegt noch kein Datenobjekt vor
```

Die Schwelle von 8 Stunden (`STALE_AFTER_MINUTES`) ist absichtlich großzügig:
Langsam meldende Sensoren und die Nacht sollen keinen Fehlalarm auslösen.
Nach einem Neustart kann der Sensor kurz `on` sein, bis die erste Auswertung
durch ist.

**Attribute:** `data_age_minutes`, `stale_after_minutes`, `source_entity`,
`source_last_updated`, `source_battery`.

---

## Attribut-Referenz

| Attribut | Vorkommen | Typ |
| --- | --- | --- |
| `source_entity` | Aktuelle Feuchtigkeit, Vorhersage, Optimale Feuchtigkeit, Sensordaten veraltet | `str` |
| `plant_type` | Aktuelle Feuchtigkeit, Optimale Feuchtigkeit | `str` |
| `sensor_type` | Aktuelle Feuchtigkeit, Optimale Feuchtigkeit | `str` |
| `optimal_min`, `optimal_max` | Aktuelle Feuchtigkeit, Optimale Feuchtigkeit, Gießen nötig, Tage bis … | `float` |
| `optimal_target` | – (nur als `target_moisture` am Wassersensor) | `float` |
| `current_moisture` | alle außer Optimale Feuchtigkeit | `float` |
| `moisture_status` | Aktuelle Feuchtigkeit, Vorhersage, Optimale Feuchtigkeit | `str` |
| `trend_per_hour` | alle außer Optimale Feuchtigkeit, Wasser, veraltet | `float` |
| `trend_direction` | wie `trend_per_hour` | `str` |
| `confidence` | wie `trend_per_hour` | `float` |
| `samples` | wie `trend_per_hour` | `int` |
| `hours_until_optimal_min` | Vorhersage, Gießen nötig | `float` |
| `days`, `hours` | Feuchtigkeit in 1/5/7 Tagen | `float` |
| `basis` | alle Vorhersage- und Terminsensoren | `str` |
| `weather_entity` | Wettersensoren | `str` |
| `forecast_days_used`, `forecast_kind`, `forecast_error` | Wettersensoren | `int` / `str` |
| `last_reading` | Aktuelle Feuchtigkeit, Vorhersage | ISO-Zeitstempel |
| `last_watering`, `minutes_since_watering` | Aktuelle Feuchtigkeit, Gießen nötig | ISO / `float` |
| `source_last_updated`, `source_battery` | Aktuelle Feuchtigkeit, veraltet | ISO / `float` |
| `data_age_minutes`, `stale_after_minutes` | Sensordaten veraltet | `float` |
| `container_volume_litres`, `water_needed_litres`, `target_moisture` | Benötigtes Wasser | `float` |
| `water_needed_ml` | Gießen nötig | `float` |
| `prediction_horizon_hours`, `history_hours` | Vorhersage | `float` |

Fehlende Werte werden weggelassen, nicht als `null` ausgegeben: Ein Attribut
erscheint nur, wenn der zugrunde liegende Wert vorliegt.

## Zustände richtig lesen

| Zustand | Bedeutung |
| --- | --- |
| Zahl | Gültiger berechneter Wert |
| `0` bei Gießmenge | Kein Wasser nötig |
| `0` bei Tage bis … | Mindestfeuchtigkeit ist bereits erreicht |
| `unknown` | Rechnung nicht möglich (kein Trend, keine Vorhersage, kein Volumen) |
| `unavailable` | Quellsensor fehlt oder liefert keinen Zahlenwert; Update fehlgeschlagen |
