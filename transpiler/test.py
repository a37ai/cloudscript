import os
from .main import convert_enhanced_hcl_to_standard

def run_transpiler_tests():
    """Run comprehensive tests for the transpiler with better error handling"""
    class TranspilerTest:
        def __init__(self):
            self.passed = 0
            self.failed = 0
        
        def assert_transpile(self, input_hcl: str, expected_output: str, test_name: str):
            try:
                result = convert_enhanced_hcl_to_standard(input_hcl)
                # Normalize whitespace for comparison
                result_norm = ' '.join(result.split())
                expected_norm = ' '.join(expected_output.split())
                
                if result_norm == expected_norm:
                    print(f"✓ {test_name}")
                    self.passed += 1
                else:
                    print(f"✗ {test_name}")
                    print("Expected:")
                    print(expected_output)
                    print("Got:")
                    print(result)
                    self.failed += 1
            except Exception as e:
                print(f"✗ {test_name}")
                print(f"Error: {str(e)}")
                self.failed += 1
    
    test = TranspilerTest()


    test.assert_transpile(
        """
        type ComputeInstance {
            cpu: number = 0,
            memory: number = 0,
            os: string = "Linux"
        }

        type Instance {
            base: ComputeInstance,
            name: string = "default-name",
            size: "t2.micro" | "t2.small" = "t2.micro"
        }
        
        resource "aws_instance" "web" {
            type = Instance
            name = "web-1"
        }
        """,
        """
resource "aws_instance" "web" {
  name = "web-1"
  cpu = 0
  memory = 0
  os = "Linux"
  size = "t2.micro"
}
        """,
        "Type with Base and Defaults"
    )

    test.assert_transpile(
        """
        type ComputedInstance {
            name: string,
            domain: string,
            fqdn: string = calc { "${name}.${domain}" }
        }
        
        resource "aws_instance" "api" {
            type = ComputedInstance
            name = "api"
            domain = "example.com"
        }
        """,
        
"""resource "aws_instance" "api" {
  name = "api"
  domain = "example.com"
  fqdn = "api.example.com"
}"""
        ,
        "Computed Fields"
    )


    test.assert_transpile(
        """
        resource "aws_instance" "web" {
            for i in range(1, 3) {
                name = "web-${i}"
                instance_type = "t2.micro"
            }
        }
        """,
        """
resource "aws_instance" "web" {
  dynamic "i" {
    for_each = range(1, 3)
    content {
      name = "web-${i}"
      instance_type = "t2.micro"
    }
  }
}
        """,
        "Basic For Loop"
    )


    test.assert_transpile(
        """
        type Instance {
            name: string
            size: "t2.micro" | "t2.small"
        }
        
        resource "aws_instance" "web" {
            name = "web-1"
            size = "t2.micro"
        }
        """,
        """
resource "aws_instance" "web" {
  name = "web-1"
  size = "t2.micro"
}
        """,
        "Type Definition"
    )

    
    test.assert_transpile(
        """
        resource "aws_instance" "env" {
            switch var.environment {
                case "prod" { instance_type = "t2.medium" }
                default { instance_type = "t2.micro" }
            }
        }
        """,
        """
resource "aws_instance" "env" {
  var.environment == "prod" ? {
    instance_type = "t2.medium"
  } : {
    instance_type = "t2.micro"
  }
}
        """,
        "Switch Statement"
    )


    test.assert_transpile(
        """
        function make_tags(env: string) {
            return {
                Environment = env
                Managed = "terraform"
            }
        }
        
        resource "aws_instance" "app" {
            tags = local.make_tags
        }
        """,
        """
locals {
  make_tags = {
    Environment = env
    Managed = "terraform"
  }
}

resource "aws_instance" "app" {
  tags = local.make_tags
}
        """,
        "Custom Function"
    )


    test.assert_transpile(
        """
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
        """,
        """
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
        """,
        "Nested Loops"
    )

    test.assert_transpile(
        """
        resource "aws_instance" "conditional_instance" {
            instance_type = var.is_production ? "t2.large" : "t2.micro"
            ami = var.is_production ? "ami-prod" : "ami-dev"
        }
        """,
        """
resource "aws_instance" "conditional_instance" {
  instance_type = var.is_production ? "t2.large" : "t2.micro"
  ami = var.is_production ? "ami-prod" : "ami-dev"
}
        """,
        "Ternary Expression in Resource"
    )
    
  
    test.assert_transpile(
        """
        type DatabaseConfig {
            engine: "postgres" | "mysql" | "sqlite"
            version: string?
            storage: number = 20
        }
        
        resource "aws_db_instance" "default" {
            type = DatabaseConfig
            engine = "postgres"
            version = "12.3"
        }
        """,
        """
resource "aws_db_instance" "default" {
  engine = "postgres"
  version = "12.3"
  storage = 20
}
        """,
        "Type with Union and Nullable Types"
    )
    

    test.assert_transpile(
        """
        type ServiceConfig {
            name: string
            port: number
            description: string? = "Default service description"
        }
        
        resource "aws_service" "my_service" {
            type = ServiceConfig
            name = "my-service"
            port = 8080
        }
        """,
        """
resource "aws_service" "my_service" {
  name = "my-service"
  port = 8080
  description = "Default service description"
}
        """,
        "Nullable Field with Default"
    )
    
    print(f"\nTests completed: {test.passed} passed, {test.failed} failed")

enhanced_hcl = """
type ComputeInstance {
    cpu: number = 4
    memory: number = 16
    os: string = "Linux"
}

type Instance {
    base: ComputeInstance
    name: string = "default-instance"
    size: "t2.micro" | "t2.small" = "t2.micro"
}

service "web_app" {
    type = "application"
    dependencies = []

    infrastructure {
        compute = [
            {
                type = Instance
                name = "web_server"
                count = 2
                size = "t2.micro"
                os = "ami-0abcdef1234567890" 
                tags = {
                    Environment = "production"
                    Role        = "web"
                }
                provisioners = [
                    {
                        type = "remote-exec"
                        inline = [
                            "sudo apt-get update -y",
                            "sudo apt-get install -y nginx",
                            "sudo systemctl start nginx",
                            "sudo systemctl enable nginx"
                        ]
                    }
                ]
            }
        ]
    }

    configuration {
        packages = ["nginx", "curl"]
        services = {
            running = ["nginx"]
            enabled = ["nginx"]
        }
        variables = {
            server_port = 80
        }
        files = {
            "/etc/nginx/sites-available/default" = "templates/nginx_default.conf"
        }
    }

    containers = [
        {
            name        = "web_container"
            image       = "nginx:latest"
            ports       = [80]
            environment = {
                NGINX_HOST = "localhost"
                NGINX_PORT = "80"
            }
            replicas    = 3
            health_check = {
                http_get = {
                    path = "/"
                    port = 80
                }
                initial_delay_seconds = 15
                period_seconds        = 20
            }
            resources = {
                limits = {
                    cpu    = "500m"
                    memory = "256Mi"
                }
                requests = {
                    cpu    = "250m"
                    memory = "128Mi"
                }
            }
        }
    ]
}
"""

run_transpiler_tests()