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

---EXPECTED---

resource "aws_service" "my_service" {
  name = "my-service"
  port = 8080
  description = "Default service description"
}
