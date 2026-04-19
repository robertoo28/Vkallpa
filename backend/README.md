# Backend (FastAPI) - V-Kallpa

## Requisitos
- Python 3.11+
- Acceso a Azure Blob Storage configurado en `config.dev.json` (raíz del repo)

## Configuración rápida

1) Crear el archivo `backend/.env` (ya hay un ejemplo en `backend/.env.example`):

```env
AUTH_USERNAME=admin
AUTH_PASSWORD_HASH=plain:admin
JWT_SECRET=tu_secreto
JWT_EXPIRE_MINUTES=60
```

2) Instalar dependencias:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r backend/requirements.txt
```

3) Ejecutar API:

```powershell
uvicorn backend.app.main:app --reload
```

La API corre en `http://127.0.0.1:8000`.

## Endpoints clave
- `POST /api/v1/auth/login`
- `GET /api/v1/health`
- `GET /api/v1/buildings`
- `GET /api/v1/buildings/{id}/range`
- `GET /api/v1/accueil/summary`
- `GET /api/v1/dashboard-multi/summary`
- `GET /api/v1/monitoring/graphs`
- `GET /api/v1/monitoring/heatmap`
- `GET /api/v1/monitoring/calendar`
- `GET /api/v1/monitoring/boxplots`
- `GET /api/v1/monitoring/comparaison-puissance`
- `GET /api/v1/profils`
- `GET /api/v1/puissance`
- `GET /api/v1/traitement/comparaison-periode`
- `GET /api/v1/traitement/batiments`
- `POST /api/v1/ia/nilm`

## Ejemplos de ejecución (curl)

### 1) Login
```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'
```

Respuesta:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

Guarda el token en una variable (ej. en bash):
```bash
TOKEN="eyJhbGciOiJIUzI1NiIs..."
```

### 2) Health
```bash
curl http://127.0.0.1:8000/api/v1/health
```

### 3) Listar edificios
```bash
curl http://127.0.0.1:8000/api/v1/buildings \
  -H "Authorization: Bearer $TOKEN"
```

### 4) Rango de fechas por edificio
```bash
curl http://127.0.0.1:8000/api/v1/buildings/MiArchivo.xlsx/range \
  -H "Authorization: Bearer $TOKEN"
```

### 5) Accueil
```bash
curl http://127.0.0.1:8000/api/v1/accueil/summary \
  -H "Authorization: Bearer $TOKEN"
```

### 6) Dashboard Multi
```bash
curl http://127.0.0.1:8000/api/v1/dashboard-multi/summary \
  -H "Authorization: Bearer $TOKEN"
```

### 7) Monitoring (graphs)
```bash
curl "http://127.0.0.1:8000/api/v1/monitoring/graphs?building=MiArchivo.xlsx&start_date=2024-01-01&end_date=2024-03-31&metric=Energie&aggregation=Jour&show_vacances=true" \
  -H "Authorization: Bearer $TOKEN"
```

### 8) Monitoring (heatmap)
```bash
curl "http://127.0.0.1:8000/api/v1/monitoring/heatmap?building=MiArchivo.xlsx&start_date=2024-01-01&end_date=2024-03-31" \
  -H "Authorization: Bearer $TOKEN"
```

### 9) Monitoring (calendar)
```bash
curl "http://127.0.0.1:8000/api/v1/monitoring/calendar?building=MiArchivo.xlsx&start_date=2024-01-01&end_date=2024-03-31" \
  -H "Authorization: Bearer $TOKEN"
```

### 10) Monitoring (boxplots)
```bash
curl "http://127.0.0.1:8000/api/v1/monitoring/boxplots?building=MiArchivo.xlsx&start_date=2024-01-01&end_date=2024-03-31" \
  -H "Authorization: Bearer $TOKEN"
```

### 11) Monitoring (comparaison puissance)
```bash
curl "http://127.0.0.1:8000/api/v1/monitoring/comparaison-puissance?building=MiArchivo.xlsx&reference_date=2024-02-01&comparison_dates=2024-02-02&comparison_dates=2024-02-08" \
  -H "Authorization: Bearer $TOKEN"
```

### 12) Profils
```bash
curl "http://127.0.0.1:8000/api/v1/profils?building=MiArchivo.xlsx&start_date=2024-01-01&end_date=2024-03-31" \
  -H "Authorization: Bearer $TOKEN"
```

### 13) Puissance
```bash
curl "http://127.0.0.1:8000/api/v1/puissance?building=MiArchivo.xlsx&start_date=2024-01-01&end_date=2024-03-31" \
  -H "Authorization: Bearer $TOKEN"
```

### 14) Comparaison Periode
```bash
curl "http://127.0.0.1:8000/api/v1/traitement/comparaison-periode?building=MiArchivo.xlsx&start_a=2024-01-01&end_a=2024-01-31&start_b=2025-01-01&end_b=2025-01-31&metric=Energie" \
  -H "Authorization: Bearer $TOKEN"
```

### 15) Batiments
```bash
curl "http://127.0.0.1:8000/api/v1/traitement/batiments?buildings=A.xlsx&buildings=B.xlsx&start_date=2024-01-01&end_date=2024-02-01&metric=Energie&aggregation=Jour&normalize=true" \
  -H "Authorization: Bearer $TOKEN"
```

### 16) NILM
```bash
curl -X POST http://127.0.0.1:8000/api/v1/ia/nilm \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"building":"MiArchivo.xlsx","start_date":"2024-01-01","end_date":"2024-03-31","aggregation":"Jour"}'
```

## Notas
- Si `config.dev.json` no está en la raíz o Azure falla, se devuelve `502`.
- En desarrollo se permite `AUTH_PASSWORD_HASH=plain:...` para simplificar.
