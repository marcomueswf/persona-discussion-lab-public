# Persona Discussion Lab

Persona Discussion Lab is a local OpenUI5 application for running structured discussions between configurable LLM personas. The frontend communicates with a FastAPI backend. Discussion state, personas, configuration, templates, and results are stored as local JSON data.

## Requirements

- [Node.js](https://nodejs.org/) and [npm](https://www.npmjs.com/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- An OpenAI-compatible API key is optional for local development; without one, the backend uses mock responses.

`uv` creates and manages the Python environment used by the development command. A manual virtual environment is not required.

## Run Locally

From this directory:

```powershell
npm install
npm run dev
```

The command starts both processes:

- OpenUI5 development server: <http://127.0.0.1:8080>
- FastAPI backend: <http://127.0.0.1:8000>
- FastAPI API documentation: <http://127.0.0.1:8000/docs>

Use `127.0.0.1` rather than `localhost` if the browser resolves localhost to IPv6 on the local machine. Press `Ctrl+C` to stop both processes.

## Configure the LLM Provider

Open **Settings** in the application and enter the runtime values under **Runtime Environment**:

- `OPENAI_API_KEY`: API key; it is never returned by the environment endpoint.
- `OPENAI_BASE_URL`: optional base URL for an OpenAI-compatible provider. Leave it empty for the official OpenAI endpoint.
- `OPENAI_MODEL`: model identifier used when a discussion does not specify another model.

Values are stored in the per-user runtime directory, not in the repository:

- Windows: `%LOCALAPPDATA%\PersonaDiscussionLab\.env`
- Other platforms: `~/.local/share/PersonaDiscussionLab/.env`

The same directory contains runtime copies of the JSON data files. The bundled defaults in `backend/data/` are copied there on first use. Do not commit `.env` files or API keys.

## Main Workflows

1. Create or edit personas in the **Personas** view.
2. Select personas, a strategy, and discussion parameters in **Discussion**.
3. Start a discussion and monitor its status and turns.
4. Inspect the structured result, Delphi metrics, or optional trace after completion.
5. Save a completed setup as a reusable discussion template when needed.

Supported base strategies are exposed by the configuration endpoint. Configurable strategy specifications can extend these built-in strategies without changing the frontend.

---

## Developer Documentation

## HTTP API

All application routes are mounted below `/api`. The interactive schema is available at `/docs` while the backend is running.

| Area | Routes |
| --- | --- |
| Health | `GET /api/health` |
| Personas | `GET/POST /api/personas`, `PATCH/DELETE /api/personas/{personaId}` |
| Configuration | `GET/PATCH /api/configuration` |
| Runtime environment | `GET/PATCH /api/env` |
| Discussions | `GET/POST /api/discussions`, `GET/DELETE /api/discussions/{discussion_id}` |
| Discussion control | `POST /api/discussions/{discussion_id}/stop` |
| Results and traces | `GET /api/discussions/{discussion_id}/result`, `GET /api/discussions/{discussion_id}/trace`, `GET /api/results/{discussion_id}` |
| Templates | `GET /api/discussion-templates`, `GET/DELETE /api/discussion-templates/{template_id}`, `POST /api/discussions/{discussion_id}/template` |

Discussion creation returns `202 Accepted`. The discussion engine continues asynchronously and persists incremental state. A stop request is cooperative and does not terminate an already running model call.

## Tests

The backend tests are written for pytest and use temporary directories for persistence tests. Run them with the project dependencies plus pytest:

```powershell
uv run --with-requirements backend/requirements.txt --with pytest pytest backend/tests
```

## Build the Frontend

Create the UI5 build output with:

```powershell
npm run build
```

The generated `dist/` directory is a build artifact and is ignored by Git.

## Package a Standalone Release

`PersonaDiscussionLab.spec` defines the PyInstaller bundle. Install PyInstaller in the active Python environment, then run:

```powershell
pyinstaller PersonaDiscussionLab.spec
```

The release entry point selects a free local port, opens the browser, and serves the packaged frontend and backend together. Release output is written to `build/` and `dist/`. With the `--onedir` build shown below, start the executable at `dist/PersonaDiscussionLab/PersonaDiscussionLab.exe`. Keep the complete `dist/PersonaDiscussionLab/` folder together because it contains the executable's `_internal/` dependencies.

For the final Windows executable, run this command from the project root:

```powershell
python -m PyInstaller `
  --name PersonaDiscussionLab `
  --onedir `
  --windowed `
  --add-data "webapp;webapp" `
  --add-data "backend/data;backend/data" `
  --collect-all fastapi `
  --collect-all uvicorn `
  --collect-all langgraph `
  --collect-all openai `
  backend/release.py
```



## Project Structure

```text
backend/
  app.py                 FastAPI composition root and static frontend hosting
  *_api.py               Thin HTTP routers
  models.py              Pydantic request and response contracts
  services/              Application use cases and projections
  core/                  Discussion orchestration and LLM agent logic
  persistence/           JSON persistence implementations
  data/                  Bundled default configuration and seed data
  tests/                 Backend unit and service tests
webapp/
  Component.js           UI5 bootstrap and model setup
  controller/            UI event handling and API coordination
  model/                 UI state and API data models
  service/               Frontend API clients
  view/                  XML views
docu/figures/            PlantUML source files for architecture diagrams
PersonaDiscussionLab.spec PyInstaller packaging definition
```

## Architecture Documentation

The diagrams in `docu/figures/` describe the main boundaries and flows:

- `architecture.puml`: overall application architecture
- `frontend.puml`: OpenUI5 MVC and API interaction
- `backend-api.puml`: FastAPI routers and application services
- `discussion-engine.puml`: generic LangGraph discussion flow
- `discussion-engine-delphi.puml`: structured Delphi rating flow
- `datamodel.puml`: persisted domain model
- `persistence.puml`: persistence boundaries

The LaTeX sources in `docu/latex/` contain the longer project documentation and can be rebuilt with the existing LaTeX toolchain when required.

## Data and Debugging Notes

- The source files in `backend/data/` are defaults; active runtime data is stored in the user data directory.
- Deleting the runtime data directory resets local configuration, personas, templates, and discussion history to the bundled defaults.
- `traceEnabled` stores prompts and model responses for a discussion. Enable it only when needed because traces can contain sensitive input or output and increase storage size.
- The CORS configuration currently allows the local UI5 development server on ports 8080 only. Restrict it further before exposing the backend beyond the local machine.
