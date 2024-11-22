resource "aws_security_group" "multi_port" {
    for port in [80, 443, 8080] {
        for cidr in var.allowed_cidrs {
            if cidr != "0.0.0.0/0" {
                ingress {
                    from_port = port
                    to_port = port
                    protocol = "tcp"
                    cidr_blocks = [cidr]
                }
            }
        }
    }
}

---EXPECTED---

resource "aws_security_group" "multi_port" {
  dynamic "port" {
    for_each = [80, 443, 8080]
    content {
      dynamic "cidr" {
        for_each = var.allowed_cidrs
        content {
          dynamic "conditional" {
            for_each = cidr != "0.0.0.0/0" ? [1] : []
            content {
              ingress {
                from_port = port
                to_port = port
                protocol = "tcp"
                cidr_blocks = [cidr]
              }
            }
          }
        }
      }
    }
  }
}
