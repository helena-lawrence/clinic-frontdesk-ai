resource "aws_lb" "clinic" {
  name               = "clinic-frontdesk-managed"
  load_balancer_type = "application"
  internal           = true
  subnets            = aws_subnet.load_balancer[*].id
  security_groups    = [aws_security_group.alb.id]
}

resource "aws_lb_target_group" "api" {
  name        = "clinic-managed-api"
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.clinic.id

  health_check {
    path = "/auth/health"
  }
}

resource "aws_lb_target_group" "ui" {
  name        = "clinic-managed-ui"
  port        = 8502
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.clinic.id

  health_check {
    path = "/_stcore/health"
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.clinic.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.ui.arn
  }
}

resource "aws_lb_listener_rule" "api" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }

  condition {
    path_pattern {
      values = ["/auth/*"]
    }
  }
}

resource "aws_cloudfront_vpc_origin" "clinic" {
  vpc_origin_endpoint_config {
    name                   = "clinic-frontdesk-managed"
    arn                    = aws_lb.clinic.arn
    http_port              = 80
    https_port             = 443
    origin_protocol_policy = "http-only"

    origin_ssl_protocols {
      items    = ["TLSv1.2"]
      quantity = 1
    }
  }

  depends_on = [aws_lb_listener.http]
}

resource "aws_cloudfront_distribution" "clinic" {
  enabled         = true
  is_ipv6_enabled = true
  comment         = "Clinic Front Desk AI"
  price_class     = "PriceClass_100"

  origin {
    domain_name = aws_lb.clinic.dns_name
    origin_id   = "clinic-private-alb"

    vpc_origin_config {
      vpc_origin_id = aws_cloudfront_vpc_origin.clinic.id
    }
  }

  default_cache_behavior {
    target_origin_id         = "clinic-private-alb"
    viewer_protocol_policy   = "redirect-to-https"
    allowed_methods          = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods           = ["GET", "HEAD"]
    cache_policy_id          = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
    origin_request_policy_id = "216adef6-5c7f-47e4-b989-5492eafa07d3"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}
