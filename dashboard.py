#!/usr/bin/env python3
"""
Revive Parental Control Dashboard
A Flask-based web interface for managing parental controls via AdGuard Home
"""

from flask import Flask, render_template_string, jsonify, request
import requests
from requests.auth import HTTPBasicAuth
import json
import os
import subprocess
from datetime import datetime

app = Flask(__name__)

# Configuration
ADGUARD_URL = "http://127.0.0.1:8080"
ADGUARD_USER = "admin"
ADGUARD_PASS = "revive123"
DNSMASQ_LEASES = "/var/lib/misc/dnsmasq.leases"

# Service definitions for blocking
BLOCKED_SERVICES = {
    "social_media": ["youtube", "tiktok", "instagram", "facebook", "snapchat", "twitter"],
    "gaming": ["roblox", "fortnite", "minecraft", "twitch"],
    "adult_content": ["adult", "porn"],
    "all": []  # Special case for bedtime mode
}

def get_adguard_auth():
    """Return authentication object for AdGuard API"""
    return HTTPBasicAuth(ADGUARD_USER, ADGUARD_PASS)

def call_adguard_api(endpoint, method="GET", data=None):
    """Make API call to AdGuard Home"""
    url = f"{ADGUARD_URL}{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url, auth=get_adguard_auth(), timeout=5)
        elif method == "POST":
            response = requests.post(url, auth=get_adguard_auth(), json=data, timeout=5)
        elif method == "PUT":
            response = requests.put(url, auth=get_adguard_auth(), json=data, timeout=5)
        
        response.raise_for_status()
        return response.json() if response.text else {}
    except requests.exceptions.RequestException as e:
        print(f"AdGuard API Error: {e}")
        return None

def run_iptables(args):
    """Run iptables command"""
    try:
        subprocess.run(["iptables"] + args, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"iptables error: {e}")
        return False

def is_blocked_by_iptables(ip):
    """Check if IP is blocked by iptables"""
    try:
        # Check if rule exists
        result = subprocess.run(
            ["iptables", "-C", "FORWARD", "-s", ip, "-j", "DROP"],
            capture_output=True
        )
        return result.returncode == 0
    except Exception:
        return False

def get_dhcp_leases():
    """Parse DHCP leases file to get device information"""
    devices = {}
    try:
        if os.path.exists(DNSMASQ_LEASES):
            with open(DNSMASQ_LEASES, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 4:
                        # Format: timestamp mac ip hostname client-id
                        mac = parts[1]
                        ip = parts[2]
                        hostname = parts[3] if parts[3] != '*' else f"Device-{mac[-5:]}"
                        devices[ip] = {
                            "mac": mac,
                            "hostname": hostname,
                            "ip": ip
                        }
    except Exception as e:
        print(f"Error reading DHCP leases: {e}")
    
    return devices

def get_connected_clients():
    """Get list of connected clients from AdGuard Home"""
    # First get DHCP lease information
    dhcp_devices = get_dhcp_leases()
    
    # Get clients from AdGuard Home
    clients_data = call_adguard_api("/control/clients")
    
    if not clients_data:
        # Return DHCP devices if AdGuard API fails
        return [{"name": dev["hostname"], "ip": ip, "mac": dev["mac"], "blocked_services": [], "safesearch_enabled": False, "bedtime_enabled": False} 
                for ip, dev in dhcp_devices.items()]
    
    # Merge AdGuard clients with DHCP data
    adguard_clients = clients_data.get("clients", [])
    auto_clients = clients_data.get("auto_clients", [])
    
    all_clients = []
    
    # Process configured clients
    for client in adguard_clients:
        client_ids = client.get("ids", [])
        client_ip = client_ids[0] if client_ids else "Unknown"
        
        device_info = dhcp_devices.get(client_ip, {})
        
        all_clients.append({
            "name": client.get("name", device_info.get("hostname", "Unknown Device")),
            "ip": client_ip,
            "mac": device_info.get("mac", "Unknown"),
            "blocked_services": client.get("blocked_services", []),
            "safesearch_enabled": client.get("safesearch_enabled", False),
            "use_global_settings": client.get("use_global_settings", True),
            "filtering_enabled": client.get("filtering_enabled", True),
            "bedtime_enabled": is_blocked_by_iptables(client_ip)
        })
    
    # Process auto-detected clients
    for client in auto_clients:
        client_ip = client.get("ip", "Unknown")
        device_info = dhcp_devices.get(client_ip, {})
        
        # Skip if already in configured clients
        if any(c["ip"] == client_ip for c in all_clients):
            continue
        
        all_clients.append({
            "name": client.get("name", device_info.get("hostname", f"Device-{client_ip}")),
            "ip": client_ip,
            "mac": device_info.get("mac", client.get("mac", "Unknown")),
            "blocked_services": [],
            "safesearch_enabled": False,
            "use_global_settings": True,
            "filtering_enabled": True,
            "bedtime_enabled": is_blocked_by_iptables(client_ip)
        })
    
    # Add any DHCP devices not in AdGuard
    for ip, device in dhcp_devices.items():
        if not any(c["ip"] == ip for c in all_clients):
            all_clients.append({
                "name": device["hostname"],
                "ip": ip,
                "mac": device["mac"],
                "blocked_services": [],
                "safesearch_enabled": False,
                "use_global_settings": True,
                "filtering_enabled": True,
                "bedtime_enabled": is_blocked_by_iptables(ip)
            })
    
    return all_clients

def get_stats():
    """Get statistics from AdGuard Home"""
    stats = call_adguard_api("/control/stats")
    if stats:
        return {
            "ads_blocked_today": stats.get("num_blocked_filtering", 0),
            "dns_queries_today": stats.get("num_dns_queries", 0),
            "avg_processing_time": stats.get("avg_processing_time", 0)
        }
    return {
        "ads_blocked_today": 0,
        "dns_queries_today": 0,
        "avg_processing_time": 0
    }

def update_client_settings(client_ip, blocked_services=None, safesearch=None, bedtime_mode=None):
    """Update client settings in AdGuard Home"""
    
    # Handle Bedtime Mode via iptables
    if bedtime_mode is not None:
        if bedtime_mode:
            # Block internet access
            if not is_blocked_by_iptables(client_ip):
                run_iptables(["-I", "FORWARD", "-s", client_ip, "-j", "DROP"])
        else:
            # Restore internet access
            if is_blocked_by_iptables(client_ip):
                run_iptables(["-D", "FORWARD", "-s", client_ip, "-j", "DROP"])
    
    # First, try to find existing client
    clients_data = call_adguard_api("/control/clients")
    existing_client = None
    
    if clients_data:
        for client in clients_data.get("clients", []):
            if client_ip in client.get("ids", []):
                existing_client = client
                break
    
    # Prepare client data
    if existing_client:
        # Update existing client
        client_data = existing_client.copy()
        
        if blocked_services is not None:
            client_data["blocked_services"] = blocked_services
        
        if safesearch is not None:
            client_data["safesearch_enabled"] = safesearch
            
        # Ensure filtering is enabled (we don't want to disable it for bedtime anymore)
        client_data["filtering_enabled"] = True
        
        # Update the client
        result = call_adguard_api("/control/clients/update", method="POST", data={
            "name": client_data.get("name"),
            "data": client_data
        })
    else:
        # Create new client
        dhcp_devices = get_dhcp_leases()
        device_info = dhcp_devices.get(client_ip, {})
        
        client_data = {
            "name": device_info.get("hostname", f"Device-{client_ip}"),
            "ids": [client_ip],
            "use_global_settings": False,
            "filtering_enabled": True,
            "parental_enabled": False,
            "safebrowsing_enabled": True,
            "safesearch_enabled": safesearch if safesearch is not None else False,
            "blocked_services": blocked_services if blocked_services is not None else []
        }
        
        result = call_adguard_api("/control/clients/add", method="POST", data=client_data)
    
    return result is not None

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Revive - Parental Control Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
        
        body {
            font-family: 'Inter', sans-serif;
        }
        
        .gradient-bg {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        
        .card-hover {
            transition: all 0.3s ease;
        }
        
        .card-hover:hover {
            transform: translateY(-4px);
            box-shadow: 0 12px 24px rgba(0, 0, 0, 0.15);
        }
        
        .toggle-checkbox:checked {
            background-color: #f97316;
            border-color: #f97316;
        }
        
        .toggle-checkbox:checked + .toggle-label {
            background-color: #f97316;
        }
        
        .stat-card {
            background: linear-gradient(135deg, #f97316 0%, #fb923c 100%);
        }
        
        .device-card {
            border-left: 4px solid #f97316;
        }
        
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid rgba(255,255,255,.3);
            border-radius: 50%;
            border-top-color: #fff;
            animation: spin 1s ease-in-out infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
    </style>
</head>
<body class="bg-gray-50">
    <!-- Header -->
    <header class="gradient-bg text-white shadow-lg">
        <div class="container mx-auto px-4 py-6">
            <div class="flex items-center justify-between">
                <div>
                    <h1 class="text-3xl font-bold">Revive</h1>
                    <p class="text-purple-100 text-sm">Parental Control Dashboard</p>
                </div>
                <div class="text-right">
                    <p class="text-sm text-purple-100">Network Status</p>
                    <p class="text-lg font-semibold">🟢 Online</p>
                </div>
            </div>
        </div>
    </header>

    <!-- Main Content -->
    <main class="container mx-auto px-4 py-8">
        <!-- Statistics Cards -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div class="stat-card text-white rounded-xl p-6 shadow-lg card-hover">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-orange-100 text-sm font-medium">Ads Blocked Today</p>
                        <p class="text-4xl font-bold mt-2" id="ads-blocked">-</p>
                    </div>
                    <div class="text-5xl opacity-50">🛡️</div>
                </div>
            </div>
            
            <div class="bg-white rounded-xl p-6 shadow-lg card-hover border-2 border-orange-200">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-gray-600 text-sm font-medium">DNS Queries</p>
                        <p class="text-4xl font-bold mt-2 text-gray-800" id="dns-queries">-</p>
                    </div>
                    <div class="text-5xl opacity-50">📊</div>
                </div>
            </div>
            
            <div class="bg-white rounded-xl p-6 shadow-lg card-hover border-2 border-orange-200">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-gray-600 text-sm font-medium">Connected Devices</p>
                        <p class="text-4xl font-bold mt-2 text-gray-800" id="device-count">-</p>
                    </div>
                    <div class="text-5xl opacity-50">📱</div>
                </div>
            </div>
        </div>

        <!-- Devices Section -->
        <div class="bg-white rounded-xl shadow-lg p-6">
            <div class="flex items-center justify-between mb-6">
                <h2 class="text-2xl font-bold text-gray-800">Connected Devices</h2>
                <button onclick="refreshData()" class="bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-lg transition">
                    🔄 Refresh
                </button>
            </div>
            
            <div id="devices-container" class="space-y-4">
                <div class="text-center py-8 text-gray-500">
                    <div class="loading mx-auto mb-4"></div>
                    <p>Loading devices...</p>
                </div>
            </div>
        </div>
    </main>

    <!-- Footer -->
    <footer class="bg-gray-800 text-white mt-12 py-6">
        <div class="container mx-auto px-4 text-center">
            <p class="text-sm text-gray-400">Revive Parental Control Router &copy; 2024</p>
            <p class="text-xs text-gray-500 mt-2">Powered by AdGuard Home, RaspAP & CasaOS</p>
        </div>
    </footer>

    <script>
        let devicesData = [];

        async function fetchStats() {
            try {
                const response = await fetch('/api/stats');
                const data = await response.json();
                
                document.getElementById('ads-blocked').textContent = data.ads_blocked_today.toLocaleString();
                document.getElementById('dns-queries').textContent = data.dns_queries_today.toLocaleString();
            } catch (error) {
                console.error('Error fetching stats:', error);
            }
        }

        async function fetchDevices() {
            try {
                const response = await fetch('/api/clients');
                const data = await response.json();
                devicesData = data.clients;
                
                document.getElementById('device-count').textContent = devicesData.length;
                renderDevices();
            } catch (error) {
                console.error('Error fetching devices:', error);
                document.getElementById('devices-container').innerHTML = 
                    '<div class="text-center py-8 text-red-500">Error loading devices</div>';
            }
        }

        function renderDevices() {
            const container = document.getElementById('devices-container');
            
            if (devicesData.length === 0) {
                container.innerHTML = '<div class="text-center py-8 text-gray-500">No devices connected</div>';
                return;
            }
            
            container.innerHTML = devicesData.map(device => `
                <div class="device-card bg-gray-50 rounded-lg p-6 hover:shadow-md transition">
                    <div class="flex items-start justify-between mb-4">
                        <div class="flex-1">
                            <h3 class="text-xl font-semibold text-gray-800">${device.name}</h3>
                            <p class="text-sm text-gray-500">IP: ${device.ip} | MAC: ${device.mac}</p>
                        </div>
                        <div class="text-3xl">📱</div>
                    </div>
                    
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <!-- Block Social Media -->
                        <div class="bg-white p-4 rounded-lg border border-gray-200">
                            <div class="flex items-center justify-between mb-2">
                                <span class="text-sm font-medium text-gray-700">Block Social Media</span>
                                <label class="relative inline-block w-12 h-6">
                                    <input type="checkbox" 
                                           class="toggle-checkbox opacity-0 w-0 h-0" 
                                           ${device.blocked_services.some(s => ['youtube', 'tiktok', 'instagram'].includes(s)) ? 'checked' : ''}
                                           onchange="toggleBlock('${device.ip}', 'social_media', this.checked)">
                                    <span class="toggle-label absolute cursor-pointer top-0 left-0 right-0 bottom-0 bg-gray-300 rounded-full transition"></span>
                                    <span class="absolute left-1 top-1 bg-white w-4 h-4 rounded-full transition transform ${device.blocked_services.some(s => ['youtube', 'tiktok', 'instagram'].includes(s)) ? 'translate-x-6' : ''}"></span>
                                </label>
                            </div>
                            <p class="text-xs text-gray-500">YouTube, TikTok, Instagram</p>
                        </div>
                        
                        <!-- Safe Search -->
                        <div class="bg-white p-4 rounded-lg border border-gray-200">
                            <div class="flex items-center justify-between mb-2">
                                <span class="text-sm font-medium text-gray-700">Safe Search</span>
                                <label class="relative inline-block w-12 h-6">
                                    <input type="checkbox" 
                                           class="toggle-checkbox opacity-0 w-0 h-0" 
                                           ${device.safesearch_enabled ? 'checked' : ''}
                                           onchange="toggleSafeSearch('${device.ip}', this.checked)">
                                    <span class="toggle-label absolute cursor-pointer top-0 left-0 right-0 bottom-0 bg-gray-300 rounded-full transition"></span>
                                    <span class="absolute left-1 top-1 bg-white w-4 h-4 rounded-full transition transform ${device.safesearch_enabled ? 'translate-x-6' : ''}"></span>
                                </label>
                            </div>
                            <p class="text-xs text-gray-500">Filter search results</p>
                        </div>
                        
                        <!-- Bedtime Mode -->
                        <div class="bg-white p-4 rounded-lg border border-gray-200">
                            <div class="flex items-center justify-between mb-2">
                                <span class="text-sm font-medium text-gray-700">Bedtime Mode</span>
                                <label class="relative inline-block w-12 h-6">
                                    <input type="checkbox" 
                                           class="toggle-checkbox opacity-0 w-0 h-0" 
                                           ${device.bedtime_enabled ? 'checked' : ''}
                                           onchange="toggleBedtime('${device.ip}', this.checked)">
                                    <span class="toggle-label absolute cursor-pointer top-0 left-0 right-0 bottom-0 bg-gray-300 rounded-full transition"></span>
                                    <span class="absolute left-1 top-1 bg-white w-4 h-4 rounded-full transition transform ${device.bedtime_enabled ? 'translate-x-6' : ''}"></span>
                                </label>
                            </div>
                            <p class="text-xs text-gray-500">Block all internet</p>
                        </div>
                    </div>
                </div>
            `).join('');
        }

        async function toggleBlock(ip, category, enabled) {
            try {
                const response = await fetch('/api/toggle-block', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ip, category, enabled})
                });
                
                if (response.ok) {
                    await fetchDevices();
                } else {
                    alert('Failed to update settings');
                }
            } catch (error) {
                console.error('Error toggling block:', error);
                alert('Error updating settings');
            }
        }

        async function toggleSafeSearch(ip, enabled) {
            try {
                const response = await fetch('/api/toggle-safesearch', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ip, enabled})
                });
                
                if (response.ok) {
                    await fetchDevices();
                } else {
                    alert('Failed to update settings');
                }
            } catch (error) {
                console.error('Error toggling safe search:', error);
                alert('Error updating settings');
            }
        }

        async function toggleBedtime(ip, enabled) {
            try {
                const response = await fetch('/api/toggle-bedtime', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ip, enabled})
                });
                
                if (response.ok) {
                    await fetchDevices();
                } else {
                    alert('Failed to update settings');
                }
            } catch (error) {
                console.error('Error toggling bedtime mode:', error);
                alert('Error updating settings');
            }
        }

        async function refreshData() {
            await Promise.all([fetchStats(), fetchDevices()]);
        }

        // Initial load
        refreshData();
        
        // Auto-refresh every 30 seconds
        setInterval(refreshData, 30000);
    </script>
</body>
</html>
"""

# Routes
@app.route('/')
def index():
    """Render the main dashboard"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/stats')
def api_stats():
    """API endpoint for statistics"""
    stats = get_stats()
    return jsonify(stats)

@app.route('/api/clients')
def api_clients():
    """API endpoint for connected clients"""
    clients = get_connected_clients()
    return jsonify({"clients": clients})

@app.route('/api/toggle-block', methods=['POST'])
def api_toggle_block():
    """API endpoint to toggle service blocking"""
    data = request.json
    client_ip = data.get('ip')
    category = data.get('category')
    enabled = data.get('enabled')
    
    if not client_ip or not category:
        return jsonify({"error": "Missing parameters"}), 400
    
    # Get current client settings
    clients = get_connected_clients()
    current_client = next((c for c in clients if c['ip'] == client_ip), None)
    
    if not current_client:
        return jsonify({"error": "Client not found"}), 404
    
    # Update blocked services
    blocked_services = set(current_client.get('blocked_services', []))
    
    if enabled:
        # Add services to block
        blocked_services.update(BLOCKED_SERVICES.get(category, []))
    else:
        # Remove services from block
        blocked_services -= set(BLOCKED_SERVICES.get(category, []))
    
    # Update client
    success = update_client_settings(client_ip, blocked_services=list(blocked_services))
    
    if success:
        return jsonify({"success": True})
    else:
        return jsonify({"error": "Failed to update client"}), 500

@app.route('/api/toggle-safesearch', methods=['POST'])
def api_toggle_safesearch():
    """API endpoint to toggle safe search"""
    data = request.json
    client_ip = data.get('ip')
    enabled = data.get('enabled')
    
    if not client_ip:
        return jsonify({"error": "Missing IP parameter"}), 400
    
    success = update_client_settings(client_ip, safesearch=enabled)
    
    if success:
        return jsonify({"success": True})
    else:
        return jsonify({"error": "Failed to update client"}), 500

@app.route('/api/toggle-bedtime', methods=['POST'])
def api_toggle_bedtime():
    """API endpoint to toggle bedtime mode"""
    data = request.json
    client_ip = data.get('ip')
    enabled = data.get('enabled')
    
    if not client_ip:
        return jsonify({"error": "Missing IP parameter"}), 400
    
    success = update_client_settings(client_ip, bedtime_mode=enabled)
    
    if success:
        return jsonify({"success": True})
    else:
        return jsonify({"error": "Failed to update client"}), 500

if __name__ == '__main__':
    # Run the Flask app
    app.run(host='0.0.0.0', port=8000, debug=False)
