resource "aws_db_subnet_group" "clinic" {
  name       = "clinic-frontdesk-managed"
  subnet_ids = aws_subnet.database[*].id
}

resource "aws_db_instance" "clinic" {
  identifier                  = "clinic-frontdesk-managed-db"
  engine                      = "postgres"
  engine_version              = "17.11"
  instance_class              = "db.t4g.micro"
  allocated_storage           = 20
  max_allocated_storage       = 100
  storage_encrypted           = true
  db_name                     = "clinicdb"
  username                    = "clinic_admin"
  manage_master_user_password = true
  db_subnet_group_name        = aws_db_subnet_group.clinic.name
  vpc_security_group_ids      = [aws_security_group.database.id]
  publicly_accessible         = false
  backup_retention_period     = 1
  deletion_protection         = true
  skip_final_snapshot         = false
  final_snapshot_identifier   = "clinic-frontdesk-managed-db-final"

  lifecycle {
    prevent_destroy = true
  }
}

# ECS injects the password when a task starts. Keep rotation disabled until
# application connections can reload credentials without replacing tasks.
resource "aws_secretsmanager_secret_rotation" "clinic_master" {
  secret_id        = aws_db_instance.clinic.master_user_secret[0].secret_arn
  rotation_enabled = false
}
