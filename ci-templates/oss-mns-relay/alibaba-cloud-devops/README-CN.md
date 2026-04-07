# 云效集成方案 - OSS MNS 中转模式

基于阿里云云效（CodeUp + Flow）与阿里云自动化服务台（IacService）的 CI/CD 集成方案，通过 OSS MNS 中转模式实现 Terraform 资源栈的自动化部署。

> **🌐 语言**：[中文文档](README-CN.md) | [English Docs](README.md)

## 目录

- [云效集成方案 - OSS MNS 中转模式](#云效集成方案---oss-mns-中转模式)
  - [目录](#目录)
- [概述](#概述)
- [前期准备](#前期准备)
  - [初始化云端基础设施](#初始化云端基础设施)
    - [1. 准备代码仓库](#1-准备代码仓库)
    - [2. 创建临时 RAM 用户](#2-创建临时-ram-用户)
    - [3. 执行 Terraform 初始化](#3-执行-terraform-初始化)
    - [4. 清理与配置](#4-清理与配置)
  - [开通云效](#开通云效)
    - [1. 创建云效 RAM 用户并配置权限](#1-创建云效-ram-用户并配置权限)
    - [2. 配置 OSS 权限](#2-配置-oss-权限)
- [云效流水线配置](#云效流水线配置)
  - [流水线源](#流水线源)
  - [阶段 0：代码上传](#阶段-0代码上传)
  - [阶段 1：plan 审核](#阶段-1plan-审核)
  - [阶段 2：执行 Plan](#阶段-2执行-plan)
  - [阶段 3：apply 审核](#阶段-3apply-审核)
  - [阶段 4：执行 Apply](#阶段-4执行-apply)
  - [配置流水线变量](#配置流水线变量)
- [日常使用](#日常使用)
  - [创建自动化服务台资源栈](#创建自动化服务台资源栈)
    - [1. 代码上传到 OSS](#1-代码上传到-oss)
    - [2. 创建资源栈](#2-创建资源栈)
  - [变更流程](#变更流程)
  - [运行参数说明](#运行参数说明)
- [运维参考](#运维参考)
  - [故障排查](#故障排查)
  - [多环境配置](#多环境配置)
    - [1. 创建 bootstrap 配置](#1-创建-bootstrap-配置)
    - [2. 创建 deployments 配置](#2-创建-deployments-配置)
    - [3. 配置云效流水线变量](#3-配置云效流水线变量)
    - [4. 验证配置](#4-验证配置)

---

# 概述

```
Developer → 云效流水线 → OSS(代码包 + 触发文件) → MNS → IacService → 执行部署 → OSS(结果) → 云效流水线 → 输出结果
```

上图为从云效出发，中转 OSS 管理自动化服务台资源栈的完整运行链路。OSS 与自动化服务台之间的交互逻辑是固定的，云效到 OSS 的交互需要基于云效流水线能力完成代码与触发文件的上传以及运行日志的读取。

流水线分为 5 个阶段：

```
代码上传 → plan 审核 → 执行 Plan → apply 审核 → 执行 Apply
```

> **注意**：云效不支持由合并请求自动触发带参数的流水线，因此采用手动触发 + 备注参数的方式。实际变更流程为：开发分支提交代码 → 创建合并请求 → 手动运行验证流水线 → 评审通过 → 合入主干。

初始化脚本（`bootstrap/terraform-dev/`）会创建以下云端资源：

| 资源 | 说明 |
|------|------|
| **RAM Role** | IacService 执行 Terraform 操作所需的服务角色，默认名称 `IaCServiceStackRole`。示例中授予 `AdministratorAccess` 权限，**实际部署时应依据最小权限原则，仅授予 Terraform 资源所需的 RAM 权限** |
| **OSS Bucket** | 存储代码包和触发文件的对象存储桶，开启版本控制，非当前版本 30 天后自动清理 |
| **MNS Topic/Queue/Subscription** | 消息服务主题、队列和订阅，将 OSS 事件转发给 IacService 的消息队列 |
| **OSS Event Rule** | 监听 Bucket 中 `.json` 文件的创建和修改事件，触发 MNS 通知 |

辅助脚本（`scripts/`）：

| 脚本 | 语言 | 依赖 | 作用 |
|------|------|------|------|
| `upload_to_oss.py` | Python 3.12 | `alibabacloud-oss-v2` | 将文件上传到 OSS。支持通过 `--unique_key` 参数进行版本去重（相同代码不重复上传）。通过环境变量 `OSS_ACCESS_KEY_ID`/`OSS_ACCESS_KEY_SECRET`/`OSS_REGION`/`OSS_BUCKET` 读取凭证 |
| `parse_exec_result.py` | Python 3.12 | `alibabacloud-oss-v2`, `PyYAML` | 轮询 OSS 等待 IacService 执行结果文件，下载后解析 JSON 并格式化为 Markdown 表格。支持多 profile 并行轮询（多线程），默认超时 600 秒 |

---

# 前期准备

## 初始化云端基础设施

### 1. 准备代码仓库

在云效中创建新仓库，将 `ci-templates/oss-mns-relay/alibaba-cloud-devops/` 目录下的所有文件复制到自己仓库的根目录中，提交并推送：

```bash
git init
git remote add origin git@codeup.aliyun.com:<org-id>/<repo-name>.git
git add .
git commit -m "init"
git push -u origin HEAD
```

### 2. 创建临时 RAM 用户

在阿里云中创建一个只允许 API 访问的 RAM User，创建 AK 密钥，授予如下权限：
- `AliyunRAMFullAccess`
- `AliyunMNSFullAccess`
- `AliyunOSSFullAccess`

将此 AK 配置到本地环境变量（初始化完成后即可删除）：

```bash
export ALICLOUD_ACCESS_KEY="xxx"
export ALICLOUD_SECRET_KEY="xxx"
```

### 3. 执行 Terraform 初始化

```bash
cd bootstrap/terraform-dev
terraform init
terraform plan
terraform apply
```

初始化完成后，`outputs.tf` 输出以下信息：
- `oss_bucket`：OSS Bucket 名称
- `oss_region`：Bucket 所在 Region
- `ram_role_arn`：RAM Role ARN

> **可选配置**：如需修改 OSS Bucket 名称或 RAM Role 名称，编辑 `bootstrap/terraform-dev/variables.tf` 中的对应变量。默认值为：
> - OSS Bucket：`iac-stack-dev-` + 随机数字
> - RAM Role：`IaCServiceStackRole`

### 4. 清理与配置

- 删除该临时 AK 及关联的 RAM User
- 将初始化输出的 `oss_bucket`、`oss_region` 填写到 `deployments/[env]/profile.yaml` 中

> **多环境说明**：如有多个环境（dev、staging、prod 等），需要为每个环境执行独立的 bootstrap 配置，使用不同的 RAM Role 和 OSS Bucket，实现环境间完全隔离。详见 [多环境配置](#多环境配置)。

---

## 开通云效

### 1. 创建云效 RAM 用户并配置权限

1. 登录到云效账号，创建一个 RAM 用户，用于登录云效
2. 授予该 RAM 用户以下权限：
   - 云效相关权限
   - OSS 读写权限（用于脚本创建和管理 Bucket）
   - 自定义权限策略 `IaCServiceStackFullAccess`（策略内容见 [docs/iam-policies.md](../../../docs/iam-policies.md)）
3. 创建 AccessKey（AK），用于云效流水线中访问阿里云资源

### 2. 配置 OSS 权限

为上述 RAM 用户授予 OSS Bucket 的读写权限（替换 `Mybucket` 为实际 Bucket 名称）：

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

# 云效流水线配置

在云效流水线界面手动创建各阶段和任务。流水线整体运行链路：

```
代码上传 → plan 审核 → 执行 Plan → apply 审核 → 执行 Apply
```

## 流水线源

1. 代码仓库选择以上一步骤新建的仓库
2. 默认分支选择主分支或常用的开发分支
3. 工作目录填写为 `code`。此名称在后续流水线脚本中会用到

## 阶段 0：代码上传

新的任务 → 空模版

**步骤 1：解析运行参数**

添加步骤 → 构建 → 执行命令。校验备注参数格式，解析 profile 和 stack 信息。

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

**步骤 2：安装 Python**

添加步骤 → 构建 → 安装 Python。选择版本 3.12

**步骤 3：下载 Python 依赖**

添加步骤 → 构建 → 执行命令。下载运行 Python 脚本所需的依赖。

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

**步骤 4：执行打包并上传**

添加步骤 → 构建 → 执行命令。按照输入的环境列表，分别打包上传代码。

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

**步骤 5：批量设置变量**

添加步骤 → 工具 → 批量设置变量。用于实现环境变量的跨阶段传递。

```
VERSION_IDS_LIST = ${VERSION_IDS_LIST}
```

## 阶段 1：plan 审核

新的任务 → 工具 → 人工卡点。手动触发，确保代码变更符合预期后发起审核。

## 阶段 2：执行 Plan

新的任务 → 空模版

**步骤 1：安装 Python**

添加步骤 → 构建 → 安装 Python。选择版本 3.12

**步骤 2：下载 Python 依赖**

添加步骤 → 构建 → 执行命令。

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

**步骤 3：上传 Plan 触发文件**

添加步骤 → 构建 → 执行命令。为每个 profile 创建 Plan 触发文件（JSON 格式）并上传到 OSS。

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

**步骤 4：查询 Plan 执行结果**

添加步骤 → 构建 → 执行命令。轮询 OSS 获取执行结果。

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

## 阶段 3：apply 审核

新的任务 → 工具 → 人工卡点。手动确认 Plan 结果符合预期后发起 Apply。

## 阶段 4：执行 Apply

新的任务 → 空模版

**步骤 1：安装 Python**

添加步骤 → 构建 → 安装 Python。选择版本 3.12

**步骤 2：下载 Python 依赖**

添加步骤 → 构建 → 执行命令。

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

**步骤 3：上传 Apply 触发文件**

添加步骤 → 构建 → 执行命令。为每个 profile 创建 Apply 触发文件（JSON 格式）并上传到 OSS。

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

**步骤 4：查询 Apply 执行结果**

添加步骤 → 构建 → 执行命令。轮询 OSS 获取执行结果。

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

## 配置流水线变量

在云效流水线【变量管理】中配置密钥对，每个 Key 和 Value 分开存储，Key 名称对应 `profile.yaml` 中配置的密钥对名称。将前置开通准备步骤中创建的 AccessKey 按对应密钥对名称进行存储。如有多个环境，按环境前缀分别配置：

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `DEV_ACCESS_KEY_ID` | 开发环境 AccessKey ID | 加密存储 |
| `DEV_ACCESS_KEY_SECRET` | 开发环境 AccessKey Secret | 加密存储 |

---

# 日常使用

## 创建自动化服务台资源栈

在进行代码的执行前，首先需要在阿里云自动化服务台上创建出对应的资源栈来承载代码的运行。在仓库代码初始化完成后，可复用以上流水线，先将代码打包上传到 OSS 上，再到自动化服务台上将对应的资源栈一次性创建出来。

### 1. 代码上传到 OSS

运行配置要指明 profile，stack 名称可随意填，因为本次我们不做部署，只为上传代码。

### 2. 创建资源栈

此处展示如何创建 `stacks/demo` 资源栈，其余同理：

1. **选择创建资源栈**

   登录阿里云自动化服务台（https://iac.console.aliyun.com/stack），选择"创建资源栈"

2. **填入资源栈相关信息**
   - **OSS Bucket 名称**：选择初始化脚本中创建出来的 bucket
   - **OSS Object 名称**：上一步流水线执行会自动将代码上传到固定目录下，选择这个压缩包
   - **工作目录**：为资源栈在代码中的存放路径，如 `stacks/demo`
   - **RAM 角色**：选择初始化脚本中创建出来的角色，用于运行 terraform 模版

> **批量创建**：建议将 `stacks/` 目录下定义的所有 Stack 一次性全部创建。每个 Stack 对应一个独立的资源栈，创建完成后会自动执行首次 `plan`，可验证配置的正确性。

## 变更流程

1. 切换开发分支，提交代码变更，新建合并请求
2. 手动运行流水线，选择开发分支，输入需要变更的资源栈（格式如：`<profileName>:<StackName1>,<StackName2>`，例如 `dev:demo`）。执行相应的 plan & apply 验证
3. apply 结果符合预期，回到合并请求，提交相应评审
4. 评审通过，变更合入主干

## 运行参数说明

流水线通过**备注信息**传递运行参数，格式如下：

```
<profileName>:<StackName1>,<StackName2>
```

**示例**：

| 备注信息 | 说明 |
|----------|------|
| `dev:demo` | 在 dev 环境运行 demo stack |
| `dev:stack1,stack2` | 在 dev 环境运行 stack1 和 stack2 |
| `dev:stack1;staging:stack2` | 在 dev 环境运行 stack1，同时在 staging 环境运行 stack2 |

**参数说明**：

| 参数 | 必填 | 说明 |
|------|------|------|
| `profileName` | 是 | 执行环境，对应 `deployments/` 目录下的环境名称 |
| `StackName` | 是 | 目标 stack 路径，支持目录嵌套，如 `demo/subDir` |

---

# 运维参考

## 故障排查

| 问题 | 排查方法 |
|------|---------|
| 部署无响应 | 检查流水线变量是否配置正确、OSS/MNS 服务是否正常、RAM 权限是否足够 |
| 命令无法识别 | 确认备注信息格式为 `<profile>:<stack>`，注意冒号分隔符 |
| `make build-package` 失败 | 确认仓库根目录存在 Makefile 且包含 `build-package` 目标 |
| profile 上传失败 | 检查 `deployments/[env]/profile.yaml` 中的 `access_key_id`/`access_key_secret` 是否与流水线变量中的 Key 名一致 |
| 结果获取超时 | 默认轮询超时 600 秒，检查 IacService 控制台确认 Stack 是否正在执行 |
| 多环境部分失败 | 查看云效流水线日志，确认失败的 profile 名称 |
| 查看详细错误信息 | 查看云效流水线运行日志，或检查 OSS 中的触发文件和结果文件内容 |


## 多环境配置

如需新增一个阿里云账号（例如新增 `test` 环境），需完成以下配置：

### 1. 创建 bootstrap 配置

```bash
mkdir -p bootstrap/terraform-test
cp bootstrap/terraform-dev/*.tf bootstrap/terraform-test/

cd bootstrap/terraform-test

vim variables.tf

terraform init
terraform apply
```

> **重要**：每个环境必须使用独立的状态文件，切勿复制 `*.tfstate` 状态文件。

### 2. 创建 deployments 配置

```bash
cp -r deployments/dev deployments/test
cd deployments/test
```

修改 `profile.yaml` 中的 `oss_bucket`、`oss_region`、`account_id` 为步骤 1 的输出值，修改 `profile.yaml` 中的 AK 变量名为新的云效流水线变量 Key。

### 3. 配置云效流水线变量

在云效流水线配置中添加新账号的变量：

| 变量名 | 说明 |
|--------|------|
| `TEST_ACCESS_KEY_ID` | 新账号的 AccessKey ID |
| `TEST_ACCESS_KEY_SECRET` | 新账号的 AccessKey Secret |

### 4. 验证配置

提交配置后，手动触发流水线，确认新环境的源码包上传成功。

> **账号隔离建议**：每个阿里云账号对应独立的 RAM Role、OSS Bucket 和 MNS 资源，通过不同的流水线变量管理凭证，实现完全隔离。推荐将不同环境划分到不同的阿里云主账号，通过阿里云资源目录（Resource Directory）进行统一治理。
