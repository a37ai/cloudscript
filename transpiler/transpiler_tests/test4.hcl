type Instance {
    name: string
    size: "t2.micro" | "t2.small"
}

resource "aws_instance" "web" {
    name = "web-1"
    size = "t2.micro"
}

---EXPECTED---

resource "aws_instance" "web" {
  name = "web-1"
  size = "t2.micro"
}
