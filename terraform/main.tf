provider "aws" {
  region = "us-east-1"
}

resource "aws_instance" "prometheus_server" {
  ami           = "ami-0c55b159cbfafe1f0"  # Update this AMI ID with the appropriate Amazon Linux 2 AMI
  instance_type = "t2.micro"
  key_name      = "your-key-name"  # Optional: replace with your key pair name

  user_data = <<EOF
#!/bin/bash
# Update the system
yum update -y

# Install wget
yum install -y wget

# Download and extract Prometheus
wget https://github.com/prometheus/prometheus/releases/download/v2.43.0/prometheus-2.43.0.linux-amd64.tar.gz
tar -xvf prometheus-2.43.0.linux-amd64.tar.gz
mv prometheus-2.43.0.linux-amd64 /usr/local/prometheus

# Create Prometheus configuration file
cat > /usr/local/prometheus/prometheus.yml <<EOL
global:
  scrape_interval: 60s
scrape_configs:
- job_name: prometheus
  static_configs:
  - targets: [localhost:9090]
EOL

# Create systemd service file for Prometheus
cat > /etc/systemd/system/prometheus.service <<EOL
[Unit]
Description=Prometheus
Wants=network.target
After=network.target

[Service]
User=ec2-user
ExecStart=/usr/local/prometheus/prometheus --config.file=/usr/local/prometheus/prometheus.yml
Restart=always

[Install]
WantedBy=multi-user.target
EOL

# Reload systemd and start Prometheus
systemctl daemon-reload
systemctl enable prometheus
systemctl start prometheus
EOF

  tags = {
    Name = "Prometheus_Server"
  }
}

