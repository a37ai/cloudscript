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

---EXPECTED---

resource "aws_db_instance" "default" {
  engine = "postgres"
  version = "12.3"
  storage = 20
}
