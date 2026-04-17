# Key Concepts Guide: Docker, Colima, and Rails

A reference guide explaining the core technologies used in this project and how they relate to each other and to the original COBOL mainframe system.

---

## Docker

**Docker is a tool that packages an application and everything it needs to run into a single container.**

### The Problem Docker Solves

Without Docker, to run the Rails app you'd need to install on your Mac:
- Ruby 3.4.5 (exact version)
- PostgreSQL 14
- Node.js
- All the gem dependencies
- All the npm packages

And if any version is slightly different from what another developer has, things break. "It works on my machine" is the classic problem.

### What Docker Does

Docker puts the app + all its dependencies inside a **container** — an isolated box that has everything pre-configured. Every developer runs the same container, so it works the same everywhere.

```
Without Docker:                    With Docker:
Your Mac                           Your Mac
├── Ruby 3.4.5 (maybe wrong)      └── Docker
├── PostgreSQL (maybe wrong)           ├── Container 1: Rails app
├── Node.js (maybe wrong)             │   ├── Ruby 3.4.5 (exact)
└── 100 other things                   │   ├── Node.js (exact)
    that could conflict                │   └── All gems/packages
                                       └── Container 2: PostgreSQL 14
                                           └── Database + data
```

### Key Docker Concepts

| Concept | What it is | Our example |
|---|---|---|
| **Image** | A snapshot/recipe of an app ready to run | Built by `Dockerfile` during `init-container` |
| **Container** | A running instance of an image | The Rails app and PostgreSQL running on your machine |
| **Dockerfile** | The recipe that builds the image | "Start with Ruby 3.4.5, add these files, install these packages" |
| **docker-compose.yml** | Defines multiple containers that work together | "Run a Rails container and a PostgreSQL container, connect them" |
| **Volume** | Persistent storage that survives container restarts | Your database data doesn't disappear when you stop the container |

### Docker Commands We Used

| Command | What Docker did |
|---|---|
| `make init-container` | Built the image from `Dockerfile`, created 2 containers (Rails + PostgreSQL), set up the database |
| `make start-container` | Started both containers so the app runs at localhost:3100 |
| `docker compose ps` | Shows which containers are running |
| `docker compose run --rm ayannasandbox bin/rails ...` | Runs a one-off command inside the Rails container (like generating migrations) |

### Docker vs Virtual Machine

A virtual machine runs an entire operating system. Docker shares your Mac's operating system and just isolates the app — so it's much faster and lighter.

| | Virtual Machine | Docker Container |
|---|---|---|
| Size | Gigabytes | Megabytes |
| Startup | Minutes | Seconds |
| Resources | Heavy | Lightweight |
| Isolation | Full OS | App-level |

---

## Colima

**Colima is the Docker engine for macOS.**

### Why You Need It

Docker has two parts:

| Part | What it is | Analogy |
|---|---|---|
| **Docker CLI** (`docker`) | The commands you type | The steering wheel |
| **Docker Engine** (Colima) | The thing that actually runs containers | The car engine |

Without Colima, you can type `docker` commands but nothing happens — there's no engine to execute them. That's why we got the error `dial unix /var/run/docker.sock: connect: no such file or directory` before we installed it.

### Why Colima and Not Docker Desktop?

Docker Desktop is the official app from Docker Inc. — it includes both the CLI and the engine in one package, but it:
- Requires a paid license for larger companies
- Uses more memory and CPU
- Has a full GUI you may not need

Colima is a **free, lightweight alternative** that just runs the engine in the background. It's popular with developers who installed Docker via Homebrew.

### The Only Commands You Need for Colima

| Command | What it does |
|---|---|
| `colima start` | Start the engine |
| `colima stop` | Stop the engine |
| `colima status` | Check if it's running |

### When to Use Colima

- **Restarted your Mac?** Run `colima start` before using Docker
- **Docker commands failing?** Check `colima status` to see if the engine is running
- **Done for the day?** Optionally run `colima stop` to free up resources

---

## Rails (Ruby on Rails)

**Rails is a framework for building web applications using the Ruby programming language.**

### What That Means

A **framework** gives you a pre-built structure so you don't start from scratch. Instead of writing code to handle URLs, talk to databases, render HTML, and manage forms yourself, Rails provides all of that out of the box.

### The Problem Rails Solves

Without a framework, to build a web app you'd write everything yourself:
- How to listen for browser requests
- How to connect to a database
- How to generate HTML pages
- How to handle form submissions
- How to manage user sessions
- How to prevent security attacks

Rails gives you all of this on day one.

### How Rails Is Organized (MVC Pattern)

Rails follows a pattern called **Model-View-Controller**. Every feature you build has 3 parts:

```
User clicks a link in the browser
        |
        v
    CONTROLLER  (app/controllers/)
    "What did the user ask for?"
        |
        v
      MODEL     (app/models/)
    "Get/save data from the database, enforce rules"
        |
        v
       VIEW     (app/views/)
    "Build the HTML page and send it back to the browser"
```

### How That Maps To What We Built

| Rails piece | File we created | What it does |
|---|---|---|
| **Model** | `claims_period.rb` | Talks to the `claims_periods` database table, enforces business rules (R09, R15, R16) |
| **Controller** | `claims_controller.rb` | Handles requests like "show me all claims" or "create a new claim" |
| **View** | `claims/index.html.erb` | The HTML page you see in the browser |
| **Migration** | `create_claims_periods.rb` | Creates the database table |
| **Route** | `config/routes.rb` | Maps URLs to controller actions |

### Rails Conventions ("Convention Over Configuration")

Rails has strong opinions about how things should be named. If you follow the conventions, everything connects automatically:

| Convention | Example |
|---|---|
| Model is singular | `ClaimsPeriod` |
| Table is plural | `claims_periods` |
| Controller is plural | `ClaimsController` |
| View folder matches controller | `app/views/claims/` |
| URL matches controller | `/claims` |
| File name matches class | `claims_period.rb` → `ClaimsPeriod` |

You don't configure any of these connections — Rails figures it out from the names.

### Key Rails Concepts

| Concept | What it is | How we used it |
|---|---|---|
| **Migration** | A Ruby script that changes the database structure | Created 4 migrations to add claims tables |
| **Model** | A Ruby class that represents a database table + business rules | `ClaimsPeriod` model validates period_key format (R16) |
| **Controller** | A Ruby class that handles HTTP requests | `ClaimsController` handles create, read, update, delete |
| **View** | An HTML template with embedded Ruby (`.html.erb`) | 7 USWDS-styled screens for claims |
| **Route** | Maps a URL to a controller action | `resources :claims` creates 7 routes from one line |
| **Partial** | A reusable chunk of HTML (filename starts with `_`) | `_form.html.erb` shared between new and edit pages |
| **Seed** | Initial data loaded into the database | 42 demographic categories + January 2017 claims |
| **Scope** | A reusable database query shortcut | `ClaimsPeriod.current` returns only active records |
| **Validation** | A rule that blocks invalid data from being saved | R17: count must be non-negative |
| **Callback** | Code that runs automatically before/after an action | `set_period_date` auto-converts "01012017" to a date |

### Why The Sandbox App Uses Rails

The sandbox app is a government project. Rails is popular in government because:
- **Fast to build** — conventions mean less code to write
- **USWDS integration** — the U.S. Web Design System works well with Rails
- **Security built in** — protects against common attacks (XSS, SQL injection, CSRF) by default
- **Large community** — easy to find developers and get support

---

## How Everything Connects

```
You type a URL in the browser
        |
        v
    COLIMA (Docker engine - must be running)
        |
        v
    DOCKER CONTAINER 1: Rails App
        |
        ├── ROUTES: /claims → ClaimsController#index
        |
        ├── CONTROLLER: Gets data from the model
        |
        ├── MODEL: Queries PostgreSQL, enforces business rules
        |       |
        |       v
        |   DOCKER CONTAINER 2: PostgreSQL Database
        |       (claims_periods, demographic_categories, etc.)
        |
        ├── VIEW: Renders HTML with USWDS styling
        |
        v
    HTML page sent back to your browser
```

---

## Technology Comparison

### Rails vs The Python Lambda Version

| | Python Lambdas | Rails |
|---|---|---|
| Structure | Each operation is a separate function in a separate folder | All operations grouped in one controller |
| Database | Raw SQL queries | Models handle it automatically |
| UI | None (API only) | Built-in HTML views with templates |
| Routing | API Gateway configuration | One line: `resources :claims` creates 7 routes |
| Validation | Manual if/else checks | Declare rules, Rails enforces them |
| Running | Deploy to AWS | `make start-container` on your laptop |

### Rails vs COBOL

| | COBOL | Rails |
|---|---|---|
| Language | COBOL (1959) | Ruby (1995) |
| Data storage | VSAM flat files | PostgreSQL relational database |
| User interface | Batch terminal commands | Web browser |
| Business rules | IF/ELSE blocks scattered across programs | Model validations in one file |
| Adding a feature | Rewrite and recompile | Generate files, write code, refresh browser |
| Audit trail | Not possible | Built in |

---

## Quick Reference: Common Commands

### Starting the App
```bash
colima start              # Start the Docker engine (after Mac restart)
make start-container      # Launch the Rails app + database
# Visit http://localhost:3100
```

### Stopping the App
```bash
# Ctrl+C in the terminal running start-container, or:
docker compose down       # Stop the containers
colima stop               # Stop the Docker engine (optional)
```

### Checking Status
```bash
colima status             # Is the Docker engine running?
docker compose ps         # Are the containers running?
```

### Running Rails Commands Inside Docker
```bash
docker compose run --rm ayannasandbox bin/rails db:migrate     # Run migrations
docker compose run --rm ayannasandbox bin/rails db:seed        # Load seed data
docker compose run --rm ayannasandbox bin/rails console        # Open Rails console
docker compose run --rm ayannasandbox bin/rails routes         # List all routes
```
