# The manual teardown job copies this override into the root module on its runner.
resource "aws_db_instance" "clinic" {
  deletion_protection = false
  apply_immediately   = true
  skip_final_snapshot = true

  lifecycle {
    prevent_destroy = false
  }
}

resource "aws_ecr_repository" "api" {
  force_delete = true
}

resource "aws_ecr_repository" "ui" {
  force_delete = true
}

resource "aws_ecr_repository" "predictor" {
  force_delete = true
}
