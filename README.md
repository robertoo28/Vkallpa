# V-Kallpa (Backend + Frontend)

Esta guía te permite ejecutar **backend** y **frontend** desde una sola consola (dos procesos).

## Requisitos
- Python 3.11+
- Node.js 18+ (en tu máquina hay `v24.10.0`)
- Acceso a Azure Blob Storage configurado en `config.dev.json`

## 1) Backend (FastAPI)

### Configuración
Crea `backend/.env` (puedes copiar `backend/.env.example`):

```env
AUTH_USERNAME=admin
AUTH_PASSWORD_HASH=plain:admin
JWT_SECRET=tu_secreto
JWT_EXPIRE_MINUTES=60
```

### Instalación
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r backend/requirements.txt
```

### Ejecutar
```powershell
uvicorn backend.app.main:app --reload
```

Backend disponible en: `http://127.0.0.1:8000`

## 2) Frontend (React + Vite)

### Instalación
```powershell
cd frontend
npm install
```

### Ejecutar
```powershell
npm run dev
```

Frontend disponible en: `http://127.0.0.1:5173`

> Si quieres apuntar a otra URL del backend:
> 
> ```powershell
> $env:VITE_API_BASE="http://127.0.0.1:8000/api/v1"
> npm run dev
> ```

## Ejecutar ambos usando una consola

En PowerShell puedes abrir dos pestañas dentro de la **misma consola**:

1. **Pestaña 1 (backend):**
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload
```

2. **Pestaña 2 (frontend):**
```powershell
cd frontend
npm install
npm run dev
```

Si necesitas hacerlo con un solo proceso en la misma pestaña, puedes usar `Start-Process`:
```powershell
Start-Process powershell "-NoExit", "-Command", "uvicorn backend.app.main:app --reload"
Start-Process powershell "-NoExit", "-Command", "cd frontend; npm run dev"
```

## Acceso
- Frontend: `http://127.0.0.1:5173`
- Backend: `http://127.0.0.1:8000`

## Login
Por defecto:
- Usuario: `admin`
- Password: `admin`
