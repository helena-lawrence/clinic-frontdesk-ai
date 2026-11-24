CLINIC FRONT-DESK AI — GITHUB ACTIONS CI/CD

There are 3 jobs in .github/workflows/clinic-ci-cd.yml:
  validate: Automatically run Python syntax verification and build 2 images.
  publish: Automatically publish 2 ECR images IF repo variable ENABLE_ECR_PUBLISH=true.
  deploy: Update 2 ECS services IF repo variable ENABLE_ECS_DEPLOY=true AND
          GitHub production environment approval passes.

IMPORTANT SAFETY RULE:
  LEAVE ENABLE_ECS_DEPLOY=false until public HTTPS, Cognito callback, shared
  sessions, secure cookies, IAM, networking and ECS services are configured.
  The current backend is explicitly LOCALHOST-ONLY and is not safe to expose.

FILES TO COPY INTO EXISTING PROJECT:
  .github/workflows/clinic-ci-cd.yml
  .github/scripts/deploy-ecs-service.sh
  aws/iam/...  (reference templates; not executable unchanged)
  README_CICD.txt

BEFORE FIRST RUN:
  - Repository must use a 'main' branch (or edit the workflows and trust policies).
  - Copy and commit Dockerfile.api, Dockerfile.ui, requirements.container.txt,
    .dockerignore, and public AWS certificate certs/global-bundle.pem from Step 11.9.1.
  - Never commit .env, ~/.aws, passwords, access tokens or trained ML model files.
  - Project's Python files must be syntactically valid (CI runs compileall).

INITIAL CI TEST:
  git status
  git add .github README_CICD.txt
  git add Dockerfile.api Dockerfile.ui requirements.container.txt .dockerignore
  git add certs/global-bundle.pem
  git commit -m "Add clinic GitHub Actions CI/CD"
  git push origin main
  In GitHub > Actions, inspect 'Clinic Front Desk - CI/CD' validate job.
  Note: If Dockerfiles were committed already, git add still works.
  Note: If .dockerignore is ignored or certificate is missing, correct before commit.

STAGE 2 - ECR PUBLISH (after CI succeeds):
  AWS eu-west-2 > ECR > Create private repos:
    clinic-frontdesk-api
    clinic-frontdesk-ui
  AWS IAM > Identity providers > add GitHub OIDC with URL:
    https://token.actions.githubusercontent.com
    audience: sts.amazonaws.com
  Create IAM OIDC role for publishing; restrict trust to repo/main using
    aws/iam/github-oidc-publisher-trust.template.json
  Attach scoped ECR publisher policy using
    aws/iam/ecr-publisher-policy.template.json
  Replace ACCOUNT_ID and OWNER/REPOSITORY first.

  GitHub repository > Settings > Secrets and variables > Actions > Variables:
    AWS_PUBLISH_ROLE_ARN = ARN of publishing IAM role
    ENABLE_ECR_PUBLISH = true
  Push to main. This produces immutable commit-SHA-tagged ECR images.
  GitHub OIDC avoids saving AWS access keys in repository secrets.

STAGE 3 - ECS DEPLOY (AFTER production readiness):
  - Create production-ready ECS API/UI services and HTTPS routing.
  - Replace hardcoded localhost URLs and in-memory auth sessions.
  - Use secure cookies, shared session store and suitable VPC/IAM/secrets.
  - GitHub > Settings > Environments > create 'production'. Restrict deployment
    branches to main; enable required reviewers if your GitHub plan supports it.
  - Create a separate ECS deployer OIDC role with trust constrained to
    repo:OWNER/REPOSITORY:environment:production.
  - Give the role least-privilege ECS Describe/Update/RegisterTaskDefinition
    and scoped iam:PassRole for task/execution roles. Restrict resources.
  - Set GitHub Actions variables:
      AWS_DEPLOY_ROLE_ARN  = deployer role ARN
      ECS_CLUSTER          = your ECS cluster name
      ECS_API_SERVICE      = API service name
      ECS_UI_SERVICE       = UI service name
      ECS_API_CONTAINER    = API container name in ECS task definition
      ECS_UI_CONTAINER     = UI container name in ECS task definition
      ENABLE_ECS_DEPLOY    = true
  - Push main -> CI -> ECR -> approval -> ECS update services.
  - GitHub hosted Ubuntu runners have jq and AWS CLI (verify runner logs).

RISKS AND COST:
  CI container builds incur hosted runner minutes (plan dependent).
  ECR image storage, ECS tasks, load balancer, NAT/VPC endpoints, RDS and AWS
  inference may incur costs. Configure AWS Budgets alerts.
  This workflow is a deployment framework, NOT proof of production safety.
  Do not publish real patient data or credentials.
