#!/usr/bin/env bash
set -euo pipefail

# Input is provided through trusted GitHub repository variables and job outputs.
: "${CLUSTER:?Set ECS_CLUSTER GitHub variable}"
: "${SERVICE:?Set ECS service variable}"
: "${CONTAINER:?Set ECS container name variable}"
: "${IMAGE_URI:?Missing ECR image URI}"

# Read the CURRENT task definition. This preserves environment and secret refs
# already defined in ECS without storing sensitive information in GitHub.
TASK_ARN="$(aws ecs describe-services \
  --cluster "$CLUSTER" --services "$SERVICE" \
  --query 'services[0].taskDefinition' --output text)"

if [[ -z "$TASK_ARN" || "$TASK_ARN" == "None" ]]; then
  echo 'ECS service was not found, or it has no task definition.' >&2
  exit 1
fi

aws ecs describe-task-definition --task-definition "$TASK_ARN" \
  --query 'taskDefinition' --output json > current-task.json

jq --arg container "$CONTAINER" --arg image "$IMAGE_URI" '
  if ([.containerDefinitions[].name] | index($container)) == null then
    error("Requested container is missing from task definition")
  else
    del(.taskDefinitionArn, .revision, .status, .requiresAttributes,
        .compatibilities, .registeredAt, .registeredBy,
        .deregisteredAt)
    | (.containerDefinitions[] | select(.name == $container) | .image) = $image
  end
' current-task.json > next-task.json

NEW_TASK_ARN="$(aws ecs register-task-definition \
  --cli-input-json file://next-task.json \
  --query 'taskDefinition.taskDefinitionArn' --output text)"

aws ecs update-service --cluster "$CLUSTER" --service "$SERVICE" \
  --task-definition "$NEW_TASK_ARN" >/dev/null

aws ecs wait services-stable --cluster "$CLUSTER" --services "$SERVICE"
echo "Deployed $SERVICE with $IMAGE_URI"
