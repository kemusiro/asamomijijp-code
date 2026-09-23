resource "aws_instance" "web" {
  for_each = aws_subnet.private

  ami                         = var.ami_id
  instance_type               = var.instance_type
  subnet_id                   = each.value.id
  vpc_security_group_ids      = [aws_security_group.web.id]
  associate_public_ip_address = false
  user_data_replace_on_change = true

  metadata_options {
    http_tokens = "required"
  }

  user_data = <<-SCRIPT
    #!/bin/bash
    set -euxo pipefail
    dnf install -y nginx
    echo 'Hello from ${each.key}' > /usr/share/nginx/html/index.html
    systemctl enable --now nginx
  SCRIPT

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-web-${each.key}"
  })

  depends_on = [
    aws_route.public_default,
    aws_route.private_default,
    aws_route_table_association.public,
    aws_route_table_association.private,
    aws_vpc_security_group_egress_rule.web_outbound,
  ]
}
