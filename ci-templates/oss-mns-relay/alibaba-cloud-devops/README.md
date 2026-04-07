# Alibaba Cloud DevOps Integration - OSS MNS Relay Mode

CI/CD integration solution based on Alibaba Cloud DevOps (CodeUp + Flow) and Alibaba Cloud IacService, implementing automated Terraform Stack deployments through the OSS MNS relay mode.

> **🌐 Language**：[中文文档](README-CN.md) | [English Docs](README.md)

## Table of Contents

- [Alibaba Cloud DevOps Integration - OSS MNS Relay Mode](#alibaba-cloud-devops-integration---oss-mns-relay-mode)
  - [Table of Contents](#table-of-contents)
- [Overview](#overview)
- [Prerequisites](#prerequisites)
  - [Initialize Cloud Infrastructure](#initialize-cloud-infrastructure)
    - [1. Prepare Code Repository](#1-prepare-code-repository)
    - [2. Create Temporary RAM User](#2-create-temporary-ram-user)
    - [3. Execute Terraform Initialization](#3-execute-terraform-initialization)
    - [4. Cleanup and Configuration](#4-cleanup-and-configuration)
  - [Provision Alibaba Cloud DevOps](#provision-alibaba-cloud-devops)
    - [1. Create Alibaba Cloud DevOps RAM User and Configure Permissions](#1-create-alibaba-cloud-devops-ram-user-and-configure-permissions)
    - [2. Configure OSS Permissions](#2-configure-oss-permissions)
- [Pipeline Flow Configuration](#pipeline-flow-configuration)
  - [Pipeline Source](#pipeline-source)
  - [Stage 0: Code Upload](#stage-0-code-upload)
  - [Stage 1: Plan Review](#stage-1-plan-review)
  - [Stage 2: Execute Plan](#stage-2-execute-plan)
  - [Stage 3: Apply Review](#stage-3-apply-review)
  - [Stage 4: Execute Apply](#stage-4-execute-apply)
  - [Configure Pipeline Variables](#configure-pipeline-variables)
- [Daily Usage](#daily-usage)
  - [Create IacService Stacks](#create-iacservice-stacks)
    - [1. Upload Code to OSS](#1-upload-code-to-oss)
    - [2. Create Stacks](#2-create-stacks)
  - [Change Workflow](#change-workflow)
  - [Runtime Parameter Reference](#runtime-parameter-reference)
- [Operations Reference](#operations-reference)
  - [Troubleshooting](#troubleshooting)
  - [Multi-Environment Configuration](#multi-environment-configuration)
    - [1. Create Bootstrap Configuration](#1-create-bootstrap-configuration)
    - [2. Create Deployments Configuration](#2-create-deployments-configuration)
    - [3. Configure Alibaba Cloud DevOps Pipeline Variables](#3-configure-alibaba-cloud-devops-pipeline-variables)
    - [4. Verify Configuration](#4-verify-configuration)

---

# Overview

```
Developer → Alibaba Cloud DevOps Pipeline → OSS (code package + trigger file) → MNS → IacService → Execute Deployment → OSS (results) → Alibaba Cloud DevOps Pipeline → Output Results
```

The diagram above shows the complete execution flow from Alibaba Cloud DevOps, relaying through OSS to manage IacService Stacks. The interaction between OSS and IacService is fixed. The interaction from Alibaba Cloud DevOps to OSS requires implementing code and trigger file uploads as well as execution log retrieval using Alibaba Cloud DevOps pipeline capabilities.

The pipeline consists of 5 stages:

```
Code Upload → Plan Review → Execute Plan → Apply Review → Execute Apply
```

> **Note**: Alibaba Cloud DevOps does not support automatically triggering parameterized pipelines from merge requests, so a manual trigger + remark parameter approach is used. The actual change workflow is: commit code to development branch → create merge request → manually run validation pipeline → review approved → merge to main branch.

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

Create a new repository in Alibaba Cloud DevOps, copy all files from the `ci-templates/oss-mns-relay/alibaba-cloud-devops/` directory to your repository root, commit and push:

```bash
git init
git remote add origin git@codeup.aliyun.com:<org-id>/<repo-name>.git
git add .
git commit -m "init"
git push -u origin HEAD
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

## Provision Alibaba Cloud DevOps

### 1. Create Alibaba Cloud DevOps RAM User and Configure Permissions

1. Log in to the Alibaba Cloud DevOps account and create a RAM User for Alibaba Cloud DevOps access
2. Grant the RAM User the following permissions:
   - Alibaba Cloud DevOps-related permissions
   - OSS read/write permissions (for script-based Bucket creation and management)
   - Custom policy `IaCServiceStackFullAccess` (see [docs/iam-policies.md](../../../docs/iam-policies.md) for policy content)
3. Create an AccessKey (AK) for accessing Alibaba Cloud resources from Alibaba Cloud DevOps pipelines

### 2. Configure OSS Permissions

Grant the above RAM User read/write permissions on the OSS Bucket (replace `Mybucket` with the actual Bucket name):

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

---

# Pipeline Flow Configuration

Manually create stages and tasks in the Alibaba Cloud DevOps pipeline interface. The overall pipeline flow:

```
Code Upload → Plan Review → Execute Plan → Apply Review → Execute Apply
```

## Pipeline Source

1. Select the repository created in the previous step as the code repository
2. Set the default branch to the main branch or a commonly used development branch
3. Set the working directory to `code`. This name will be used in subsequent pipeline scripts

## Stage 0: Code Upload

New Task → Blank Template

**Step 1: Parse Runtime Parameters**

Add Step → Build → Execute Command. Validate remark parameter format, parse profile and stack information.

```bash
set -e

IFS=';' read -ra PROFILES <<< "${BUILD_REMARK}"

for i in "${!PROFILES[@]}"; do
  PART="${PROFILES[$i]}"
  
  if [[ "$PART" == *":"* ]]; then
    PROFILE_NAME=$(echo "$PART" | cut -d':' -f1)
    STACK_VALUES=$(echo "$PART" | cut -d':' -f2)
  else
    echo "Error: Profile '$PART' does not contain a colon separator" >&2
    exit 1
  fi
  
  if [ ! -d "deployments/$PROFILE_NAME" ]; then
    echo "Error: Profile '$PROFILE_NAME' does not exist in deployments directories" >&2
    exit 1
  fi
  
  if [ -z "$STACK_VALUES" ]; then
    echo "Error: No stack values provided for profile '$PROFILE_NAME'" >&2
    exit 1
  fi
  profiles+=("$PROFILE_NAME")
  stacks+=("$STACK_VALUES")
  
  echo "Profile $((i+1)): $PROFILE_NAME"
  echo "  Stacks: $STACK_VALUES"
  
done
```

**Step 2: Install Python**

Add Step → Build → Install Python. Select version 3.12

**Step 3: Install Python Dependencies**

Add Step → Build → Execute Command. Install dependencies required by Python scripts.

```bash
mkdir -p ~/.pip
cat > ~/.pip/pip.conf << 'EOF'
[global]
index-url = https://mirrors.aliyun.com/pypi/simple/
trusted-host = mirrors.aliyun.com
EOF

python -m pip install --upgrade pip
pip install alibabacloud-oss-v2
pip install PyYAML
```

**Step 4: Package and Upload**

Add Step → Build → Execute Command. Package and upload code for each environment in the input list.

```bash
echo "Creating source package..."
set -e

chmod +x scripts/yq
chmod +x scripts/*.py

YQ_CMD="./scripts/yq"
if [ ! -f "$$YQ_CMD" ]; then 
    YQ_CMD="scripts/yq"
fi
cd ..

IFS=';' read -ra PROFILES <<< "${BUILD_REMARK}"

version_ids_list=()

for i in "${!PROFILES[@]}"; do
    PART="${PROFILES[$i]}"
    profile=$(echo "$PART" | cut -d':' -f1)
    stack_values=$(echo "$PART" | cut -d':' -f2)

    echo ""
    echo "Processing profile: $profile"
    echo "  Stacks: $stack_values"
    codeDir="code-$profile"

    
    mkdir $codeDir && cp -rp code/* $codeDir/
    cd $codeDir
    rm -rf Python/

    echo "Building package for profile: $profile"
    make_output_file=$(mktemp)
    make build-package PROFILE=$profile 2>&1 | tee "$make_output_file"
    make_exit_code=${PIPESTATUS[0]}
    make_output=$(cat "$make_output_file")
    rm -f "$make_output_file"
    if [ "$make_exit_code" -ne 0 ]; then
        echo "Error: Failed to build package for profile: $profile"
        exit 1
    fi
    hash=$(echo "$make_output" | grep -o "Hash: [a-f0-9]*" | awk '{print $2}')

    profile_file="stacks/profile.yaml"
    if [ ! -f "$profile_file" ]; then
        echo "Error: Profile file not found: $profile_file"
        exit 1
    fi

    oss_region="cn-beijing"
    oss_bucket=$($YQ_CMD '.oss_bucket' "$profile_file")
    access_key_id_name=$($YQ_CMD '.access_key_id' "$profile_file")
    access_key_secret_name=$($YQ_CMD '.access_key_secret' "$profile_file")

    access_key_id="${!access_key_id_name}"
    access_key_secret="${!access_key_secret_name}"

    if [ -z "$access_key_id" ] || [ -z "$access_key_secret" ]; then
        echo "Error: Missing access key ID or access key secret"
        exit 1
    fi
    export OSS_BUCKET=$oss_bucket OSS_REGION=$oss_region OSS_ACCESS_KEY_ID=$access_key_id OSS_ACCESS_KEY_SECRET=$access_key_secret


    mv $codeDir.zip ../
    cd ../
    ls -all *.zip

    object_path="repositories/codeup/${CI_SOURCE_NAME}"
    code_path="${object_path}/code.zip"


    echo "Uploading to OSS with key: $code_path"
    output_file=$(mktemp)
    python $codeDir/scripts/upload_to_oss.py --key="$code_path" --file_path=$codeDir.zip --unique_key="$hash" 2>&1 | tee "$output_file"
    upload_exit_code=${PIPESTATUS[0]}
    output=$(cat "$output_file")
    rm -f "$output_file"

    if [ "$upload_exit_code" -ne 0 ]; then
        echo "Error: Failed to upload to OSS for profile: $profile (exit code: $upload_exit_code)"
        exit 1
    fi

    echo "INFO: Upload successfully"
    version_id=$(echo "$output" | grep -o 'Version ID: [^,]*' | sed 's/.*Version ID: //')
    if [ -z "$version_id" ]; then
        echo "Warning: Could not extract version_id from output"
        version_id=""
    fi

    echo "Profile: $profile, Version ID: $version_id"

    version_ids_list+=("$profile@$version_id")
done


version_ids_list_final=$(IFS=';'; echo "${version_ids_list[*]}")
echo "$version_ids_list_final"
echo "VERSION_IDS_LIST=$version_ids_list_final" >> "$FLOW_ENV"
echo "All source packages created and uploaded to OSS"
```

**Step 5: Batch Set Variables**

Add Step → Tools → Batch Set Variables. Used for passing environment variables across stages.

```
VERSION_IDS_LIST = ${VERSION_IDS_LIST}
```

## Stage 1: Plan Review

New Task → Tools → Manual Gate. Manually trigger after confirming code changes meet expectations.

## Stage 2: Execute Plan

New Task → Blank Template

**Step 1: Install Python**

Add Step → Build → Install Python. Select version 3.12

**Step 2: Install Python Dependencies**

Add Step → Build → Execute Command.

```bash
mkdir -p ~/.pip
cat > ~/.pip/pip.conf << 'EOF'
[global]
index-url = https://mirrors.aliyun.com/pypi/simple/
trusted-host = mirrors.aliyun.com
EOF

python -m pip install --upgrade pip
pip install alibabacloud-oss-v2
pip install PyYAML
```

**Step 3: Upload Plan Trigger File**

Add Step → Build → Execute Command. Create Plan trigger files (JSON format) for each profile and upload to OSS.

```bash
echo "Creating Plan Trigger File..."
set -e

chmod +x scripts/yq
chmod +x scripts/*.py

YQ_CMD="./scripts/yq"
if [ ! -f "$$YQ_CMD" ]; then 
    YQ_CMD="scripts/yq"
fi

IFS=';' read -ra PROFILES <<< "${BUILD_REMARK}"

declare -A VERSION_ID_MAP
if [ -n "${VERSION_IDS_LIST}" ]; then
    IFS=';' read -ra VERSION_PARTS <<< "${VERSION_IDS_LIST}"
    for version_part in "${VERSION_PARTS[@]}"; do
        if [[ "$version_part" == *"@"* ]]; then
            profile_name=$(echo "$version_part" | cut -d'@' -f1)
            version_id_value=$(echo "$version_part" | cut -d'@' -f2-)
            VERSION_ID_MAP["$profile_name"]="$version_id_value"
            echo "Parsed version_id: profile=$profile_name, versionId=$version_id_value"
        fi
    done
fi

for i in "${!PROFILES[@]}"; do
    PART="${PROFILES[$i]}"
    profile=$(echo "$PART" | cut -d':' -f1)
    stack_values=$(echo "$PART" | cut -d':' -f2)

    echo ""
    echo "Processing profile: $profile"
    echo "  Stacks: $stack_values"

    profile_file="deployments/$profile/profile.yaml"
    if [ ! -f "$profile_file" ]; then
        echo "Error: Profile file not found: $profile_file"
        exit 1
    fi

    oss_region="cn-beijing"
    oss_bucket=$($YQ_CMD '.oss_bucket' "$profile_file")
    access_key_id_name=$($YQ_CMD '.access_key_id' "$profile_file")
    access_key_secret_name=$($YQ_CMD '.access_key_secret' "$profile_file")

    access_key_id="${!access_key_id_name}"
    access_key_secret="${!access_key_secret_name}"

    if [ -z "$access_key_id" ] || [ -z "$access_key_secret" ]; then
        echo "Error: Missing access key ID or access key secret"
        exit 1
    fi
    export OSS_BUCKET=$oss_bucket OSS_REGION=$oss_region OSS_ACCESS_KEY_ID=$access_key_id OSS_ACCESS_KEY_SECRET=$access_key_secret


    object_path="repositories/codeup/${CI_SOURCE_NAME}"
    code_path="${object_path}/code.zip"
    trigger_file_name="BUILD[${BUILD_NUMBER}]-[${BUILD_EXECUTOR}]-plan.json"
    trigger_path="${object_path}/${trigger_file_name}"

    oss_path="oss::https://${oss_bucket}.oss-${oss_region}.aliyuncs.com"
    code_path="${oss_path}/${code_path}"
    result_path="${oss_path}/notifications/codeup/${CI_SOURCE_NAME}/${trigger_file_name}"
    trigger_id="${trigger_file_name%.json}"

    IFS=',' read -r -a stack_array <<< "$stack_values"
    result_array=()
    for stack in "${stack_array[@]}"; do
        if [[ "$stack" != */ ]]; then
            stack="${stack}/"
        fi
        result_array+=("stacks/${stack}")
    done
    stacks_final=$(IFS=','; echo "${result_array[*]}")

    version_id="${VERSION_ID_MAP[$profile]}"
    if [ -z "$version_id" ]; then
        echo "Warning: No version_id found for profile: $profile"
        version_id=""
    else
        echo "Using version_id for profile $profile: $version_id"
    fi

    echo "Creating trigger event file for command: plan"
    cat > trigger-event.json << EOF
{
    "id": "${trigger_id}",
    "action": "terraform plan",
    "codeHeadSha": "${CI_COMMIT_SHA}",
    "codeVersionId": "${version_id}",
    "codePackagePath": "${code_path}",
    "execResultPath": "${result_path}",
    "changedFolders": "${stacks_final}"
}
EOF

    echo "Trigger event file content:"
    cat trigger-event.json
    python ./scripts/upload_to_oss.py --key=$trigger_path --file_path=trigger-event.json

    result_path_list+=("$profile@$result_path")
  
done


result_path_list_final=$(IFS=';'; echo "${result_path_list[*]}")
echo "$result_path_list_final"
echo "RESULT_PATH=$result_path_list_final" >> "$FLOW_ENV"
echo "All Plan trigger event files created and uploaded to OSS"
```

**Step 4: Query Plan Execution Results**

Add Step → Build → Execute Command. Poll OSS for execution results.

```bash
result_path=${RESULT_PATH}
         
python ./scripts/parse_exec_result.py \
    --code-path="./" \
    --oss-url="${result_path}" \
    --output-file=execution_result.txt

if [ ! -f execution_result.txt ]; then
    exit 1
fi
```

## Stage 3: Apply Review

New Task → Tools → Manual Gate. Manually confirm Plan results meet expectations before initiating Apply.

## Stage 4: Execute Apply

New Task → Blank Template

**Step 1: Install Python**

Add Step → Build → Install Python. Select version 3.12

**Step 2: Install Python Dependencies**

Add Step → Build → Execute Command.

```bash
mkdir -p ~/.pip
cat > ~/.pip/pip.conf << 'EOF'
[global]
index-url = https://mirrors.aliyun.com/pypi/simple/
trusted-host = mirrors.aliyun.com
EOF

python -m pip install --upgrade pip
pip install alibabacloud-oss-v2
pip install PyYAML
```

**Step 3: Upload Apply Trigger File**

Add Step → Build → Execute Command. Create Apply trigger files (JSON format) for each profile and upload to OSS.

```bash
echo "Creating Apply Trigger File..."
set -e

chmod +x scripts/yq
chmod +x scripts/*.py

YQ_CMD="./scripts/yq"
if [ ! -f "$$YQ_CMD" ]; then 
    YQ_CMD="scripts/yq"
fi

IFS=';' read -ra PROFILES <<< "${BUILD_REMARK}"

declare -A VERSION_ID_MAP
if [ -n "${VERSION_IDS_LIST}" ]; then
    IFS=';' read -ra VERSION_PARTS <<< "${VERSION_IDS_LIST}"
    for version_part in "${VERSION_PARTS[@]}"; do
        if [[ "$version_part" == *"@"* ]]; then
            profile_name=$(echo "$version_part" | cut -d'@' -f1)
            version_id_value=$(echo "$version_part" | cut -d'@' -f2-)
            VERSION_ID_MAP["$profile_name"]="$version_id_value"
            echo "Parsed version_id: profile=$profile_name, versionId=$version_id_value"
        fi
    done
fi

for i in "${!PROFILES[@]}"; do
    PART="${PROFILES[$i]}"
    profile=$(echo "$PART" | cut -d':' -f1)
    stack_values=$(echo "$PART" | cut -d':' -f2)

    echo ""
    echo "Processing profile: $profile"
    echo "  Stacks: $stack_values"

    profile_file="deployments/$profile/profile.yaml"
    if [ ! -f "$profile_file" ]; then
        echo "Error: Profile file not found: $profile_file"
        exit 1
    fi

    oss_region="cn-beijing"
    oss_bucket=$($YQ_CMD '.oss_bucket' "$profile_file")
    access_key_id_name=$($YQ_CMD '.access_key_id' "$profile_file")
    access_key_secret_name=$($YQ_CMD '.access_key_secret' "$profile_file")

    access_key_id="${!access_key_id_name}"
    access_key_secret="${!access_key_secret_name}"

    if [ -z "$access_key_id" ] || [ -z "$access_key_secret" ]; then
        echo "Error: Missing access key ID or access key secret"
        exit 1
    fi
    export OSS_BUCKET=$oss_bucket OSS_REGION=$oss_region OSS_ACCESS_KEY_ID=$access_key_id OSS_ACCESS_KEY_SECRET=$access_key_secret


    object_path="repositories/codeup/${CI_SOURCE_NAME}"
    code_path="${object_path}/code.zip"
    trigger_file_name="BUILD[${BUILD_NUMBER}]-[${BUILD_EXECUTOR}]-apply.json"
    trigger_path="${object_path}/${trigger_file_name}"

    oss_path="oss::https://${oss_bucket}.oss-${oss_region}.aliyuncs.com"
    code_path="${oss_path}/${code_path}"
    result_path="${oss_path}/notifications/codeup/${CI_SOURCE_NAME}/${trigger_file_name}"
    trigger_id="${trigger_file_name%.json}"

    IFS=',' read -r -a stack_array <<< "$stack_values"
    result_array=()
    for stack in "${stack_array[@]}"; do
        if [[ "$stack" != */ ]]; then
            stack="${stack}/"
        fi
        result_array+=("stacks/${stack}")
    done
    stacks_final=$(IFS=','; echo "${result_array[*]}")

    version_id="${VERSION_ID_MAP[$profile]}"
    if [ -z "$version_id" ]; then
        echo "Warning: No version_id found for profile: $profile"
        version_id=""
    else
        echo "Using version_id for profile $profile: $version_id"
    fi

    echo "Creating trigger event file for command: apply"
    cat > trigger-event.json << EOF
{
    "id": "${trigger_id}",
    "action": "terraform apply",
    "codeHeadSha": "${CI_COMMIT_SHA}",
    "codeVersionId": "${version_id}",
    "codePackagePath": "${code_path}",
    "execResultPath": "${result_path}",
    "changedFolders": "${stacks_final}"
}
EOF

    echo "Trigger event file content:"
    cat trigger-event.json
    python ./scripts/upload_to_oss.py --key=$trigger_path --file_path=trigger-event.json

    result_path_list+=("$profile@$result_path")
  
done


result_path_list_final=$(IFS=';'; echo "${result_path_list[*]}")
echo "$result_path_list_final"
echo "RESULT_PATH=$result_path_list_final" >> "$FLOW_ENV"
echo "All Apply trigger event files created and uploaded to OSS"
```

**Step 4: Query Apply Execution Results**

Add Step → Build → Execute Command. Poll OSS for execution results.

```bash
result_path=${RESULT_PATH}
         
python ./scripts/parse_exec_result.py \
    --code-path="./" \
    --oss-url="${result_path}" \
    --output-file=execution_result.txt

if [ ! -f execution_result.txt ]; then
    exit 1
fi
```

## Configure Pipeline Variables

In the Alibaba Cloud DevOps pipeline **Variable Management**, configure key pairs with each Key and Value stored separately. The Key name corresponds to the key pair name configured in `profile.yaml`. Store the AccessKey created in the pre-provisioning step under the corresponding key pair name. For multiple environments, configure with environment prefixes:

| Variable Name | Description | Example Value |
|---------------|-------------|---------------|
| `DEV_ACCESS_KEY_ID` | Development environment AccessKey ID | Encrypted |
| `DEV_ACCESS_KEY_SECRET` | Development environment AccessKey Secret | Encrypted |

---

# Daily Usage

## Create IacService Stacks

Before executing code, you first need to create the corresponding Stacks on Alibaba Cloud IacService to host the code execution. After repository code initialization, reuse the pipeline above to first package and upload code to OSS, then create all corresponding Stacks at once on the IacService console.

### 1. Upload Code to OSS

Specify the profile in the run configuration. The stack name can be anything, as this run is only for uploading code, not for deployment.

### 2. Create Stacks

Here is how to create the `stacks/demo` Stack — the same process applies to others:

1. **Select Create Stack**

   Log in to Alibaba Cloud IacService (https://iac.console.aliyun.com/stack) and select "Create Stack"

2. **Fill in Stack Information**
   - **OSS Bucket Name**: Select the bucket created by the initialization script
   - **OSS Object Name**: The pipeline automatically uploads code to a fixed directory — select this archive
   - **Working Directory**: The path where the Stack is stored in the code, e.g., `stacks/demo`
   - **RAM Role**: Select the role created by the initialization script for running Terraform templates

> **Batch Creation**: It is recommended to create all Stacks defined under the `stacks/` directory at once. Each Stack corresponds to an independent resource stack. After creation, an initial `plan` will be automatically executed to verify configuration correctness.

## Change Workflow

1. Switch to a development branch, commit code changes, create a merge request
2. Manually run the pipeline, select the development branch, and enter the Stacks to change (format: `<profileName>:<StackName1>,<StackName2>`, e.g., `dev:demo`). Execute the corresponding plan & apply validation
3. If apply results meet expectations, return to the merge request and submit the review
4. After review approval, merge changes to the main branch

## Runtime Parameter Reference

The pipeline passes runtime parameters via **remark information** in the following format:

```
<profileName>:<StackName1>,<StackName2>
```

**Examples**:

| Remark | Description |
|--------|-------------|
| `dev:demo` | Run demo stack in dev environment |
| `dev:stack1,stack2` | Run stack1 and stack2 in dev environment |
| `dev:stack1;staging:stack2` | Run stack1 in dev environment and stack2 in staging environment simultaneously |

**Parameter Reference**:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `profileName` | Yes | Execution environment, corresponds to environment name under `deployments/` directory |
| `StackName` | Yes | Target stack path, supports directory nesting, e.g., `demo/subDir` |

---

# Operations Reference

## Troubleshooting

| Issue | Resolution |
|-------|-----------|
| No deployment response | Check if pipeline variables are configured correctly, if OSS/MNS services are operational, if RAM permissions are sufficient |
| Command not recognized | Confirm remark format is `<profile>:<stack>`, note the colon separator |
| `make build-package` fails | Confirm the repository root contains a Makefile with the `build-package` target |
| Profile upload fails | Check if `access_key_id`/`access_key_secret` in `deployments/[env]/profile.yaml` match the Key names in pipeline variables |
| Result retrieval timeout | Default polling timeout is 600 seconds, check IacService console to confirm if the Stack is executing |
| Partial multi-environment failure | Check Alibaba Cloud DevOps pipeline logs, identify the failed profile name |
| View detailed errors | Check Alibaba Cloud DevOps pipeline run logs, or inspect trigger and result files in OSS |


## Multi-Environment Configuration

To add a new Alibaba Cloud account (e.g., adding a `test` environment), complete the following:

### 1. Create Bootstrap Configuration

```bash
mkdir -p bootstrap/terraform-test
cp bootstrap/terraform-dev/*.tf bootstrap/terraform-test/

cd bootstrap/terraform-test

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

Modify `profile.yaml` to update `oss_bucket`, `oss_region`, and `account_id` to the values from step 1 output, and change the AK variable names in `profile.yaml` to the new Alibaba Cloud DevOps pipeline variable keys.

### 3. Configure Alibaba Cloud DevOps Pipeline Variables

Add variables for the new account in the Alibaba Cloud DevOps pipeline configuration:

| Variable Name | Description |
|---------------|-------------|
| `TEST_ACCESS_KEY_ID` | New account AccessKey ID |
| `TEST_ACCESS_KEY_SECRET` | New account AccessKey Secret |

### 4. Verify Configuration

After committing the configuration, manually trigger the pipeline to confirm the new environment's source package uploads successfully.

> **Account Isolation Recommendation**: Each Alibaba Cloud account should have independent RAM Roles, OSS Buckets, and MNS resources, with credentials managed through separate pipeline variables for complete isolation. It is recommended to allocate different environments to different Alibaba Cloud master accounts and manage them centrally through Alibaba Cloud Resource Directory.
