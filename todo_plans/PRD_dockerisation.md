# Product Requirements Document

## Dockerisation of LLM Evaluation and Business Risk Platform

**Version**: 1.0.0  
**Date**: 2026-06-14  
**Status**: Planned

---

## 1. Objective

Define and implement a production-like, repeatable container workflow for this repository, while preserving current behavior:
- file-based artifacts under `outputs/`
- MLflow tracking on SQLite (`sqlite:///mlflow.db`)
- optional FastAPI runtime
- CLI-based evaluation and business-evaluation jobs

This effort intentionally avoids backend migration to Postgres at this time.

---

## 2. Scope

### 2.1 In Scope

- Add a reusable base image for all runtime modes.
- Add Docker Compose orchestration for:
  - API runtime
  - evaluation job
  - business-evaluation job
  - MLflow UI
- Persist runtime state across runs:
  - `outputs/`
  - `mlruns/`
  - `mlflow.db`
- Add Docker usage documentation with commands and troubleshooting.

### 2.2 Out of Scope

- MLflow backend migration to Postgres.
- Kubernetes manifests.
- CI/CD pipeline changes.
- Reverse proxy/TLS setup.

---

## 3. Current State Summary

- Runtime entrypoints:
  - `run_evaluation.py`
  - `run_business_evaluation.py`
  - `run_business_api.py`
- Dependencies:
  - `requirements.txt` (core)
  - `requirements-api.txt` (optional API)
- Env keys expected from `.env`:
  - `OPENAI_API_KEY`
  - `GEMINI_API_KEY`
- MLflow default tracking URI: `sqlite:///mlflow.db`
- Relative paths are widely used in config and code, so container CWD must remain project root.

---

## 4. Functional Requirements

### FR-1: Container Image

- Provide `Dockerfile` based on Python 3.12 slim.
- Install both dependency sets to support all runtime modes from one image.
- Use `/app` as `WORKDIR`.
- Run as non-root user.

### FR-2: Compose Services

- Provide `docker-compose.yml` services:
  - `api`: serves FastAPI app on port 8000.
  - `eval`: one-off evaluation job with config path override.
  - `business-eval`: one-off business evaluation job with experiment dir override.
  - `mlflow`: MLflow UI on port 5000 using SQLite backend.

### FR-3: Persistence

- Persist and share across services:
  - `./outputs:/app/outputs`
  - `./mlruns:/app/mlruns`
  - `./mlflow.db:/app/mlflow.db`

### FR-4: Environment Injection

- Load provider keys and optional overrides via `.env`.
- Support existing `LIE_*` runtime environment overrides.

### FR-5: Build Context Hygiene

- Provide `.dockerignore` excluding generated and local-only directories/files to reduce build time and context size.

### FR-6: Documentation

- Update `Readme.md` with:
  - build/start commands
  - run-job commands
  - expected outputs and where to find them
  - troubleshooting section

---

## 5. Non-Functional Requirements

- Reproducible: same commands work for any developer on Linux/macOS with Docker.
- Minimal intrusion: no change to core evaluation or business logic.
- Clear separation of always-on services (API, MLflow UI) vs job services (eval, business-eval).
- Secure-by-default guidance: do not bake secrets into images.

---

## 6. Implementation Plan

### Phase 1: Foundation

1. Create `Dockerfile` with unified runtime dependencies.
2. Create `.dockerignore` with build-context exclusions.

### Phase 2: Orchestration

3. Create `docker-compose.yml` with `api`, `eval`, `business-eval`, `mlflow` services.
4. Add profiles for job services to prevent accidental auto-start.

### Phase 3: Documentation

5. Add a dedicated Docker section in `Readme.md`.
6. Document one canonical run order:
   1. Build image
   2. Start API and MLflow
   3. Run evaluation job
   4. Run business-evaluation job

### Phase 4: Verification

7. Validate compose config.
8. Start API container and verify `/ui` and `/business/experiments` endpoints.
9. Run evaluation and business-evaluation jobs and verify artifacts.
10. Start MLflow UI and verify visibility of experiments.

---

## 7. Acceptance Criteria

- `docker compose build` succeeds.
- `docker compose up -d api mlflow` succeeds and both services are reachable.
- `docker compose run --rm eval` writes experiment artifacts under `outputs/experiments/`.
- `docker compose run --rm business-eval` writes business artifacts for a chosen experiment.
- MLflow UI reads from the same persisted SQLite database and artifact root.
- README Docker instructions are sufficient for a first-time user.

---

## 8. Risks and Mitigations

- Risk: Relative path assumptions break in container.
  - Mitigation: enforce `WORKDIR /app` and project-root layout in image.

- Risk: Permissions on bind-mounted host directories.
  - Mitigation: document common ownership fix commands.

- Risk: Missing provider keys in `.env`.
  - Mitigation: document `.env-template` copy step and expected vars.

- Risk: Confusion between job and service containers.
  - Mitigation: use Compose profiles and explicit command examples.

---

## 9. Future Improvement Note

If the project later requires concurrent read/write access, multi-user load, or stronger durability guarantees, migrate MLflow backend from SQLite to Postgres. This is intentionally deferred for the current scope.
