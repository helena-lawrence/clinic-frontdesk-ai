resource "aws_ecr_repository" "api" {
  name                 = "clinic-frontdesk-managed-api"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "ui" {
  name                 = "clinic-frontdesk-managed-ui"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "predictor" {
  name                 = "clinic-frontdesk-managed-predictor"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the last 20 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 20
      }
      action = { type = "expire" }
    }]
  })
}

resource "aws_ecr_lifecycle_policy" "ui" {
  repository = aws_ecr_repository.ui.name
  policy     = aws_ecr_lifecycle_policy.api.policy
}

resource "aws_ecr_lifecycle_policy" "predictor" {
  repository = aws_ecr_repository.predictor.name
  policy     = aws_ecr_lifecycle_policy.api.policy
}
