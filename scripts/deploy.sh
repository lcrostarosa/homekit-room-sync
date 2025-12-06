#!/bin/bash

#
# deploy.sh - Deploy homekit-room-sync to a Home Assistant server via SSH
#
# Usage:
#   ./scripts/deploy.sh [HOST]
#   ./scripts/deploy.sh 192.168.1.100
#   ./scripts/deploy.sh homeassistant.local
#
# Environment variables (can be set in .env file):
#   HA_HOST          - IP address or hostname of Home Assistant server
#   HA_USER          - SSH user (default: root)
#   HA_CONFIG_PATH   - Path to HA config directory (default: /config)
#   HA_SSH_PORT      - SSH port (default: 22)
#   HA_RESTART       - Restart Home Assistant after deploy (default: false)
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load .env file if it exists
ENV_FILE="$PROJECT_ROOT/.env"
if [[ -f "$ENV_FILE" ]]; then
    echo -e "${BLUE}Loading environment from .env file${NC}"
    set -a
    source "$ENV_FILE"
    set +a
fi

# Configuration with defaults
HOST="${1:-${HA_HOST:-}}"
USER="${HA_USER:-root}"
CONFIG_PATH="${HA_CONFIG_PATH:-/config}"
SSH_PORT="${HA_SSH_PORT:-22}"
RESTART="${HA_RESTART:-false}"
CONTAINER_NAME="${HA_CONTAINER_NAME:-homeassistant}"
# Shell used on the remote host to run commands; override if the default shell is non-POSIX (e.g., nushell)
REMOTE_SHELL="${REMOTE_SHELL:-/bin/bash}"

# Source path
SOURCE_DIR="$PROJECT_ROOT/custom_components/homekit_room_sync"
CONFIG_PATH_CLEAN="" # populated after argument parsing
DEST_PATH=""         # populated after argument parsing

recalculate_paths() {
    CONFIG_PATH_CLEAN="${CONFIG_PATH%/}"
    if [[ -z "$CONFIG_PATH_CLEAN" ]]; then
        CONFIG_PATH_CLEAN="/"
    fi
    DEST_PATH="$CONFIG_PATH_CLEAN/custom_components/homekit_room_sync"
}

# Functions
print_header() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  HomeKit Room Sync - Deployment Script${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

print_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS] [HOST]

Deploy homekit-room-sync to a Home Assistant server via SSH.

Arguments:
  HOST                IP address or hostname (overrides HA_HOST env var)

Options:
  -h, --help          Show this help message
  -u, --user USER     SSH user (default: root)
  -p, --port PORT     SSH port (default: 22)
  -c, --config PATH   HA config directory (default: /config)
  -r, --restart       Restart Home Assistant after deployment
  -s, --remote-shell  Remote shell to use (default: /bin/sh)
  --dry-run           Show what would be done without executing

Environment variables:
  HA_HOST             Default host if not provided as argument
  HA_USER             SSH user (default: root)
  HA_CONFIG_PATH      HA config directory (default: /config)
  HA_SSH_PORT         SSH port (default: 22)
  HA_RESTART          Set to 'true' to restart HA after deploy

Examples:
  $(basename "$0") 192.168.1.100
  $(basename "$0") homeassistant.local --restart
  $(basename "$0") -u homeassistant -p 2222 ha.local
  HA_HOST=192.168.1.100 $(basename "$0")

EOF
}

error() {
    echo -e "${RED}✗ Error: $1${NC}" >&2
    exit 1
}

warn() {
    echo -e "${YELLOW}⚠ Warning: $1${NC}"
}

success() {
    echo -e "${GREEN}✓ $1${NC}"
}

info() {
    echo -e "${BLUE}→ $1${NC}"
}

# Run a command on the remote host while safely passing arguments (works even if
# the login shell is non-POSIX such as nushell).
run_remote() {
    local template="$1"
    shift
    
    # Construct the remote script with arguments injected using set --
    # This avoids passing positional arguments through the remote login shell.
    local script=""
    if [ $# -gt 0 ]; then
        script="set --"
        for arg in "$@"; do
            script="$script $(printf %q "$arg")"
        done
        script="$script;"
    fi
    script="${script}${template}"

    # Encode script to base64 to avoid parsing issues by the remote login shell (e.g. nushell)
    local encoded
    encoded=$(echo "$script" | base64 | tr -d '\n')

    # Execute on remote by decoding and piping to shell
    ssh $SSH_OPTS -- "$SSH_TARGET" "echo '$encoded' | base64 -d | $REMOTE_SHELL -l"
}

# Parse command line arguments
DRY_RUN=false
POSITIONAL_ARGS=()

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            print_usage
            exit 0
            ;;
        -u|--user)
            USER="$2"
            shift 2
            ;;
        -p|--port)
            SSH_PORT="$2"
            shift 2
            ;;
        -c|--config)
            CONFIG_PATH="$2"
            shift 2
            ;;
        -r|--restart)
            RESTART=true
            shift
            ;;
        -s|--remote-shell)
            REMOTE_SHELL="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -*)
            error "Unknown option: $1"
            ;;
        *)
            POSITIONAL_ARGS+=("$1")
            shift
            ;;
    esac
done

# Set HOST from positional argument if provided
if [[ ${#POSITIONAL_ARGS[@]} -gt 0 ]]; then
    HOST="${POSITIONAL_ARGS[0]}"
fi

# Main deployment logic
main() {
    # Ensure paths are normalized before use
    recalculate_paths

    if [[ -z "$CONFIG_PATH_CLEAN" ]]; then
        error "Resolved config path is empty after normalization."
    fi

    print_header

    # Validate host
    if [[ -z "$HOST" ]]; then
        echo -e "${RED}✗ No host specified!${NC}\n"
        echo "Please provide a host via:"
        echo "  1. Command line argument: ./scripts/deploy.sh 192.168.1.100"
        echo "  2. Environment variable: export HA_HOST=192.168.1.100"
        echo "  3. .env file with HA_HOST=192.168.1.100"
        echo ""
        echo "Run './scripts/deploy.sh --help' for more options."
        exit 1
    fi

    # Validate source directory exists
    if [[ ! -d "$SOURCE_DIR" ]]; then
        error "Source directory not found: $SOURCE_DIR"
    fi

    # Get version from manifest.json
    VERSION=$(jq -r '.version' "$SOURCE_DIR/manifest.json" 2>/dev/null || echo "unknown")

    # Display configuration
    echo "Configuration:"
    echo "  Host:        $HOST"
    echo "  User:        $USER"
    echo "  Port:        $SSH_PORT"
    echo "  Config path: $CONFIG_PATH_CLEAN"
    echo "  Remote shell: $REMOTE_SHELL"
    echo "  Version:     $VERSION"
    echo "  Restart HA:  $RESTART"
    if $DRY_RUN; then
        echo -e "  ${YELLOW}Mode: DRY RUN${NC}"
    fi
    echo ""

    SSH_OPTS="-o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -p $SSH_PORT"
    SSH_TARGET="$USER@$HOST"

    # Test SSH connection
    info "Testing SSH connection..."
    if $DRY_RUN; then
        echo "  Would run: ssh $SSH_OPTS $SSH_TARGET 'echo ok'"
    else
        if ! ssh $SSH_OPTS "$SSH_TARGET" "$REMOTE_SHELL" -lc 'echo ok' > /dev/null 2>&1; then
            error "Cannot connect to $SSH_TARGET on port $SSH_PORT. Check your SSH configuration."
        fi
        success "SSH connection successful"
    fi

    # Create custom_components directory if needed
    info "Ensuring custom_components directory exists..."
    TARGET_CC="$CONFIG_PATH_CLEAN/custom_components"
    if $DRY_RUN; then
        echo "  Would run: ssh $SSH_OPTS $SSH_TARGET \"$REMOTE_SHELL\" -lc 'mkdir -p -- \"\$1\"' _ \"$TARGET_CC\""
    else
        run_remote 'mkdir -p -- "$1"' "$TARGET_CC"
        success "Directory ready"
    fi

    # Backup existing installation if present
    # info "Checking for existing installation..."
    # if $DRY_RUN; then
    #     echo "  Would check for and backup existing installation"
    # else
    #     if run_remote 'test -d "$1"' "$DEST_PATH" 2>/dev/null; then
    #         # BACKUP_NAME="homekit_room_sync.backup.$(date +%Y%m%d_%H%M%S)"
    #         # warn "Existing installation found, backing up to $BACKUP_NAME"
    #         # run_remote 'sudo cp -r "$1" "$2"' "$DEST_PATH" "$CONFIG_PATH_CLEAN/custom_components/$BACKUP_NAME"
    #         # success "Backup created"
    #         info "Existing installation found, overwriting..."
    #     else
    #         success "No existing installation (fresh install)"
    #     fi
    # fi

    # Deploy using rsync
    info "Deploying homekit_room_sync..."
    if $DRY_RUN; then
        echo "  Would run: rsync -avz --delete --rsync-path=\"sudo rsync\" -e 'ssh -p $SSH_PORT' $SOURCE_DIR/ $SSH_TARGET:$DEST_PATH/"
    else
        rsync -avz --delete \
            --exclude '__pycache__' \
            --exclude '*.pyc' \
            --exclude '.DS_Store' \
            --rsync-path="sudo rsync" \
            -e "ssh -p $SSH_PORT" \
            "$SOURCE_DIR/" \
            "$SSH_TARGET:$DEST_PATH/"
        success "Deployment complete"
    fi

    # Restart Home Assistant if requested
    if [[ "$RESTART" == "true" ]]; then
        info "Restarting Home Assistant..."
        if $DRY_RUN; then
            echo "  Would run: ssh $SSH_OPTS $SSH_TARGET \"$REMOTE_SHELL\" -lc '<restart commands>'"
        else
            # Try different restart methods (HAOS, Docker, systemd)
            if run_remote "command -v ha >/dev/null 2>&1" 2>/dev/null; then
                run_remote "ha core restart"
            elif run_remote "docker ps | grep -q $CONTAINER_NAME" 2>/dev/null; then
                run_remote "docker restart $CONTAINER_NAME"
            elif run_remote "systemctl is-active home-assistant >/dev/null 2>&1" 2>/dev/null; then
                run_remote "systemctl restart home-assistant"
            else
                warn "Could not detect Home Assistant installation type. Please restart manually."
            fi
            success "Restart command sent"
        fi
    else
        echo ""
        echo -e "${YELLOW}Note: Remember to restart Home Assistant to load the changes.${NC}"
    fi

    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  Deployment successful! (v$VERSION)${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

main


