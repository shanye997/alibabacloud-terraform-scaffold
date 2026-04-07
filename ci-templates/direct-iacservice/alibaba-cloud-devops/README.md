# Alibaba Cloud DevOps Integration - Direct IacService Mode

CI/CD integration solution based on Alibaba Cloud DevOps (CodeUp + Flow) and Alibaba Cloud IacService, triggering automated Terraform Stack deployments directly via IacService API.

> **🌐 Language**：[中文文档](README-CN.md) | [English Docs](README.md)

## Table of Contents

- [Alibaba Cloud DevOps Integration - Direct IacService Mode](#alibaba-cloud-devops-integration---direct-iacservice-mode)
  - [Table of Contents](#table-of-contents)
- [Overview](#overview)
- [Prerequisites](#prerequisites)
  - [Prepare Code Repository](#prepare-code-repository)
  - [Pre-provisioning Setup](#pre-provisioning-setup)
    - [RAM User 1: Admin User](#ram-user-1-admin-user)
    - [RAM User 2: Pipeline Trigger User](#ram-user-2-pipeline-trigger-user)
    - [RAM Role: IacService Execution Role](#ram-role-iacservice-execution-role)
  - [Create IacService Template](#create-iacservice-template)
    - [Console Operations](#console-operations)
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
    - [0. Profile Configuration](#0-profile-configuration)
    - [1. Upload Code to IacService](#1-upload-code-to-iacservice)
    - [2. Create Stacks](#2-create-stacks)
  - [Change Workflow](#change-workflow)
  - [Runtime Parameter Reference](#runtime-parameter-reference)
- [Operations Reference](#operations-reference)
  - [Troubleshooting](#troubleshooting)
  - [Multi-Environment Configuration](#multi-environment-configuration)
    - [1. Create Deployments Configuration](#1-create-deployments-configuration)
    - [2. Configure Alibaba Cloud DevOps Pipeline Variables](#2-configure-alibaba-cloud-devops-pipeline-variables)
    - [3. Create IacService Module and Stacks](#3-create-iacservice-module-and-stacks)
    - [4. Verify Configuration](#4-verify-configuration)

---

# Overview

```
Developer → Alibaba Cloud DevOps Pipeline → IacService API (upload code + trigger execution) → Execute Deployment → IacService API (query results) → Alibaba Cloud DevOps Pipeline → Output Results
```

Unlike the OSS MNS relay mode, the direct mode uploads code packages and triggers Stack execution directly via IacService API, without relying on OSS or MNS as intermediaries.

The pipeline consists of 5 stages:

```
Code Upload → Plan Review → Execute Plan → Apply Review → Execute Apply
```

> **Note**: Alibaba Cloud DevOps does not support automatically triggering parameterized pipelines from merge requests, so a manual trigger + remark parameter approach is used. The actual change workflow is: commit code to development branch → create merge request → manually run validation pipeline → review approved → merge to main branch.

Helper scripts (`scripts/`):

| Script | Language | Dependencies | Purpose |
|--------|----------|-------------|---------|
| `upload_iac_module.py` | Python 3.12 | `alibabacloud_iacservice20210806` | Packages and uploads code to IacService module. Reads credentials and configuration from environment variables `IAC_ACCESS_KEY_ID`/`IAC_ACCESS_KEY_SECRET`/`IAC_REGION`/`CODE_MODULE_ID` |
| `trigger_stack.py` | Python 3.12 | `alibabacloud_iacservice20210806` | Triggers Plan or Apply operations on a Stack, returns Trigger ID for subsequent queries |
| `get_trigger_result.py` | Python 3.12 | `alibabacloud_iacservice20210806`, `PyYAML` | Polls IacService API for execution results with formatted output. Supports multi-profile parallel polling (multi-threaded), default timeout 600 seconds |
| `yamlparser.py` | Python 3.12 | `PyYAML` | YAML configuration file parser, compatible with `yq` command-line invocation |

---

# Prerequisites

## Prepare Code Repository

Create a new repository in Alibaba Cloud DevOps, copy all files from the `ci-templates/direct-iacservice/alibaba-cloud-devops/` directory to your repository root, commit and push:

```bash
git init
git remote add origin git@codeup.aliyun.com:<org-id>/<repo-name>.git
git add .
git commit -m "init"
git push -u origin HEAD
```

---

## Pre-provisioning Setup

### RAM User 1: Admin User

Used for initial provisioning of Alibaba Cloud DevOps and IacService resources — a one-time operation. Operations staff can use this user for subsequent management:

1. Log in to the [RAM Console](https://ram.console.aliyun.com/), create a user and enable **OpenAPI Access**
2. Attach the following policies to the user:
   - Alibaba Cloud DevOps code management & pipeline management permissions
   - Custom policy `IaCServiceStackFullAccess` (see [docs/iam-policies.md](../../../docs/iam-policies.md) for policy content)

### RAM User 2: Pipeline Trigger User

Used by Alibaba Cloud DevOps pipelines to call IacService API. Configure the AccessKey in pipeline variables for long-term use:

1. Create a user and enable **OpenAPI Access**
2. Attach custom policy `IaCServiceStackTriggerAccess` (see [docs/iam-policies.md](../../../docs/iam-policies.md) for policy content)
3. Create an AccessKey, record the AccessKey ID and Secret — these will be needed when configuring pipeline variables (this document uses the development environment as an example, assuming the key pair is named `DEV_ACCESS_KEY_ID` / `DEV_ACCESS_KEY_SECRET`)

### RAM Role: IacService Execution Role

Used to authorize IacService to assume this role for executing Terraform templates:

1. Create a new RAM Role in the RAM Console
2. Configure the trust policy to allow IacService to assume this role (see [docs/iam-policies.md](../../../docs/iam-policies.md) for trust policy content)
3. Attach permission policies required for executing Terraform templates (e.g., if the template includes ECS instances, add ECS-related permissions)

---

## Create IacService Template

This step creates an IacService template. A template corresponds to a codebase, and each code modification requires publishing a new version. Different changes to the same codebase correspond to different template versions.

> **Important**: Record the Template ID (ModuleId) after creation — it will be needed in subsequent steps.

### Console Operations

**Step 1: Create Template**

Click **Template Management**, then select **Create Template**.

**Step 2: Select Template Source**

Select the **Blank Template** option.

**Step 3: Fill in Template Parameters**

Fill in the following parameters and click **Submit**.

| Parameter | Required | Description |
|-----------|----------|-------------|
| Template Name | Yes | Name of the template, must be unique |
| Template Description | No | Description of the template |
| Add to Project Group | No | Optionally select a project group for unified template management |

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
pip install alibabacloud_iacservice20210806
pip install PyYAML
```

**Step 4: Package and Upload**

Add Step → Build → Execute Command. Package and upload code to IacService for each environment in the input list.

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

    iac_region="cn-zhangjiakou"
    code_module_id=$($YQ_CMD '.code_module_id' "$profile_file")
    access_key_id_name=$($YQ_CMD '.access_key_id' "$profile_file")
    access_key_secret_name=$($YQ_CMD '.access_key_secret' "$profile_file")

    access_key_id="${!access_key_id_name}"
    access_key_secret="${!access_key_secret_name}"

    if [ -z "$access_key_id" ] || [ -z "$access_key_secret" ]; then
        echo "Error: Missing access key ID or access key secret"
        exit 1
    fi
    export CODE_MODULE_ID=$code_module_id IAC_REGION=$iac_region IAC_ACCESS_KEY_ID=$access_key_id IAC_ACCESS_KEY_SECRET=$access_key_secret


    mv $codeDir.zip ../
    cd ../
    ls -all *.zip

    echo "Uploading to IAC Module..."
    output_file=$(mktemp)
    python $codeDir/scripts/upload_iac_module.py --file_path=$codeDir.zip 2>&1 | tee "$output_file"
    upload_exit_code=${PIPESTATUS[0]}
    output=$(cat "$output_file")
    rm -f "$output_file"

    if [ "$upload_exit_code" -ne 0 ]; then
        echo "Error: Failed to upload to IAC for profile: $profile (exit code: $upload_exit_code)"
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
echo "All source packages created and uploaded to IAC"
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
pip install alibabacloud_iacservice20210806
pip install PyYAML
```

**Step 3: Trigger Plan Execution**

Add Step → Build → Execute Command. Call IacService API to trigger Plan for each profile.

```bash
echo "Trigger Plan..."
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

    iac_region="cn-zhangjiakou"
    code_module_id=$($YQ_CMD '.code_module_id' "$profile_file")
    access_key_id_name=$($YQ_CMD '.access_key_id' "$profile_file")
    access_key_secret_name=$($YQ_CMD '.access_key_secret' "$profile_file")

    access_key_id="${!access_key_id_name}"
    access_key_secret="${!access_key_secret_name}"

    if [ -z "$access_key_id" ] || [ -z "$access_key_secret" ]; then
        echo "Error: Missing access key ID or access key secret"
        exit 1
    fi
    export CODE_MODULE_ID=$code_module_id IAC_REGION=$iac_region IAC_ACCESS_KEY_ID=$access_key_id IAC_ACCESS_KEY_SECRET=$access_key_secret

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

    output=$(python ./scripts/trigger_stack.py --action="terraform plan" --code_module_version="${version_id}" --change_folders="${stacks_final}")

    trigger_id=$(echo "$output" | grep -o 'Trigger ID: [^,]*' | sed 's/.*Trigger ID: //')
    
    echo "Profile: $profile, Trigger ID: $trigger_id"

    result_path_list+=("$profile@$trigger_id")
  
done


result_path_list_final=$(IFS=';'; echo "${result_path_list[*]}")
echo "$result_path_list_final"
echo "RESULT_PATH=$result_path_list_final" >> "$FLOW_ENV"
echo "All Plan event trigger done"
```

**Step 4: Query Plan Execution Results**

Add Step → Build → Execute Command. Poll IacService API for execution results.

```bash
result_path=${RESULT_PATH}
         
python ./scripts/get_trigger_result.py \
    --code-path="./" \
    --result-path="${result_path}" \
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
pip install alibabacloud_iacservice20210806
pip install PyYAML
```

**Step 3: Trigger Apply Execution**

Add Step → Build → Execute Command. Call IacService API to trigger Apply for each profile.

```bash
echo "Trigger Apply..."
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

    iac_region="cn-zhangjiakou"
    code_module_id=$($YQ_CMD '.code_module_id' "$profile_file")
    access_key_id_name=$($YQ_CMD '.access_key_id' "$profile_file")
    access_key_secret_name=$($YQ_CMD '.access_key_secret' "$profile_file")

    access_key_id="${!access_key_id_name}"
    access_key_secret="${!access_key_secret_name}"

    if [ -z "$access_key_id" ] || [ -z "$access_key_secret" ]; then
        echo "Error: Missing access key ID or access key secret"
        exit 1
    fi
    export CODE_MODULE_ID=$code_module_id IAC_REGION=$iac_region IAC_ACCESS_KEY_ID=$access_key_id IAC_ACCESS_KEY_SECRET=$access_key_secret

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

    output=$(python ./scripts/trigger_stack.py --action="terraform apply" --code_module_version="${version_id}" --change_folders="${stacks_final}")

    trigger_id=$(echo "$output" | grep -o 'Trigger ID: [^,]*' | sed 's/.*Trigger ID: //')
    
    echo "Profile: $profile, Trigger ID: $trigger_id"

    result_path_list+=("$profile@$trigger_id")
  
done


result_path_list_final=$(IFS=';'; echo "${result_path_list[*]}")
echo "$result_path_list_final"
echo "RESULT_PATH=$result_path_list_final" >> "$FLOW_ENV"
echo "All Apply trigger done"
```

**Step 4: Query Apply Execution Results**

Add Step → Build → Execute Command. Poll IacService API for execution results.

```bash
result_path=${RESULT_PATH}
         
python ./scripts/get_trigger_result.py \
    --code-path="./" \
    --result-path="${result_path}" \
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

Before executing code, you first need to create the corresponding Stacks on Alibaba Cloud IacService to host the code execution. After repository code initialization, reuse the pipeline above to first package and upload code to IacService, then create all corresponding Stacks at once on the IacService console.

### 0. Profile Configuration

Fill in configuration in `deployments/[env]/profile.yaml`:

```yaml
account_id: "<your-account-id>"
access_key_id: "DEV_ACCESS_KEY_ID"         # Corresponds to the variable name in Alibaba Cloud DevOps pipeline variables
access_key_secret: "DEV_ACCESS_KEY_SECRET"  # Corresponds to the variable name in Alibaba Cloud DevOps pipeline variables
code_module_id: "mod-xxx"                       # IacService Module ID
```

> **Note**: The values of `access_key_id` and `access_key_secret` are **variable names**, not actual AK values. Actual AK values must be stored as sensitive variables in Alibaba Cloud DevOps and referenced via variable names in the pipeline.


### 1. Upload Code to IacService

Specify the profile in the run configuration. The stack name can be anything, as this run is only for uploading code, not for deployment.

### 2. Create Stacks

Here is how to create the `stacks/demo` Stack — the same process applies to others:

1. **Select Create Stack**

   Log in to Alibaba Cloud IacService (https://iac.console.aliyun.com/stack) and select "Create Stack"

2. **Fill in Stack Information**
   - **Code Module**: Select the IacService module created in the prerequisites
   - **Working Directory**: The path where the Stack is stored in the code, e.g., `stacks/demo`
   - **RAM Role**: Select the role trusted by IacService for Stack operations

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

**Notes**:

- A PR can be reused until merged, but creating independent PRs for each task is recommended for traceability
- `plan` must be executed before each `apply`; `plan` can be executed multiple times consecutively
- Different environment profiles correspond to different Alibaba Cloud accounts and resources, with no mutual impact

---

# Operations Reference

## Troubleshooting

| Issue | Resolution |
|-------|-----------|
| No deployment response | Check if pipeline variables are configured correctly, if IacService is operational, if RAM permissions are sufficient |
| Command not recognized | Confirm remark format is `<profile>:<stack>`, note the colon separator |
| `make build-package` fails | Confirm the repository root contains a Makefile with the `build-package` target |
| Code upload fails | Check if `code_module_id` is correct, if AK has IacService permissions |
| Trigger execution fails | Check if `code_module_version` is correct, if the Stack has been created |
| Result retrieval timeout | Default polling timeout is 600 seconds, check IacService console to confirm if the Stack is executing |
| Partial multi-environment failure | Check Alibaba Cloud DevOps pipeline logs, identify the failed profile name |

## Multi-Environment Configuration

To add a new Alibaba Cloud account (e.g., adding a `test` environment), complete the following:

### 1. Create Deployments Configuration

```bash
cp -r deployments/dev deployments/test
cd deployments/test
```

Modify `profile.yaml` to update `account_id` and `code_module_id` to the new environment's values, and change AK variable names to the new Alibaba Cloud DevOps pipeline variable keys.

### 2. Configure Alibaba Cloud DevOps Pipeline Variables

Add variables for the new account in the Alibaba Cloud DevOps pipeline configuration:

| Variable Name | Description |
|---------------|-------------|
| `TEST_ACCESS_KEY_ID` | New account AccessKey ID |
| `TEST_ACCESS_KEY_SECRET` | New account AccessKey Secret |

### 3. Create IacService Module and Stacks

Create code modules and Stacks in the new account's IacService console. Refer to the [Create IacService Stacks](#create-iac-service-stacks) section.

### 4. Verify Configuration

After committing the configuration, manually trigger the pipeline to confirm code upload and execution work correctly for the new environment.

> **Account Isolation Recommendation**: Each Alibaba Cloud account should have independent IacService modules and Stacks, with credentials managed through separate pipeline variables for complete isolation. It is recommended to allocate different environments to different Alibaba Cloud master accounts and manage them centrally through Alibaba Cloud Resource Directory.

---
