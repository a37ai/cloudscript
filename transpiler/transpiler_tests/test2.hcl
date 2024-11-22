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

---EXPECTED---

resource "aws_instance" "api" {
  name = "api"
  domain = "example.com"
  fqdn = "api.example.com"
}
