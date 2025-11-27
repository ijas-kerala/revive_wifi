#!/bin/bash
#
# Revive Parental Control Router - One-Shot Installer
# For Raspberry Pi 4/5 running Raspberry Pi OS Lite (64-bit)
#
# This script installs and configures:
# - RaspAP (Access Point on wlan0, Port 80)
# - AdGuard Home (DNS filtering, Port 8080)
# - CasaOS (Container management, Port 81)
# - Revive Dashboard (Flask app, Port 8000)
#

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    log_error "Please run as root (use sudo)"
    exit 1
fi

# Check Architecture
ARCH=$(uname -m)
if [[ "$ARCH" != "aarch64" && "$ARCH" != "arm64" ]]; then
    log_error "This script is designed for Raspberry Pi 4/5 (64-bit ARM). Detected: $ARCH"
    log_warn "Proceeding might fail. Press Ctrl+C to abort or wait 5 seconds..."
    sleep 5
fi

log_info "Starting Revive installation..."

# ============================================================================
# PHASE 1: System Preparation
# ============================================================================
log_info "Phase 1: Updating system and installing dependencies..."

apt update -y
apt upgrade -y

# Install essential packages
apt install -y \
    python3-pip \
    python3-venv \
    git \
    curl \
    wget \
    dnsmasq \
    hostapd \
    dhcpcd5 \
    iptables \
    netfilter-persistent \
    iptables-persistent

# Install Python packages globally for the dashboard
pip3 install --break-system-packages flask requests gunicorn

log_info "System preparation complete."

# ============================================================================
# PHASE 2: Install RaspAP
# ============================================================================
log_info "Phase 2: Installing RaspAP..."

# RaspAP unattended installation
export DEBIAN_FRONTEND=noninteractive

# Download and run RaspAP installer with unattended options
curl -sL https://install.raspap.com | bash -s -- --yes --openvpn 0 --wireguard 0 --adblock 0

# Wait for RaspAP to complete installation
sleep 5

# Configure RaspAP hotspot settings
log_info "Configuring RaspAP hotspot..."

# Update hostapd configuration
cat > /etc/hostapd/hostapd.conf <<EOF
interface=wlan0
driver=nl80211
ssid=Revive_Secure_Home
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=securekids123
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
country_code=US
EOF

# Update dnsmasq configuration to point DNS to AdGuard Home
cat > /etc/dnsmasq.d/090_raspap.conf <<EOF
interface=wlan0
bind-dynamic
domain-needed
bogus-priv
dhcp-range=10.3.141.50,10.3.141.150,255.255.255.0,12h
dhcp-option=6,10.3.141.1
EOF

# Restart RaspAP services
systemctl restart hostapd
systemctl restart dnsmasq

log_info "RaspAP installation complete. Web UI available at http://<pi-ip>:80"
log_info "Default credentials: admin/secret"

# ============================================================================
# PHASE 3: Install AdGuard Home
# ============================================================================
log_info "Phase 3: Installing AdGuard Home..."

# Download and install AdGuard Home
cd /tmp
wget https://static.adguard.com/adguardhome/release/AdGuardHome_linux_arm64.tar.gz
tar -xvf AdGuardHome_linux_arm64.tar.gz
cd AdGuardHome
./AdGuardHome -s install

# Create AdGuard Home configuration directory
mkdir -p /opt/AdGuardHome

# Configure AdGuard Home to run on port 8080
cat > /opt/AdGuardHome/AdGuardHome.yaml <<EOF
bind_host: 0.0.0.0
bind_port: 8080
users:
  - name: admin
    password: \$2a\$10\$YJHlKjJKqZ9Z9Z9Z9Z9Z9.ZKjJKqZ9Z9Z9Z9Z9Z9ZKjJKqZ9Z9Z9Z
auth_attempts: 5
block_auth_min: 15
http_proxy: ""
language: ""
theme: auto
dns:
  bind_hosts:
    - 0.0.0.0
  port: 53
  anonymize_client_ip: false
  protection_enabled: true
  blocking_mode: default
  blocking_ipv4: ""
  blocking_ipv6: ""
  blocked_response_ttl: 10
  parental_block_host: family-block.dns.adguard.com
  safebrowsing_block_host: standard-block.dns.adguard.com
  ratelimit: 20
  ratelimit_whitelist: []
  refuse_any: true
  upstream_dns:
    - https://dns10.quad9.net/dns-query
    - https://dns.cloudflare.com/dns-query
  upstream_dns_file: ""
  bootstrap_dns:
    - 9.9.9.10
    - 149.112.112.10
    - 2620:fe::10
    - 2620:fe::fe:10
  all_servers: false
  fastest_addr: false
  allowed_clients: []
  disallowed_clients: []
  blocked_hosts:
    - version.bind
    - id.server
    - hostname.bind
  cache_size: 4194304
  cache_ttl_min: 0
  cache_ttl_max: 0
  cache_optimistic: false
  bogus_nxdomain: []
  aaaa_disabled: false
  enable_dnssec: false
  edns_client_subnet: false
  max_goroutines: 300
  ipset: []
  filtering_enabled: true
  filters_update_interval: 24
  parental_enabled: false
  safesearch_enabled: false
  safebrowsing_enabled: false
  safebrowsing_cache_size: 1048576
  safesearch_cache_size: 1048576
  parental_cache_size: 1048576
  cache_time: 30
  rewrites: []
  blocked_services: []
  local_domain_name: lan
  resolve_clients: true
  local_ptr_upstreams: []
tls:
  enabled: false
  server_name: ""
  force_https: false
  port_https: 443
  port_dns_over_tls: 853
  port_dns_over_quic: 784
  port_dnscrypt: 0
  dnscrypt_config_file: ""
  allow_unencrypted_doh: false
  strict_sni_check: false
  certificate_chain: ""
  private_key: ""
  certificate_path: ""
  private_key_path: ""
filters:
  - enabled: true
    url: https://adguardteam.github.io/AdGuardSDNSFilter/Filters/filter.txt
    name: AdGuard DNS filter
    id: 1
  - enabled: true
    url: https://adaway.org/hosts.txt
    name: AdAway Default Blocklist
    id: 2
whitelist_filters: []
user_rules: []
dhcp:
  enabled: false
  interface_name: ""
  dhcpv4:
    gateway_ip: ""
    subnet_mask: ""
    range_start: ""
    range_end: ""
    lease_duration: 86400
    icmp_timeout_msec: 1000
    options: []
  dhcpv6:
    range_start: ""
    lease_duration: 86400
    ra_slaac_only: false
    ra_allow_slaac: false
clients: []
log_compress: false
log_localtime: false
log_max_backups: 0
log_max_size: 100
log_max_age: 3
log_file: ""
verbose: false
schema_version: 14
EOF

# Set proper password hash for admin/revive123
# Using bcrypt hash for "revive123"
ADMIN_HASH='$2a$10$8K1p/a0dL3LKzOkR3.aYLOxvYxFYK5TgmjoelinEacXHZot8pK5S6'
sed -i "s|password: .*|password: $ADMIN_HASH|" /opt/AdGuardHome/AdGuardHome.yaml

# Start AdGuard Home
systemctl enable AdGuardHome
systemctl restart AdGuardHome

log_info "AdGuard Home installation complete. Web UI available at http://<pi-ip>:8080"
log_info "Credentials: admin/revive123"

# ============================================================================
# PHASE 4: Install CasaOS
# ============================================================================
log_info "Phase 4: Installing CasaOS..."

# Install CasaOS
# We use a trick to pre-configure port 81 to avoid conflicts with RaspAP
mkdir -p /etc/casaos
cat > /etc/casaos/gateway.ini <<EOF
[server]
port = 81
EOF

curl -fsSL https://get.casaos.io | bash

# Wait for CasaOS to initialize
sleep 10

# Ensure CasaOS port is 81
log_info "Ensuring CasaOS uses port 81..."

# Check and modify gateway.ini
if [ -f /etc/casaos/gateway.ini ]; then
    sed -i 's/port = 80/port = 81/g' /etc/casaos/gateway.ini
fi

# Check and modify casaos.conf
if [ -f /etc/casaos/casaos.conf ]; then
    sed -i 's/"port":80/"port":81/g' /etc/casaos/casaos.conf
    sed -i 's/"port": 80/"port": 81/g' /etc/casaos/casaos.conf
fi

# Also check for env file
if [ -f /etc/casaos/.env ]; then
    sed -i 's/CASA_PORT=80/CASA_PORT=81/g' /etc/casaos/.env
fi

# Restart CasaOS services
systemctl restart casaos-gateway.service 2>/dev/null || true
systemctl restart casaos.service 2>/dev/null || true
systemctl restart casaos-*.service 2>/dev/null || true

log_info "CasaOS installation complete. Web UI available at http://<pi-ip>:81"

# ============================================================================
# PHASE 5: Install Revive Dashboard
# ============================================================================
log_info "Phase 5: Setting up Revive Dashboard..."

# Create dashboard directory
mkdir -p /opt/revive
cd /opt/revive

# Copy dashboard files
if [ -f "dashboard.py" ]; then
    cp dashboard.py /opt/revive/
    chmod +x /opt/revive/dashboard.py
    log_info "Copied dashboard.py"
else
    # If script is run from a location where dashboard.py isn't present, try to find it or warn
    log_warn "dashboard.py not found in current directory. Please copy it to /opt/revive/ manually."
fi

# Install Service
if [ -f "revive-dashboard.service" ]; then
    cp revive-dashboard.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable revive-dashboard
    systemctl start revive-dashboard
    log_info "Revive Dashboard service installed and started."
else
    log_warn "revive-dashboard.service not found. Please install it manually."
fi

log_info "Dashboard directory created at /opt/revive"

# ============================================================================
# PHASE 6: Network Configuration
# ============================================================================
log_info "Phase 6: Configuring network routing..."

# Enable IP forwarding
echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
sysctl -p

# Configure iptables for NAT
iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
iptables -A FORWARD -i eth0 -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT
iptables -A FORWARD -i wlan0 -o eth0 -j ACCEPT

# Allow traffic to local services
iptables -A INPUT -i wlan0 -p tcp --dport 80 -j ACCEPT   # RaspAP
iptables -A INPUT -i wlan0 -p tcp --dport 81 -j ACCEPT   # CasaOS
iptables -A INPUT -i wlan0 -p tcp --dport 8080 -j ACCEPT # AdGuard Home
iptables -A INPUT -i wlan0 -p tcp --dport 8000 -j ACCEPT # Revive Dashboard
iptables -A INPUT -i wlan0 -p udp --dport 53 -j ACCEPT   # DNS (UDP)
iptables -A INPUT -i wlan0 -p tcp --dport 53 -j ACCEPT   # DNS (TCP)

# Save iptables rules
netfilter-persistent save

log_info "Network configuration complete."

# ============================================================================
# FINAL STEPS
# ============================================================================
log_info "Installation complete!"
echo ""
echo "=========================================="
echo "  Revive Parental Control Router"
echo "=========================================="
echo ""
echo "Services installed:"
echo "  - RaspAP:        http://<pi-ip>:80 (admin/secret)"
echo "  - AdGuard Home:  http://<pi-ip>:8080 (admin/revive123)"
echo "  - CasaOS:        http://<pi-ip>:81"
echo "  - Revive Dashboard: http://<pi-ip>:8000"
echo ""
echo "WiFi Hotspot:"
echo "  - SSID: Revive_Secure_Home"
echo "  - Password: securekids123"
echo ""
echo "A reboot is recommended to ensure all services start correctly."
echo "=========================================="
