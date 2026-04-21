# Run and Stop the Website

This project currently runs best with:
- `backend` + `postgres` + `redis` via Docker Compose
- `frontend` via local Vite server

## 1) Open (start) the entire website

From the project root:

```bash
cd /Users/nguyenlong/Documents/Booking_Web_Project
docker compose up -d postgres redis backend
```

Then start frontend in a second terminal:

```bash
cd /Users/nguyenlong/Documents/Booking_Web_Project/frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

Open:
- Frontend: http://localhost:5173
- Backend docs: http://localhost:8000/docs

## 2) Close (stop) the entire website

### Stop frontend
If frontend is running in a terminal, press:

```bash
Ctrl + C
```

### Stop backend + database + redis
From project root:

```bash
cd /Users/nguyenlong/Documents/Booking_Web_Project
docker compose stop backend postgres redis
```

If you want to remove containers too (clean stop):

```bash
docker compose rm -f backend postgres redis
```

## 3) Quick checks

Check Docker services:

```bash
cd /Users/nguyenlong/Documents/Booking_Web_Project
docker compose ps
```

Check backend health in browser:
- http://localhost:8000/docs

Check frontend in browser:
- http://localhost:5173

## Notes

- If port `5173` or `8000` is busy, stop old processes first, then run again.
- If frontend dependencies were not installed yet:

```bash
cd /Users/nguyenlong/Documents/Booking_Web_Project/frontend
npm install
```
