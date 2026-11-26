# Bodenfeuchte-Indikator

Custom Integration für Home Assistant, die aus einem vorhandenen
Bodenfeuchtesensor einen **Trocknungstrend**, eine **Vorhersage** und die
**optimale Feuchtigkeit der Pflanze** ableitet.

Die Integration misst nicht selbst. Sie liest einen beliebigen `sensor` mit
Werten in Prozent (ESPHome, Zigbee, MQTT, analoge Sensoren über ADC) und
rechnet daraus alles Weitere: Trend, Prognose, Gießzeitpunkt, Wassermenge und
einen Diagnosewert für die Datenqualität. Alles läuft lokal, ohne Cloud und
ohne zusätzliche Abhängigkeiten.

- **Trend** aus der Sensorgeschichte per Regressionsgerade (Standard: 24 h).
- **Vorhersage** für 12 h (einstellbar), 1, 5 und 7 Tage.
- **Wetterbasierte 7-Tage-Vorhersage** aus `weather.get_forecasts`, stündlich
  wenn verfügbar, sonst täglich.
- **Gießtermin** in Tagen bis zum unteren Rand des Optimalbereichs – linear und
  mit Wettervorhersage.
- **Gießmenge** in Millilitern aus dem Substratvolumen.
- **Gieß-Erkennung**: ein Feuchtesprung startet den Trend neu, damit eine
  Wassergabe die Prognose nicht verfälscht.
- **36 Pflanzenprofile** und **zwei Sensortypen** (kapazitiv/resistiv).
- **Zwei fertige Lovelace-Karten** (Verlauf, Gauge).

Aktuelle Version: **1.4.0** (siehe [CHANGELOG.md](CHANGELOG.md)).

## Datenfluss

```
Quellsensor (%)           Recorder-Historie
      │                          │
      └──────────┬───────────────┘
                 ▼
     Messpunkte (Zeitstempel, %)
                 ▼
     Trendgerade: Steigung in %/h  ──────► trend_per_hour, confidence
                 │
      ┌──────────┼──────────────┬─────────────────┐
      ▼          ▼              ▼                 ▼
  Prognose   Gießtermin    Gießmenge        Wettermodell
  (linear)   (Tage)         (ml)            (Regen, Temperatur,
                                            Strahlung, Wind)
```

## Installation

### HACS (empfohlen)

1. HACS → Integrationen → Drei-Punkte-Menü → *Benutzerdefinierte
   Repositories*.
2. `https://github.com/LEM-HUB/Soil-Moisture-indicator` als Kategorie
   *Integration* hinzufügen.
3. „Soil Moisture Indicator“ installieren und Home Assistant neu starten.

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
   „Soil Moisture Indicator“.
2. Bodenfeuchtesensor auswählen.
3. Pflanzentyp wählen – bestimmt den Optimalbereich.
4. Sensortyp wählen: *Kapazitiv* (Standard) oder *Resistiv*.
5. Optional eine Wetterentität wählen. Ohne Auswahl wird die einzige
   Wetterentität der Instanz genutzt; gibt es mehrere, bleibt die
   wetterbasierte Vorhersage aus.
6. Optional das Substratvolumen in Litern eintragen (0 schaltet die
   Gießmenge ab).
7. Optional einen Namen vergeben (z. B. „Tomaten Gewächshaus“).

Der Eintrag erscheint in der Integrationsliste (nicht im Helfer-Tab, weil die
Integration als `integration_type: device` gemeldet ist) und erzeugt ein Gerät
mit allen Entitäten.

### Optionen

Über *Konfigurieren* an der Integration jederzeit änderbar:

| Option | Wertebereich | Standard | Wirkung |
| --- | --- | --- | --- |
| Pflanzentyp | 36 Profile | Zimmerpflanze | Optimalbereich, Zielwert, alle Schwellen |
| Sensortyp | Kapazitiv, Resistiv | Kapazitiv | Verschiebt den Optimalbereich um −8 Prozentpunkte |
| Vorhersagehorizont | 1–72 h, Schritt 1 | 12 h | Zeitraum von `Feuchtigkeitsvorhersage` |
| Historienfenster | 2–168 h, Schritt 1 | 24 h | Zeitraum, über den der Trend gefittet wird |
| Wetterentität | beliebige `weather.*` | automatisch | Quelle der Wettervorhersage |
| Substratvolumen | 0–1000 L, Schritt 0,5 | 0 L | Grundlage der Gießmenge, 0 = aus |

Änderungen lösen einen Reload der Integration aus; die Entitäten behalten ihre
IDs. Der Trend wird dabei neu aufgebaut (Historienfenster wird erneut geladen).

## Entitäten

Pro Einrichtung entstehen ein Gerät, zehn Sensoren und zwei Binärsensoren. Die
IDs leiten sich aus dem Namen und der Sprache der Instanz ab; die Tabelle zeigt
die deutschen IDs bei einem Eintrag namens „Vera“.

| Entität | Einheit | Rechenkern |
| --- | --- | --- |
| `sensor.vera_aktuelle_feuchtigkeit` | % | Messwert des Quellsensors |
| `sensor.vera_feuchtigkeitsvorhersage` | % | `aktuell + Steigung × Horizont` |
| `sensor.vera_feuchtigkeit_in_1_tag` | % | `aktuell + Steigung × 24` |
| `sensor.vera_feuchtigkeit_in_5_tagen` | % | `aktuell + Steigung × 120` |
| `sensor.vera_feuchtigkeit_in_7_tagen` | % | `aktuell + Steigung × 168` |
| `sensor.vera_feuchtigkeit_in_7_tagen_wettervorhersage` | % | stündliches bzw. tägliches Wettermodell über 168 h |
| `sensor.vera_optimale_feuchtigkeit` | % | Mitte des Optimalbereichs |
| `sensor.vera_benoetigtes_wasser` | mL | `(Ziel − aktuell) × Volumen × 10` |
| `sensor.vera_tage_bis_zur_mindestfeuchtigkeit` | Tage | `(aktuell − Schwelle) / Steigung / 24` |
| `sensor.vera_tage_bis_zur_mindestfeuchtigkeit_wettervorhersage` | Tage | dasselbe mit Wettermodell |
| `binary_sensor.vera_giessen_noetig` | – | `aktuell < optimal_min` |
| `binary_sensor.vera_sensordaten_veraltet` | – | Quellsensor seit > 480 min ohne Update |

Die Binärsensoren zeigen intern `on`/`off` und übersetzt `Ja`/`Nein` bzw.
`Veraltet`/`Aktuell` (englisch `Yes`/`No`, `Stale`/`Up to date`). Sie tragen
bewusst **keine** `moisture`-Zustandsklasse: Diese beschreibt den Boden selbst
und würde `on` als „nass“ beschriften – genau umgekehrt zur Bedeutung hier.

Details zu jedem Sensor (Formel, Eingangswerte, Sonderfälle, Attribute,
Rechenbeispiel): **[docs/sensoren.md](docs/sensoren.md)**.

## Sensortypen

| Sensortyp | Messprinzip | Anpassung des Optimalbereichs |
| --- | --- | --- |
| `capacitive` (Standard) | Dielektrizitätskonstante des Substrats, linear, driftarm | keine |
| `resistive` | Leitwert zwischen zwei Elektroden, reagiert auf Wasser **und** Salze, sättigt im nassen Bereich | −8 Prozentpunkte |

Für dasselbe Substrat meldet ein resistiver Sensor einige Prozentpunkte
feuchter als ein kapazitiver. Deshalb wird sein Optimalbereich um 8
Prozentpunkte nach unten verschoben (`SENSOR_TYPE_THRESHOLD_OFFSET`). Alle
abgeleiteten Größen wandern automatisch mit, weil die Schwelle zentral im
Coordinator kalibriert wird: Gießen nötig, Tage bis zur Mindestfeuchtigkeit,
Gießmenge und die Attribute `optimal_min`/`optimal_max`.

Aus 40–60 % (Zimmerpflanze) werden 32–52 %. Der Bereich wird nie schmaler als
15 Prozentpunkte und nie außerhalb 0–100 % (`MIN_OPTIMAL_RANGE_WIDTH`).
Bestehende Einträge ohne gespeicherten Sensortyp gelten weiter als kapazitiv,
unbekannte Werte fallen ebenfalls darauf zurück.

Wer die Rohwerte seines Sensors vorher per Template auf 0–100 % umrechnet,
sollte bei *Kapazitiv* bleiben.

## Pflanzenprofile

Die Bereiche sind Richtwerte für kapazitive Sensoren. „Ziel“ ist die Mitte des
Bereichs – der Wert, auf den die Gießmenge rechnet. Die resistiven Spalten
zeigen die automatische Verschiebung um −8 Prozentpunkte.

| Pflanze | Optimal (%) | Ziel (%) | Optimal resistiv (%) | Ziel resistiv (%) |
| --- | --- | --- | --- | --- |
| Agave | 10–30 | 20 | 2–22 | 12 |
| Aloe Vera | 10–30 | 20 | 2–22 | 12 |
| Avocado | 50–70 | 60 | 42–62 | 52 |
| Bambus | 55–75 | 65 | 47–67 | 57 |
| Baum | 40–65 | 52,5 | 32–57 | 44,5 |
| Bogenhanf | 15–30 | 22,5 | 7–22 | 14,5 |
| Bonsai | 50–70 | 60 | 42–62 | 52 |
| Chili | 55–70 | 62,5 | 47–62 | 54,5 |
| Efeutute | 35–55 | 45 | 27–47 | 37 |
| Einblatt | 55–75 | 65 | 47–67 | 57 |
| Erdbeere | 55–75 | 65 | 47–67 | 57 |
| Farn | 60–80 | 70 | 52–72 | 62 |
| Glücksfeder | 15–35 | 25 | 7–27 | 17 |
| Gurke | 65–85 | 75 | 57–77 | 67 |
| Hecke | 40–65 | 52,5 | 32–57 | 44,5 |
| Heidelbeere | 55–75 | 65 | 47–67 | 57 |
| Kartoffel | 50–70 | 60 | 42–62 | 52 |
| Korbmarante | 60–80 | 70 | 52–72 | 62 |
| Kräuter | 45–65 | 55 | 37–57 | 47 |
| Lavendel | 25–45 | 35 | 17–37 | 27 |
| Monstera | 40–60 | 50 | 32–52 | 42 |
| Orchidee | 35–55 | 45 | 27–47 | 37 |
| Paprika | 55–70 | 62,5 | 47–62 | 54,5 |
| Rasen | 40–60 | 50 | 32–52 | 42 |
| Rose | 50–70 | 60 | 42–62 | 52 |
| Rosmarin | 25–45 | 35 | 17–37 | 27 |
| Salat | 60–75 | 67,5 | 52–67 | 59,5 |
| Sukkulente / Kaktus | 15–35 | 25 | 7–27 | 17 |
| Tillandsie (Luftpflanze) | 30–50 | 40 | 22–42 | 32 |
| Tomate | 60–80 | 70 | 52–72 | 62 |
| Venusfliegenfalle | 55–80 | 67,5 | 47–72 | 59,5 |
| Yucca | 20–40 | 30 | 12–32 | 22 |
| Zimmerpalme | 50–70 | 60 | 42–62 | 52 |
| Zimmerpflanze | 40–60 | 50 | 32–52 | 42 |
| Zitruspflanze | 45–65 | 55 | 37–57 | 47 |
| Zucchini | 60–80 | 70 | 52–72 | 62 |

Reihenfolge und Werte stehen in `custom_components/soil_moisture/const.py`
(`PLANT_PROFILES`); die Dropdown-Reihenfolge folgt der alphabetischen Liste
`PLANT_TYPES`.

## Berechnung in Kürze

1. Alle 5 Minuten wird der Quellsensor gelesen und als Messpunkt gespeichert;
   beim Start kommen die letzten `history_hours` aus dem Recorder dazu.
2. Über die Messpunkte legt eine Regression (kleinste Quadrate) eine Gerade.
   Deren Steigung in Prozentpunkten pro Stunde ist der Trend; das
   Bestimmtheitsmaß R² landet im Attribut `confidence`.
3. Vorhersagen sind `aktueller Wert + Steigung × Zeit`, begrenzt auf 0–100 %.
4. Der Gießtermin ist der Schnittpunkt dieser Geraden mit `optimal_min`.
5. Das Wettermodell skaliert die Trocknung pro Stunde mit Temperatur,
   Strahlung bzw. Bewölkung und Luftfeuchte und addiert Regen.

Vollständige Formeln, Faktoren, Grenzwerte und ein durchgerechnetes Beispiel:
**[docs/berechnungsgrundlagen.md](docs/berechnungsgrundlagen.md)**.

## Dashboard-Karten

Zwei fertige Karten liegen in
[`dashboards/soil_moisture_cards.yaml`](dashboards/soil_moisture_cards.yaml).
Entity-IDs an die eigene Einrichtung anpassen.

### Verlauf der letzten 5 Tage mit nächstem Gießtermin

`history-graph` zeigt 120 Stunden Feuchte und Optimalwert; die Markdown-Karte
darunter rechnet aus `days_until_min_weather` das konkrete Datum der nächsten
Wässerung und nennt den linearen Termin als Vergleich.

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

`segments` funktioniert nur zusammen mit `needle: true` und erlaubt – anders als
`severity` – eine grüne Mittelzone. Die Grenzen 40 und 60 gehören zur
Zimmerpflanze; für andere Pflanzen `optimal_min`/`optimal_max` aus den
Attributen von `sensor.<name>_aktuelle_feuchtigkeit` einsetzen.

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

## Automationsbeispiele

### Benachrichtigung, wenn in weniger als 6 Stunden gegossen werden muss

```yaml
automation:
  - alias: "Bodenfeuchte: Gießen nötig"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.vera_tage_bis_zur_mindestfeuchtigkeit
        below: 0.25
    conditions:
      - condition: template
        value_template: >-
          {{ is_state_attr('sensor.vera_aktuelle_feuchtigkeit',
                           'trend_direction', 'falling') }}
    actions:
      - action: notify.mobile_app
        data:
          message: >-
            Bodenfeuchte {{ states('sensor.vera_aktuelle_feuchtigkeit') }} %,
            Optimalbereich ab {{ state_attr('sensor.vera_aktuelle_feuchtigkeit',
                                            'optimal_min') }} %.
            Voraussichtlich in {{ states('sensor.vera_tage_bis_zur_mindestfeuchtigkeit_wettervorhersage') }}
            Tagen gießen.
```

### Bewässerung nur bei fallendem Trend und trockenem Boden starten

```yaml
condition:
  - condition: template
    value_template: >-
      {{ is_state_attr('sensor.vera_aktuelle_feuchtigkeit', 'trend_direction', 'falling')
         and states('sensor.vera_aktuelle_feuchtigkeit') | float(100)
             < state_attr('sensor.vera_aktuelle_feuchtigkeit', 'optimal_min') | float(0) }}
```

### Gießmenge ausgeben

```yaml
- action: notify.mobile_app
  data:
    message: >-
      {{ states('sensor.vera_benoetigtes_wasser') }} ml gießen
      (Ziel {{ state_attr('sensor.vera_benoetigtes_wasser', 'target_moisture') }} %,
      Topf {{ state_attr('sensor.vera_benoetigtes_wasser', 'container_volume_litres') }} l).
```

## Fehlerbehebung

| Symptom | Ursache und Abhilfe |
| --- | --- |
| Alle Sensoren `unavailable` | Quellsensor fehlt oder liefert keinen Zahlenwert (`unknown`, `unavailable`). Sobald er wieder Werte liefert, erholen sich die Entitäten. |
| Vorhersage = aktueller Wert | Noch zu wenig Geschichte: unter 3 Messpunkten oder unter 30 Minuten. Nach einigen Messungen entsteht eine echte Prognose. |
| Gießtermin `unknown` | Der Trend steigt oder ist flach (Steigung ≥ −0,05 %/h) – die Schwelle wird nie erreicht. |
| Gießmenge `unknown` | Kein Substratvolumen eingetragen (0 L). |
| Wettervorhersage `unknown` | Kein oder mehrdeutiges Wetterobjekt. Das Attribut `forecast_error` nennt den Grund (siehe unten). |
| Alles wirkt zu nass | Resistiver Sensor? Dann Sensortyp auf *Resistiv* stellen; der Optimalbereich liegt dann 8 Prozentpunkte tiefer. |
| Werte in Rohskala | Die Integration erwartet Prozent. Vorher per Template auf 0–100 % umrechnen und Sensortyp auf *Kapazitiv* lassen. |
| Keine Historie nach Neustart | Recorder deaktiviert: Die Prognose startet leer und füllt sich ab dem Start. |

`forecast_error` kennt vier Fälle:

| Wert | Bedeutung |
| --- | --- |
| `no_weather_entity` | Keine Wetterentität vorhanden und keine konfiguriert |
| `multiple_weather_entities` | Mehrere Wetterentitäten vorhanden, keine ausgewählt |
| `empty_forecast` | Der Dienst antwortet ohne Einträge |
| `service_error: …` | Fehler beim Aufruf von `weather.get_forecasts`, Text angehängt |

Diagnosewerte liefert `binary_sensor.<name>_sensordaten_veraltet`: `on`, wenn
der Quellsensor länger als 480 Minuten nichts gemeldet hat oder das Update
fehlschlägt; `data_age_minutes` nennt das Alter der letzten Messung,
`source_battery` den Batteriestand, falls der Sensor einen meldet.

## Dokumentation

| Dokument | Inhalt |
| --- | --- |
| [docs/sensoren.md](docs/sensoren.md) | Jeder Sensor einzeln: Zweck, Formel, Eingangswerte, Sonderfälle, Attribute |
| [docs/berechnungsgrundlagen.md](docs/berechnungsgrundlagen.md) | Trendfit, Gieß-Erkennung, Wettermodell, Konstanten, durchgerechnetes Beispiel |
| [dashboards/soil_moisture_cards.yaml](dashboards/soil_moisture_cards.yaml) | Fertige Lovelace-Karten |
| [CHANGELOG.md](CHANGELOG.md) | Versionshistorie |

## Veröffentlichung

- **Version:** `custom_components/soil_moisture/manifest.json` und `VERSION` in
  `const.py` tragen dieselbe Nummer. Ist sie neu, erzeugt
  `.github/workflows/release.yml` beim Push auf `main` automatisch den Tag
  `v<version>` und ein GitHub-Release mit generierten Notizen.
- **Changelog:** [CHANGELOG.md](CHANGELOG.md).
- **Brand-Assets:** `custom_components/soil_moisture/brand/icon.png` (256×256)
  und `logo.png` (512×512); Home Assistant nutzt sie ab 2026 direkt aus der
  Integration.
- **Standard-Repository von HACS:** noch offen. Dafür muss das Repository
  öffentlich sein, Releases und Brand-Assets enthalten und in `hacs/default`
  unter `integration` eingetragen werden (Pull Request mit dem Repo-Namen in
  alphabetischer Reihenfolge).

## Entwicklung

Die Rechenmodule `predict.py`, `weather.py` und `const.py` sind bewusst frei von
Home-Assistant-Importen und damit ohne laufende Instanz testbar.

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
pytest
```

## Projektstruktur

```
custom_components/soil_moisture/
  __init__.py      Setup und Options-Reload
  config_flow.py   Einrichtung und Optionen
  const.py         Konstanten, Pflanzenprofile, Sensortyp-Kalibrierung
  coordinator.py   Sensorabfrage, Recorder-Historie, Trend- und Wetterberechnung
  predict.py       Trend- und Vorhersage-Mathematik (HA-frei)
  weather.py       Wettermodell für die Trocknung (HA-frei)
  sensor.py        Zehn Sensoren
  binary_sensor.py Gießen nötig und Diagnose
  brand/           icon.png und logo.png
  manifest.json
  strings.json
  translations/    en, de
tests/             41 Tests für const, predict und weather
docs/              Sensor- und Berechnungsdokumentation
dashboards/        Fertige Lovelace-Karten
.github/           Release-Workflow
CHANGELOG.md
```
