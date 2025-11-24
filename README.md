# Revive - Parental Control Router

A complete software stack for Raspberry Pi 4/5 that transforms it into a powerful parental control router with a WhatsApp-simple interface.

## 🎯 Features

- **WiFi Access Point**: Secure hotspot with WPA2 encryption
- **Ad Blocking**: AdGuard Home blocks ads and trackers network-wide
- **Parental Controls**: Easy-to-use dashboard for managing device restrictions
- **Container Management**: CasaOS for running additional services
- **Professional Backend**: RaspAP, AdGuard Home, and custom Flask dashboard

## 📋 Requirements

- Raspberry Pi 4 or 5
- Raspberry Pi OS Lite (64-bit)
- 8GB+ microSD card
- Ethernet connection for WAN
- WiFi adapter for AP (built-in works fine)

## 🚀 Installation

### Quick Install (One Command)

```bash
sudo bash install_revive.sh
```

This script will automatically:
1. Update your system
2. Install RaspAP (WiFi AP on port 80)
3. Install AdGuard Home (DNS filtering on port 8080)
4. Install CasaOS (Container management on port 81)
5. Configure networking and firewall rules

### Manual Setup (After Installation)

1. **Copy the dashboard files:**
```bash
sudo cp dashboard.py /opt/revive/
sudo cp revive-dashboard.service /etc/systemd/system/
```

2. **Enable and start the dashboard:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable revive-dashboard
sudo systemctl start revive-dashboard
```

3. **Reboot to ensure all services start correctly:**
```bash
sudo reboot
```

## 🌐 Access Points

After installation, you can access the following services:

| Service | URL | Default Credentials |
|---------|-----|---------------------|
| **Revive Dashboard** | `http://<pi-ip>:8000` | No login required |
| **RaspAP** | `http://<pi-ip>:80` | admin / secret |
| **AdGuard Home** | `http://<pi-ip>:8080` | admin / revive123 |
| **CasaOS** | `http://<pi-ip>:81` | Set on first login |

### WiFi Hotspot

- **SSID**: `Revive_Secure_Home`
- **Password**: `securekids123`

## 📱 Using the Parental Dashboard

The Revive Dashboard (`http://<pi-ip>:8000`) provides a simple interface for parents:

### Features:

1. **Network Statistics**
   - Ads blocked today
   - DNS queries processed
   - Connected devices count

2. **Device Management**
   - View all connected devices
   - See device names, IPs, and MAC addresses

3. **Per-Device Controls**
   - **Block Social Media**: Blocks YouTube, TikTok, Instagram, Facebook, Snapchat, Twitter
   - **Safe Search**: Enforces safe search on Google, Bing, etc.
   - **Bedtime Mode**: Blocks all internet access for the device

### How It Works:

- The dashboard communicates with AdGuard Home's API
- Changes are applied in real-time
- No need to restart services
- Settings persist across reboots

## 🔧 Advanced Configuration

### Changing AdGuard Home Settings

1. Access AdGuard Home at `http://<pi-ip>:8080`
2. Login with `admin` / `revive123`
3. Configure additional filters, blocklists, or DNS settings

### Customizing the WiFi Hotspot

1. Access RaspAP at `http://<pi-ip>:80`
2. Login with `admin` / `secret`
3. Go to Hotspot settings to change SSID, password, or channel

### Adding More Services with CasaOS

1. Access CasaOS at `http://<pi-ip>:81`
2. Browse the app store for additional services
3. Install Docker containers with one click

## 🛠️ Troubleshooting

### Dashboard Not Loading

```bash
# Check if the service is running
sudo systemctl status revive-dashboard

# View logs
sudo journalctl -u revive-dashboard -f
```

### AdGuard Home Not Blocking

```bash
# Check AdGuard Home status
sudo systemctl status AdGuardHome

# Restart AdGuard Home
sudo systemctl restart AdGuardHome
```

### WiFi Hotspot Not Working

```bash
# Check hostapd status
sudo systemctl status hostapd

# Check dnsmasq status
sudo systemctl status dnsmasq

# Restart both services
sudo systemctl restart hostapd dnsmasq
```

### Port Conflicts

If you encounter port conflicts:

```bash
# Check what's using a specific port
sudo netstat -tulpn | grep :<port>

# Example: Check port 80
sudo netstat -tulpn | grep :80
```

## 📊 Architecture

```
Internet (eth0)
    ↓
Raspberry Pi
    ├── RaspAP (Port 80) - WiFi AP Management
    ├── AdGuard Home (Port 8080) - DNS Filtering
    ├── CasaOS (Port 81) - Container Management
    └── Revive Dashboard (Port 8000) - Parental Controls
    ↓
WiFi Hotspot (wlan0)
    ↓
Client Devices
```

### Network Flow:

1. Clients connect to WiFi hotspot (RaspAP)
2. DHCP assigns IP addresses
3. DNS queries go to AdGuard Home (127.0.0.1:53)
4. AdGuard Home filters and forwards to upstream DNS
5. Parents manage controls via Revive Dashboard

## 🔐 Security Notes

- **Change default passwords** immediately after installation
- The dashboard runs as root (required for DHCP lease access)
- AdGuard Home uses HTTP Basic Auth
- Consider setting up HTTPS for production use
- Firewall rules are configured to allow only necessary traffic

## 🎨 Customization

### Changing Dashboard Theme

Edit `/opt/revive/dashboard.py` and modify the CSS in the HTML template:

```python
# Look for the <style> section
# Change colors, fonts, or layout
```

### Adding More Blocked Services

Edit the `BLOCKED_SERVICES` dictionary in `dashboard.py`:

```python
BLOCKED_SERVICES = {
    "social_media": ["youtube", "tiktok", "instagram", "facebook"],
    "gaming": ["roblox", "fortnite", "minecraft"],
    "custom_category": ["service1", "service2"],
}
```

## 📝 License

This project is provided as-is for educational and personal use.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## 📧 Support

For issues or questions:
1. Check the troubleshooting section
2. Review AdGuard Home documentation
3. Check RaspAP documentation
4. Open an issue on GitHub

## 🙏 Acknowledgments

- **AdGuard Home** - Network-wide ad blocking
- **RaspAP** - WiFi access point management
- **CasaOS** - Container management platform
- **Flask** - Python web framework
- **Tailwind CSS** - UI styling

---

**Made with ❤️ for parents who want to keep their kids safe online**
