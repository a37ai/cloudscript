import os
from .main import convert_enhanced_hcl_to_standard_string

def run_transpiler_tests():
    """Run comprehensive tests for the transpiler with better error handling."""
    class TranspilerTest:
        def __init__(self):
            self.passed = 0
            self.failed = 0

        def remove_comments(self, text: str) -> str:
            """Removes comment lines from the HCL text."""
            lines = text.splitlines()
            non_comment_lines = [line for line in lines if not line.strip().startswith("#") and not line.strip().startswith("//")]
            return "\n".join(non_comment_lines)

        def assert_transpile(self, input_hcl: str, expected_output: str, test_name: str):
            try:
                # Convert the input using the transpiler function
                result = convert_enhanced_hcl_to_standard_string(input_hcl)
                
                # Remove comments from both result and expected output
                result_no_comments = self.remove_comments(result)
                expected_no_comments = self.remove_comments(expected_output)
                
                # Normalize whitespace for comparison
                result_norm = ' '.join(result_no_comments.split())
                expected_norm = ' '.join(expected_no_comments.split())
                
                # Check if normalized outputs match
                if result_norm == expected_norm:
                    print(f"✓ {test_name}")
                    self.passed += 1
                else:
                    print(f"✗ {test_name}")
                    print("Expected (no comments):")
                    print(expected_no_comments)
                    print("Got (no comments):")
                    print(result_no_comments)
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

#     test.assert_transpile(
#         """
#         resource "aws_instance" "conditional_instance" {
#             instance_type = var.is_production ? "t2.large" : "t2.micro"
#             ami = var.is_production ? "ami-prod" : "ami-dev"
#         }
#         """,
#         """
# resource "aws_instance" "conditional_instance" {
#   instance_type = var.is_production ? "t2.large" : "t2.micro"
#   ami = var.is_production ? "ami-prod" : "ami-dev"
# }
#         """,
#         "Ternary Expression in Resource"
#     )
    
  
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

run_transpiler_tests()