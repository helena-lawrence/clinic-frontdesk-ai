terraform {
  backend "s3" {
    bucket       = "clinic-frontdesk-tfstate-202506667107-eu-west-2"
    key          = "clinic-frontdesk/prod.tfstate"
    region       = "eu-west-2"
    encrypt      = true
    use_lockfile = true
  }
}
