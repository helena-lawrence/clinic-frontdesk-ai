# Fresh AWS deployment

This configuration creates a separate VPC, private PostgreSQL database, three ECR repositories, a private Application Load Balancer, a CloudFront HTTPS URL, a Cognito user pool, an ECS Fargate cluster with API and UI services, and a Lambda predictor. Existing clinic AWS resources are not imported or changed.

The only bootstrap resources reused are the existing S3 state bucket `clinic-frontdesk-tfstate-202506667107-eu-west-2` and GitHub OIDC role named by `AWS_TERRAFORM_ROLE_ARN`. The role must have permissions to provision this stack and push to the new ECR repositories. Its state-bucket policy alone is insufficient.

## First deployment

1. Ensure the GitHub repository variable `AWS_TERRAFORM_ROLE_ARN` points to the Terraform role, and that its OIDC trust allows the `production` GitHub environment. Keep the `production` environment restricted to `main`.
2. On `ClinicGitHubTerraformRole`, add [ClinicTerraformDeploy](../iam/ClinicTerraformDeploy.json) as a new inline policy. In **IAM → Policies**, create two customer managed policies using the exact file names without the `.json` extension: [ClinicTerraformInfrastructure](../iam/ClinicTerraformInfrastructure.json) and [ClinicWorkloadBoundary](../iam/ClinicWorkloadBoundary.json). Attach **ClinicTerraformInfrastructure** to the GitHub role. Terraform sets **ClinicWorkloadBoundary** as the maximum permissions for the four ECS and Lambda roles it creates. Create the boundary at the default IAM path `/`. Some networking permissions cover other VPC resources in London and CloudFront updates cover distributions in this account. Review those scopes before granting them.
3. Merge or push these files to `main` after review. Run **Clinic Front Desk - CI/CD** with `bootstrap=true`. Optionally enter a demo patient email to invite that user and link it to synthetic patient `P001`.
4. The workflow creates the foundation, builds three images with the commit SHA, applies the services, and runs a one-off ECS task that creates the schema and generates fresh synthetic records and embeddings. It prints the CloudFront HTTPS URL.
5. Set the repository variable `ENABLE_ECS_DEPLOY=true` for future `main` pushes to publish images and apply service updates automatically. Leave `ENABLE_ECR_PUBLISH` and the old publisher/deployer role variables unused for this new stack.

If `bootstrap=true` is run after services already exist, the workflow stops before applying `enable_services=false`; this prevents it from tearing down live services.

## Notes

- PostgreSQL starts empty. The initialization task generates synthetic demo data inside the new deployment; it does not copy from the old database.
- Cognito permits admin-created users only. Supply `patient_email` in a manual workflow run to invite and link a test user to `P001`. The invitation email comes from Cognito.
- The CloudFront URL uses AWS's default certificate, so no custom domain or ACM certificate is needed. The load balancer is private and reached through a CloudFront VPC origin.
- ECS tasks currently run in public subnets with public IP addresses for outbound AWS API access. Their security group admits application traffic only from the private load balancer. The database is private.
- RDS deletion protection and Terraform `prevent_destroy` protect the new database. The generated password is managed by RDS Secrets Manager and injected into tasks at startup; automatic rotation is disabled until the app can refresh its connections.
- This is a synthetic demo. The API keeps login sessions in one process, so a task restart signs users out. It is not ready for real patient data.
- CloudFront, the load balancer, ECS, RDS, public IPv4 addresses, and Bedrock calls can incur charges even when traffic is low.
