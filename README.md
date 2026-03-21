# face_tracker

[![CI](https://github.com/SErothompson/face_tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/SErothompson/face_tracker/actions) [![Codecov](https://codecov.io/gh/SErothompson/face_tracker/branch/master/graph/badge.svg)](https://codecov.io/gh/SErothompson/face_tracker)

Face Tracker — a Flask-based Python application for facial tracking and analysis.

## Overview

- Lightweight web app for uploading images and running face landmarking/analysis.
- Includes API endpoints, tests, Docker support, and migrations.

## Prerequisites

- Python 3.8+ recommended
- git
- (Optional) Docker & docker-compose for containerized runs

## Setup (local)

1. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install Python dependencies:

```bash
pip install -r requirements.txt
```

3. Set environment variables (example):

```bash
cp .env.example .env
# Edit .env and set SECRET_KEY, DATABASE_URL, etc.
```

4. Initialize the database (Alembic migrations):

```bash
flask db upgrade
```

5. Run the app locally:

```bash
flask run --port 5000
```

Or run via the entrypoint:

```bash
python main.py
```

## Docker

Build and run with docker-compose:

```bash
docker-compose build
docker-compose up
```

### Docker quickstart

Build the image and run a container (example):

```bash
# build image locally
docker build -t face-tracker:latest .

# run with an env file and port mapping
docker run --rm -p 5000:5000 --env-file .env -v "$PWD/uploads":/app/uploads face-tracker:latest
```

Using `docker-compose` (recommended for development):

```bash
docker-compose up --build
```

Note: ensure you copy `.env.example` to `.env` and set required variables before running containers.

## Tests

Run the test suite with `pytest`:

```bash
pytest
```

## Project Structure (high level)

- `app/` — Flask app package (blueprints, models, utils)
- `migrations/` — Alembic migration scripts
- `models/` — ML models and tasks
- `tests/` — Unit and integration tests
- `uploads/` — example uploaded files (not committed in general)

## Notes

- Uploads live in the `uploads/` directory in development. Remove or rotate large files before publishing.
- Use `.env` to store secrets; do not check it into git.

## Contributing

Please open issues or PRs. Run tests and follow existing code style.

## License

See the repository license (if present) or add one before public distribution.

---
If you want, I can also add a project badge, CI instructions, or a short quickstart snippet for Docker deployment.
