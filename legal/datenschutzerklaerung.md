# Datenschutzerklärung

_Stand: {{DATE}}_

## 1. Verantwortlicher

Verantwortlicher im Sinne der Datenschutz-Grundverordnung (DSGVO) und
anderer nationaler Datenschutzgesetze der Mitgliedstaaten sowie
sonstiger datenschutzrechtlicher Bestimmungen ist:

{{FULL_NAME}}
{{POSTAL_STREET_HNR}}
{{POSTAL_PLZ_CITY}}
Deutschland

E-Mail: {{EMAIL}}
Website: https://{{DOMAIN}}

## 2. Zweck und Charakter der Website

{{PRODUCT_NAME}} ist ein öffentlich zugängliches Werkzeug, das Berliner
Adressen mit offenen Geo- und Statistikdaten anreichert. Die Website
erfordert keine Registrierung und speichert keine Nutzerkonten.
Sämtliche fachlichen Auswertungen erfolgen serverseitig, ohne
Personenbezug auf den Endnutzer.

## 3. Erhebung und Speicherung personenbezogener Daten

### 3.1 Beim Aufruf der Website (Server-Logfiles)

Beim Aufruf unserer Website werden durch den auf Ihrem Endgerät
verwendeten Browser automatisch Informationen an den Server unserer
Website gesendet. Diese Informationen werden temporär in einem
sogenannten Logfile gespeichert. Folgende Informationen werden dabei
ohne Ihr Zutun erfasst und bis zur automatischen Löschung gespeichert:

- IP-Adresse des anfragenden Rechners (in gekürzter Form, sofern
  technisch möglich, oder vollständig anonymisiert nach spätestens
  sieben Tagen),
- Datum und Uhrzeit des Zugriffs,
- Name und URL der abgerufenen Datei,
- Website, von der aus der Zugriff erfolgt (Referrer-URL),
- verwendeter Browser und ggf. das Betriebssystem Ihres Rechners.

**Rechtsgrundlage:** Art. 6 Abs. 1 lit. f DSGVO (berechtigtes Interesse
an der technischen Bereitstellung, IT-Sicherheit und
Missbrauchsabwehr).

**Speicherdauer:** maximal 7 Tage, danach automatische Löschung oder
vollständige Anonymisierung.

Eine Zusammenführung dieser Daten mit anderen Datenquellen wird nicht
vorgenommen. Wir behalten uns vor, die Daten nachträglich zu prüfen,
wenn uns konkrete Anhaltspunkte für eine rechtswidrige Nutzung bekannt
werden.

### 3.2 Bei Nutzung der Adress-Abfrage (`/api/lookup`, `/api/amenities`)

Wenn Sie eine Adresse abfragen, wird diese an unseren Server übermittelt
und dort mit externen Datenquellen (Berliner Geoportal, VBB, Geofabrik-
OSM-Snapshot) abgeglichen. Die abgefragte Adresse wird für die Dauer
der Anfrage im Arbeitsspeicher gehalten und **nicht dauerhaft mit Ihrer
IP-Adresse verknüpft gespeichert**. Für die Fehler- und
Leistungsanalyse können Adress-Anfragen in aggregierter, nicht auf
Einzelpersonen zurückführbarer Form in Server-Logs erscheinen.

**Rechtsgrundlage:** Art. 6 Abs. 1 lit. b DSGVO (Erfüllung des Dienstes,
den Sie aktiv angefordert haben) sowie Art. 6 Abs. 1 lit. f DSGVO
(berechtigtes Interesse an Betriebs- und Fehleranalyse).

### 3.3 Bei Nutzung der KI-Erklärungen (`/api/card_insight`)

Beim Aufruf einer KI-generierten Erklärung zu einer Datenkarte werden
die zugehörigen Sachdaten (Zahlen, Kategorien, Distanzen) an unseren
Inferenz-Dienst ({{INFERENCE_HOST}}) übermittelt und dort verarbeitet.
Es werden **keine personenbezogenen Daten** an den Inferenz-Dienst
gesendet — insbesondere keine IP-Adresse, kein Nutzer-Identifier und
keine Adresse in Freitextform.

**Rechtsgrundlage:** Art. 6 Abs. 1 lit. b DSGVO (Erfüllung des Dienstes)
sowie Art. 6 Abs. 1 lit. f DSGVO (berechtigtes Interesse an
Bereitstellung eines nützlichen Zusatzangebots).

## 4. Lokale Speicherung im Browser (LocalStorage)

Zur Verbesserung des Nutzererlebnisses speichert die Website folgende
Informationen ausschließlich lokal in Ihrem Browser (`localStorage`):

- die zuletzt gewählte Ansicht ("Life Mode Lens"),
- eine Liste der zuletzt abgefragten Adressen (für die Vergleichs- und
  Verlaufsfunktion).

Diese Daten verlassen Ihren Browser **nicht** und werden nicht an
unseren Server übertragen. Sie können den `localStorage` jederzeit über
die Einstellungen Ihres Browsers löschen.

Bei diesen Einträgen handelt es sich technisch nicht um Cookies im
Sinne der ePrivacy-Richtlinie; eine Einwilligungsabfrage ist daher nach
derzeitiger Rechtsprechung nicht erforderlich.

## 5. Weitergabe von Daten an Dritte

Eine Übermittlung Ihrer personenbezogenen Daten an Dritte findet
grundsätzlich nicht statt. Ausnahmen bilden ausschließlich die
folgenden, für den Betrieb der Website notwendigen Auftragsverarbeiter:

### 5.1 Hosting

{{HOSTING_PROVIDER}}

Der Hostinganbieter verarbeitet in unserem Auftrag Server-Logfiles
(siehe Abschnitt 3.1) auf Grundlage eines Auftragsverarbeitungsvertrags
gemäß Art. 28 DSGVO.

### 5.2 Fehleranalyse

{{ERROR_TRACKING}}

_Falls konfiguriert, verarbeitet unser Fehlerprotokollierungsdienst
technische Fehlermeldungen (Stacktraces, Browsertypen, HTTP-Statuscodes)
zum Zweck der Fehlerdiagnose. Personenbezogene Nutzdaten werden aus
Fehlermeldungen soweit technisch möglich entfernt._

### 5.3 Reichweiten- und Nutzungsanalyse

{{ANALYTICS_PROVIDER}}

_Falls konfiguriert, verwenden wir einen datenschutzfreundlichen
Analyse-Dienst, der ohne Cookies und ohne IP-Speicherung arbeitet und
keine Nutzerprofile erstellt._

## 6. Datenquellen (offene Daten)

Die auf der Website dargestellten Informationen (Schulen, Verkehr,
Umwelt, Sozialindikatoren u.a.) stammen aus offen lizenzierten
Datenquellen. Personenbezogene Daten werden aus diesen Quellen nicht
verarbeitet; sämtliche Datensätze beziehen sich auf öffentliche
Einrichtungen, Adressen und Aggregate. Die vollständige Liste der
Quellen und Lizenzen ist im Impressum aufgeführt.

## 7. Ihre Rechte

Sie haben gegenüber dem Verantwortlichen folgende Rechte hinsichtlich
der Sie betreffenden personenbezogenen Daten:

- **Recht auf Auskunft** (Art. 15 DSGVO),
- **Recht auf Berichtigung** (Art. 16 DSGVO),
- **Recht auf Löschung** (Art. 17 DSGVO),
- **Recht auf Einschränkung der Verarbeitung** (Art. 18 DSGVO),
- **Recht auf Datenübertragbarkeit** (Art. 20 DSGVO),
- **Recht auf Widerspruch gegen die Verarbeitung** (Art. 21 DSGVO).

Sie haben zudem das Recht, sich bei einer Datenschutz-Aufsichtsbehörde
über die Verarbeitung Ihrer personenbezogenen Daten durch uns zu
beschweren (Art. 77 DSGVO). Zuständig ist die Berliner Beauftragte für
Datenschutz und Informationsfreiheit:

Berliner Beauftragte für Datenschutz und Informationsfreiheit
Alt-Moabit 59-61
10555 Berlin
[https://www.datenschutz-berlin.de/](https://www.datenschutz-berlin.de/)

## 8. Widerspruchsrecht

Sofern wir personenbezogene Daten auf Grundlage berechtigter Interessen
gemäß Art. 6 Abs. 1 lit. f DSGVO verarbeiten, haben Sie das Recht, aus
Gründen, die sich aus Ihrer besonderen Situation ergeben, jederzeit
Widerspruch gegen die Verarbeitung Ihrer personenbezogenen Daten
einzulegen. Der Widerspruch kann formfrei per E-Mail an {{EMAIL}}
erfolgen.

## 9. Datensicherheit

Wir verwenden innerhalb des Website-Besuchs das verbreitete
SSL/TLS-Verfahren (HTTPS) in Verbindung mit der jeweils höchsten
Verschlüsselungsstufe, die von Ihrem Browser unterstützt wird. Zusätzlich
sichern wir unsere Website und sonstigen Systeme durch technische und
organisatorische Maßnahmen gegen Verlust, Zerstörung, Zugriff,
Veränderung oder Verbreitung Ihrer Daten durch unbefugte Personen.

## 10. Automatisierte Entscheidungsfindung

Eine ausschließlich auf automatisierter Verarbeitung beruhende
Entscheidungsfindung im Sinne von Art. 22 DSGVO findet **nicht** statt.
Die auf der Website dargestellten Ampel-Kategorien ("grün / gelb / rot")
sind rein informatorisch und dienen der Orientierung; es werden daraus
keine für den Nutzer rechtlich oder wirtschaftlich bindenden Wirkungen
abgeleitet.

## 11. Aktualität und Änderung dieser Datenschutzerklärung

Diese Datenschutzerklärung ist aktuell gültig und hat den Stand
{{DATE}}. Durch die Weiterentwicklung der Website oder aufgrund
geänderter gesetzlicher bzw. behördlicher Vorgaben kann es notwendig
werden, diese Datenschutzerklärung anzupassen. Die jeweils aktuelle
Datenschutzerklärung kann jederzeit auf der Website unter
`https://{{DOMAIN}}/datenschutzerklaerung` abgerufen werden.

---

# Privacy Policy (English translation)

_This English text is provided for the convenience of international
visitors. In case of any dispute, the German version above is legally
authoritative._

_Version: {{DATE}}_

## 1. Data Controller

The data controller within the meaning of the General Data Protection
Regulation (GDPR) and other national data protection laws of the
Member States as well as other data protection regulations is:

{{FULL_NAME}}
{{POSTAL_STREET_HNR}}
{{POSTAL_PLZ_CITY}}
Germany

Email: {{EMAIL}}
Website: https://{{DOMAIN}}

## 2. Purpose and character of the website

{{PRODUCT_NAME}} is a publicly accessible tool that enriches Berlin
addresses with open geo and statistical data. The website requires no
registration and stores no user accounts. All processing occurs
server-side, without personal reference to the end user.

## 3. Collection and storage of personal data

### 3.1 When accessing the website (server logfiles)

When you access our website, the browser used on your device
automatically sends information to the server of our website. This
information is temporarily stored in what is called a logfile. The
following information is collected without any action on your part and
stored until automatically deleted:

- IP address of the requesting device (in shortened form where
  technically possible, or fully anonymised within seven days at the
  latest),
- date and time of access,
- name and URL of the file retrieved,
- website from which access was made (referrer URL),
- browser used and, where applicable, the operating system of your
  device.

**Legal basis:** Art. 6 (1) (f) GDPR (legitimate interest in technical
provision, IT security and abuse prevention).

**Retention period:** maximum 7 days, then automatic deletion or full
anonymisation.

This data is not merged with other data sources. We reserve the right
to review the data retrospectively if we become aware of concrete
indications of unlawful use.

### 3.2 When using the address lookup (`/api/lookup`, `/api/amenities`)

When you query an address, it is transmitted to our server and matched
against external data sources (Berlin Geoportal, VBB, Geofabrik OSM
snapshot). The queried address is held in memory for the duration of
the request and is **not permanently stored linked to your IP address**.
For error and performance analysis, address queries may appear in
server logs in aggregated form that cannot be traced back to
individuals.

**Legal basis:** Art. 6 (1) (b) GDPR (performance of the service you
actively requested) and Art. 6 (1) (f) GDPR (legitimate interest in
operational and error analysis).

### 3.3 When using the AI explanations (`/api/card_insight`)

When you request an AI-generated explanation for a data card, the
related factual data (numbers, categories, distances) is transmitted
to our inference service ({{INFERENCE_HOST}}) and processed there.
**No personal data** is sent to the inference service — in particular,
no IP address, no user identifier, and no free-text address.

**Legal basis:** Art. 6 (1) (b) GDPR (performance of the service) and
Art. 6 (1) (f) GDPR (legitimate interest in providing a useful
supplementary offering).

## 4. Local browser storage (localStorage)

To improve the user experience, the website stores the following
information exclusively locally in your browser (`localStorage`):

- the most recently chosen view ("Life Mode Lens"),
- a list of your most recently queried addresses (for the compare and
  history function).

This data **does not leave your browser** and is not transmitted to our
server. You can delete `localStorage` at any time via your browser
settings.

These entries are technically not cookies within the meaning of the
ePrivacy Directive; a consent prompt is therefore not required under
current case law.

## 5. Transfer of data to third parties

Your personal data is generally not transferred to third parties.
Exceptions are exclusively the following processors, which are
necessary for the operation of the website:

### 5.1 Hosting

{{HOSTING_PROVIDER}}

The hosting provider processes server logfiles (see section 3.1) on our
behalf under a data processing agreement pursuant to Art. 28 GDPR.

### 5.2 Error tracking

{{ERROR_TRACKING}}

_If configured, our error tracking service processes technical error
messages (stacktraces, browser types, HTTP status codes) for the purpose
of error diagnosis. Personal payload data is removed from error
messages to the extent technically possible._

### 5.3 Reach and usage analysis

{{ANALYTICS_PROVIDER}}

_If configured, we use a privacy-friendly analytics service that
operates without cookies and without IP storage, and does not create
user profiles._

## 6. Data sources (open data)

The information shown on the website (schools, transport, environment,
social indicators, etc.) originates from openly licensed data sources.
No personal data is processed from these sources; all data sets refer
to public facilities, addresses and aggregates. The full list of sources
and licences is provided in the Imprint.

## 7. Your rights

You have the following rights with respect to the personal data
concerning you:

- **Right of access** (Art. 15 GDPR),
- **Right to rectification** (Art. 16 GDPR),
- **Right to erasure** (Art. 17 GDPR),
- **Right to restriction of processing** (Art. 18 GDPR),
- **Right to data portability** (Art. 20 GDPR),
- **Right to object to processing** (Art. 21 GDPR).

You also have the right to lodge a complaint with a data protection
supervisory authority about the processing of your personal data by us
(Art. 77 GDPR). The competent authority is:

Berliner Beauftragte für Datenschutz und Informationsfreiheit
Alt-Moabit 59-61
10555 Berlin
[https://www.datenschutz-berlin.de/](https://www.datenschutz-berlin.de/)

## 8. Right to object

Insofar as we process personal data on the basis of legitimate
interests pursuant to Art. 6 (1) (f) GDPR, you have the right, for
reasons arising from your particular situation, to object at any time
to the processing of your personal data. The objection can be made
informally by email to {{EMAIL}}.

## 9. Data security

We use the widespread SSL/TLS procedure (HTTPS) in conjunction with
the highest level of encryption supported by your browser. Additionally,
we secure our website and other systems through technical and
organisational measures against loss, destruction, access, modification
or distribution of your data by unauthorised persons.

## 10. Automated decision-making

Decision-making based exclusively on automated processing within the
meaning of Art. 22 GDPR **does not** take place. The traffic-light
categories displayed on the website ("green / amber / red") are purely
informational and serve as orientation; no legally or economically
binding effects for the user are derived from them.

## 11. Currency and modification of this privacy policy

This privacy policy is currently valid and dated {{DATE}}. Due to the
further development of the website or due to changed legal or
regulatory requirements, it may become necessary to adapt this privacy
policy. The current privacy policy can be accessed on the website at
any time at `https://{{DOMAIN}}/datenschutzerklaerung`.
