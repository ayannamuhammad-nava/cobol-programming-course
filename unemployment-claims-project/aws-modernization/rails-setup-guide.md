# Rails Sandbox Setup Guide - From Zero to Running

## Phase 1: Install Docker (Prerequisites)

| Step | Command | What it does |
|---|---|---|
| 1 | `brew install docker` | Installs the Docker CLI - the tool that lets you talk to containers |

**What is Docker?** Think of it like a lightweight virtual machine. Instead of installing Ruby, PostgreSQL, Node, etc. directly on your Mac, Docker runs them in isolated containers. Everyone on the team gets the exact same setup.

---

## Phase 2: Install Docker's Supporting Tools

| Step | Command | What it does |
|---|---|---|
| 2 | `brew install docker-compose` | Installs the Compose plugin - lets you define and run multiple containers together (Rails app + database) from one file |
| 3 | Updated `~/.docker/config.json` | Told Docker where to find the Compose plugin on your Mac |
| 4 | `brew install colima` | Installs Colima - the engine that actually runs containers on macOS (Docker CLI is just the remote control, Colima is the TV) |
| 5 | `colima start` | Starts the Docker engine in the background so containers can actually run |

**Why so many pieces?** Docker has 3 parts:
- **CLI** (`docker`) - you type commands
- **Compose** (`docker compose`) - manages multi-container apps
- **Runtime** (Colima) - actually runs the containers

---

## Phase 3: Configure the Rails App

| Step | Command | What it does |
|---|---|---|
| 6 | `make .env` | Copies `local.env.example` to `.env` - this file holds all the app's configuration (database password, auth settings, etc.) |

**What is `.env`?** It's like a settings file. Instead of hardcoding passwords and config into the app code, they live here. Each developer can have their own settings.

---

## Phase 4: Build & Initialize

| Step | Command | What it does |
|---|---|---|
| 7 | `make init-container` | Does everything below in one command: |
| | `docker compose build` | Reads the `Dockerfile`, downloads Ruby 3.4.5, installs gems and Node packages, builds the app image |
| | `db:create` | Creates the PostgreSQL database inside the database container |
| | `db:migrate` | Runs all migration files to create the tables the app needs |
| | `db:test:prepare` | Sets up a separate database for running tests |
| | `db:seed` | Loads any starter data the app needs |

**What is a Dockerfile?** A recipe that says "start with Ruby, add these files, install these packages." Docker follows the recipe to build an image - a snapshot of your app ready to run.

**What is docker-compose.yml?** Defines the containers your app needs. This app has two:
- `ayannasandbox` - the Rails app (port 3100)
- `ayannasandbox-database` - PostgreSQL (port 5432)

---

## Phase 5: Run It

| Step | Command | What it does |
|---|---|---|
| 8 | `make start-container` | Starts both containers - Rails app + database |
| 9 | Visit http://localhost:3100 | See the app in your browser |

---

## Quick Reference - The Full Picture

```bash
brew install docker          # CLI (the remote control)
brew install docker-compose  # Compose plugin (multi-container orchestration)
brew install colima          # Runtime (the engine)
colima start                 # Turn on the engine
make .env                    # Configure the app
make init-container          # Build image + setup database
make start-container         # Launch the app
```

---

## Next Steps After Setup

Once the Rails app is running, the next phase is integrating the unemployment claims system into it:

1. **Database Layer** (Steps 1-4) - Create migrations for claims tables
2. **Models** (Steps 5-9) - Define business logic and validations
3. **Controllers** (Steps 10-12) - Handle HTTP requests and CRUD operations
4. **Views** (Steps 13-19) - Build UI screens with USWDS styling
5. **Wiring** (Steps 20-22) - Routes, navigation, and seed data

See the main [README.md](./README.md) for details on the unemployment claims system architecture.
