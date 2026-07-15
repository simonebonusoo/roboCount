# Migration Report

## Struttura iniziale

Repository originale analizzato:

- `frontend/` con app React + Vite
- `backend/` con API FastAPI
- `services.py` con business logic e trasformazioni pandas
- `database.py` come adapter PostgreSQL/Supabase compatibile con il vecchio codice stile SQLite
- `_deprecated_review/` con materiale legacy gia isolato
- file storici di deploy locale/non piu necessari (`render.yaml`, `Procfile`, `app.py`, `ui_helpers.py`, asset root legacy)

## Principali problemi trovati

- impossibilita di creare una cartella sorella `RoboCount` accanto a `roboCount` sul filesystem corrente, perche il volume macOS e case-insensitive
- frontend e backend separati in una struttura non pronta come root unica per Vercel
- sessioni backend basate su memoria di processo (`SESSION_STORE`), inadatte a serverless e multi-instance
- presenza di file e asset legacy non piu referenziati nel runtime attivo
- configurazione deploy ancora orientata a Render/backend separato
- dipendenze frontend minimali ma senza lint dedicato alla nuova root
- alcune ricostruzioni categorie lato backend rifacevano piu volte lo stesso accesso pandas/query
- persistente presenza di piccoli residui di codice non usato nel frontend, non bloccanti ma da rifinire

## File rimossi o non migrati

- `_deprecated_review/`
- `frontend_unused/` e materiale Streamlit legacy
- `app.py`
- `ui_helpers.py`
- `components/live_search/index.html`
- `render.yaml`
- `Procfile`
- asset root legacy (`hero-*`)
- pagine/componenti frontend non piu referenziati:
  - `DashboardPage.jsx`
  - `PlaceholderPage.jsx`
  - `CoupleHeroCard.*`
  - `HomeHeroCard.jsx`
  - immagini non ottimizzate `login-robot.png`, `signup-robot.png`

## Dipendenze rimosse o non mantenute nella nuova root

- nessuna dipendenza Streamlit/legacy e stata portata nella nuova cartella
- non e stato mantenuto il file separato `requirements-backend.txt`; sostituito da `requirements.txt`
- il frontend ora dichiara solo le dipendenze necessarie a build/runtime e una toolchain lint minima (`eslint`, `@eslint/js`, `eslint-plugin-react`, `globals`)

## Modifiche strutturali

- creata la nuova cartella `RoboCount/` all'interno del repository originale, per limite del filesystem case-insensitive
- frontend spostato in root Vite della nuova cartella (`src/`, `index.html`, `vite.config.js`, `package.json`)
- backend mantenuto in `backend/` con entrypoint Vercel in `api/index.py`
- aggiunti:
  - `vercel.json`
  - `.env.example`
  - `.gitignore`
  - `eslint.config.js`
  - `README.md`
  - `MIGRATION_REPORT.md`

## Bug corretti

- sostituito il session store in memoria con cookie firmato stateless, compatibile con deploy serverless
- aggiunta gestione produzione/dev del `SESSION_SECRET`
- centralizzata la gestione degli origin CORS tramite env (`ALLOWED_ORIGINS`, `CORS_ORIGINS`, `VERCEL_URL`)
- rimossa la configurazione FastAPI `startup` deprecata a favore di `lifespan`
- corretti script locali per la nuova struttura root
- introdotto un lint coerente con un progetto React JavaScript senza TypeScript e senza `prop-types`

## Performance

- preservato il lazy loading delle route React gia presente
- ottimizzato il calcolo delle categorie backend evitando ricostruzioni ripetute dello stesso dataset visibile
- mantenuta la separazione in chunk del frontend durante la build production

## Persistenza locale trovata

- `localStorage` per tema (`app-theme`)
- `localStorage` per cache avatar frontend
- `localStorage` per override locali delle categorie nel profilo
- nessun uso di IndexedDB rilevato
- nessun filesystem locale richiesto a runtime nella nuova root
- persistenza applicativa principale: PostgreSQL via `DATABASE_URL`

Gestione:

- la persistenza dati principale e gia predisposta lato server via PostgreSQL/Supabase-compatible
- le chiavi `localStorage` restano solo come enhancement UI locale e non come requisito applicativo centrale

## Preparazione Supabase

Gia predisposto:

- `DATABASE_URL` come punto unico di connessione PostgreSQL
- struttura backend separata per API/business logic/data access
- assenza di chiavi hardcoded
- `.env.example` per variabili richieste
- sessioni stateless compatibili con infrastruttura serverless

Da collegare successivamente:

- credenziali reali Supabase
- eventuale auth nativa Supabase se si vorra sostituire l'auth corrente
- eventuale storage remoto
- eventuale RLS a livello schema/database

## Deploy Vercel

Configurazione predisposta:

- root deployabile: `RoboCount`
- build frontend: `npm run build`
- output: `dist`
- API Python esposta tramite `api/index.py`
- routing SPA + API tramite `vercel.json`

Variabili d'ambiente richieste:

- `DATABASE_URL`
- `SESSION_SECRET`
- `MONITOR_SPESE_COOKIE_SECURE=true` in produzione

Variabili opzionali:

- `ALLOWED_ORIGINS`
- `VITE_API_BASE_URL`

## Comandi

Installare frontend:

```bash
cd RoboCount
npm install
```

Installare backend:

```bash
cd RoboCount
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Avvio sviluppo completo:

```bash
cd RoboCount
./run-dev.sh
```

Typecheck:

```bash
cd RoboCount
npm run typecheck
```

Lint:

```bash
cd RoboCount
npm run lint
```

Build production:

```bash
cd RoboCount
npm run build
```

## Funzionalita verificate

- [x] bootstrap frontend Vite
- [x] import backend FastAPI (`api.index`)
- [x] build production frontend completata
- [x] sessioni backend non piu dipendenti da memoria locale del processo
- [x] route frontend principali migrate: login, home, calendar, expenses, incomes, savings, report, profile, admin users, couple balance
- [x] CRUD spese mantenuto nel codice migrato
- [x] CRUD entrate mantenuto nel codice migrato
- [x] gestione categorie profilo e mensili mantenuta nel codice migrato
- [x] inviti di coppia mantenuti nel codice migrato
- [x] area admin utenti mantenuta nel codice migrato
- [x] tema e avatar mantenuti nel codice migrato
- [x] struttura pronta per Vercel con root unica

## Verifiche eseguite

Comandi eseguiti durante la migrazione:

- `npm install`
- `npm run lint`
- `npm run typecheck`
- `npm run build`
- `python -c "from api.index import app; print(app.title)"`

## Problemi residui

- il progetto non e stato testato end-to-end contro database reale per assenza di credenziali `DATABASE_URL` nel task corrente
- `npm run lint` passa ma segnala ancora warning di codice JS non usato in alcune pagine/componenti; non bloccano la build, ma sono candidati a un ulteriore passaggio di rifinitura
- gli asset `login-robot-optimized.png` e `signup-robot-optimized.png` restano relativamente pesanti e possono essere compressi ulteriormente in un secondo passaggio
- per limite del filesystem corrente, la nuova cartella non puo esistere come sorella con sola differenza di maiuscole/minuscole rispetto a `roboCount`; per questo la migrazione e stata collocata in `roboCount/RoboCount`
