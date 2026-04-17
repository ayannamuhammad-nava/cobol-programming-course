#!/bin/bash
#############################################################################
# Rails Project Setup Script
#
# This script sets up a Rails sandbox environment and collects information
# about your source application so Claude Code can integrate it into Rails.
#
# Usage: Run this script in Claude Code by typing:
#   ! bash /path/to/setup-rails-project.sh
#
# It will prompt you for information, set up Docker and Rails, and create
# a config file that Claude Code uses to build your integration.
#############################################################################

set -e

echo ""
echo "============================================================"
echo "  RAILS PROJECT SETUP"
echo "  This script will set up your Rails sandbox and prepare"
echo "  your application for integration into Rails."
echo "============================================================"
echo ""

# -------------------------------------------------------------------
# Step 1: Collect Information
# -------------------------------------------------------------------
echo "--- STEP 1: Tell me about your project ---"
echo ""

read -p "What is your sandbox name? (e.g., mysandbox): " SANDBOX_NAME
if [ -z "$SANDBOX_NAME" ]; then
  echo "Error: Sandbox name is required."
  exit 1
fi

read -p "Where is your sandbox located? (full path, e.g., /Users/yourname/$SANDBOX_NAME): " SANDBOX_PATH
if [ -z "$SANDBOX_PATH" ]; then
  echo "Error: Sandbox path is required."
  exit 1
fi

if [ ! -d "$SANDBOX_PATH" ]; then
  echo "Error: Sandbox directory not found at $SANDBOX_PATH"
  echo "Make sure you've created the sandbox first with:"
  echo "  nava-platform app install --template-uri https://github.com/navapbc/template-application-rails . $SANDBOX_NAME"
  exit 1
fi

read -p "Where is your source application located? (full path to the app you want to convert): " SOURCE_APP_PATH
if [ -z "$SOURCE_APP_PATH" ]; then
  echo "Error: Source application path is required."
  exit 1
fi

if [ ! -d "$SOURCE_APP_PATH" ]; then
  echo "Error: Source application not found at $SOURCE_APP_PATH"
  exit 1
fi

read -p "What is your application name? (e.g., unemployment-claims, inventory-system): " APP_NAME
if [ -z "$APP_NAME" ]; then
  echo "Error: Application name is required."
  exit 1
fi

read -p "Brief description of what your app does: " APP_DESCRIPTION

read -p "What port do you want the app to run on? (default: 3100): " APP_PORT
APP_PORT=${APP_PORT:-3100}

echo ""
echo "--- Your settings ---"
echo "  Sandbox name:     $SANDBOX_NAME"
echo "  Sandbox path:     $SANDBOX_PATH"
echo "  Source app path:   $SOURCE_APP_PATH"
echo "  App name:          $APP_NAME"
echo "  Description:       $APP_DESCRIPTION"
echo "  Port:              $APP_PORT"
echo ""
read -p "Is this correct? (y/n): " CONFIRM
if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
  echo "Setup cancelled. Run the script again."
  exit 0
fi

# -------------------------------------------------------------------
# Step 2: Check and Install Docker
# -------------------------------------------------------------------
echo ""
echo "--- STEP 2: Checking Docker installation ---"
echo ""

# Check for Docker CLI
if command -v docker &> /dev/null; then
  echo "  Docker CLI: installed ($(docker --version 2>/dev/null | head -1))"
else
  echo "  Docker CLI: not found. Installing..."
  brew install docker
  echo "  Docker CLI: installed"
fi

# Check for Docker Compose
if docker compose version &> /dev/null 2>&1; then
  echo "  Docker Compose: installed ($(docker compose version 2>/dev/null))"
else
  echo "  Docker Compose: not found. Installing..."
  brew install docker-compose

  # Configure plugin path
  mkdir -p ~/.docker
  if [ -f ~/.docker/config.json ]; then
    # Add cliPluginsExtraDirs if not already present
    if ! grep -q "cliPluginsExtraDirs" ~/.docker/config.json; then
      # Use python/node to merge JSON, or create fresh if simple
      TEMP_CONFIG=$(cat ~/.docker/config.json)
      echo "$TEMP_CONFIG" | python3 -c "
import json, sys
config = json.load(sys.stdin)
config['cliPluginsExtraDirs'] = ['/opt/homebrew/lib/docker/cli-plugins']
print(json.dumps(config, indent=2))
" > ~/.docker/config.json
    fi
  else
    echo '{
  "cliPluginsExtraDirs": [
    "/opt/homebrew/lib/docker/cli-plugins"
  ]
}' > ~/.docker/config.json
  fi
  echo "  Docker Compose: installed and configured"
fi

# Check for Colima
if command -v colima &> /dev/null; then
  echo "  Colima: installed"
else
  echo "  Colima: not found. Installing..."
  brew install colima
  echo "  Colima: installed"
fi

# -------------------------------------------------------------------
# Step 3: Start Colima (Docker Engine)
# -------------------------------------------------------------------
echo ""
echo "--- STEP 3: Starting Docker engine (Colima) ---"
echo ""

if colima status &> /dev/null 2>&1; then
  echo "  Colima is already running."
else
  echo "  Starting Colima..."
  colima start
  echo "  Colima started."
fi

# -------------------------------------------------------------------
# Step 4: Set up the Rails sandbox
# -------------------------------------------------------------------
echo ""
echo "--- STEP 4: Setting up Rails sandbox ---"
echo ""

cd "$SANDBOX_PATH"

# Create .env if it doesn't exist
if [ -f ".env" ]; then
  echo "  .env file: already exists"
else
  if [ -f "Makefile" ] && grep -q "\.env" Makefile; then
    echo "  Creating .env file..."
    make .env
    echo "  .env file: created"
  elif [ -f "local.env.example" ]; then
    cp local.env.example .env
    echo "  .env file: created from local.env.example"
  else
    echo "  Warning: No .env template found. You may need to create one manually."
  fi
fi

# -------------------------------------------------------------------
# Step 5: Build and initialize containers
# -------------------------------------------------------------------
echo ""
echo "--- STEP 5: Building and initializing containers ---"
echo "  This may take several minutes on first run..."
echo ""

# Update docker-compose port if user chose a different one
if [ "$APP_PORT" != "3100" ] && [ -f "docker-compose.yml" ]; then
  if grep -q "3100:3000" docker-compose.yml; then
    echo "  Updating docker-compose.yml port to $APP_PORT..."
    sed -i '' "s/3100:3000/$APP_PORT:3000/g" docker-compose.yml
  fi
fi

if [ -f "Makefile" ] && grep -q "init-container" Makefile; then
  make init-container
else
  echo "  Warning: No init-container target in Makefile."
  echo "  Trying docker compose build..."
  docker compose build
  docker compose run --rm "$SANDBOX_NAME" bin/rails db:create db:migrate db:seed 2>/dev/null || true
fi

# -------------------------------------------------------------------
# Step 6: Save configuration for Claude Code
# -------------------------------------------------------------------
echo ""
echo "--- STEP 6: Saving configuration for Claude Code ---"
echo ""

CONFIG_FILE="$SANDBOX_PATH/.claude-rails-setup.json"
cat > "$CONFIG_FILE" << CONFIGEOF
{
  "sandbox_name": "$SANDBOX_NAME",
  "sandbox_path": "$SANDBOX_PATH",
  "source_app_path": "$SOURCE_APP_PATH",
  "app_name": "$APP_NAME",
  "app_description": "$APP_DESCRIPTION",
  "app_port": "$APP_PORT",
  "app_url": "http://localhost:$APP_PORT",
  "setup_date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "status": "ready_for_integration"
}
CONFIGEOF

echo "  Configuration saved to: $CONFIG_FILE"

# -------------------------------------------------------------------
# Step 7: List source application files for Claude
# -------------------------------------------------------------------
echo ""
echo "--- STEP 7: Scanning source application ---"
echo ""

SOURCE_FILES_LIST="$SANDBOX_PATH/.claude-source-files.txt"
find "$SOURCE_APP_PATH" -type f \
  ! -path "*/.git/*" \
  ! -path "*/__pycache__/*" \
  ! -path "*/node_modules/*" \
  ! -path "*/.claude/*" \
  ! -name "*.pyc" \
  ! -name "*.db" \
  ! -name "*.db-shm" \
  ! -name "*.db-wal" \
  ! -name "*.png" \
  ! -name "*.jpg" \
  > "$SOURCE_FILES_LIST" 2>/dev/null

FILE_COUNT=$(wc -l < "$SOURCE_FILES_LIST" | tr -d ' ')
echo "  Found $FILE_COUNT source files."
echo "  File list saved to: $SOURCE_FILES_LIST"

# -------------------------------------------------------------------
# Done
# -------------------------------------------------------------------
echo ""
echo "============================================================"
echo "  SETUP COMPLETE!"
echo "============================================================"
echo ""
echo "  Your Rails sandbox is built and ready."
echo "  Docker containers are initialized."
echo ""
echo "  NEXT STEPS (in Claude Code):"
echo ""
echo "  Tell Claude:"
echo "    'Read the config at $CONFIG_FILE"
echo "     and the source files list at $SOURCE_FILES_LIST"
echo "     then integrate my app into Rails.'"
echo ""
echo "  Claude will:"
echo "    1. Read your source application files"
echo "    2. Understand the business logic"
echo "    3. Create Rails migrations, models, controllers, views"
echo "    4. Add routes and navigation"
echo "    5. Create seed data"
echo ""
echo "  When Claude is done, run:"
echo "    cd $SANDBOX_PATH"
echo "    make start-container"
echo ""
echo "  Then visit: http://localhost:$APP_PORT"
echo ""
echo "============================================================"
