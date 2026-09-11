# Datenschutzerklärung

_Stand: 27.08.2026_

## 1. Verantwortlicher

Verantwortlicher im Sinne der Datenschutz-Grundverordnung (DSGVO) und
anderer nationaler Datenschutzgesetze der Mitgliedstaaten sowie
sonstiger datenschutzrechtlicher Bestimmungen ist:

Saptadip Sarkar
Hanns-Eisler-Platz 3
39128, Magdeburg
Deutschland

E-Mail: sapta@addrlens.de
Website: https://addrlens.de

## 2. Zweck und Charakter der Website

Berlin Address Intelligence ist ein öffentlich zugängliches Werkzeug, das Berliner
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

Zur Missbrauchsabwehr wird die von Cloudflare im HTTP-Header
`CF-Connecting-IP` übermittelte Client-IP-Adresse zusätzlich für ein
prozessinternes, endpunkt-spezifisches Rate-Limiting ausgelesen. Diese
Verarbeitung erfolgt ausschließlich im Arbeitsspeicher und wird nicht
persistiert.

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

### 3.3 Bei Nutzung der KI-Erklärungen (`/api/card_insight`, `/api/history`)

Beim Aufruf einer KI-generierten Erklärung zu einer Datenkarte
(`/api/card_insight`) oder einer historischen Kurzbeschreibung zur
Umgebung einer Adresse (`/api/history`) werden die zugehörigen
Sachdaten (Zahlen, Kategorien, Distanzen, Bezirk und Ortsteil sowie
eine kuratierte Liste öffentlicher OpenStreetMap-Objekte im Umkreis)
an einen Sprachmodell-Dienst übermittelt und dort verarbeitet.

- Für den Endpunkt `/api/card_insight` erfolgt die Modellinferenz
  ausschließlich auf einem lokal betriebenen Sprachmodell (llama.cpp)
  auf demselben Server bei Hetzner.
- Für den Endpunkt `/api/history` wird der Dienst Cloudflare Workers AI
  (siehe Abschnitt 5.5) genutzt. Bei Nichterreichbarkeit dieses Dienstes
  greift automatisch das lokal betriebene Sprachmodell.

Es werden **keine personenbezogenen Daten** an den Sprachmodell-Dienst
gesendet — insbesondere keine IP-Adresse, kein Nutzer-Identifier und
keine Adresse in Freitextform (Straßenname und Hausnummer werden vor
der Übermittlung entfernt). Die übermittelten Standortangaben
beschränken sich auf Bezirks- und Ortsteil-Ebene.

**Rechtsgrundlage:** Art. 6 Abs. 1 lit. b DSGVO (Erfüllung des Dienstes)
sowie Art. 6 Abs. 1 lit. f DSGVO (berechtigtes Interesse an
Bereitstellung eines nützlichen Zusatzangebots).

### 3.4 Zwischenspeicherung generierter Kurzbeschreibungen

Zur Reduktion externer Anfragen und Antwortzeiten werden die für
`/api/history` generierten Kurztexte für maximal sieben Tage in einem
serverseitigen Zwischenspeicher gehalten. Der Schlüssel dieses
Zwischenspeichers ist ein auf ca. 100 Meter Rasterweite gerundetes
Koordinatenpaar (Länge/Breite) — es besteht **keinerlei Verknüpfung**
mit IP-Adressen, Sitzungen oder Nutzer-Identifikatoren. Beim Ablauf
der Frist bzw. beim Neustart des Dienstes wird der Zwischenspeicher
automatisch geleert.

**Rechtsgrundlage:** Art. 6 Abs. 1 lit. f DSGVO (berechtigtes Interesse
an einem effizienten Betrieb und der Schonung externer Verarbeitungs-
kontingente).

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

Hetzner Online GmbH,
Industriestr. 25,
91710 Gunzenhausen

Der Hostinganbieter verarbeitet in unserem Auftrag Server-Logfiles
(siehe Abschnitt 3.1) auf Grundlage eines Auftragsverarbeitungsvertrags
gemäß Art. 28 DSGVO.

### 5.2 Fehleranalyse (Sentry)

Functional Software, Inc. dba Sentry
45 Fremont Street, Suite 800
San Francisco, CA 94105, USA

Zur Diagnose technischer Fehler nutzen wir den Dienst Sentry in der
EU-Region (Ingest-Endpunkt `de.sentry.io`, Rechenzentrum Frankfurt am
Main). Fehlerereignisse enthalten Stack-Traces, HTTP-Statuscodes,
Umgebungs- und Release-Informationen (Git-Commit). Personenbezogene
Nutzdaten werden vor der Übermittlung entfernt:

- Die Sentry-Option `send_default_pii=False` unterdrückt die
  automatische Aufnahme von IP-Adressen und Sitzungsdaten.
- Ein serverseitiger `before_send`-Filter entfernt alle
  Query-Parameter mit Adressbezug (`address`, `street`, `hnr`, `plz`)
  sowie die HTTP-Header `CF-Connecting-IP`, `X-Forwarded-For` und
  `X-Real-IP`, und redigiert den vollständigen Request-Body des
  internen Inferenz-Dienstes.

Die Datenübermittlung an einen Anbieter mit Sitz außerhalb des EWR
erfolgt auf Grundlage von EU-Standardvertragsklauseln gemäß
Art. 46 Abs. 2 lit. c DSGVO in Verbindung mit einem
Auftragsverarbeitungsvertrag nach Art. 28 DSGVO.

**Rechtsgrundlage:** Art. 6 Abs. 1 lit. f DSGVO (berechtigtes Interesse
an Fehleranalyse und IT-Sicherheit).

### 5.3 Reichweiten- und Nutzungsanalyse (Umami, self-hosted)

Zur Analyse der Reichweite und Nutzung dieser Website betreiben wir
eine Instanz der Open-Source-Software Umami
(<https://umami.is/>) auf demselben Server bei Hetzner Online GmbH
(siehe Abschnitt 5.1). Es findet **keine Übermittlung an Dritte**
statt.

Umami verarbeitet ausschließlich pseudonymisierte, aggregierte
Nutzungsdaten:

- URL der aufgerufenen Seite,
- Referrer-URL,
- Datum und Uhrzeit,
- ungefähre Bildschirmgröße,
- Browser- und Gerätetyp.

Umami arbeitet **ohne Cookies**, **ohne Speicherung der vollständigen
IP-Adresse in der Datenbank**, **ohne Erstellung individueller Nutzer-
profile** und **ohne seitenübergreifendes Tracking**. Aus den erhobenen
Daten kann kein Rückschluss auf einzelne Personen gezogen werden.

**Rechtsgrundlage:** Art. 6 Abs. 1 lit. f DSGVO (berechtigtes Interesse
an statistischer Analyse der Nutzung des eigenen Dienstes).

### 5.4 Content Delivery Network, TLS-Terminierung und DDoS-Schutz (Cloudflare)

Cloudflare, Inc.
101 Townsend Street
San Francisco, CA 94107, USA

Sämtlicher HTTP-Verkehr zu und von addrlens.de wird über die
Infrastruktur von Cloudflare (in der Regel Rechenzentrum Frankfurt
am Main für europäische Nutzer) geleitet. Cloudflare terminiert die
TLS-Verbindung, filtert erkannte Bedrohungen (WAF, Rate Limiting) und
leitet legitime Anfragen über einen verschlüsselten Cloudflare-Tunnel
an den Ursprungs-Server bei Hetzner weiter. Der Ursprungs-Server ist
nicht direkt aus dem öffentlichen Internet erreichbar.

Cloudflare verarbeitet dabei folgende Daten:

- IP-Adresse,
- Datum und Uhrzeit,
- HTTP-Methode, URL, Statuscode,
- User-Agent,
- ggf. TLS-Fingerprint zur Bot-Erkennung.

Die Datenübermittlung an einen Anbieter mit Sitz außerhalb des EWR
erfolgt auf Grundlage von EU-Standardvertragsklauseln gemäß
Art. 46 Abs. 2 lit. c DSGVO in Verbindung mit einem
Auftragsverarbeitungsvertrag nach Art. 28 DSGVO.

**Rechtsgrundlage:** Art. 6 Abs. 1 lit. f DSGVO (berechtigtes Interesse
an IT-Sicherheit, Abwehr von Angriffen und effizienter Auslieferung).

### 5.5 Sprachmodell-Dienst für generierte Kurzbeschreibungen (Cloudflare Workers AI)

Cloudflare, Inc.
101 Townsend Street
San Francisco, CA 94107, USA

Für den Endpunkt `/api/history` (siehe Abschnitt 3.3) wird der Dienst
*Workers AI* von Cloudflare eingesetzt. Übermittelt werden ausschließ-
lich der Berliner Bezirk und Ortsteil der abgefragten Adresse sowie
eine strukturierte Liste öffentlicher OpenStreetMap-Objekte
(Gedenkstätten, Denkmäler, historische Gebäude) im Umkreis von ca.
500 Metern. Es werden **keine IP-Adressen, Nutzer-Identifikatoren,
Straßennamen oder Hausnummern** übermittelt.

Bei Nichterreichbarkeit des Dienstes wird die Anfrage automatisch
durch das lokal auf dem Ursprungs-Server betriebene Sprachmodell
beantwortet (siehe Abschnitt 3.3).

Die Datenübermittlung an einen Anbieter mit Sitz außerhalb des EWR
erfolgt auf Grundlage von EU-Standardvertragsklauseln gemäß
Art. 46 Abs. 2 lit. c DSGVO in Verbindung mit einem
Auftragsverarbeitungsvertrag nach Art. 28 DSGVO.

**Rechtsgrundlage:** Art. 6 Abs. 1 lit. b DSGVO (Erfüllung des von
Ihnen aktiv angeforderten KI-Dienstes) sowie Art. 6 Abs. 1 lit. f
DSGVO (berechtigtes Interesse an einem nützlichen Zusatzangebot).

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
einzulegen. Der Widerspruch kann formfrei per E-Mail an sapta@addrlens.de
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
27.08.2026. Durch die Weiterentwicklung der Website oder aufgrund
geänderter gesetzlicher bzw. behördlicher Vorgaben kann es notwendig
werden, diese Datenschutzerklärung anzupassen. Die jeweils aktuelle
Datenschutzerklärung kann jederzeit auf der Website unter
`https://addrlens.de/datenschutzerklaerung` abgerufen werden.

---

# Privacy Policy (English translation)

_This English text is provided for the convenience of international
visitors. In case of any dispute, the German version above is legally
authoritative._

_Version: 27.08.2026_

## 1. Data Controller

The data controller within the meaning of the General Data Protection
Regulation (GDPR) and other national data protection laws of the
Member States as well as other data protection regulations is:

Saptadip Sarkar
Hanns-Eisler-Platz 3
39128, Magdeburg
Deutschland

E-Mail: sapta@addrlens.de
Website: https://addrlens.de

## 2. Purpose and character of the website

Berlin Address Intelligence is a publicly accessible tool that enriches Berlin
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

For abuse prevention, the client IP address forwarded by Cloudflare in
the `CF-Connecting-IP` HTTP header is additionally read for
per-endpoint rate limiting inside the app process. This processing is
in-memory only and is not persisted.

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

### 3.3 When using the AI explanations (`/api/card_insight`, `/api/history`)

When you request an AI-generated explanation for a data card
(`/api/card_insight`) or a short historical description of an
address's surroundings (`/api/history`), the related factual data
(numbers, categories, distances, borough and Ortsteil, and a curated
list of public OpenStreetMap features within a short radius) is
transmitted to a language-model service and processed there.

- For the `/api/card_insight` endpoint, inference runs exclusively on
  a locally-operated language model (llama.cpp) on the same server at
  Hetzner.
- For the `/api/history` endpoint, Cloudflare Workers AI is used
  (see section 5.5). If that service is unreachable, the locally-
  operated model automatically takes over.

**No personal data** is sent to the language-model service — in
particular, no IP address, no user identifier, and no free-text
address (street name and house number are stripped before
transmission). Transmitted location information is limited to
borough and Ortsteil level.

**Legal basis:** Art. 6 (1) (b) GDPR (performance of the service) and
Art. 6 (1) (f) GDPR (legitimate interest in providing a useful
supplementary offering).

### 3.4 Caching of generated summaries

To reduce external requests and response times, the short texts
generated for `/api/history` are held in a server-side cache for at
most seven days. The cache key is a coordinate pair (latitude /
longitude) rounded to approximately 100-metre grid cells — there is
**no link** to IP addresses, sessions, or user identifiers. The cache
is cleared automatically when the TTL expires or when the service
restarts.

**Legal basis:** Art. 6 (1) (f) GDPR (legitimate interest in efficient
operation and preservation of external processing quotas).

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

Hetzner Online GmbH,
Industriestr. 25,
91710 Gunzenhausen

The hosting provider processes server logfiles (see section 3.1) on our
behalf under a data processing agreement pursuant to Art. 28 GDPR.

### 5.2 Error tracking (Sentry)

Functional Software, Inc. dba Sentry
45 Fremont Street, Suite 800
San Francisco, CA 94105, USA

For technical error diagnosis we use the Sentry service in the EU
region (ingest endpoint `de.sentry.io`, Frankfurt am Main). Error
events contain stack traces, HTTP status codes, environment and
release (git commit) information. Personal payload data is stripped
before transmission:

- The Sentry option `send_default_pii=False` disables automatic
  capture of IP addresses and session data.
- A server-side `before_send` filter redacts all address-bearing
  query-string parameters (`address`, `street`, `hnr`, `plz`), the
  HTTP headers `CF-Connecting-IP`, `X-Forwarded-For`, `X-Real-IP`,
  and the full request body of the internal inference service.

Transfer to a provider based outside the EEA takes place on the basis
of EU Standard Contractual Clauses pursuant to Art. 46 (2) (c) GDPR in
combination with a data processing agreement pursuant to Art. 28 GDPR.

**Legal basis:** Art. 6 (1) (f) GDPR (legitimate interest in error
analysis and IT security).

### 5.3 Reach and usage analysis (Umami, self-hosted)

For reach and usage analysis of this website we run an instance of
the open-source software Umami (<https://umami.is/>) on the same
server at Hetzner Online GmbH (see section 5.1). **No transfer to
third parties** takes place.

Umami processes only pseudonymised, aggregated usage data:

- URL of the page visited,
- referrer URL,
- date and time,
- approximate screen size,
- browser and device type.

Umami operates **without cookies**, **without storing the full IP
address in the database**, **without creating individual user
profiles**, and **without cross-site tracking**. The collected data
does not allow inferences about individual persons.

**Legal basis:** Art. 6 (1) (f) GDPR (legitimate interest in
statistical analysis of usage of our own service).

### 5.4 Content Delivery Network, TLS termination and DDoS protection (Cloudflare)

Cloudflare, Inc.
101 Townsend Street
San Francisco, CA 94107, USA

All HTTP traffic to and from addrlens.de is routed through
Cloudflare's infrastructure (typically the Frankfurt am Main data
centre for European visitors). Cloudflare terminates the TLS
connection, filters recognised threats (WAF, rate limiting), and
forwards legitimate requests through an encrypted Cloudflare Tunnel
to the origin server at Hetzner. The origin server is not directly
reachable from the public internet.

Cloudflare processes the following data:

- IP address,
- date and time,
- HTTP method, URL, status code,
- User-Agent,
- optionally a TLS fingerprint for bot detection.

Transfer to a provider based outside the EEA takes place on the basis
of EU Standard Contractual Clauses pursuant to Art. 46 (2) (c) GDPR in
combination with a data processing agreement pursuant to Art. 28 GDPR.

**Legal basis:** Art. 6 (1) (f) GDPR (legitimate interest in IT
security, defence against attacks and efficient delivery).

### 5.5 Language-model service for generated summaries (Cloudflare Workers AI)

Cloudflare, Inc.
101 Townsend Street
San Francisco, CA 94107, USA

For the `/api/history` endpoint (see section 3.3) we use Cloudflare's
*Workers AI* service. Transmitted are only the Berlin borough and
Ortsteil of the queried address plus a structured list of public
OpenStreetMap features (memorials, monuments, historic buildings)
within approximately 500 metres. **No IP addresses, user identifiers,
street names, or house numbers** are transmitted.

If the service is unreachable, the request is automatically served by
the language model running locally on the origin server (see
section 3.3).

Transfer to a provider based outside the EEA takes place on the basis
of EU Standard Contractual Clauses pursuant to Art. 46 (2) (c) GDPR in
combination with a data processing agreement pursuant to Art. 28 GDPR.

**Legal basis:** Art. 6 (1) (b) GDPR (performance of the AI service
you actively requested) and Art. 6 (1) (f) GDPR (legitimate interest
in providing a useful supplementary offering).

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
informally by email to sapta@addrlens.de.

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

This privacy policy is currently valid and dated 27.08.2026. Due to the
further development of the website or due to changed legal or
regulatory requirements, it may become necessary to adapt this privacy
policy. The current privacy policy can be accessed on the website at
any time at `https://addrlens.de/datenschutzerklaerung`.
