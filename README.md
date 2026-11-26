# Soil Moisture Indicator für Home Assistant

Custom Integration, die einen vorhandenen Bodenfeuchtesensor ausliest, den
**Feuchtigkeitsverlauf vorhersagt** und die **optimale Feuchtigkeit für den
jeweiligen Pflanzentyp** als Sensor bereitstellt.

- Liest jeden `sensor` mit Feuchtewerten in `%` (z. B. ESPHome, Zigbee- oder
  MQTT-Bodenfeuchtesensoren).
- Bildet aus der Sensorgeschichte (Recorder) einen linearen Trend und
  extrapoliert ihn um einen einstellbaren Horizont (Standard: 12 h).
- Liefert zusätzlich die **Stunden bis zum unteren Rand des Optimalbereichs** –
  also den Zeitpunkt, ab dem gegossen werden sollte.
- Liefert Sensoren für die aktuelle Feuchtigkeit, den linearen
  Trocknungsverlauf nach 1, 5 und 7 Tagen sowie eine 7-Tage-Vorhersage, die die
  Wettervorhersage (`weather.get_forecasts`) stündlich einbezieht.
- Zählt in Tagen, bis die Mindestfeuchtigkeit erreicht ist – einmal rein linear,
  einmal mit der Wettervorhersage (Regen und Verdunstung).
- Erkennt Gießen an einem plötzlichen Feuchtesprung und startet den Trend neu,
  damit die Prognose nicht durch die Wassergabe verfälscht wird.
- Berechnet aus dem Substratvolumen die nötige Wassermenge in Millilitern und
  meldet per Binärsensor, wann gegossen werden muss bzw. Daten fehlen.
- Stellt den Optimalbereich je Pflanzentyp bereit (36 Profile, von Tomate bis
  Aloe Vera).
- Unterscheidet **kapazitive und resistive Sensoren** und verschiebt den
  Optimalbereich passend zum Sensortyp.
- Enthält zwei fertige Lovelace-Karten (Verlauf der letzten 5 Tage inklusive
  nächstem Gießtermin, Gauge mit grünem Optimalbereich).
- Läuft komplett lokal, ohne Cloud und ohne zusätzliche Abhängigkeiten.

## Installation

### HACS (empfohlen)

1. HACS → Integrationen → Drei-Punkte-Menü → *Benutzerdefinierte Repositories*.
2. `https://github.com/LEM-HUB/Soil-Moisture-indicator` als Kategorie
   *Integration* hinzufügen.
3. „Soil Moisture Indicator" installieren und Home Assistant neu starten.

Solange das Repository nicht in der Standardliste von HACS steht, ist der
Eintrag als *Benutzerdefiniertes Repository* nötig. Die Aufnahme ist vorbereitet
(Brand-Assets, Releases, `hacs.json`), aber noch nicht eingereicht – siehe
[Veröffentlichung](#veröffentlichung).

### Manuell

Den Ordner `custom_components/soil_moisture` nach
`<config>/custom_components/soil_moisture` kopieren und Home Assistant neu
starten.

## Einrichtung

1. *Einstellungen → Geräte & Dienste → Integration hinzufügen* →
   „Soil Moisture Indicator".
2. Bodenfeuchtesensor auswählen.
3. Pflanzentyp wählen (bestimmt den Optimalbereich).
4. Sensortyp wählen: *Kapazitiv* (Standard) oder *Resistiv*.
5. Optional eine Wetterentität für die wetterbasierte 7-Tage-Vorhersage
   wählen. Ohne Auswahl wird die einzige Wetterentität der Instanz genutzt.
6. Optional das Substratvolumen in Litern eintragen (z. B. 5 für einen 5-l-Topf).
   Daraus berechnet die Integration die nötige Gießmenge; `0` schaltet die
   Mengenangabe ab.
7. Optional einen Namen vergeben (z. B. „Tomaten Gewächshaus").

Nach dem Anlegen steht der Eintrag in der Integrationsliste unter
„Soil Moisture Indicator“ – nicht im Tab *Helfer*, weil die Integration als
`integration_type: device` gemeldet ist. Das erzeugte Gerät trägt den oben
vergebenen Namen.

Über *Konfigurieren* an der Integration lassen sich Pflanzentyp, Sensortyp,
Vorhersagehorizont (1–72 h), Historienfenster (2–168 h) und Substratvolumen
jederzeit ändern.

## Entitäten

Pro Einrichtung entstehen ein Gerät, zehn Sensoren und zwei Binärsensoren:

| Entität | Einheit | Bedeutung |
| --- | --- | --- |
| `sensor.<name>_aktuelle_feuchtigkeit` | % | Aktueller Messwert des Quellsensors |
| `sensor.<name>_feuchtigkeit_in_1_tag` | % | Linearer Trocknungsverlauf nach 24 h |
| `sensor.<name>_feuchtigkeit_in_5_tagen` | % | Linearer Trocknungsverlauf nach 120 h |
| `sensor.<name>_feuchtigkeit_in_7_tagen` | % | Linearer Trocknungsverlauf nach 168 h |
| `sensor.<name>_feuchtigkeit_in_7_tagen_wettervorhersage` | % | 7 Tage inklusive Wettervorhersage |
| `sensor.<name>_feuchtigkeitsvorhersage` | % | Vorhergesagte Bodenfeuchte nach dem eingestellten Horizont |
| `sensor.<name>_optimale_feuchtigkeit` | % | Mitte des Optimalbereichs der Pflanze |
| `sensor.<name>_benoetigtes_wasser` | mL | Wassermenge bis zur Mitte des Optimalbereichs (nur mit Substratvolumen) |
| `sensor.<name>_tage_bis_zur_mindestfeuchtigkeit` | Tage | Tage bis zum unteren Rand des Optimalbereichs nach dem linearen Modell |
| `sensor.<name>_tage_bis_zur_mindestfeuchtigkeit_wettervorhersage` | Tage | Tage bis zum unteren Rand inklusive Wettervorhersage |
| `binary_sensor.<name>_giessen_noetig` | – | `on`, sobald die Feuchte unter den Optimalbereich fällt |
| `binary_sensor.<name>_sensordaten_veraltet` | – | `on`, wenn der Quellsensor länger als 8 Stunden nichts liefert |

Die Entity-IDs leiten sich aus dem vergebenen Namen und der Sprache der
Instanz ab; die Tabelle zeigt die deutschen IDs.

Die Zustände der Binärsensoren sind intern `on`/`off`. Angezeigt werden
übersetzte Texte: `binary_sensor.<name>_giessen_noetig` zeigt `Ja`/`Nein`,
`binary_sensor.<name>_sensordaten_veraltet` zeigt `Veraltet`/`Aktuell`
(englisch `Yes`/`No` bzw. `Stale`/`Up to date`). Beide Sensoren tragen keine
`moisture`-Zustandsklasse, weil diese den Boden selbst beschreibt und `on` als
„nass“ beschriften würde – also genau umgekehrt zur Bedeutung hier.

### Attribute der Vorhersage

| Attribut | Beschreibung |
| --- | --- |
| `source_entity` | Ausgewerteter Sensor |
| `sensor_type` | `capacitive` oder `resistive` |
| `current_moisture` | Aktueller Messwert |
| `prediction_horizon_hours` | Horizont der Vorhersage |
| `history_hours` | Verwendetes Historienfenster |
| `trend_per_hour` | Steigung in Prozentpunkten pro Stunde (negativ = trocknet) |
| `trend_direction` | `falling`, `stable` oder `rising` |
| `confidence` | Bestimmtheitsmaß R² der Trendgeraden (0–1) |
| `hours_until_optimal_min` | Stunden bis zum unteren Rand des Optimalbereichs (nur bei fallendem Trend) |
| `samples` | Anzahl der Messpunkte im Fit |
| `moisture_status` | `below_optimal`, `optimal` oder `above_optimal` |
| `last_reading` | Zeitpunkt der letzten Messung |
| `last_watering` | Zeitpunkt des zuletzt erkannten Gießens |
| `minutes_since_watering` | Minuten seit dem letzten Gießen |
| `source_last_updated` | Letzte Zustandsänderung des Quellsensors |
| `source_battery` | Batteriestand des Quellsensors, falls gemeldet |

### Attribute der optimalen Feuchtigkeit

| Attribut | Beschreibung |
| --- | --- |
| `plant_type` | Gewählter Pflanzentyp |
| `sensor_type` | `capacitive` oder `resistive` – Sensortyp, auf den die Grenzen abgestimmt sind |
| `optimal_min` / `optimal_max` | Unter- und Obergrenze in % (bereits auf den Sensortyp angepasst) |
| `current_moisture` | Aktueller Messwert |
| `moisture_status` | Aktueller Zustand relativ zum Optimalbereich |

### Attribute der Gießmenge

| Attribut | Beschreibung |
| --- | --- |
| `container_volume_litres` | Eingetragenes Substratvolumen |
| `target_moisture` | Zielwert (Mitte des Optimalbereichs) |
| `water_needed_litres` | Benötigte Menge in Litern |
| `current_moisture` | Aktueller Messwert |

### Attribute der Tage bis zur Mindestfeuchtigkeit

| Attribut | Beschreibung |
| --- | --- |
| `basis` | `linear_drying` oder `weather_forecast` |
| `optimal_min` | Schwelle, deren Erreichen gezählt wird |
| `current_moisture` | Aktueller Messwert |
| `trend_per_hour` / `confidence` | Steigung und Bestimmtheitsmaß des Trends |
| `weather_entity` | Ausgewertete Wetterentität (nur Wettersensor) |
| `forecast_days_used` / `forecast_kind` | Anzahl und Art der genutzten Vorhersagetage |
| `forecast_error` | Grund, falls keine Wettervorhersage vorlag |

Beide Sensoren liefern den Wert in Tagen mit einer Nachkommastelle. `0` heißt,
die Mindestfeuchtigkeit ist bereits erreicht; `unknown` heißt, der Trend fällt
nicht (stabil oder steigend), sodass die Schwelle nie erreicht wird. Reicht die
Wettervorhersage nicht bis zum erwarteten Tag, rechnet der Wettersensor danach
mit dem linearen Trend weiter; `forecast_days_used` zeigt, wie viele Tage
tatsächlich aus der Vorhersage stammen.

## Pflanzenprofile

| Pflanzentyp | Optimalbereich (%) |
| --- | --- |
| Zimmerpflanze | 40–60 |
| Tomate | 60–80 |
| Paprika | 55–70 |
| Gurke | 65–85 |
| Zucchini | 60–80 |
| Salat | 60–75 |
| Kartoffel | 50–70 |
| Erdbeere | 55–75 |
| Heidelbeere | 55–75 |
| Zitruspflanze | 45–65 |
| Avocado | 50–70 |
| Rose | 50–70 |
| Kräuter | 45–65 |
| Farn | 60–80 |
| Rasen | 40–60 |
| Hecke | 40–65 |
| Baum | 40–65 |
| Bonsai | 50–70 |
| Orchidee | 35–55 |
| Sukkulente / Kaktus | 15–35 |
| Aloe Vera | 10–30 |
| Agave | 10–30 |
| Bogenhanf | 15–30 |
| Glücksfeder | 15–35 |
| Yucca | 20–40 |
| Efeutute | 35–55 |
| Monstera | 40–60 |
| Zimmerpalme | 50–70 |
| Bambus | 55–75 |
| Einblatt | 55–75 |
| Korbmarante | 60–80 |
| Venusfliegenfalle | 55–80 |
| Tillandsie (Luftpflanze) | 30–50 |
| Lavendel | 25–45 |
| Rosmarin | 25–45 |
| Chili | 55–70 |

Die Bereiche sind Richtwerte für kapazitive Sensoren, die 0 % (trocken) bis
100 % (gesättigt) liefern. Sie liegen in
`custom_components/soil_moisture/const.py` und lassen sich dort leicht an den
eigenen Sensor anpassen.

## Sensortyp

In Einrichtung und Optionen lässt sich der Sensortyp wählen:

| Sensortyp | Verhalten | Anpassung des Optimalbereichs |
| --- | --- | --- |
| `capacitive` (Standard) | misst die Dielektrizitätskonstante des Substrats, linear und driftarm | keine |
| `resistive` | misst den Leitwert zwischen zwei Elektroden, reagiert auf Wasser **und** Salze und sättigt im nassen Bereich | −8 Prozentpunkte |

Für dasselbe Substrat meldet ein resistiver Sensor einige Prozentpunkte
feuchter als ein kapazitiver. Damit die Pflanzenprofile weiter stimmen, wird
ihr Optimalbereich beim resistiven Sensor um 8 Prozentpunkte nach unten
verschoben (Konstante `SENSOR_TYPE_THRESHOLD_OFFSET`). Alle daraus abgeleiteten
Schwellen wandern automatisch mit: `giessen_noetig`, die Tage bis zur
Mindestfeuchtigkeit, die Wassermenge und `optimal_min`/`optimal_max` in den
Attributen. Aus 40–60 % (Zimmerpflanze) werden so 32–52 %.

Der Bereich wird nie schmaler als 15 Prozentpunkte und nie außerhalb 0–100 %.
Bestehende Einträge gelten weiter als kapazitiv, solange nichts anderes gewählt
ist. Wer die Rohwerte seines Sensors vorher per Template auf 0–100 % umrechnet,
sollte bei *Kapazitiv* bleiben.

### Attribute der Vorhersagesensoren

| Attribut | Beschreibung |
| --- | --- |
| `days` / `hours` | Horizont des Sensors |
| `basis` | `linear_drying` oder `weather_forecast` |
| `current_moisture` | Aktueller Messwert |
| `trend_per_hour` | Steigung in Prozentpunkten pro Stunde |
| `trend_direction` | `falling`, `stable` oder `rising` |
| `confidence` | Bestimmtheitsmaß R² der Trendgeraden (0–1) |
| `samples` | Anzahl der Messpunkte im Fit |
| `weather_entity` | Genutzte Wetterentität (nur wetterbasierter Sensor) |
| `forecast_days_used` | Anzahl der verwendeten Vorhersagetage |
| `forecast_kind` | `daily` oder `hourly` – Datenquelle der Vorhersage |
| `forecast_error` | Grund, falls keine Wettervorhersage vorliegt |

## Wie die Vorhersage funktioniert

1. Bei jedem Update (alle 5 Minuten) wird der Sensorwert gelesen und als
   Messpunkt gespeichert.
2. Beim Start werden zusätzlich die letzten `history_hours` aus dem
   Home-Assistant-Recorder geladen, damit die Vorhersage einen Neustart
   übersteht.
3. Über die Messpunkte wird eine Regressionsgerade gelegt (Methode der
   kleinsten Quadrate). Die Steigung in Prozentpunkten pro Stunde ist der Trend.
4. Die Vorhersage ist `aktueller Wert + Steigung × Horizont`, begrenzt auf
   0–100 %.
5. Aus der Steigung ergibt sich die Zeit bis zum unteren Rand des
   Optimalbereichs – die praktische „Gießen in …"-Angabe.

### Feste Horizonte: 1, 5 und 7 Tage

Für die Sensoren mit festem Horizont gilt reine lineare Trocknung:

`Wert = aktueller Wert + Steigung × 24 × Tage`, begrenzt auf 0–100 %.

### Wetterbasierte 7-Tage-Vorhersage

Bevorzugt wird die **stündliche** Vorhersage (`weather.get_forecasts`, Typ
`hourly`): Für jede Stunde wird die Trocknung angepasst, der Regen der Stunde
addiert und anschließend die fehlenden Stunden linear fortgeschrieben. Kann
die Wetterentität nur Tageswerte (Typ `daily`), rechnet die Integration in
Tagesschritten. Das Attribut `forecast_kind` zeigt, welche Variante genutzt
wurde.

`Änderung je Stunde = Steigung × Wetterfaktor + Regenzuschlag`

| Größe | Formel |
| --- | --- |
| Temperaturfaktor | `1 + 0,03 × (Temperatur − 20 °C)`, begrenzt auf 0,5–2,0 |
| Verdunstungsfaktor | `Verdunstung / 0,05 mm/h`, begrenzt auf 0,3–3,0 – ersetzt Strahlung und Luftfeuchte |
| Strahlungsfaktor | `1 + (Globalstrahlung − 300 W/m²) × 0,0005`, begrenzt auf 0,8–1,5 |
| Wolkenfaktor | `1 − 0,3 × Bewölkung/100` (0,7 bei voller Bewölkung), nur ohne Strahlungswerte |
| Luftfeuchtefaktor | `1 + (50 − relative Luftfeuchte) × 0,008`, begrenzt auf 0,6–1,4 – nur ohne Verdunstungswerte |
| Regenzuschlag | `2 Prozentpunkte pro mm`, maximal 40 pro Tag |

Fehlende Stunden bzw. Tage werden linear fortgeschrieben. Liegt keine
Wettervorhersage vor, bleibt der Sensor `unknown` und nennt den Grund im
Attribut `forecast_error` (`no_weather_entity`, `multiple_weather_entities`,
`empty_forecast` oder `service_error: …`). Die Konstanten stehen in
`custom_components/soil_moisture/weather.py`.

### Gieß-Erkennung

Steigt die Feuchte innerhalb von 30 Minuten um mindestens 5 Prozentpunkte,
wertet die Integration das als Gießen: Der bisherige Verlauf wird verworfen,
der Trend startet mit dem neuen Wert neu, und `last_watering` /
`minutes_since_watering` erscheinen am Sensor für die aktuelle Feuchtigkeit.
So verfälscht ein Wassergaben-Sprung nicht die Trocknungsprognose.

### Gießmenge

Mit eingetragenem Substratvolumen liefert `sensor.<name>_benoetigtes_wasser`
die Wassermenge bis zur Mitte des Optimalbereichs:

`ml = (Zielwert − aktuelle Feuchte) × Volumen in Litern × 10`

Die Faustregel dahinter: 1 Prozentpunkt Feuchte in 1 Liter Substrat entspricht
rund 10 ml Wasser. Ist die Feuchte bereits im Optimalbereich oder darüber,
steht der Sensor auf `0`; ohne Volumen bleibt er `unknown`.

### Diagnose

`binary_sensor.<name>_sensordaten_veraltet` wird `on`, wenn der Quellsensor
länger als 8 Stunden (480 Minuten) nicht aktualisiert wurde oder das Update
fehlschlägt.
Das Attribut `data_age_minutes` nennt das Alter der letzten Messung,
`source_battery` den Batteriestand des Sensors, falls er einen meldet.

Für einen belastbaren Trend sind mindestens 3 Messpunkte über mindestens
30 Minuten nötig; bei sehr trägen Sensoren kann das Historienfenster erhöht
werden. Die Vorhersage ist eine lineare Extrapolation und damit eine
Momentaufnahme – nach dem Gießen springt die Steigung und die Vorhersage
folgt innerhalb weniger Messungen.

## Beispiele

### Benachrichtigung, wenn in weniger als 6 Stunden gegossen werden muss

```yaml
automation:
  - alias: "Bodenfeuchte: Gießen nötig"
    trigger:
      - platform: numeric_state
        entity_id: sensor.tomaten_gewaechshaus_feuchtigkeitsvorhersage
        below: 62
    condition:
      - condition: template
        value_template: >
          {{ state_attr('sensor.tomaten_gewaechshaus_feuchtigkeitsvorhersage',
                        'hours_until_optimal_min') | float(999) < 6 }}
    action:
      - service: notify.mobile_app
        data:
          message: >
            Bodenfeuchte {{ state_attr('sensor.tomaten_gewaechshaus_feuchtigkeitsvorhersage',
                                       'current_moisture') }} %,
            in {{ state_attr('sensor.tomaten_gewaechshaus_feuchtigkeitsvorhersage',
                             'hours_until_optimal_min') }} h gießen.
```

### Bewässerung nur bei tatsächlich fallendem Trend starten

```yaml
condition:
  - condition: template
    value_template: >
      {{ is_state_attr('sensor.tomaten_gewaechshaus_feuchtigkeitsvorhersage',
                       'trend_direction', 'falling')
         and states('sensor.tomaten_gewaechshaus_feuchtigkeitsvorhersage') | float(100) < 60 }}
```

### Lovelace-Karte

```yaml
type: entities
title: Tomaten
entities:
  - entity: sensor.tomaten_gewaechshaus_feuchtigkeitsvorhersage
  - entity: sensor.tomaten_gewaechshaus_optimale_feuchtigkeit
  - type: attribute
    entity: sensor.tomaten_gewaechshaus_feuchtigkeitsvorhersage
    attribute: hours_until_optimal_min
    name: Gießen in (h)
```

## Dashboard-Karten

Zwei fertige Karten liegen in
[`dashboards/soil_moisture_cards.yaml`](dashboards/soil_moisture_cards.yaml).
Entity-IDs an die eigene Einrichtung anpassen (`sensor.<name>_…`).

### Verlauf der letzten 5 Tage mit nächstem Gießtermin

`history-graph` zeigt 120 Stunden Feuchte und Optimalwert; die Markdown-Karte
darunter rechnet aus `days_until_min_weather` das konkrete Datum der nächsten
Wässerung und nennt zusätzlich den linearen Termin.

```yaml
type: vertical-stack
cards:
  - type: history-graph
    title: Bodenfeuchte – letzte 5 Tage
    hours_to_show: 120
    refresh_interval: 60
    entities:
      - entity: sensor.vera_aktuelle_feuchtigkeit
        name: Aktuell
      - entity: sensor.vera_optimale_feuchtigkeit
        name: Optimal
  - type: markdown
    content: |
      {% set current = states('sensor.vera_aktuelle_feuchtigkeit') %}
      {% set min = state_attr('sensor.vera_aktuelle_feuchtigkeit', 'optimal_min') %}
      {% set weather = states('sensor.vera_tage_bis_zur_mindestfeuchtigkeit_wettervorhersage') %}
      {% set linear = states('sensor.vera_tage_bis_zur_mindestfeuchtigkeit') %}

      **Aktuell:** {{ current }} % · Optimalbereich ab {{ min }} %

      {% if is_number(weather) and weather | float > 0 %}
      **Nächste Wässerung:** {{ (as_timestamp(now()) + weather | float * 86400) | timestamp_custom('%d.%m.%Y, %H:%M') }} · in {{ weather }} Tagen (mit Wettervorhersage)
      {% elif is_number(weather) %}
      **Nächste Wässerung:** jetzt – die Mindestfeuchtigkeit ist erreicht
      {% else %}
      **Nächste Wässerung:** nicht absehbar, der Trend fällt nicht
      {% endif %}
```

### Gauge mit grünem Optimalbereich

Die Karte nutzt `segments` (nur mit `needle: true`), damit der Optimalbereich
grün und alles darüber/darunter gelb bzw. rot erscheint. Die Grenzen 40 und 60
gehören zur Zimmerpflanze; für eine andere Pflanze `optimal_min` und
`optimal_max` aus den Attributen von `sensor.<name>_aktuelle_feuchtigkeit`
einsetzen.

```yaml
type: gauge
entity: sensor.vera_aktuelle_feuchtigkeit
name: Bodenfeuchte
needle: true
min: 0
max: 100
segments:
  - from: 0
    color: '#d32f2f'
  - from: 30
    color: '#f9a825'
  - from: 40
    color: '#2e7d32'
  - from: 60
    color: '#f9a825'
  - from: 75
    color: '#d32f2f'
```

## Veröffentlichung

- **Version:** `custom_components/soil_moisture/manifest.json` und `VERSION` in
  `const.py` tragen dieselbe Nummer. Ist sie neu, erzeugt
  `.github/workflows/release.yml` beim Push auf `main` automatisch den Tag
  `v<version>` und ein GitHub-Release mit generierten Notizen.
- **Changelog:** [`CHANGELOG.md`](CHANGELOG.md).
- **Brand-Assets:** `custom_components/soil_moisture/brand/icon.png` (256×256)
  und `logo.png` (512×512); Home Assistant nutzt sie ab 2026 direkt aus der
  Integration.
- **Standard-Repository von HACS:** noch offen. Dafür muss das Repository
  öffentlich sein, Releases und Brand-Assets enthalten und in
  `hacs/default` unter `integration` eingetragen werden (Pull Request mit dem
  Repo-Namen in alphabetischer Reihenfolge).

## Fehlerbehebung

- **Sensoren bleiben `unavailable`:** Der Quellsensor liefert keinen numerischen
  Wert (z. B. `unknown`). Sobald er wieder Werte liefert, erholen sich die
  Entitäten automatisch.
- **Vorhersage entspricht dem aktuellen Wert:** Noch zu wenig Geschichte
  (weniger als 3 Messpunkte bzw. unter 30 Minuten) oder der Trend ist flach.
  Nach einigen Messungen erscheint eine echte Vorhersage.
- **Einheit prüfen:** Die Integration erwartet Prozentwerte. Liefert der Sensor
  Rohwerte (z. B. 0–4095), vorher mit einem Template-Sensor auf 0–100 %
  umrechnen und den Sensortyp auf *Kapazitiv* lassen.
- **Alles wirkt zu nass:** Bei einem resistiven Sensor den Sensortyp auf
  *Resistiv* stellen – dann liegt der Optimalbereich 8 Prozentpunkte tiefer.
- **Recorder deaktiviert:** Ohne Recorder startet die Vorhersage leer und füllt
  sich ab dem Start der Integration.

## Entwicklung

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
pytest
```

Die Vorhersage-Mathematik (`predict.py`) und die Pflanzenprofile (`const.py`)
sind bewusst frei von Home-Assistant-Importen und damit ohne laufende
Home-Assistant-Instanz testbar.

## Struktur

```
custom_components/soil_moisture/
  __init__.py      Setup und Options-Reload
  config_flow.py   Einrichtung und Optionen
  const.py         Konstanten und Pflanzenprofile
  coordinator.py   Sensorabfrage, Recorder-Historie, Trendberechnung
  predict.py       Trend-/Vorhersage-Mathematik (HA-frei)
  weather.py       Wettermodell für die Trocknung (HA-frei)
  sensor.py        Feuchte-, Vorhersage-, Optimal- und Gießmengen-Sensor
  binary_sensor.py Gießen nötig und Diagnose
  brand/           icon.png und logo.png für Home Assistant
  manifest.json
  strings.json
  translations/    en, de

dashboards/         fertige Lovelace-Karten
.github/           Release-Workflow
CHANGELOG.md
```
