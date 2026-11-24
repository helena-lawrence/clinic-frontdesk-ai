data "aws_caller_identity" "current" {}

locals {
  region     = "eu-west-2"
  public_url = "https://${aws_cloudfront_distribution.clinic.domain_name}"
  db_secret  = aws_db_instance.clinic.master_user_secret[0].secret_arn
  db_settings = [
    { name = "AWS_REGION", value = local.region },
    { name = "DB_HOST", value = aws_db_instance.clinic.address },
    { name = "DB_PORT", value = tostring(aws_db_instance.clinic.port) },
    { name = "DB_NAME", value = aws_db_instance.clinic.db_name },
    { name = "DB_USER", value = aws_db_instance.clinic.username },
  ]
  db_password = [{ name = "DB_PASSWORD", valueFrom = "${local.db_secret}:password::" }]
  logs_api = {
    logDriver = "awslogs"
    options = {
      awslogs-group         = aws_cloudwatch_log_group.api.name
      awslogs-region        = local.region
      awslogs-stream-prefix = "api"
    }
  }
  logs_ui = {
    logDriver = "awslogs"
    options = {
      awslogs-group         = aws_cloudwatch_log_group.ui.name
      awslogs-region        = local.region
      awslogs-stream-prefix = "ui"
    }
  }
  logs_init = {
    logDriver = "awslogs"
    options = {
      awslogs-group         = aws_cloudwatch_log_group.init.name
      awslogs-region        = local.region
      awslogs-stream-prefix = "init"
    }
  }
}

resource "aws_ecs_cluster" "clinic" {
  name = "clinic-frontdesk-managed"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/clinic-frontdesk-managed/api"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "ui" {
  name              = "/ecs/clinic-frontdesk-managed/ui"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "init" {
  name              = "/ecs/clinic-frontdesk-managed/init"
  retention_in_days = 30
}

resource "aws_iam_role" "execution" {
  name = "clinic-frontdesk-managed-execution"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "database_secret" {
  name = "read-managed-database-password"
  role = aws_iam_role.execution.id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = local.db_secret }]
  })
}

resource "aws_iam_role" "api" {
  name               = "clinic-frontdesk-managed-api-task"
  assume_role_policy = aws_iam_role.execution.assume_role_policy
}

resource "aws_iam_role" "ui" {
  name               = "clinic-frontdesk-managed-ui-task"
  assume_role_policy = aws_iam_role.execution.assume_role_policy
}

resource "aws_iam_role_policy" "ui_models" {
  name = "invoke-clinic-models"
  role = aws_iam_role.ui.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel"]
        Resource = ["arn:aws:bedrock:eu-west-2::foundation-model/amazon.nova-lite-v1:0", "arn:aws:bedrock:eu-west-2::foundation-model/amazon.titan-embed-text-v2:0"]
      },
      {
        Effect   = "Allow"
        Action   = ["lambda:InvokeFunction"]
        Resource = "arn:aws:lambda:eu-west-2:${data.aws_caller_identity.current.account_id}:function:clinic-frontdesk-managed-predictor"
      }
    ]
  })
}

resource "aws_ecs_task_definition" "api" {
  count                    = var.enable_services ? 1 : 0
  family                   = "clinic-frontdesk-managed-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.api.arn

  container_definitions = jsonencode([{
    name         = "api"
    image        = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
    essential    = true
    portMappings = [{ containerPort = 8000, protocol = "tcp" }]
    environment = concat(local.db_settings, [
      { name = "COGNITO_DOMAIN", value = "https://${aws_cognito_user_pool_domain.clinic.domain}.auth.${local.region}.amazoncognito.com" },
      { name = "COGNITO_REGION", value = local.region },
      { name = "COGNITO_USER_POOL_ID", value = aws_cognito_user_pool.clinic.id },
      { name = "COGNITO_CLIENT_ID", value = aws_cognito_user_pool_client.clinic.id },
      { name = "COGNITO_REDIRECT_URI", value = "${local.public_url}/auth/callback" },
      { name = "CLINIC_UI_URL", value = "${local.public_url}/" },
    ])
    secrets          = local.db_password
    logConfiguration = local.logs_api
  }])

  lifecycle {
    precondition {
      condition     = length(var.image_tag) == 40
      error_message = "Set image_tag to the published 40-character Git commit SHA when enabling services."
    }
  }
}

resource "aws_ecs_task_definition" "ui" {
  count                    = var.enable_services ? 1 : 0
  family                   = "clinic-frontdesk-managed-ui"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.ui.arn

  container_definitions = jsonencode([{
    name         = "ui"
    image        = "${aws_ecr_repository.ui.repository_url}:${var.image_tag}"
    essential    = true
    portMappings = [{ containerPort = 8502, protocol = "tcp" }]
    environment = concat(local.db_settings, [
      { name = "CLINIC_API_INTERNAL_URL", value = local.public_url },
      { name = "CLINIC_API_PUBLIC_URL", value = local.public_url },
      { name = "CLINIC_PREDICTOR_FUNCTION", value = "clinic-frontdesk-managed-predictor" },
    ])
    secrets          = local.db_password
    logConfiguration = local.logs_ui
  }])
}

resource "aws_ecs_task_definition" "init" {
  count                    = var.enable_services ? 1 : 0
  family                   = "clinic-frontdesk-managed-init"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.ui.arn

  container_definitions = jsonencode([{
    name             = "init"
    image            = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
    essential        = true
    command          = ["python", "-m", "scripts.bootstrap_managed_database"]
    environment      = local.db_settings
    secrets          = local.db_password
    logConfiguration = local.logs_init
  }])
}

resource "aws_ecs_service" "api" {
  count           = var.enable_services ? 1 : 0
  name            = "clinic-frontdesk-managed-api"
  cluster         = aws_ecs_cluster.clinic.id
  task_definition = aws_ecs_task_definition.api[0].arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  depends_on = [aws_lb_listener_rule.api, aws_iam_role_policy.database_secret, aws_iam_role_policy_attachment.execution]
}

resource "aws_ecs_service" "ui" {
  count           = var.enable_services ? 1 : 0
  name            = "clinic-frontdesk-managed-ui"
  cluster         = aws_ecs_cluster.clinic.id
  task_definition = aws_ecs_task_definition.ui[0].arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.ui.arn
    container_name   = "ui"
    container_port   = 8502
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  depends_on = [aws_lb_listener.http, aws_iam_role_policy.database_secret, aws_iam_role_policy_attachment.execution]
}
