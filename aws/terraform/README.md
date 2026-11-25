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

## Delete the Terraform-managed stack

1. Set the GitHub repository variable `ENABLE_ECS_DEPLOY=false` before pushing the teardown workflow to `main` if you want subsequent pushes to run validation only.
2. In **Actions → Clinic Front Desk - Terraform teardown → Run workflow**, select `main` and `preview`. The job reads the production S3 state and prints the proposed deletions. Its **Generate IAM permissions for review** step produces an IAM Policy Autopilot report from that plan. The existing deploy policies cover provisioning and omit several delete actions. Review the generated permissions, scope them to the listed clinic resources and attach the required supplemental permissions to `ClinicGitHubTerraformRole` before running `destroy`. Each customer-managed policy can contain up to 6,144 non-whitespace characters.
3. When ready to remove the stack, run the same workflow with `destroy` and enter `DELETE clinic-frontdesk-managed`. This deletes the managed PostgreSQL database **without a final snapshot**, Cognito users, ECR repositories and images, log groups, and the remaining infrastructure in this state. The original manually created database, Terraform S3 backend, GitHub role and other bootstrap resources are outside this state.
4. Look for **Teardown complete** in the run summary. After a partial failure, correct the reported error and start a new preview or destroy run. Terraform uses the latest state on each run. You can remove the supplemental teardown permissions after completion.

## Notes

- PostgreSQL starts empty. The initialization task generates synthetic demo data inside the new deployment; it does not copy from the old database.
- Cognito permits admin-created users only. Supply `patient_email` in a manual workflow run to invite and link a test user to `P001`. The invitation email comes from Cognito.
- The CloudFront URL uses AWS's default certificate, so no custom domain or ACM certificate is needed. The load balancer is private and reached through a CloudFront VPC origin.
- ECS tasks currently run in public subnets with public IP addresses for outbound AWS API access. Their security group admits application traffic only from the private load balancer. The database is private.
- RDS deletion protection and Terraform `prevent_destroy` protect the new database. The generated password is managed by RDS Secrets Manager and injected into tasks at startup; automatic rotation is disabled until the app can refresh its connections.
- This is a synthetic demo. The API keeps login sessions in one process, so a task restart signs users out. It is not ready for real patient data.
- CloudFront, the load balancer, ECS, RDS, public IPv4 addresses, and Bedrock calls can incur charges even when traffic is low.
