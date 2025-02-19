terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

resource "aws_instance" "prometheus_vm" {
  ami           = "ami-005fc0f236362e99f"  # Amazon Linux 2 image
  instance_type = "t2.micro"

  user_data = <<-EOF
    #!/bin/bash
    yum update -y
    amazon-linux-extras install prometheus2 -y
    systemctl enable prometheus
    systemctl start prometheus
EOF

  tags = {
    Name = "prometheus-vm"
  }
}

