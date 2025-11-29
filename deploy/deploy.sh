#!/bin/bash
#
# ThesisApp Production Deployment Script
# Target: Ubuntu Server 24.04 LTS
# Server: ns3086089.ip-145-239-65.eu (145.239.65.130)
#
# Usage:
#   ./deploy.sh              # Full deployment
#   ./deploy.sh --update     # Update existing deployment
#   ./deploy.sh --restart    # Restart services
#   ./deploy.sh --logs       # View logs
#   ./deploy.sh --status     # Check status
#

set -euo pipefail

# ============================================================================
# CONFIGURATION
# ============================================================================

# Application settings
APP_NAME="thesisapp"
APP_USER="thesisapp"
APP_DIR="/opt/thesisapp"
REPO_URL="https://github.com/GrabowMar/ThesisAppRework.git"

# Ports
FLASK_PORT=5000
NGINX_HTTP_PORT=80
NGINX_HTTPS_PORT=443

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

log_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# ============================================================================
# SYSTEM PREREQUISITES
# ============================================================================

install_prerequisites() {
    log_info "Installing system prerequisites..."
    
    # Update system
    apt-get update && apt-get upgrade -y
    
    # Install required packages
    apt-get install -y \
        curl \
        git \
        wget \
        unzip \
        htop \
        net-tools \
        ufw \
        fail2ban \
        nginx \
        certbot \
        python3-certbot-nginx \
        ca-certificates \
        gnupg \
        lsb-release
    
    log_success "Prerequisites installed"
}

install_docker() {
    log_info "Installing Docker..."
    
    # Check if Docker is already installed
    if command -v docker &> /dev/null; then
        log_info "Docker already installed: $(docker --version)"
        return 0
    fi
    
    # Add Docker's official GPG key
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    
    # Add Docker repository
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
        $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
        tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Install Docker
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    # Start and enable Docker
    systemctl start docker
    systemctl enable docker
    
    log_success "Docker installed: $(docker --version)"
}

# ============================================================================
# APPLICATION USER SETUP
# ============================================================================

setup_app_user() {
    log_info "Setting up application user..."
    
    # Create user if doesn't exist
    if ! id "$APP_USER" &>/dev/null; then
        useradd -m -s /bin/bash "$APP_USER"
        log_info "Created user: $APP_USER"
    fi
    
    # Add user to docker group
    usermod -aG docker "$APP_USER"
    
    # Create application directory
    mkdir -p "$APP_DIR"
    chown -R "$APP_USER:$APP_USER" "$APP_DIR"
    
    log_success "User setup complete"
}

# ============================================================================
# FIREWALL CONFIGURATION
# ============================================================================

configure_firewall() {
    log_info "Configuring firewall..."
    
    # Enable UFW
    ufw --force enable
    
    # Allow SSH
    ufw allow 22/tcp
    
    # Allow HTTP and HTTPS
    ufw allow 80/tcp
    ufw allow 443/tcp
    
    # Allow Flask port (only from localhost/nginx)
    # ufw allow from 127.0.0.1 to any port $FLASK_PORT
    
    # Reload UFW
    ufw reload
    
    log_success "Firewall configured"
}

# ============================================================================
# APPLICATION DEPLOYMENT
# ============================================================================

clone_repository() {
    log_info "Cloning repository..."
    
    if [[ -d "$APP_DIR/.git" ]]; then
        log_info "Repository exists, pulling latest changes..."
        cd "$APP_DIR"
        sudo -u "$APP_USER" git fetch origin
        sudo -u "$APP_USER" git reset --hard origin/main
    else
        log_info "Cloning fresh repository..."
        rm -rf "$APP_DIR"/*
        sudo -u "$APP_USER" git clone "$REPO_URL" "$APP_DIR"
    fi
    
    cd "$APP_DIR"
    log_success "Repository ready"
}

create_env_file() {
    log_info "Creating environment file..."
    
    ENV_FILE="$APP_DIR/.env"
    
    if [[ ! -f "$ENV_FILE" ]]; then
        # Generate secure secret key
        SECRET_KEY=$(openssl rand -hex 32)
        
        cat > "$ENV_FILE" << EOF
# ThesisApp Production Environment
# Generated on $(date)

# Flask Configuration
FLASK_ENV=production
SECRET_KEY=${SECRET_KEY}
HOST=0.0.0.0
PORT=5000

# Database
DATABASE_URL=sqlite:////app/src/data/thesis_app.db

# Logging
LOG_LEVEL=INFO

# OpenRouter API (for AI analyzer - add your key)
OPENROUTER_API_KEY=
OPENROUTER_ALLOW_ALL_PROVIDERS=true

# Security
REGISTRATION_ENABLED=false
SESSION_COOKIE_SECURE=true
SESSION_LIFETIME=86400

# Docker BuildKit
DOCKER_BUILDKIT=1
COMPOSE_DOCKER_CLI_BUILD=1
EOF

        chown "$APP_USER:$APP_USER" "$ENV_FILE"
        chmod 600 "$ENV_FILE"
        
        log_warning "Environment file created at $ENV_FILE"
        log_warning "Please add your OPENROUTER_API_KEY if you want AI analysis features"
    else
        log_info "Environment file already exists"
    fi
}

build_and_start() {
    log_info "Building and starting Docker containers..."
    
    cd "$APP_DIR"
    
    # Stop existing containers
    sudo -u "$APP_USER" docker compose down 2>/dev/null || true
    
    # Build containers
    sudo -u "$APP_USER" docker compose build --parallel
    
    # Start containers
    sudo -u "$APP_USER" docker compose up -d
    
    log_success "Docker containers started"
}

# ============================================================================
# NGINX CONFIGURATION
# ============================================================================

configure_nginx() {
    log_info "Configuring Nginx reverse proxy..."
    
    # Create Nginx configuration
    cat > /etc/nginx/sites-available/thesisapp << 'EOF'
# ThesisApp Nginx Configuration
# Reverse proxy for Flask application

upstream thesisapp {
    server 127.0.0.1:5000;
    keepalive 32;
}

server {
    listen 80;
    listen [::]:80;
    server_name _;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Logging
    access_log /var/log/nginx/thesisapp_access.log;
    error_log /var/log/nginx/thesisapp_error.log;

    # Max upload size
    client_max_body_size 50M;

    # Proxy settings
    location / {
        proxy_pass http://thesisapp;
        proxy_http_version 1.1;
        
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 300s;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://thesisapp/health;
        proxy_http_version 1.1;
        access_log off;
    }

    # Static files (if any)
    location /static {
        proxy_pass http://thesisapp/static;
        proxy_http_version 1.1;
        proxy_cache_valid 200 1d;
        expires 1d;
        add_header Cache-Control "public, immutable";
    }
}
EOF

    # Enable site
    ln -sf /etc/nginx/sites-available/thesisapp /etc/nginx/sites-enabled/
    
    # Remove default site
    rm -f /etc/nginx/sites-enabled/default
    
    # Test configuration
    nginx -t
    
    # Reload Nginx
    systemctl reload nginx
    
    log_success "Nginx configured"
}

# ============================================================================
# SSL CERTIFICATE (Optional)
# ============================================================================

setup_ssl() {
    local domain="$1"
    
    log_info "Setting up SSL certificate for $domain..."
    
    # Update Nginx config with domain
    sed -i "s/server_name _;/server_name $domain;/" /etc/nginx/sites-available/thesisapp
    nginx -t && systemctl reload nginx
    
    # Get certificate
    certbot --nginx -d "$domain" --non-interactive --agree-tos --email admin@$domain
    
    # Setup auto-renewal
    systemctl enable certbot.timer
    systemctl start certbot.timer
    
    log_success "SSL certificate installed"
}

# ============================================================================
# SYSTEMD SERVICE
# ============================================================================

create_systemd_service() {
    log_info "Creating systemd service..."
    
    cat > /etc/systemd/system/thesisapp.service << EOF
[Unit]
Description=ThesisApp Docker Compose Application
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
User=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd
    systemctl daemon-reload
    
    # Enable service
    systemctl enable thesisapp.service
    
    log_success "Systemd service created"
}

# ============================================================================
# MONITORING & LOGS
# ============================================================================

show_status() {
    log_info "Service Status:"
    echo ""
    
    # Docker containers
    echo -e "${CYAN}Docker Containers:${NC}"
    cd "$APP_DIR" && docker compose ps
    echo ""
    
    # Nginx
    echo -e "${CYAN}Nginx Status:${NC}"
    systemctl status nginx --no-pager | head -5
    echo ""
    
    # Firewall
    echo -e "${CYAN}Firewall Status:${NC}"
    ufw status verbose | head -10
}

show_logs() {
    log_info "Showing logs (Ctrl+C to exit)..."
    cd "$APP_DIR" && docker compose logs -f --tail=100
}

# ============================================================================
# UPDATE FUNCTIONS
# ============================================================================

update_deployment() {
    log_info "Updating deployment..."
    
    cd "$APP_DIR"
    
    # Pull latest code
    sudo -u "$APP_USER" git fetch origin
    sudo -u "$APP_USER" git reset --hard origin/main
    
    # Rebuild and restart
    sudo -u "$APP_USER" docker compose down
    sudo -u "$APP_USER" docker compose build --parallel
    sudo -u "$APP_USER" docker compose up -d
    
    log_success "Update complete"
}

restart_services() {
    log_info "Restarting services..."
    
    cd "$APP_DIR"
    sudo -u "$APP_USER" docker compose restart
    systemctl restart nginx
    
    log_success "Services restarted"
}

# ============================================================================
# FULL DEPLOYMENT
# ============================================================================

full_deployment() {
    log_info "Starting full deployment..."
    echo ""
    
    check_root
    install_prerequisites
    install_docker
    setup_app_user
    configure_firewall
    clone_repository
    create_env_file
    build_and_start
    configure_nginx
    create_systemd_service
    
    echo ""
    log_success "============================================"
    log_success "   ThesisApp Deployment Complete!          "
    log_success "============================================"
    echo ""
    echo -e "Access your application at:"
    echo -e "  ${GREEN}http://$(hostname -I | awk '{print $1}')${NC}"
    echo -e "  ${GREEN}http://$(hostname)${NC}"
    echo ""
    echo -e "Useful commands:"
    echo -e "  ${CYAN}./deploy.sh --status${NC}   - Check service status"
    echo -e "  ${CYAN}./deploy.sh --logs${NC}     - View application logs"
    echo -e "  ${CYAN}./deploy.sh --update${NC}   - Update to latest version"
    echo -e "  ${CYAN}./deploy.sh --restart${NC}  - Restart all services"
    echo ""
    echo -e "${YELLOW}Note: Add your OPENROUTER_API_KEY to $APP_DIR/.env for AI features${NC}"
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    case "${1:-}" in
        --update|-u)
            check_root
            update_deployment
            ;;
        --restart|-r)
            check_root
            restart_services
            ;;
        --logs|-l)
            show_logs
            ;;
        --status|-s)
            show_status
            ;;
        --ssl)
            check_root
            if [[ -z "${2:-}" ]]; then
                log_error "Usage: $0 --ssl <domain>"
                exit 1
            fi
            setup_ssl "$2"
            ;;
        --help|-h)
            echo "ThesisApp Deployment Script"
            echo ""
            echo "Usage: $0 [option]"
            echo ""
            echo "Options:"
            echo "  (none)          Full deployment"
            echo "  --update, -u    Update existing deployment"
            echo "  --restart, -r   Restart all services"
            echo "  --logs, -l      View application logs"
            echo "  --status, -s    Check service status"
            echo "  --ssl <domain>  Setup SSL certificate"
            echo "  --help, -h      Show this help"
            ;;
        *)
            full_deployment
            ;;
    esac
}

main "$@"
