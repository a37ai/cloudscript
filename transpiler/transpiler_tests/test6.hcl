function make_tags(env: string) {
    return {
        Environment = env
        Managed = "terraform"
    }
}

resource "aws_instance" "app" {
    tags = local.make_tags
}

---EXPECTED---

locals {
  make_tags = {
    Environment = env
    Managed = "terraform"
  }
}

resource "aws_instance" "app" {
  tags = local.make_tags
}
