resource "aws_instance" "web" {
    for i in range(1, 3) {
        name = "web-${i}"
        instance_type = "t2.micro"
    }
}

---EXPECTED---

resource "aws_instance" "web" {
  dynamic "i" {
    for_each = range(1, 3)
    content {
      name = "web-${i}"
      instance_type = "t2.micro"
    }
  }
}
