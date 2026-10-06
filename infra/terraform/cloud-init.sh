#!/bin/bash
# First-boot bootstrap of the Vigie node, rendered by Terraform templatefile().
# Nothing secret belongs here: user_data stays readable through the metadata service.
set -euo pipefail
exec > >(tee -a /var/log/vigie-bootstrap.log) 2>&1

K3S_VERSION="${k3s_version}"
export DEBIAN_FRONTEND=noninteractive

echo "vigie bootstrap start $(date -u +%FT%TZ)"

# --- Host firewall -----------------------------------------------------------------
# Oracle's Ubuntu image ships an iptables policy that rejects everything except SSH, on
# top of the cloud security list. Both layers must agree, so 80 and 443 open here too.
# The k3s pod (10.42/16) and service (10.43/16) ranges are accepted as well, otherwise
# the image's final REJECT rules break CoreDNS and metrics-server talking to the node.
iptables -I INPUT 1 -p tcp -m state --state NEW -m multiport --dports 80,443 -j ACCEPT
iptables -I INPUT 2 -s 10.42.0.0/16 -j ACCEPT
iptables -I INPUT 3 -s 10.43.0.0/16 -j ACCEPT
iptables -I FORWARD 1 -s 10.42.0.0/16 -j ACCEPT
iptables -I FORWARD 2 -d 10.42.0.0/16 -j ACCEPT
# Saved before k3s starts, so its dynamic chains are never frozen into the boot rules.
netfilter-persistent save

# --- SSH hardening ------------------------------------------------------------------
# sshd keeps the first value it reads, and drop-ins load in lexical order, so the 00
# prefix wins over the cloud image defaults.
cat > /etc/ssh/sshd_config.d/00-vigie-hardening.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
MaxAuthTries 3
X11Forwarding no
EOF
sshd -t
systemctl reload ssh

# --- Patching and brute-force protection -------------------------------------------
apt-get update -q
apt-get install -y -q unattended-upgrades fail2ban

cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF

# Ubuntu 24.04 logs SSH to the journal only, hence the systemd backend.
cat > /etc/fail2ban/jail.d/vigie.local <<'EOF'
[sshd]
enabled = true
backend = systemd
maxretry = 5
findtime = 10m
bantime = 1h
EOF
systemctl enable --now unattended-upgrades fail2ban
systemctl restart fail2ban

# --- Idle reclamation guard ---------------------------------------------------------
# Oracle reclaims an Always Free instance whose 95th percentile CPU stays under 20 % for
# a week. Eight minutes of one busy core every hour keeps that percentile above the bar,
# at the lowest priority so the real workload always wins.
cat > /etc/systemd/system/vigie-keepalive.service <<'EOF'
[Unit]
Description=Vigie light background load against Always Free idle reclamation

[Service]
Type=oneshot
Nice=19
CPUWeight=1
IOSchedulingClass=idle
ExecStart=/usr/bin/timeout 480 /usr/bin/sha256sum /dev/zero
SuccessExitStatus=124
EOF

cat > /etc/systemd/system/vigie-keepalive.timer <<'EOF'
[Unit]
Description=Hourly Vigie keepalive load

[Timer]
OnBootSec=15min
OnUnitActiveSec=1h
RandomizedDelaySec=5min

[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now vigie-keepalive.timer

# --- k3s ----------------------------------------------------------------------------
# The installer is fetched from the same pinned tag as the binary, which it then checks
# against the release checksums. Kubeconfig stays root-only and Secrets are encrypted at
# rest in the datastore.
K3S_TAG=$(printf '%s' "$K3S_VERSION" | sed 's/+/%2B/')
curl -sfL "https://raw.githubusercontent.com/k3s-io/k3s/$K3S_TAG/install.sh" -o /tmp/k3s-install.sh
INSTALL_K3S_VERSION="$K3S_VERSION" sh /tmp/k3s-install.sh server \
  --write-kubeconfig-mode 600 \
  --secrets-encryption
rm -f /tmp/k3s-install.sh

mkdir -p /var/lib/vigie
date -u +%FT%TZ > /var/lib/vigie/bootstrap.done
echo "vigie bootstrap done $(date -u +%FT%TZ)"
