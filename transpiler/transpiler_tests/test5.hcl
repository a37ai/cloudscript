resource "aws_instance" "env" {
    switch var.environment {
        case "prod" { instance_type = "t2.medium" }
        default { instance_type = "t2.micro" }
    }
}

---EXPECTED---

resource "aws_instance" "env" {
  var.environment == "prod" ? {
    instance_type = "t2.medium"
  } : {
    instance_type = "t2.micro"
  }
}
