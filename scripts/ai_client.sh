#!/bin/bash
# AI Client for Thesis Platform - Bash Version
# Pure bash/curl implementation for maximum portability

set -e

# Configuration
BASE_URL="${THESIS_PLATFORM_URL:-http://localhost:5000}"
TOKEN="${THESIS_PLATFORM_TOKEN:-}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
print_error() { echo -e "${RED}❌ Error: $1${NC}" >&2; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }

# Show usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS] COMMAND

AI Client for Thesis Platform - Interact with the platform API

Options:
    --base-url URL    Base URL of the platform (default: http://localhost:5000)
    --token TOKEN     API authentication token
    -h, --help        Show this help message

Commands:
    get-token         Login and generate an API token
    list-models       List all available AI models
    list-apps         List all generated applications
    stats             Get dashboard statistics
    health            Check system health
    verify            Verify token is valid
    generate          Generate a new application
    interactive       Start interactive mode

Environment Variables:
    THESIS_PLATFORM_URL     Base URL (alternative to --base-url)
    THESIS_PLATFORM_TOKEN   API token (alternative to --token)

Examples:
    # Get a token
    $0 get-token --username admin --password admin123

    # Export token for convenience
    export THESIS_PLATFORM_TOKEN="your-token-here"

    # List models
    $0 list-models

    # Get statistics
    $0 stats

    # Generate application
    $0 generate --model openai_gpt-4 --template 1 --name my-app

    # Interactive mode
    $0 interactive
EOF
    exit 0
}

# Make API request
api_request() {
    local endpoint="$1"
    local method="${2:-GET}"
    local data="${3:-}"
    local require_auth="${4:-true}"
    
    local url="${BASE_URL}${endpoint}"
    local headers=(-H "Content-Type: application/json")
    
    if [ "$require_auth" = "true" ]; then
        if [ -z "$TOKEN" ]; then
            print_error "Authentication required but no token provided"
            print_info "Use: export THESIS_PLATFORM_TOKEN='your-token' or --token flag"
            exit 1
        fi
        headers+=(-H "Authorization: Bearer $TOKEN")
    fi
    
    if [ -n "$data" ]; then
        curl -s -X "$method" "${headers[@]}" -d "$data" "$url"
    else
        curl -s -X "$method" "${headers[@]}" "$url"
    fi
}

# Get token by logging in
cmd_get_token() {
    local username=""
    local password=""
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --username) username="$2"; shift 2 ;;
            --password) password="$2"; shift 2 ;;
            *) print_error "Unknown option: $1"; exit 1 ;;
        esac
    done
    
    if [ -z "$username" ] || [ -z "$password" ]; then
        print_error "Username and password required"
        echo "Usage: $0 get-token --username USER --password PASS"
        exit 1
    fi
    
    print_info "Logging in as $username..."
    
    # Login to get session cookie
    local cookie_jar=$(mktemp)
    curl -s -c "$cookie_jar" -X POST \
        -d "username=$username&password=$password" \
        "${BASE_URL}/auth/login" > /dev/null
    
    # Generate token using session
    local response=$(curl -s -b "$cookie_jar" -X POST \
        "${BASE_URL}/api/tokens/generate")
    
    rm -f "$cookie_jar"
    
    local token=$(echo "$response" | grep -o '"token":"[^"]*"' | cut -d'"' -f4)
    
    if [ -z "$token" ]; then
        print_error "Failed to generate token"
        echo "$response"
        exit 1
    fi
    
    print_success "Token generated successfully!"
    echo ""
    echo "🔑 Your API Token:"
    echo "$token"
    echo ""
    echo "💡 Save this token! Use it with:"
    echo "   export THESIS_PLATFORM_TOKEN='$token'"
    echo "   $0 list-models"
}

# List models
cmd_list_models() {
    print_info "Fetching available models..."
    local response=$(api_request "/api/models" "GET" "" "true")
    local count=$(echo "$response" | grep -o '"models":\[' | wc -l)
    print_success "Found models"
    echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
}

# List applications
cmd_list_apps() {
    print_info "Fetching generated applications..."
    local response=$(api_request "/api/applications" "GET" "" "true")
    print_success "Applications retrieved"
    echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
}

# Get statistics
cmd_stats() {
    print_info "Fetching dashboard statistics..."
    local response=$(api_request "/api/dashboard/stats" "GET" "" "true")
    print_success "Statistics retrieved"
    echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
}

# Health check
cmd_health() {
    print_info "Checking system health..."
    local response=$(api_request "/api/health" "GET" "" "false")
    print_success "Health check complete"
    echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
}

# Verify token
cmd_verify() {
    print_info "Verifying token..."
    local response=$(api_request "/api/tokens/verify" "GET" "" "true")
    
    if echo "$response" | grep -q '"valid":true'; then
        print_success "Token is valid!"
    else
        print_error "Token is invalid!"
    fi
    
    echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
}

# Generate application
cmd_generate() {
    local model=""
    local template=""
    local name=""
    local description=""
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --model) model="$2"; shift 2 ;;
            --template) template="$2"; shift 2 ;;
            --name) name="$2"; shift 2 ;;
            --description) description="$2"; shift 2 ;;
            *) print_error "Unknown option: $1"; exit 1 ;;
        esac
    done
    
    if [ -z "$model" ] || [ -z "$template" ] || [ -z "$name" ]; then
        print_error "Model, template, and name are required"
        echo "Usage: $0 generate --model MODEL --template ID --name NAME"
        exit 1
    fi
    
    local data="{\"model\":\"$model\",\"template_id\":$template,\"app_name\":\"$name\""
    if [ -n "$description" ]; then
        data="${data},\"description\":\"$description\""
    fi
    data="${data}}"
    
    print_info "Generating application '$name' with $model..."
    local response=$(api_request "/api/gen/generate" "POST" "$data" "true")
    print_success "Generation request submitted!"
    echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
}

# Interactive mode
cmd_interactive() {
    clear
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║   Thesis Platform - Interactive AI Client                 ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    
    if [ -z "$TOKEN" ]; then
        print_warning "No token provided. Limited functionality available."
        echo "   Use: export THESIS_PLATFORM_TOKEN='your-token'"
        echo ""
    fi
    
    while true; do
        echo ""
        echo "Available Commands:"
        echo "  1. List Models"
        echo "  2. List Applications"
        echo "  3. Get Statistics"
        echo "  4. Health Check"
        echo "  5. Verify Token"
        echo "  q. Quit"
        echo ""
        read -p "Enter command: " choice
        echo ""
        
        case $choice in
            1) cmd_list_models ;;
            2) cmd_list_apps ;;
            3) cmd_stats ;;
            4) cmd_health ;;
            5) cmd_verify ;;
            q|Q) print_success "Goodbye!"; exit 0 ;;
            *) print_error "Invalid choice. Try again." ;;
        esac
    done
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --base-url)
            BASE_URL="$2"
            shift 2
            ;;
        --token)
            TOKEN="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        get-token)
            shift
            cmd_get_token "$@"
            exit 0
            ;;
        list-models)
            cmd_list_models
            exit 0
            ;;
        list-apps)
            cmd_list_apps
            exit 0
            ;;
        stats)
            cmd_stats
            exit 0
            ;;
        health)
            cmd_health
            exit 0
            ;;
        verify)
            cmd_verify
            exit 0
            ;;
        generate)
            shift
            cmd_generate "$@"
            exit 0
            ;;
        interactive)
            cmd_interactive
            exit 0
            ;;
        *)
            print_error "Unknown command: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# If no command specified, show usage
usage
