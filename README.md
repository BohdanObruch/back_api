# Back Service

This folder contains a standalone backend for the root test project.

## What it implements

- `POST /api/user/create`
- `GET /api/user/id/{id}`
- `GET /api/user/name/{name}`
- `PUT /api/user/update/{id}`
- `DELETE /api/user/delete/{id}`

The API accepts the same payload keys used by the root project:

```json
{
  "Name": "John",
  "Surname": "Doe",
  "DateOfBirth": "01.01.2000",
  "Interests": ["football", "gaming"]
}
```

## Run locally

```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

## Deploy to Render

Option 1:
Push only the contents of `back/` into a separate repository and create a Render Web Service from that repository.

Option 2:
Push the whole repository and let Render use `back/render.yaml`.

Render settings if you configure manually:

- Runtime: `Python`
- Root Directory: `back`
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app:app --host 0.0.0.0 --port $PORT`

After deploy, copy the Render URL into the root project's `.env` as `APP_URL`.
