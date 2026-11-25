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
  Wettervorhersage (`weather.get_forecasts`) einbezieht.
- Stellt den Optimalbereich je Pflanzentyp bereit (36 Profile, von Tomate bis
  Aloe Vera).
- Läuft komplett lokal, ohne Cloud und ohne zusätzliche Abhängigkeiten.

## Installation

### HACS (empfohlen)

1. HACS → Integrationen → Drei-Punkte-Menü → *Benutzerdefinierte Repositories*.
2. `https://github.com/LEM-HUB/Soil-Moisture-indicator` als Kategorie
   *Integration* hinzufügen.
3. „Soil Moisture Indicator" installieren und Home Assistant neu starten.

### Manuell

Den Ordner `custom_components/soil_moisture` nach
`<config>/custom_components/soil_moisture` kopieren und Home Assistant neu
starten.

## Einrichtung

1. *Einstellungen → Geräte & Dienste → Integration hinzufügen* →
   „Soil Moisture Indicator".
2. Bodenfeuchtesensor auswählen.
3. Pflanzentyp wählen (bestimmt den Optimalbereich).
4. Optional eine Wetterentität für die wetterbasierte 7-Tage-Vorhersage
   wählen. Ohne Auswahl wird die einzige Wetterentität der Instanz genutzt.
5. Optional einen Namen vergeben (z. B. „Tomaten Gewächshaus").

Über *Konfigurieren* an der Integration lassen sich Pflanzentyp,
Vorhersagehorizont (1–72 h) und Historienfenster (2–168 h) jederzeit ändern.

## Entitäten

Pro Einrichtung entstehen ein Gerät und sieben Sensoren:

| Entität | Einheit | Bedeutung |
| --- | --- | --- |
| `sensor.<name>_aktuelle_feuchtigkeit` | % | Aktueller Messwert des Quellsensors |
| `sensor.<name>_feuchtigkeit_in_1_tag` | % | Linearer Trocknungsverlauf nach 24 h |
| `sensor.<name>_feuchtigkeit_in_5_tagen` | % | Linearer Trocknungsverlauf nach 120 h |
| `sensor.<name>_feuchtigkeit_in_7_tagen` | % | Linearer Trocknungsverlauf nach 168 h |
| `sensor.<name>_feuchtigkeit_in_7_tagen_wettervorhersage` | % | 7 Tage inklusive Wettervorhersage |
| `sensor.<name>_feuchtigkeitsvorhersage` | % | Vorhergesagte Bodenfeuchte nach dem eingestellten Horizont |
| `sensor.<name>_optimale_feuchtigkeit` | % | Mitte des Optimalbereichs der Pflanze |

Die Entity-IDs leiten sich aus dem vergebenen Namen und der Sprache der
Instanz ab; die Tabelle zeigt die deutschen IDs.

### Attribute der Vorhersage

| Attribut | Beschreibung |
| --- | --- |
| `source_entity` | Ausgewerteter Sensor |
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

### Attribute der optimalen Feuchtigkeit

| Attribut | Beschreibung |
| --- | --- |
| `plant_type` | Gewählter Pflanzentyp |
| `optimal_min` / `optimal_max` | Unter- und Obergrenze in % |
| `current_moisture` | Aktueller Messwert |
| `moisture_status` | Aktueller Zustand relativ zum Optimalbereich |

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

Die Bereiche sind Richtwerte für kapazitive/resistive Sensoren, die 0 % (trocken)
bis 100 % (gesättigt) liefern. Sie liegen in `custom_components/soil_moisture/const.py`
und lassen sich dort leicht an den eigenen Sensor anpassen.

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

Für jeden Vorhersagetag der Wetterentität (`weather.get_forecasts`, Typ
`daily`) wird die Trocknung an Temperatur und Bewölkung angepasst und der
Regen des Tages addiert:

`Änderung = Steigung × 24 × Temperaturfaktor × Wolkenfaktor + Regenzuschlag`

| Größe | Formel |
| --- | --- |
| Temperaturfaktor | `1 + 0,03 × (Tageshöchsttemperatur − 20 °C)`, begrenzt auf 0,5–2,0 |
| Wolkenfaktor | `1 − 0,3 × Bewölkung/100` (0,7 bei voller Bewölkung) |
| Regenzuschlag | `2 Prozentpunkte pro mm`, maximal 40 pro Tag |

Fehlende Vorhersagetage werden linear fortgeschrieben. Liegt keine
Wettervorhersage vor, bleibt der Sensor `unknown` und nennt den Grund im
Attribut `forecast_error` (`no_weather_entity`, `multiple_weather_entities`,
`empty_forecast` oder `service_error: …`). Die Konstanten stehen in
`custom_components/soil_moisture/weather.py`.

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

## Fehlerbehebung

- **Sensoren bleiben `unavailable`:** Der Quellsensor liefert keinen numerischen
  Wert (z. B. `unknown`). Sobald er wieder Werte liefert, erholen sich die
  Entitäten automatisch.
- **Vorhersage entspricht dem aktuellen Wert:** Noch zu wenig Geschichte
  (weniger als 3 Messpunkte bzw. unter 30 Minuten) oder der Trend ist flach.
  Nach einigen Messungen erscheint eine echte Vorhersage.
- **Einheit prüfen:** Die Integration erwartet Prozentwerte. Liefert der Sensor
  Rohwerte (z. B. 0–4095), vorher mit einem Template-Sensor auf 0–100 %
  umrechnen.
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
  sensor.py        Vorhersage- und Optimal-Sensor
  manifest.json
  strings.json
  translations/    en, de
```
