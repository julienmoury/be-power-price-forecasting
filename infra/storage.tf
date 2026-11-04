# ECR: the image of the project, the last 5 kept.
resource "aws_ecr_repository" "app" {
  name                 = local.name
  image_tag_mutability = "MUTABLE" # a re-run of the same commit pushes the same tag
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true # basic scanning, free
  }
}

resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the last 5 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = { type = "expire" }
    }]
  })
}

# Data bucket, private: cache/ (raw ENTSO-E and SMARD downloads, never public) and state/
# (the live files of the repository: results/forecasts/live, results/dnn/live,
# results/live, live).
resource "aws_s3_bucket" "data" {
  bucket        = local.data_bucket
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    id     = "old-versions"
    status = "Enabled"
    filter {}
    # Every run rewrites the cache: keep 30 days of old versions, not all of them.
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }

  depends_on = [aws_s3_bucket_versioning.data]
}

# Site bucket, private: read by CloudFront only (site.tf).
resource "aws_s3_bucket" "site" {
  bucket        = local.site_bucket
  force_destroy = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "bucket" {
  for_each = { data = aws_s3_bucket.data.id, site = aws_s3_bucket.site.id }
  bucket   = each.value

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "bucket" {
  for_each = { data = aws_s3_bucket.data.id, site = aws_s3_bucket.site.id }
  bucket   = each.value

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "bucket" {
  for_each = { data = aws_s3_bucket.data.id, site = aws_s3_bucket.site.id }
  bucket   = each.value

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

data "aws_iam_policy_document" "data_bucket" {
  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.data.arn, "${aws_s3_bucket.data.arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "data" {
  bucket     = aws_s3_bucket.data.id
  policy     = data.aws_iam_policy_document.data_bucket.json
  depends_on = [aws_s3_bucket_public_access_block.bucket]
}
