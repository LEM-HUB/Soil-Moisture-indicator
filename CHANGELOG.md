# Changelog

Nennenswerte Änderungen an dieser Integration. Die Version steht in
`custom_components/soil_moisture/manifest.json`; ein Push auf `main` mit einer
neuen Version erzeugt automatisch Tag und GitHub-Release (siehe
`.github/workflows/release.yml`).

## 1.4.1

### Behoben

- Wetterbasierter Gießtermin und 7-Tage-Prognose nutzen jetzt dieselben ersten
  7 Tage Vorhersage; danach rechnet der Termin linear weiter. Vorher konnte der
  Termin bei längeren Vorhersagen von der Prognose abweichen.
- Gieß-Erkennung beim ersten Start: Die Recorder-Historie wird vor der
  Erkennung geladen und auf Messungen vor dem aktuellen Wert beschnitten. Ein
  Gießen direkt vor einem Neustart wird dadurch erkannt und der Trend sauber
  neu gestartet, statt mit Vor-Gieß-Werten weiterzurechnen.
- Ein Trend zwischen −0,05 und 0 %/h gilt auch im Wettermodell als stabil,
  passend zur linearen Terminrechnung.
- `forecast_days_used` nennt die tatsächlich abgedeckten Tage (Stunden ÷ 24,
  höchstens 7) statt aufgerundeter Tage.
- `prediction_horizon` fällt wie die übrigen Optionen auf die Daten der
  Einrichtung zurück.
- Diagnosesensor „Sensordaten veraltet“ führt keine Gieß-Attribute mehr mit.
- Toter Code (`hourly_change`) und eine ungenutzte Variable entfernt.

### Dokumentation

- README als Einstieg neu strukturiert; Sensor- und Berechnungsdetails stehen
  jetzt in `docs/sensoren.md` und `docs/berechnungsgrundlagen.md`.

## 1.4.0

### Hinzugefügt

- **Sensortyp** in Einrichtung und Optionen: *Kapazitiv* oder *Resistiv*.
  Resistive Sensoren melden für dasselbe Substrat einige Prozentpunkte
  feuchter, deshalb liegt ihr Optimalbereich 8 Prozentpunkte tiefer. Alle
  daraus abgeleiteten Schwellen (Gießen nötig, Tage bis zur
  Mindestfeuchtigkeit, Wassermenge) wandern mit.
- Attribut `sensor_type` an *Aktuelle Feuchtigkeit* und *Optimale Feuchtigkeit*.
- Zwei fertige Lovelace-Karten in `dashboards/soil_moisture_cards.yaml`.
- Brand-Assets in `custom_components/soil_moisture/brand/`.
- Release-Workflow, der aus der Manifest-Version Tag und Release erzeugt.

### Geändert

- `hacs.json` um `content_in_root` ergänzt.

## 1.3.5

- Schwelle für `binary_sensor.<name>_sensordaten_veraltet` von 30 Minuten auf
  8 Stunden erhöht.

## 1.3.4

- Pflanzenliste im Dropdown alphabetisch nach dem angezeigten Namen sortiert.

## 1.3.3

- Zwei Sensoren „Tage bis zur Mindestfeuchtigkeit": linear und mit
  Wettervorhersage.

## 1.3.2

- `integration_type: device`, damit der Eintrag in der Integrationsliste statt
  im Helfer-Tab erscheint.

## 1.3.1

- Übersetzte Zustandstexte der Binärsensoren (Ja/Nein, Veraltet/Aktuell), keine
  `moisture`-Zustandsklasse mehr.

## 1.3.0

- Gieß-Erkennung, stündliches Wettermodell, Binärsensoren, Wassermenge in ml.
