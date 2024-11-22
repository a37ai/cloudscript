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

---EXPECTED---

resource "aws_instance" "web" {
  name = "web-1"
  cpu = 0
  memory = 0
  os = "Linux"
  size = "t2.micro"
}
