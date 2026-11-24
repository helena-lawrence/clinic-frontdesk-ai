data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_ec2_managed_prefix_list" "cloudfront" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}

resource "aws_vpc" "clinic" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "clinic-frontdesk" }
}

resource "aws_internet_gateway" "clinic" {
  vpc_id = aws_vpc.clinic.id
  tags   = { Name = "clinic-frontdesk" }
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.clinic.id
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  cidr_block              = cidrsubnet(aws_vpc.clinic.cidr_block, 8, count.index)
  map_public_ip_on_launch = true
  tags                    = { Name = "clinic-frontdesk-public-${count.index + 1}" }
}

resource "aws_subnet" "database" {
  count             = 2
  vpc_id            = aws_vpc.clinic.id
  availability_zone = data.aws_availability_zones.available.names[count.index]
  cidr_block        = cidrsubnet(aws_vpc.clinic.cidr_block, 8, count.index + 10)
  tags              = { Name = "clinic-frontdesk-db-${count.index + 1}" }
}

resource "aws_subnet" "load_balancer" {
  count             = 2
  vpc_id            = aws_vpc.clinic.id
  availability_zone = data.aws_availability_zones.available.names[count.index]
  cidr_block        = cidrsubnet(aws_vpc.clinic.cidr_block, 8, count.index + 20)
  tags              = { Name = "clinic-frontdesk-alb-${count.index + 1}" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.clinic.id
  tags   = { Name = "clinic-frontdesk-public" }
}

resource "aws_route" "internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.clinic.id
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "alb" {
  name_prefix = "clinic-frontdesk-alb-"
  description = "CloudFront to clinic ALB"
  vpc_id      = aws_vpc.clinic.id
}

resource "aws_vpc_security_group_ingress_rule" "alb_from_vpc_origin" {
  security_group_id = aws_security_group.alb.id
  prefix_list_id    = data.aws_ec2_managed_prefix_list.cloudfront.id
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
  description       = "CloudFront origin-facing network"
}

resource "aws_security_group" "ecs" {
  name_prefix = "clinic-frontdesk-ecs-"
  description = "Clinic API and UI tasks"
  vpc_id      = aws_vpc.clinic.id
}

resource "aws_security_group" "database" {
  name_prefix = "clinic-frontdesk-db-"
  description = "PostgreSQL access from clinic tasks"
  vpc_id      = aws_vpc.clinic.id
}

resource "aws_vpc_security_group_ingress_rule" "database_from_ecs" {
  security_group_id            = aws_security_group.database.id
  referenced_security_group_id = aws_security_group.ecs.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "ecs_outbound" {
  security_group_id = aws_security_group.ecs.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_vpc_security_group_ingress_rule" "ecs_api_from_alb" {
  security_group_id            = aws_security_group.ecs.id
  referenced_security_group_id = aws_security_group.alb.id
  from_port                    = 8000
  to_port                      = 8000
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "ecs_ui_from_alb" {
  security_group_id            = aws_security_group.ecs.id
  referenced_security_group_id = aws_security_group.alb.id
  from_port                    = 8502
  to_port                      = 8502
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "alb_api" {
  security_group_id            = aws_security_group.alb.id
  referenced_security_group_id = aws_security_group.ecs.id
  from_port                    = 8000
  to_port                      = 8000
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "alb_ui" {
  security_group_id            = aws_security_group.alb.id
  referenced_security_group_id = aws_security_group.ecs.id
  from_port                    = 8502
  to_port                      = 8502
  ip_protocol                  = "tcp"
}
