# 云效集成方案 - 直连 IacService 模式

基于阿里云云效（CodeUp + Flow）与阿里云 IacService 的 CI/CD 集成方案，通过 IacService API 直接触发 Terraform 资源栈的自动化部署。

> **🌐 语言**：[中文文档](README-CN.md) | [English Docs](README.md)

## 目录

- [云效集成方案 - 直连 IacService 模式](#云效集成方案---直连-iacservice-模式)
  - [目录](#目录)
- [概述](#概述)
- [前期准备](#前期准备)
  - [准备代码仓库](#准备代码仓库)
  - [前置开通准备](#前置开通准备)
    - [RAM 用户 1：管理用户](#ram-用户-1管理用户)
    - [RAM 用户 2：流水线触发用户](#ram-用户-2流水线触发用户)
    - [RAM 角色：自动化服务台执行角色](#ram-角色自动化服务台执行角色)
  - [创建自动化服务台模板](#创建自动化服务台模板)
    - [控制台操作](#控制台操作)
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
    - [0. Profile 配置](#0-profile-配置)
    - [1. 代码上传到 IacService](#1-代码上传到-iacservice)
    - [2. 创建资源栈](#2-创建资源栈)
  - [变更流程](#变更流程)
  - [运行参数说明](#运行参数说明)
- [运维参考](#运维参考)
  - [故障排查](#故障排查)
  - [多环境配置](#多环境配置)
    - [1. 创建 deployments 配置](#1-创建-deployments-配置)
    - [2. 配置云效流水线变量](#2-配置云效流水线变量)
    - [3. 创建 IacService 模块和资源栈](#3-创建-iacservice-模块和资源栈)
    - [4. 验证配置](#4-验证配置)

---

# 概述

```
Developer → 云效流水线 → IacService API(上传代码 + 触发执行) → 执行部署 → IacService API(查询结果) → 云效流水线 → 输出结果
```

与 OSS MNS 中转模式不同，直连模式通过 IacService API 直接上传代码包和触发资源栈执行，无需中转 OSS 和 MNS。

流水线分为 5 个阶段：

```
代码上传 → plan 审核 → 执行 Plan → apply 审核 → 执行 Apply
```

> **注意**：云效不支持由合并请求自动触发带参数的流水线，因此采用手动触发 + 备注参数的方式。实际变更流程为：开发分支提交代码 → 创建合并请求 → 手动运行验证流水线 → 评审通过 → 合入主干。

辅助脚本（`scripts/`）：

| 脚本 | 语言 | 依赖 | 作用 |
|------|------|------|------|
| `upload_iac_module.py` | Python 3.12 | `alibabacloud_iacservice20210806` | 打包代码并上传到 IacService 模块。通过环境变量 `IAC_ACCESS_KEY_ID`/`IAC_ACCESS_KEY_SECRET`/`IAC_REGION`/`CODE_MODULE_ID` 读取凭证和配置 |
| `trigger_stack.py` | Python 3.12 | `alibabacloud_iacservice20210806` | 触发资源栈的 Plan 或 Apply 操作，返回 Trigger ID 用于后续查询 |
| `get_trigger_result.py` | Python 3.12 | `alibabacloud_iacservice20210806`, `PyYAML` | 轮询 IacService API 等待执行结果，格式化输出。支持多 profile 并行轮询（多线程），默认超时 600 秒 |
| `yamlparser.py` | Python 3.12 | `PyYAML` | YAML 配置文件解析，兼容 `yq` 命令行调用方式 |

---

# 前期准备

## 准备代码仓库

在云效中创建新仓库，将 `ci-templates/direct-iacservice/alibaba-cloud-devops/` 目录下的所有文件复制到自己仓库的根目录中，提交并推送：

```bash
git init
git remote add origin git@codeup.aliyun.com:<org-id>/<repo-name>.git
git add .
git commit -m "init"
git push -u origin HEAD
```

---

## 前置开通准备

### RAM 用户 1：管理用户

用于开通云效及自动化服务台资源的初始化配置，一次性操作。后续运维人员可使用当前用户登陆进行操作：

1. 登录 [RAM 控制台](https://ram.console.aliyun.com/)，创建用户并启用【OpenAPI 调用访问】
2. 为用户附加以下策略：
   - 云效代码管理&流水线管理相关权限
   - 自定义权限策略 `IaCServiceStackFullAccess`（策略内容见 [docs/iam-policies.md](../../../docs/iam-policies.md)）

### RAM 用户 2：流水线触发用户

用于云效流水线调用 IacService API，将 AccessKey 配置到流水线变量中长期使用：

1. 创建用户并启用【OpenAPI 调用访问】
2. 附加自定义权限策略 `IaCServiceStackTriggerAccess`（策略内容见 [docs/iam-policies.md](../../../docs/iam-policies.md)）
3. 创建 AccessKey，记录 AccessKey ID 和 Secret，后续配置流水线变量时会用到（本文以开发环境为例，假设密钥对命名为 `DEV_ACCESS_KEY_ID` / `DEV_ACCESS_KEY_SECRET`）

### RAM 角色：自动化服务台执行角色

用于授权自动化服务台扮演该角色执行 Terraform 模板。详细操作参考《创建自动化服务台的 RAM 角色》，操作步骤：

1. 在 RAM 控制台创建新的 RAM 角色
2. 配置信任策略，允许自动化服务台服务扮演此角色（信任策略内容见 [docs/iam-policies.md](../../../docs/iam-policies.md)）
3. 为该角色添加执行 Terraform 模板所需的权限策略（例如模板包含 ECS 实例，则需添加 ECS 相关权限）

---

## 创建自动化服务台模板

本步骤主要创建自动化服务台的模板。模板对应一份代码，每次代码修改后需要重新发布为新版本。同一份代码的不同变更对应不同的模板版本。

> **重要**：创建完成后请记录模板 ID（ModuleId），后续步骤需要用到。

### 控制台操作

**步骤 1：新建模板**

点击【模板管理】，选择【新建模板】。

**步骤 2：选择模板来源**

选择【空白模版】方式。

**步骤 3：填写模板参数**

填写如下的参数后，点击【提交】。

| 参数 | 是否必填 | 说明 |
|------|----------|------|
| 模板名称 | 是 | 模板的名称，不可重复 |
| 模板描述 | 否 | 模板的描述信息 |
| 加入项目分组 | 否 | 可选择项目分组，用项目方式统一管理模板 |

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
pip install alibabacloud_iacservice20210806
pip install PyYAML
```

**步骤 4：执行打包并上传**

添加步骤 → 构建 → 执行命令。按照输入的环境列表，分别打包上传代码到 IacService。

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
pip install alibabacloud_iacservice20210806
pip install PyYAML
```

**步骤 3：触发 Plan 执行**

添加步骤 → 构建 → 执行命令。为每个 profile 调用 IacService API 触发 Plan。

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

**步骤 4：查询 Plan 执行结果**

添加步骤 → 构建 → 执行命令。轮询 IacService API 获取执行结果。

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
pip install alibabacloud_iacservice20210806
pip install PyYAML
```

**步骤 3：触发 Apply 执行**

添加步骤 → 构建 → 执行命令。为每个 profile 调用 IacService API 触发 Apply。

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

**步骤 4：查询 Apply 执行结果**

添加步骤 → 构建 → 执行命令。轮询 IacService API 获取执行结果。

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

## 配置流水线变量

在云效流水线【变量管理】中配置密钥对，每个 Key 和 Value 分开存储，Key 名称对应 `profile.yaml` 中配置的密钥对名称。将前置开通准备步骤中创建的 AccessKey 按对应密钥对名称进行存储。如有多个环境，按环境前缀分别配置：

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `DEV_ACCESS_KEY_ID` | 开发环境 AccessKey ID | 加密存储 |
| `DEV_ACCESS_KEY_SECRET` | 开发环境 AccessKey Secret | 加密存储 |


---

# 日常使用

## 创建自动化服务台资源栈

在进行代码的执行前，首先需要在阿里云自动化服务台上创建出对应的资源栈来承载代码的运行。在仓库代码初始化完成后，可复用以上流水线，先将代码打包上传到 IacService，再到自动化服务台上将对应的资源栈一次性创建出来。

### 0. Profile 配置

在 `deployments/[env]/profile.yaml` 中填写配置信息：

```yaml
account_id: "<your-account-id>"
access_key_id: "DEV_ACCESS_KEY_ID"         # 对应云效流水线变量中的变量名
access_key_secret: "DEV_ACCESS_KEY_SECRET"  # 对应云效流水线变量中的变量名
code_module_id: "mod-xxx"                       # IacService 模块 ID
```

> **注意**：`access_key_id` 和 `access_key_secret` 的值是**变量名**，不是实际的 AK 值。实际的 AK 值需要存储为云效的敏感变量，并在流水线中通过变量名引用。


### 1. 代码上传到 IacService

运行配置要指明 profile，stack 名称可随意填，因为本次我们不做部署，只为上传代码。

### 2. 创建资源栈

此处展示如何创建 `stacks/demo` 资源栈，其余同理：

1. **选择创建资源栈**

   登录阿里云自动化服务台（https://iac.console.aliyun.com/stack），选择"创建资源栈"

2. **填入资源栈相关信息**
   - **代码模块**：选择前期准备中创建的 IacService 模块
   - **工作目录**：为资源栈在代码中的存放路径，如 `stacks/demo`
   - **RAM 角色**：选择信任自动化服务台操作资源栈的角色

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

**注意事项**：

- 一个 PR 可重复使用直到 Merge 关闭，但建议每个任务创建独立 PR 便于追踪
- 每次 `apply` 前需先执行 `plan`，`plan` 可连续执行多次
- 不同环境的 profile 对应不同的阿里云账号和资源，互不影响

---

# 运维参考

## 故障排查

| 问题 | 排查方法 |
|------|---------|
| 部署无响应 | 检查流水线变量是否配置正确、IacService 是否正常、RAM 权限是否足够 |
| 命令无法识别 | 确认备注信息格式为 `<profile>:<stack>`，注意冒号分隔符 |
| `make build-package` 失败 | 确认仓库根目录存在 Makefile 且包含 `build-package` 目标 |
| 代码上传失败 | 检查 `code_module_id` 是否正确、AK 是否有 IacService 相关权限 |
| 触发执行失败 | 检查 `code_module_version` 是否正确、资源栈是否已创建 |
| 结果获取超时 | 默认轮询超时 600 秒，检查 IacService 控制台确认 Stack 是否正在执行 |
| 多环境部分失败 | 查看云效流水线日志，确认失败的 profile 名称 |

## 多环境配置

如需新增一个阿里云账号（例如新增 `test` 环境），需完成以下配置：

### 1. 创建 deployments 配置

```bash
cp -r deployments/dev deployments/test
cd deployments/test
```

修改 `profile.yaml` 中的 `account_id`、`code_module_id` 为新环境的值，修改 AK 变量名为新的云效流水线变量 Key。

### 2. 配置云效流水线变量

在云效流水线配置中添加新账号的变量：

| 变量名 | 说明 |
|--------|------|
| `TEST_ACCESS_KEY_ID` | 新账号的 AccessKey ID |
| `TEST_ACCESS_KEY_SECRET` | 新账号的 AccessKey Secret |

### 3. 创建 IacService 模块和资源栈

在新账号的自动化服务台中创建代码模块和资源栈，参考 [创建自动化服务台资源栈](#创建自动化服务台资源栈) 章节。

### 4. 验证配置

提交配置后，手动触发流水线，确认新环境的代码上传和执行正常。

> **账号隔离建议**：每个阿里云账号对应独立的 IacService 模块和资源栈，通过不同的流水线变量管理凭证，实现完全隔离。推荐将不同环境划分到不同的阿里云主账号，通过阿里云资源目录（Resource Directory）进行统一治理。

---
