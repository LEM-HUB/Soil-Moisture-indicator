# Changelog

Nennenswerte Änderungen an dieser Integration. Die Version steht in
`custom_components/soil_moisture/manifest.json`; ein Push auf `main` mit einer
neuen Version erzeugt automatisch Tag und GitHub-Release (siehe
`.github/workflows/release.yml`).

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
