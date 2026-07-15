# RoboCount

Versione pulita e production-ready di RoboCount, ricostruita partendo dal runtime effettivamente usato nel repository originale.

## Stack

- Frontend: React 18 + Vite
- Backend: FastAPI
- Database: PostgreSQL via `DATABASE_URL`
- Deploy target: Vercel (frontend static + API Python in `api/index.py`)

## Struttura

```text
RoboCount/
├── api/
│   └── index.py
├── backend/
│   ├── main.py
│   ├── schemas.py
│   └── serializers.py
├── src/
├── database.py
├── services.py
├── package.json
├── requirements.txt
├── run-dev.sh
└── vercel.json
```

## Variabili d'ambiente

Copia `.env.example` in `.env` e valorizza almeno:

- `DATABASE_URL`
- `SESSION_SECRET`

Variabili opzionali:

- `ALLOWED_ORIGINS`
- `MONITOR_SPESE_COOKIE_SECURE`
- `VITE_API_BASE_URL`

Note importanti:

- `DATABASE_URL` deve puntare al Supabase Shared Pooler in transaction mode sulla porta `6543`
- lo username deve mantenere il formato `postgres.PROJECT_REF`
- se la password contiene caratteri speciali riservati nell'URL, deve essere percent-encoded

## Comandi

Installazione frontend:

```bash
npm install
```

Installazione backend:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Sviluppo completo:

```bash
./run-dev.sh
```

Lo script:

- crea `.venv` se manca
- installa dipendenze Python se necessarie
- valida `.env`
- usa sempre il Python locale della `.venv`
- reinstalla dipendenze frontend solo quando serve

Sviluppo separato:

```bash
npm run dev
.venv/bin/python -m uvicorn api.index:app --reload --host 127.0.0.1 --port 8000
```

Lint:

```bash
npm run lint
```

Typecheck:

```bash
npm run typecheck
```

Build production:

```bash
npm run build
```

## Deploy su Vercel

Imposta nel progetto Vercel:

- Root directory: `RoboCount`
- Build command: `npm run build`
- Output directory: `dist`

Environment variables richieste:

- `DATABASE_URL`
- `SESSION_SECRET`
- `MONITOR_SPESE_COOKIE_SECURE=true`

`ALLOWED_ORIGINS` e `VITE_API_BASE_URL` sono opzionali. Con frontend e API sullo stesso dominio, `VITE_API_BASE_URL=/api` e il comportamento di default sono gia sufficienti.

## Note applicative

- lo schema PostgreSQL viene inizializzato automaticamente allo startup tramite `initialize_database()`
- il primo utente registrato viene promosso admin automaticamente
