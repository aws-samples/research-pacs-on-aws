# Operate the Solution

## Logging

The logs of the Orthanc servers and of the solution components are available in Amazon CloudWatch Logs. There is one log group per component whose log group name starts with `{stack-name}/app-logs/`. The access logs (user activity in the self-service portal) are stored in the log group `{stack-name}/access-logs`.

## Monitoring

The solution uses only services that are managed by AWS: the Docker containers are orchestrated with Amazon ECS, and run on AWS Fargate. The database is executed by Amazon Aurora.

## Upgrading

To upgrade the Orthanc server or the solution components, you can start a new build of the associated AWS CodeBuild project. This will automatically create a new Docker image and tag it with the tag `latest`. Then, stop the current task in Amazon ECS, and it will automatically be replaced by a new task running the latest version of the Docker container. The previous versions of the Docker images are retained in the Amazon ECR repositories.
