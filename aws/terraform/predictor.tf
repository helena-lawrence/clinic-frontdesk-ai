resource "aws_iam_role" "predictor" {
  name = "clinic-frontdesk-managed-predictor"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy_attachment" "predictor_logs" {
  role       = aws_iam_role.predictor.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_cloudwatch_log_group" "predictor" {
  name              = "/aws/lambda/clinic-frontdesk-managed-predictor"
  retention_in_days = 30
}

resource "aws_lambda_function" "predictor" {
  count         = var.enable_services ? 1 : 0
  function_name = "clinic-frontdesk-managed-predictor"
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.predictor.repository_url}:${var.image_tag}"
  role          = aws_iam_role.predictor.arn
  memory_size   = 1024
  timeout       = 30

  depends_on = [aws_iam_role_policy_attachment.predictor_logs, aws_cloudwatch_log_group.predictor]
}
