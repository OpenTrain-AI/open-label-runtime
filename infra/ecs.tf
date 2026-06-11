resource "aws_cloudwatch_log_group" "main" {
  name              = "/ecs/${local.name}"
  retention_in_days = 30
}

resource "aws_ecs_cluster" "main" {
  name = local.name
}

data "aws_kms_alias" "ssm" {
  name = "alias/aws/ssm"
}

resource "aws_iam_role" "task_exec" {
  name = "${local.name}-exec"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "task_exec_managed" {
  role       = aws_iam_role.task_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "task_exec_ssm" {
  name = "ssm-secrets"
  role = aws_iam_role.task_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ssm:GetParameters"]
        Resource = "arn:aws:ssm:${local.region}:${local.account_id}:parameter${local.ssm_prefix}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = data.aws_kms_alias.ssm.target_key_arn
      },
    ]
  })
}

resource "aws_iam_role" "task" {
  name = "${local.name}-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "task_s3" {
  name = "media-bucket-rw"
  role = aws_iam_role.task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:GetBucketLocation"]
        Resource = aws_s3_bucket.media.arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:AbortMultipartUpload",
        ]
        Resource = "${aws_s3_bucket.media.arn}/*"
      },
    ]
  })
}

locals {
  image = "${aws_ecr_repository.runtime.repository_url}:${var.image_tag}"

  app_environment = [
    { name = "DJANGO_DB", value = "default" },
    { name = "POSTGRE_HOST", value = aws_db_instance.main.address },
    { name = "POSTGRE_PORT", value = "5432" },
    { name = "POSTGRE_NAME", value = "labelstudio" },
    { name = "POSTGRE_USER", value = "labelstudio" },
    { name = "POSTGRE_SSL_MODE", value = "require" },
    { name = "LABEL_STUDIO_HOST", value = "https://${local.domain}" },
    { name = "CSRF_TRUSTED_ORIGINS", value = "https://${local.domain}" },
    { name = "LABEL_STUDIO_USERNAME", value = var.ls_username },
    { name = "LABEL_STUDIO_ENABLE_LEGACY_API_TOKEN", value = "1" },
    { name = "STORAGE_TYPE", value = "s3" },
    { name = "STORAGE_AWS_BUCKET_NAME", value = aws_s3_bucket.media.bucket },
    { name = "STORAGE_AWS_REGION_NAME", value = local.region },
    { name = "STORAGE_AWS_FOLDER", value = "media" },
    { name = "OPEN_LABEL_CONTROL_PLANE_BASE_URL", value = var.control_plane_base_url },
    { name = "WEBHOOK_TIMEOUT", value = "5" },
    { name = "SSRF_PROTECTION_ENABLED", value = "true" },
    { name = "SENTRY_DSN", value = "" },
    { name = "FRONTEND_SENTRY_DSN", value = "" },
    { name = "COLLECT_ANALYTICS", value = "0" },
    { name = "LATEST_VERSION_CHECK", value = "0" },
    { name = "SESSION_COOKIE_SECURE", value = "1" },
    { name = "CSRF_COOKIE_SECURE", value = "1" },
    { name = "JSON_LOG", value = "1" },
    { name = "UWSGI_PROCESSES", value = "2" },
    { name = "UWSGI_WORKER_RELOAD_ON_RSS", value = "600" },
  ]

  app_secrets = [
    for key in [
      "SECRET_KEY",
      "POSTGRE_PASSWORD",
      "LABEL_STUDIO_PASSWORD",
      "LABEL_STUDIO_USER_TOKEN",
      "OPEN_LABEL_WEBHOOK_SECRET",
      "OPEN_LABEL_SESSION_SIGNING_SECRET",
    ] : {
      name      = key
      valueFrom = "arn:aws:ssm:${local.region}:${local.account_id}:parameter${local.ssm_prefix}/${key}"
    }
  ]
}

resource "aws_ecs_task_definition" "main" {
  family                   = local.name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 1024
  memory                   = 2048
  execution_role_arn       = aws_iam_role.task_exec.arn
  task_role_arn            = aws_iam_role.task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name        = "app"
      image       = local.image
      command     = ["label-studio-uwsgi"]
      essential   = true
      environment = local.app_environment
      secrets     = local.app_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.main.name
          "awslogs-region"        = local.region
          "awslogs-stream-prefix" = "app"
        }
      }
    },
    {
      name      = "nginx"
      image     = local.image
      command   = ["nginx"]
      essential = true
      environment = [
        { name = "APP_HOST", value = "localhost" },
      ]
      portMappings = [
        { containerPort = 8085, protocol = "tcp" }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.main.name
          "awslogs-region"        = local.region
          "awslogs-stream-prefix" = "nginx"
        }
      }
    },
  ])
}

resource "aws_ecs_service" "main" {
  name            = local.name
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.main.arn
  desired_count   = var.service_desired_count
  launch_type     = "FARGATE"

  health_check_grace_period_seconds = 300

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.svc.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.main.arn
    container_name   = "nginx"
    container_port   = 8085
  }

  depends_on = [aws_lb_listener.https]
}
