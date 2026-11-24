resource "aws_cognito_user_pool" "clinic" {
  name                     = "clinic-frontdesk-managed"
  auto_verified_attributes = ["email"]
  username_attributes      = ["email"]

  password_policy {
    minimum_length    = 12
    require_lowercase = true
    require_uppercase = true
    require_numbers   = true
    require_symbols   = true
  }

  admin_create_user_config {
    allow_admin_create_user_only = true
  }
}

resource "aws_cognito_user_pool_client" "clinic" {
  name                                 = "clinic-frontdesk-managed-web"
  user_pool_id                         = aws_cognito_user_pool.clinic.id
  generate_secret                      = false
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email"]
  callback_urls                        = ["https://${aws_cloudfront_distribution.clinic.domain_name}/auth/callback"]
  logout_urls                          = ["https://${aws_cloudfront_distribution.clinic.domain_name}/"]
  supported_identity_providers         = ["COGNITO"]
  prevent_user_existence_errors        = "ENABLED"
}

resource "aws_cognito_user_pool_domain" "clinic" {
  domain                = var.cognito_domain_prefix
  user_pool_id          = aws_cognito_user_pool.clinic.id
  managed_login_version = 1
}
