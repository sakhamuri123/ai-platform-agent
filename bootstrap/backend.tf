#bootstrap/backend.tf
provider "aws" {
    region = "ap-south-1"
}

resource "aws_s3_bucket" "tf_state" {
    bucket = "rajesh-platform-tf-state"

    lifecycle {
        prevent_destroy = true  
    }
}

resource "aws_s3_bucket_versioning" "tf_state_versioning" {
    bucket = aws_s3_bucket.tf_state.id
    versioning_configuration {
        status = "Enabled"
    }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tf_state_encryption" {
    bucket = aws_s3_bucket.tf_state.id
    rule {
        apply_server_side_encryption_by_default {
            sse_algorithm = "AES256"
        }
    }
}

resource "aws_s3_bucket_public_access_block" "tf_state_public_access_block" {
    bucket = aws_s3_bucket.tf_state.id
    block_public_acls       = true
    block_public_policy     = true
    ignore_public_acls      = true
    restrict_public_buckets = true
}

resource "aws_dynamodb_table" "tf_lock" {
    name = "terraform-locks"
    billing_mode = "PAY_PER_REQUEST"
    hash_key = "LockID"
    attribute {
        name = "LockID"
        type = "S"
    }
}
