# Dansk Vægtløftning – Analyse-app: Projektdokument

## 1. Formål, Grundprincip og Hovedkrav

### Formål og mål
Appen leverer hurtige, korrekte og overskuelige analyser af dansk vægtløftning (fra 2019 og frem) som et moderne, analytisk supplement til `vlstat.dk`.

* **Grundprincip:** Høj datakvalitet, stabil drift og hensynsfuld interaktion med eksterne kilder vægtes altid højere end hurtig udrulning af nye funktioner.

### Hovedkrav til funktioner
* **Hit-rates på enkeltforsøg:** Fordelt på forsøgsnummer (1., 2. og 3. forsøg), disciplin (træk/stød) og løfter.
* **Træk/stød-forhold og progression:** Historisk udvikling og ratio-analyser over tid.
* **Dynamiske beregninger:** Automatisk udregning af Total og Sinclair-point m.fl. i vores eget system (hentes ikke fra `vlstat.dk`).
* **Løfterprofiler (DPM.lol-inspireret):** Søgbare profiler med personlige rekorder (PR), historisk udvikling, interaktive grafer og skæve/underholdende statistikker (f.eks. *"laveste hit-rate på 3. stød"*, *"foretrukne vægtøgning"* eller *"mest stabile løfter"*).
* **Stævnesider (Konkurrence-hubs):** Dedikerede sider med samlede resultatlister, stævne-metrics (f.eks. samlet succesrate for stævnet, PR-oversigter), overblik over dagens bedste Sinclair-præstationer samt klubopgørelser.
* **Admin-side til manuel indtastning:** Beskyttet side i UI'et (login via password i `.env`), hvor nye stævner og resultater fremadrettet kan indtastes via formular eller CSV-upload.
* **Strikt skånsomhed over for vlstat.dk:** Historisk data (2019–2026) hentes kun én gang via et lokalt seed-script. Ingen live-scraping eller on-the-fly belastning under brug. Al data i appen læses udelukkende fra egen PostgreSQL/Supabase-database.

---

## 2. Arkitektur & Ansvarsfordeling (Clean Architecture / MVC)

Systemet er opdelt i tre uafhængige lag med databasen som eneste kontrakt:

1. **Data & Infrastructure Layer (Scraper & Database):**
   * Indeholder one-off scraperen (`Playwright` + `BeautifulSoup4`), lagring af rå HTML, `Pydantic`-validering og idempotent indlæsning til PostgreSQL/Supabase.
   * Håndterer database-migrations, adgangsstyring og præ-aggregerede SQL-views (totals, hit-rates, progression, PR-markeringer).
2. **Business Logic / Controller Layer:**
   * En separat, testet Python-pakke til forretningslogik, valideringsregler og formler (f.eks. Sinclair-beregning på tværs af årgange).
   * Indeholder **ingen** UI-kode.
3. **Presentation Layer (View / Frontend):**
   * Bygget i `Streamlit` + `Plotly` med caching for lynhurtig brugerflade og interaktive grafer.
   * Indeholder udelukkende visuel præsentation samt Admin-interfacet til oprettelse af nye stævner. Kalder Business Logic-pakken og SQL-views uden selv at implementere udregninger.

---

## 3. Datamodel (Single Source of Truth)

Vi gemmer kun rå kildedata i tabellerne. Afledte værdier (Total, Sinclair-point, placering, hit-rates) må **ikke** gemmes som faste kolonner, men beregnes dynamisk i SQL-views og Business Logic-laget.

* **`lifter`**: `id` (intern PK), `vlstat_id` (unik nøgle fra vlstat), `name`, `gender`, `birth_year`.
* **`competition`**: `id`, `vlstat_id`, `name`, `date`, `location`.
* **`entry`**: Relation mellem løfter og stævne (`lifter_id`, `competition_id`, `bodyweight`, `weight_class`, `club`).
* **`attempt`**: Enkeltforsøg (`entry_id`, `discipline` [`'snatch'` | `'cj'`], `attempt_number` [`1` | `2` | `3`], `weight_kg` [`int`], `is_successful` [`bool`]).
  * *Logik for forsøg:* Et løft er enten ramt (`is_successful = True`) eller ikke ramt (`is_successful = False`). Hvis løfteren stod over et forsøg, oprettes rækken enten ikke, eller vægten sættes til `NULL`.
* **`sinclair_coefficient`**: Koefficienter (`a`, `b`, `gender`, `valid_from_year`, `valid_to_year`) til dynamisk pointberegning.

---

## 4. Dataindsamling: One-Off Seed Scraper (2019–2026)

Da `vlstat.dk` er bygget i ældre ASP.NET WebForms (`.aspx`) med server-side `__VIEWSTATE` postbacks, og da fødselsår/køn kræver opslag på den enkelte løfters profil, opdeles engangs-scrapingen i to adskilte faser:

### Fase 1: Rå HTML-høst (`scraper/fetch_raw.py`)
* **Værktøj:** Python `Playwright` (kørt synkront i én tråd).
* **Stævne-høst:** Navigerer gennem stævneresultater fra 2019–2026 og gemmer den rå HTML for hvert stævne lokalt i `data/raw_html/competitions/`.
* **Løfter-høst (Deduplikeret):** Når scriptet møder en løfter (ud fra `vlstat_id`), tjekker det, om `data/raw_html/lifters/{vlstat_id}.html` allerede findes lokalt. Kun hvis filen ikke findes, besøges løfterens profilside for at gemme HTML'en med fødselsår og køn. Dermed rammes hver løfterprofil højst én gang i hele processen.
* **Skånsomhed (Rate-limiting):** Hardcodet `time.sleep(3.0)` mellem hvert eneste klik/sideskift. Scriptet må aldrig parse data eller skrive til databasen under høsten.

### Fase 2: Lokal Parsing & Database-seed (`scraper/parse_and_seed.py`)
* **Værktøj:** `BeautifulSoup4` + `Pydantic` + `SQLAlchemy`/`psycopg2`.
* **Opførsel:** Læser udelukkende fra de lokale filer i `data/raw_html/`.
* **Parser-regler:** Udtrækker løfterdata, stævnedata, kropsvægt, vægtklasse, klub samt forsøg 1–3 i træk og stød (kilo samt om løftet blev ramt eller ej). Ignorerer kolonner for Total og Point fra vlstat. Validerer alt gennem Pydantic og indsætter i Supabase.

---

## 5. Drift, Sikkerhed og Admin-modul

* **Database-roller:** PostgreSQL/Supabase sættes op med strikt rollefordeling:
  * `read_only`-rolle til den offentlige Streamlit-frontend.
  * `write`-rolle til seed-scriptet samt til Admin-modulet, når brugeren er logget ind.
* **Miljøvariabler:** Database-URLs og `ADMIN_PASSWORD` gemmes i `.env` (udeladt via `.gitignore`).
* **Datakvalitet:** Sikring af dataintegritet gennem automatisk validering ved indlæsning og strikte typer.
* **GDPR:** Fødselsdatoer begrænses til fødselsår (`birth_year`), så der ikke udstilles unødig personhenførbar data for bl.a. juniorløftere.

---

## 6. UI-Design, Farvetema og Løft-visning

### Farvepalette
* **Light Cream (`RGB: 255, 249, 242` / `#FFF9F2`):** Primær baggrundsfarve på hele applikationen for et lyst, let og læsvenligt udtryk.
* **Warm Beige (`RGB: 243, 230, 213` / `#F3E6D5`):** Paneler, kort, tabeller og sekundære baggrundsområder (f.eks. sidebar) for at skabe en behagelig kontrast.
* **Deep Burgundy (`RGB: 128, 0, 32` / `#800020`):** Primær brand- og overskriftsfarve, fremhævede knapper og overordnede fokuselementer i Streamlit.
* **Coral Rose (`RGB: 212, 80, 96` / `#D45060`):** Accentfarve til interaktive elementer, nøgletal/metrics, PR-markeringer og fremhævede grafelementer i Plotly.

### Visning af enkeltforsøg i tabeller
Der bruges **ikke** gennemstregning eller minustegn i UI'et. Alle forsøg vises som selve vægttallet (f.eks. `95`), hvor ramte løft (`is_successful = True`) og ikke-ramte løft (`is_successful = False`) adskilles tydeligt ved, at selve tallet har to forskellige farver (f.eks. mørk/grønlig tekst for ramte løft og Coral Rose `#D45060` eller dæmpet rød for ikke-ramte løft).

---

## 7. Bindende regler for AI-assisteret udvikling (1–8)

1. **Følg altid den valgte arkitektur (MVC / Clean Architecture):** Hold Data, Business Logic og View skarpt adskilt.
2. **Ingen forretningslogik i Viewet:** Streamlit-filer må aldrig indeholde udregninger af Sinclair, totals eller hit-rates.
3. **Genbrug eksisterende datamodeller:** Brug altid fastlagte Pydantic-modeller, typer og konstanter frem for at oprette nye/overlappende.
4. **Fokuserede ændringer:** Hold kodeændringer minimale og strengt afgrænsede til den aktuelle opgave.
5. **Sikkerhed:** Ingen hardkodede nøgler, passwords eller miljøafhængige konfigurationer i koden (brug `.env`).
6. **Bagudkompatibilitet:** Bevar fuld kompatibilitet for eksisterende SQL-views og database-schemaer ved ændringer.
7. **Dokumentation:** Dokumentér ændringer og arkitektoniske beslutninger løbende i projektdokumentationen.
8. **Definition of Done:** En funktion er først færdig, når koden er testet (`pytest`), valideret mod datamodellen, integreret uden nedbrud og fuldt dokumenteret.

---

## 8. AI-Agent Workflow & Token-Optimering (Model Routing)

Projektet bygges med AI-kodningsagenter (Claude Code, Codex, Antigravity/Gemini). For at maksimere kvaliteten på svære opgaver og spare tokens/penge på rutineopgaver skal arbejde routes efter følgende model-strategi:

### Niveau 1: Frontier / High-Reasoning Modeller (f.eks. Claude Opus/Sonnet, Gemini 2.5 Pro, o3)
*Anvendes KUN til arkitektur, komplekse udregninger og svær DOM-analyse (ca. 20 % af arbejdet):*
* Design af PostgreSQL-schema, relationer og komplekse SQL-views (vinduesfunktioner til PR-udvikling, streaks og hit-rates).
* Udvikling af kerne-forretningslogik (Sinclair-formler på tværs af perioder og logik for totals).
* Opsætning af Playwright-navigation til ASP.NET `__VIEWSTATE`-håndtering og deduplikering af løfter-opslag.

### Niveau 2: Hurtige / Billige Modeller (f.eks. Claude Haiku, Gemini 2.5 Flash, GPT-4o-mini)
*Anvendes til al boilerplate, UI, standard-parsing og tests (ca. 80 % af arbejdet):*
1. Skrivning af Pydantic-modeller, standard CRUD-funktioner og formularerne på Admin-siden.
2. Opbygning af Streamlit-sider, tabeller, søgefiltre og CSS-styling med farvetemaet.
3. Opsætning af Plotly-grafer ud fra allerede definerede SQL-views/dataframes.
4. Skrivning af unit-tests (`pytest`) og løbende dokumentation.

### Regler for Token-Hygiejne (Kontekst-besparelse)
* **Indlæs aldrig hele `.aspx` HTML-filer i AI-konteksten:** ASP.NET-filer indeholder enorme `__VIEWSTATE`-tekststrenge, som æder tusindvis af tokens til ingen verdens nytte. Når parseren (`parse_and_seed.py`) skal skrives, må agenten kun inspicere et lille udsnit (f.eks. én `<table>` eller 2–3 `<tr>`-rækker) fra en gemt HTML-fil.
* **Arbejd modulært:** Når en agent arbejder på Streamlit UI, må den kun læse funktionssignaturer i Business Logic-laget og SQL-views – den skal aldrig læse kode eller filer i `scraper/`-mappen.