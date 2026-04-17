# How To Integrate Your Application Into Rails

This guide lets anyone take an existing application (COBOL, Python, Java, etc.) and integrate it into a Rails sandbox app — the same process used to convert the unemployment claims system.

---

## Prerequisites

Before you start, you need:

1. **A Mac with Homebrew installed** — https://brew.sh
2. **Claude Code installed** — the CLI tool you're reading this in
3. **Nava Platform CLI installed** — to create the Rails sandbox
4. **Your source application** — the app you want to convert, somewhere on your machine

### If you haven't created a sandbox yet:

```bash
# Install UV (Python package manager for Nava CLI)
# Install Nava Platform CLI
uv tool install git+https://github.com/navapbc/platform-cli

# Create your sandbox
nava-platform app install --template-uri https://github.com/navapbc/template-application-rails . yoursandboxname
```

---

## Step 1: Run the Setup Script

Open Claude Code and run:

```bash
! bash /path/to/setup-rails-project.sh
```

The script will prompt you for:

| Prompt | What to enter | Example |
|---|---|---|
| **Sandbox name** | The name of your Rails sandbox | `mysandbox` |
| **Sandbox path** | Full path to your sandbox folder | `/Users/yourname/mysandbox` |
| **Source app path** | Full path to the app you want to convert | `/Users/yourname/my-legacy-app` |
| **App name** | A short name for your application | `inventory-system` |
| **Description** | What your app does | `Tracks warehouse inventory and shipments` |
| **Port** | Port number for the app (default 3100) | `3200` |

### What the script does automatically:

| Step | What happens |
|---|---|
| 1 | Collects your project information |
| 2 | Checks/installs Docker CLI, Docker Compose, and Colima |
| 3 | Starts the Docker engine (Colima) |
| 4 | Creates the .env configuration file |
| 5 | Updates docker-compose.yml with your chosen port |
| 6 | Builds the Docker image and initializes the database (`make init-container`) |
| 6 | Saves a config file (`.claude-rails-setup.json`) for Claude Code to use |
| 7 | Scans your source application and lists all files |

After the script finishes, your Rails sandbox is built and ready for integration.

---

## Step 2: Tell Claude Code to Integrate Your App

In Claude Code, type:

```
Read the config at /path/to/yoursandbox/.claude-rails-setup.json
and the source files list at /path/to/yoursandbox/.claude-source-files.txt
then integrate my app into Rails.
```

Claude will:

1. **Read your source application** — understand the data structures, business logic, and rules
2. **Create database migrations** — tables for your data
3. **Create models** — with validations matching your business rules
4. **Create controllers** — CRUD operations (create, read, update, delete)
5. **Create views** — USWDS-styled UI screens (forms, tables, detail pages)
6. **Add routes** — wire URLs to controllers
7. **Add navigation** — link in the app header
8. **Create seed data** — load initial data from your source app

---

## Step 3: Launch the App

Once Claude is done building, run:

```bash
cd /path/to/yoursandbox
make start-container
```

Then visit **http://localhost:YOUR_PORT** in your browser (the port you chose during setup, default 3100).

- Sign up with any email and password (mock auth mode)
- Your app's features will appear in the navigation bar

---

## Step 4: Restart the App Later

If you close everything and come back later:

```bash
colima start                    # Start the Docker engine
cd /path/to/yoursandbox         # Go to your sandbox
make start-container            # Launch the app
```

Then visit http://localhost:YOUR_PORT (check your `.claude-rails-setup.json` for the port you chose).

---

## What You'll Get

| What | Description |
|---|---|
| **Index page** | Table listing all records with status |
| **Detail page** | Full view of a single record with all fields |
| **New form** | Form to create a new record |
| **Edit form** | Form to update an existing record |
| **Delete** | Soft delete with confirmation |
| **Audit trail** | Log of every create, update, delete operation |
| **Report page** | Summary statistics dashboard |

All styled with the U.S. Web Design System (USWDS).

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `docker: command not found` | Run `brew install docker` |
| `docker compose: unknown command` | Run `brew install docker-compose` |
| `dial unix /var/run/docker.sock: connect: no such file or directory` | Run `colima start` |
| `make: *** [init-container] Error` | Make sure Colima is running: `colima status` |
| Your port already in use | Stop the other container: `docker compose down` in the other project, or re-run setup with a different port |
| Port 5432 already in use | Stop existing PostgreSQL: `brew services stop postgresql` |
| Can't sign in | The app uses mock auth — sign up first with any email/password |
| Changes not showing | Restart with `make start-container` |

---

## File Reference

After setup, these files are created in your sandbox:

```
yoursandbox/
├── .claude-rails-setup.json        # Config file Claude reads
├── .claude-source-files.txt        # List of your source app files
├── .env                            # App configuration
├── db/migrate/                     # Database table definitions
│   └── *_create_*.rb              # One migration per table
├── app/models/                     # Business logic and validations
│   └── *.rb                       # One model per table
├── app/controllers/                # Request handling (CRUD)
│   └── *_controller.rb            # One controller per feature
├── app/policies/                   # Authorization rules
│   └── *_policy.rb                # One policy per model
├── app/views/                      # UI screens
│   └── feature_name/
│       ├── index.html.erb         # List page
│       ├── show.html.erb          # Detail page
│       ├── new.html.erb           # New form
│       ├── edit.html.erb          # Edit form
│       └── _form.html.erb         # Shared form partial
├── config/routes.rb                # URL routing (modified)
└── db/seeds/development.rb         # Initial data
```

---

## How It Works (Behind the Scenes)

```
1. You run the setup script
   └── Installs Docker, builds Rails, creates database

2. You tell Claude Code to integrate
   └── Claude reads your source app
   └── Claude creates Rails files (migrations, models, controllers, views)
   └── Claude runs migrations and seeds

3. You launch the app
   └── make start-container
   └── Visit http://localhost:YOUR_PORT
```

The setup script handles infrastructure. Claude Code handles the application logic. You get a working web app.
