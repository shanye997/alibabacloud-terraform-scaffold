# GitHub Integration - OSS MNS Relay Mode

CI/CD integration solution based on GitHub Actions and Alibaba Cloud IacService, implementing automated Terraform Stack deployments through the OSS MNS relay mode.

> **🌐 Language**：[中文文档](README-CN.md) | [English Docs](README.md)

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
  - [Initialize Cloud Infrastructure](#initialize-cloud-infrastructure)
  - [GitHub Configuration](#github-configuration)
- [GitHub Actions Workflow Configuration](#github-actions-workflow-configuration)
  - [Workflow Files](#workflow-files)
  - [Workflow Dependencies](#workflow-dependencies)
- [Daily Usage](#daily-usage)
  - [Create IacService Stacks](#create-iac-service-stacks)
  - [Change Workflow](#change-workflow)
  - [Runtime Parameter Reference](#runtime-parameter-reference)
- [Operations Reference](#operations-reference)
  - [Troubleshooting](#troubleshooting)
  - [CI Dependencies](#ci-dependencies)
  - [Multi-Environment Configuration](#multi-environment-configuration)
- [Appendix](#appendix)
  - [Workflow Design Details](#workflow-design-details)

---

# Overview

```
Developer → PR Comment → GitHub Actions → OSS (code package + trigger file) → MNS → IacService → Execute Deployment → OSS (results) → GitHub Actions → PR Comment
```

The diagram above shows the complete execution flow from GitHub, relaying through OSS to manage IacService Stacks. The interaction between OSS and IacService is fixed. The interaction from GitHub Actions to OSS is handled through workflows that manage code and trigger file uploads as well as execution log retrieval.

Workflows are triggered via PR comments, supporting the following commands:

```
iac terraform plan [-profile=<profile>] [-stack=<stack>]
iac terraform apply [-profile=<profile>] [-stack=<stack>]
```

> **Auto-inference**: When a PR only contains changes in the `deployments/` directory, the `-profile` and `-stack` parameters can be omitted — the workflow will automatically infer them from the changed files. If the PR contains changes in other directories, both parameters must be specified manually.

The initialization scripts (`bootstrap/terraform-dev/`) create the following cloud resources:

| Resource | Description |
|----------|-------------|
| **RAM Role** | Service role required by IacService to execute Terraform operations, default name `IaCServiceStackRole`. The example grants `AdministratorAccess` — **in production, follow the principle of least privilege and only grant RAM permissions required by the Terraform resources** |
| **OSS Bucket** | Object storage bucket for code packages and trigger files, with versioning enabled and automatic cleanup of non-current versions after 30 days |
| **MNS Topic/Queue/Subscription** | Message service topic, queue, and subscription for forwarding OSS events to the IacService message queue |
| **OSS Event Rule** | Monitors creation and modification events of `.json` files in the Bucket to trigger MNS notifications |

Helper scripts (`scripts/`):

| Script | Language | Dependencies | Purpose |
|--------|----------|-------------|---------|
| `upload_to_oss.py` | Python 3.12 | `alibabacloud-oss-v2` | Uploads files to OSS. Supports version deduplication via `--unique_key` parameter (identical code is not re-uploaded). Reads credentials from environment variables `OSS_ACCESS_KEY_ID`/`OSS_ACCESS_KEY_SECRET`/`OSS_REGION`/`OSS_BUCKET` |
| `parse_exec_result.py` | Python 3.12 | `alibabacloud-oss-v2`, `PyYAML` | Polls OSS for IacService execution result files, downloads and parses JSON into formatted Markdown tables. Supports multi-profile parallel polling (multi-threaded), default timeout 600 seconds |

---

# Prerequisites

## Initialize Cloud Infrastructure

### 1. Prepare Code Repository

Create a new repository on GitHub, copy all files from the `ci-templates/oss-mns-relay/github/` directory to your repository root, commit and push:

```bash
git add .
git commit -m "init"
git push --set-upstream origin main
```

### 2. Create Temporary RAM User

Create an API-access-only RAM User in Alibaba Cloud, create an AK key pair, and grant the following permissions:
- `AliyunRAMFullAccess`
- `AliyunMNSFullAccess`
- `AliyunOSSFullAccess`

Configure this AK in local environment variables (can be deleted after initialization):

```bash
export ALICLOUD_ACCESS_KEY="xxx"
export ALICLOUD_SECRET_KEY="xxx"
```

### 3. Execute Terraform Initialization

```bash
cd bootstrap/terraform-dev
terraform init
terraform plan
terraform apply
```

After initialization, `outputs.tf` outputs the following:
- `oss_bucket`: OSS Bucket name
- `oss_region`: Bucket region
- `ram_role_arn`: RAM Role ARN

> **Optional Configuration**: To modify the OSS Bucket name or RAM Role name, edit the corresponding variables in `bootstrap/terraform-dev/variables.tf`. Default values are:
> - OSS Bucket: `iac-stack-dev-` + random number
> - RAM Role: `IaCServiceStackRole`

### 4. Cleanup and Configuration

- Delete the temporary AK and associated RAM User
- Fill in the `oss_bucket` and `oss_region` from initialization output into `deployments/[env]/profile.yaml`

> **Multi-Environment Note**: For multiple environments (dev, staging, prod, etc.), each environment requires an independent bootstrap configuration with different RAM Roles and OSS Buckets for complete environment isolation. See [Multi-Environment Configuration](#multi-environment-configuration).

---

## GitHub Configuration

### 1. Create RAM User and Configure OSS Permissions

Create an API-access-only RAM User, create an AK, and grant the following minimum permissions (replace `Mybucket` with the actual Bucket name):

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "oss:PutObject",
        "oss:GetObject",
        "oss:GetObjectVersion",
        "oss:ListObjectVersions"
      ],
      "Resource": [
        "acs:oss:*:*:Mybucket",
        "acs:oss:*:*:Mybucket/*"
      ]
    }
  ]
}
```

### 2. Configure GitHub Secrets

Add the AK to the GitHub repository's Secrets, storing each Key and Value separately. The Key name corresponds to the key pair name configured in `profile.yaml`:

| Secrets Key | Secrets Value |
|-------------|---------------|
| `DEV_ACCESS_KEY_ID` | `"xxx"` |
| `DEV_ACCESS_KEY_SECRET` | `"xxx"` |

> For multiple environments, configure with environment prefixes, e.g., `STAGING_ACCESS_KEY_ID`, `STAGING_ACCESS_KEY_SECRET`, `PROD_ACCESS_KEY_ID`, `PROD_ACCESS_KEY_SECRET`

### 3. Declare Workflow Environment Variables

In `.github/workflows/pull-request-comment.yml` and `scheduled-check.yml`, declare Secrets references in the `env` block:

```yaml
env:
  DEV_ACCESS_KEY_ID: ${{ secrets.DEV_ACCESS_KEY_ID }}
  DEV_ACCESS_KEY_SECRET: ${{ secrets.DEV_ACCESS_KEY_SECRET }}
  # Other environments...
```

> **Note**: All workflow files (including shared workflows) that use hardcoded environment prefixes must also have the corresponding Secrets references added.

### 4. Initialize OSS

Commit the current branch code and manually trigger the **Scheduled Check** workflow in GitHub Actions to initialize OSS (select the current branch before running, no need to check "Whether to run detect check").

> If the run fails, it may be because multiple environments exist under `deployments/` but are not fully configured. Delete extra environment directories or complete their configuration.

---

# GitHub Actions Workflow Configuration

The repository contains 5 workflow files in two categories:

## Workflow Files

**Main workflows** (triggered directly by GitHub events):

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `pull-request-comment.yml` | PR comment created/edited | Parses `iac terraform plan/apply` commands, packages and uploads code, triggers IacService execution, writes results back to PR |
| `scheduled-check.yml` | Manual trigger / scheduled | Uploads source packages for all environments to OSS, optionally triggers drift detection |

**Shared workflows** (called by main workflows, can be extracted for reuse):

| Workflow | Caller | Purpose |
|----------|--------|---------|
| `shared-ci-get-pull-request-info.yml` | `pull-request-comment` | Validates PR mergeability, parses `-profile`/`-stack` parameters from comments, auto-infers affected stacks from changed files |
| `shared-ci-upload-source-package.yml` | `scheduled-check` | Iterates all profiles, runs `make build-package` to build source packages and upload to OSS; single profile failure does not affect others |
| `shared-ci-upload-trigger-file.yml` | `pull-request-comment` | Builds source packages for each profile, creates trigger files containing execution commands and changed stacks, uploads to OSS; any failure terminates immediately |

## Workflow Dependencies

```
pull-request-comment.yml
├── shared-ci-get-pull-request-info.yml    # Step 1: Parse commands, get PR info
├── shared-ci-upload-trigger-file.yml      # Step 2: Package and upload code + trigger files
└── get_exec_result (inline job)           # Step 3: Poll results → write back to PR Comment

scheduled-check.yml
├── shared-ci-upload-source-package.yml    # Step 1: Upload source packages for all profiles
└── get_exec_result (inline job)           # Step 2: Poll detection results (only when run_detect=true)
```

---

# Daily Usage

## Create IacService Stacks

Before executing code, you first need to create the corresponding Stacks on Alibaba Cloud IacService to host the code execution. After repository code initialization, first upload code to OSS via the Scheduled Check workflow, then create all corresponding Stacks at once on the IacService console.

Go to Alibaba Cloud IacService (https://iac.console.aliyun.com/stack) to create Stacks:

- **Stack Name**: Recommended to match the module directory name under `stacks/`
- **OSS Bucket**: Select from the dropdown (created by bootstrap initialization)
- **OSS Object**: Select the OSS Object path for the corresponding environment
- **RAM Role**: Select from the dropdown (created by bootstrap initialization)
- **Working Directory**: Fill in the stack's relative path, e.g., `stacks/demo`

> **Batch Creation**: It is recommended to create all Stacks defined under the `stacks/` directory at once. Each Stack corresponds to an independent resource stack. After creation, an initial `plan` will be automatically executed to verify configuration correctness.

## Change Workflow

1. Create a development branch, commit code changes, push to GitHub

```bash
git checkout -b dev
# Modify configurations in stacks/ or deployments/[env]/...
git add .
git commit -m "update stack config"
git push --set-upstream origin dev
```

2. Create a PR to the main branch (e.g., `main`), enter commands in PR comments to trigger deployment:

```bash
iac terraform plan -profile=dev -stack=demo
iac terraform apply -profile=dev -stack=demo
```

3. Execution results are automatically written back to PR comments — confirm apply results meet expectations
4. After review approval, merge changes to the main branch

## Runtime Parameter Reference

Runtime parameters are passed via PR comments in the following format:

```
iac terraform plan/apply [-profile=<profileName>] [-stack=<StackName>]
```

**Parameter Reference**:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `-profile` | Yes* | Execution environment, corresponds to environment name under `deployments/` directory |
| `-stack` | Yes* | Target stack path, supports directory nesting, e.g., `demo/subDir` |

> *When a PR only contains changes in the `deployments/` directory, both parameters can be omitted — the workflow will auto-infer from changed files.

**Notes**:

- A PR can be reused until merged, but creating independent PRs for each task is recommended for traceability
- `plan` must be executed before each `apply`; `plan` can be executed multiple times consecutively
- Different environment `-profile` values correspond to different Alibaba Cloud accounts and resources, with no mutual impact

---

# Operations Reference

## Troubleshooting

| Issue | Resolution |
|-------|-----------|
| No deployment response | Check if GitHub Secrets are configured correctly, if OSS/MNS services are operational, if RAM permissions are sufficient |
| Command not recognized | Confirm PR Comment format is `iac terraform plan/apply`, note the prefix must match exactly |
| `make build-package` fails | Confirm the repository root contains a Makefile with the `build-package` target |
| Profile upload fails | Check if `access_key_id`/`access_key_secret` in `deployments/[env]/profile.yaml` match the Key names in GitHub Secrets |
| Result retrieval timeout | Default polling timeout is 600 seconds, check IacService console to confirm if the Stack is executing |
| Partial multi-environment failure | Check GitHub Actions logs, `shared-ci-upload-source-package` will list the failed profile names |
| View detailed errors | Check GitHub Actions run logs, or inspect trigger and result files in OSS |

## CI Dependencies

GitHub Actions runtime requires the following dependencies:

| Dependency | Purpose | Provisioning |
|------------|---------|-------------|
| **Python 3.12** | Running `upload_to_oss.py` and `parse_exec_result.py` scripts | Auto-installed via `actions/setup-python@v5` |
| **alibabacloud-oss-v2** | Alibaba Cloud OSS SDK for uploading code packages and retrieving execution results | `pip install alibabacloud-oss-v2` |
| **PyYAML** | Parsing `profile.yaml` and credential files | `pip install PyYAML` |
| **make** | Running `make build-package` to build source packages | Pre-installed in `ubuntu-latest` image |
| **curl / jq** | Fetching PR info, parsing JSON responses | Pre-installed in `ubuntu-latest` image |

> **Offline Environment Note**: If GitHub Actions runs on self-hosted Runners without public internet access, pre-install the above dependencies in the Runner image or cache dependency packages in a private repository/artifact store.

## Multi-Environment Configuration

To add a new Alibaba Cloud account (e.g., adding a `test` environment), complete the following:

### 1. Create Bootstrap Configuration

```bash
mkdir -p bootstrap/terraform-test
cp bootstrap/terraform-dev/*.tf bootstrap/terraform-test/

cd bootstrap/terraform-test

# Modify bucket_name and ram_role_name in variables.tf to ensure they differ from other environments
vim variables.tf

terraform init
terraform apply
```

> **Important**: Each environment must use an independent state file. Do not copy `*.tfstate` state files.

### 2. Create Deployments Configuration

```bash
cp -r deployments/dev deployments/test
cd deployments/test
```

Modify `profile.yaml` to update `oss_bucket`, `oss_region`, and `account_id` to the values from step 1 output, and change the AK variable names in `profile.yaml` to the new GitHub Secrets keys.

### 3. Configure GitHub Secrets

In GitHub repository Settings → Secrets and variables → Actions, add:

| Secrets Key | Secrets Value |
|-------------|---------------|
| `TEST_ACCESS_KEY_ID` | New account AccessKey ID |
| `TEST_ACCESS_KEY_SECRET` | New account AccessKey Secret |

### 4. Declare CI Environment Variables

In `.github/workflows/pull-request-comment.yml` and `scheduled-check.yml`, add references for the new account in the `env` block:

```yaml
env:
  # ... other environments
  TEST_ACCESS_KEY_ID: ${{ secrets.TEST_ACCESS_KEY_ID }}
  TEST_ACCESS_KEY_SECRET: ${{ secrets.TEST_ACCESS_KEY_SECRET }}
```

> **Note**: All workflow files (including shared workflows) that use hardcoded environment prefixes (e.g., `DEV_`, `PROD_`) must also have `TEST_` references added.

### 5. Create Stack

Go to the Alibaba Cloud IaC console to create Stacks, selecting the OSS Bucket and RAM Role created in step 1. Refer to the [Create IacService Stacks](#create-iac-service-stacks) section.

### 6. Verify Configuration

After committing the configuration, manually trigger the **Scheduled Check** workflow to confirm the new environment's source package uploads successfully.

> **Account Isolation Recommendation**: Each Alibaba Cloud account should have independent RAM Roles, OSS Buckets, and MNS resources, with credentials managed through separate GitHub Secrets for complete isolation. It is recommended to allocate different environments to different Alibaba Cloud master accounts and manage them centrally through Alibaba Cloud Resource Directory.

---

# Appendix

## Workflow Design Details

### pull-request-comment.yml

**Trigger**: PR comment created or edited (`issue_comment: [created, edited]`)

**Flow**:

1. **get_trigger_info** — Calls `shared-ci-get-pull-request-info.yml`, parses commands from comments, gets PR head SHA and base ref, infers affected stacks
2. **process_trigger_file** — Calls `shared-ci-upload-trigger-file.yml`, packages code and uploads trigger files to OSS
3. **get_exec_result** — Polls OSS for execution results, formats and writes back to PR comment

**Supported command formats**:

```
iac terraform plan [-profile=<profile>] [-stack=<stack>]
iac terraform apply [-profile=<profile>] [-stack=<stack>]
```

> When a PR only contains changes in the `deployments/` directory, the workflow auto-infers profiles and stacks from changed files, making `-profile` and `-stack` optional. If the PR contains changes in other directories, both parameters must be specified manually.

### scheduled-check.yml

**Trigger**: Manual trigger (`workflow_dispatch`) or scheduled run

**Flow**:

1. **process_code** — Calls `shared-ci-upload-source-package.yml`, processes source package uploads for all profiles (`profiles: all`); if `run_detect` is enabled, also creates detection trigger files
2. **get_exec_result** — Only executes when `run_detect=true` or on scheduled triggers, fetches and outputs execution results

**Primary uses**:

- **Drift Detection**: Triggered via `run_detect=true`, automatically detects drift between actual cloud resources and Terraform configurations
- **Source Package Initialization**: Uploads source packages to OSS during initial setup, preparing for PR deployments
- **Code Integrity Verification**: Periodically verifies that all environments' code can build successfully

> **Code Source**: Uploads code from the `main` branch by default. Drift detection compares cloud resource state against `main` branch configurations, generating detection reports when drift is found.

### Shared Workflows

**shared-ci-get-pull-request-info.yml**

Retrieves PR details and parses command parameters. Main functions: validates PR mergeability, extracts head SHA and base ref, parses `-profile`/`-stack` parameters, auto-infers affected stacks from changed files.

Main outputs: `command`, `base_ref`, `head_sha`, `all_changed_stacks`

**shared-ci-upload-source-package.yml**

Builds source packages and uploads to OSS, supporting multi-profile batch processing. Runs `make build-package PROFILE=<profile>` for each profile to build code packages, uploads via `upload_to_oss.py`. Single profile failure does not affect others; all failures are summarized after completion.

**shared-ci-upload-trigger-file.yml**

Uploads source packages and trigger files to OSS, initiating IacService execution. Parses the `all_changed_stacks` parameter, creates trigger files (JSON format) for each profile containing execution commands, code paths, and changed stacks. Uses a fail-fast strategy — any profile failure terminates immediately.

Trigger file structure example:

```json
{
  "id": "PR123-[user]-1",
  "action": "terraform plan",
  "codeHeadSha": "abc123...",
  "codeVersionId": "v1",
  "codePackagePath": "oss::https://bucket.oss-cn-beijing.aliyuncs.com/repositories/org/repo/main/code.zip",
  "execResultPath": "oss::https://bucket.oss-cn-beijing.aliyuncs.com/notifications/org/repo/main/PR123-[user]-1.json",
  "changedFolders": "stacks/demo/"
}
```
