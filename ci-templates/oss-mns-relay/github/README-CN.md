# GitHub 集成方案 - OSS MNS 中转模式

基于 GitHub Actions 与阿里云自动化服务台（IacService）的 CI/CD 集成方案，通过 OSS MNS 中转模式实现 Terraform 资源栈的自动化部署。

> **🌐 语言**：[中文文档](README-CN.md) | [English Docs](README.md)

## 目录

- [概述](#概述)
- [前期准备](#前期准备)
  - [初始化云端基础设施](#初始化云端基础设施)
  - [GitHub 配置](#github-配置)
- [GitHub Actions 工作流配置](#github-actions-工作流配置)
  - [工作流文件](#工作流文件)
  - [工作流依赖关系](#工作流依赖关系)
- [日常使用](#日常使用)
  - [创建自动化服务台资源栈](#创建自动化服务台资源栈)
  - [变更流程](#变更流程)
  - [运行参数说明](#运行参数说明)
- [运维参考](#运维参考)
  - [故障排查](#故障排查)
  - [CI 依赖](#ci-依赖)
  - [多环境配置](#多环境配置)
- [附录](#附录)
  - [工作流设计详解](#工作流设计详解)

---

# 概述

```
Developer → PR Comment → GitHub Actions → OSS(代码包+触发文件) → MNS → IacService → 执行部署 → OSS(结果) → GitHub Actions → PR Comment
```

上图为从 GitHub 出发，中转 OSS 管理自动化服务台资源栈的完整运行链路。OSS 与自动化服务台之间的交互逻辑是固定的，GitHub Actions 到 OSS 的交互通过工作流完成代码与触发文件的上传以及运行日志的读取。

工作流通过 PR 评论触发，支持以下命令：

```
iac terraform plan [-profile=<profile>] [-stack=<stack>]
iac terraform apply [-profile=<profile>] [-stack=<stack>]
```

> **自动推断**：当 PR 仅包含 `deployments/` 目录的变更时，可省略 `-profile` 和 `-stack` 参数，工作流会自动从变更文件推断。如果 PR 包含其他目录的变更，则必须手动指定这两个参数。

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

在 GitHub 中创建新仓库，将 `ci-templates/oss-mns-relay/github/` 目录下的所有文件复制到自己仓库的根目录中，提交并推送：

```bash
git add .
git commit -m "init"
git push --set-upstream origin main
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

## GitHub 配置

### 1. 创建 RAM 用户并配置 OSS 权限

创建一个只允许 API 访问的 RAM User，创建 AK，授予以下最小权限（替换 `Mybucket` 为实际 Bucket 名称）：

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

### 2. 配置 GitHub Secrets

将 AK 添加到 GitHub 仓库的 Secrets，每个 Key 和 Value 分开存储，Key 名称对应 `profile.yaml` 中配置的密钥对名称：

| Secrets Key | Secrets Value |
|-------------|---------------|
| `DEV_ACCESS_KEY_ID` | `"xxx"` |
| `DEV_ACCESS_KEY_SECRET` | `"xxx"` |

> 如有多个环境，按环境前缀分别配置，例如 `STAGING_ACCESS_KEY_ID`、`STAGING_ACCESS_KEY_SECRET`、`PROD_ACCESS_KEY_ID`、`PROD_ACCESS_KEY_SECRET`

### 3. 声明工作流环境变量

在 `.github/workflows/pull-request-comment.yml` 和 `scheduled-check.yml` 的 `env` 块中声明 Secrets 引用：

```yaml
env:
  DEV_ACCESS_KEY_ID: ${{ secrets.DEV_ACCESS_KEY_ID }}
  DEV_ACCESS_KEY_SECRET: ${{ secrets.DEV_ACCESS_KEY_SECRET }}
  # 其他环境...
```

> **注意**：所有工作流文件（包括共享工作流）中如使用了硬编码的环境前缀，也需相应添加 Secrets 引用。

### 4. 初始化 OSS

提交当前分支代码，手动触发 GitHub Actions 中的 **Scheduled Check** 工作流以初始化 OSS（运行前选择当前分支，无需勾选 "Whether to run detect check"）。

> 如果运行报错，可能是 `deployments/` 下存在多个环境但未全部配置，删除多余环境目录或补全配置即可。

---

# GitHub Actions 工作流配置

仓库包含 5 个工作流文件，分为两类：

## 工作流文件

**主工作流**（由 GitHub 事件直接触发）：

| 工作流 | 触发方式 | 作用 |
|--------|---------|------|
| `pull-request-comment.yml` | PR 评论创建/编辑 | 解析 `iac terraform plan/apply` 命令，打包上传代码，触发 IacService 执行，将结果回写 PR |
| `scheduled-check.yml` | 手动触发 / 定时任务 | 上传所有环境的源码包到 OSS，可选触发漂移检测 |

**共享工作流**（被主工作流调用，可独立抽取复用）：

| 工作流 | 调用方 | 作用 |
|--------|-------|------|
| `shared-ci-get-pull-request-info.yml` | `pull-request-comment` | 校验 PR 可合并性，解析评论中的 `-profile`/`-stack` 参数，从变更文件自动推断受影响的 stacks |
| `shared-ci-upload-source-package.yml` | `scheduled-check` | 遍历所有 profile，执行 `make build-package` 构建源码包并上传 OSS；单个 profile 失败不影响其他 |
| `shared-ci-upload-trigger-file.yml` | `pull-request-comment` | 为每个 profile 构建源码包、创建包含执行命令和变更 stacks 的触发文件并上传 OSS；任一失败立即终止 |

## 工作流依赖关系

```
pull-request-comment.yml
├── shared-ci-get-pull-request-info.yml    # Step 1: 解析命令、获取 PR 信息
├── shared-ci-upload-trigger-file.yml      # Step 2: 打包上传代码 + 触发文件
└── get_exec_result (内联 job)              # Step 3: 轮询结果 → 回写 PR Comment

scheduled-check.yml
├── shared-ci-upload-source-package.yml    # Step 1: 上传所有 profile 的源码包
└── get_exec_result (内联 job)              # Step 2: 轮询检测结果（仅 run_detect=true 时）
```

---

# 日常使用

## 创建自动化服务台资源栈

在进行代码的执行前，首先需要在阿里云自动化服务台上创建出对应的资源栈来承载代码的运行。在仓库代码初始化完成后，先通过 Scheduled Check 工作流将代码打包上传到 OSS 上，再到自动化服务台上将对应的资源栈一次性创建出来。

到阿里云自动化服务台（https://iac.console.aliyun.com/stack）创建 Stack：

- **资源栈名称**：建议与 `stacks/` 下的模块目录名一致
- **OSS Bucket**：从下拉框选择（已由 bootstrap 初始化创建）
- **OSS Object**：选择对应环境的 OSS Object 路径
- **RAM 角色**：从下拉框选择（已由 bootstrap 初始化创建）
- **工作目录**：填写 stack 的相对路径，如 `stacks/demo`

> **批量创建**：建议将 `stacks/` 目录下定义的所有 Stack 一次性全部创建。每个 Stack 对应一个独立的资源栈，创建完成后会自动执行首次 `plan`，可验证配置的正确性。

## 变更流程

1. 创建开发分支，提交代码变更，推送到 GitHub

```bash
git checkout -b dev
# 修改 stacks/ 或 deployments/[env]/ 中的配置...
git add .
git commit -m "update stack config"
git push --set-upstream origin dev
```

2. 创建 PR 到主分支（如 `main`），在 PR 评论中输入命令触发部署：

```bash
iac terraform plan -profile=dev -stack=demo
iac terraform apply -profile=dev -stack=demo
```

3. 执行结果会自动回写到 PR 评论，确认 apply 结果符合预期
4. 评审通过，变更合入主干

## 运行参数说明

通过 PR 评论传递运行参数，格式如下：

```
iac terraform plan/apply [-profile=<profileName>] [-stack=<StackName>]
```

**参数说明**：

| 参数 | 必填 | 说明 |
|------|------|------|
| `-profile` | 是* | 执行环境，对应 `deployments/` 目录下的环境名称 |
| `-stack` | 是* | 目标 stack 路径，支持目录嵌套，如 `demo/subDir` |

> *当 PR 仅包含 `deployments/` 目录的变更时，可省略这两个参数，工作流会自动从变更文件推断。

**注意事项**：

- 一个 PR 可重复使用直到 Merge 关闭，但建议每个任务创建独立 PR 便于追踪
- 每次 `apply` 前需先执行 `plan`，`plan` 可连续执行多次
- 不同环境的 `-profile` 对应不同的阿里云账号和资源，互不影响

---

# 运维参考

## 故障排查

| 问题 | 排查方法 |
|------|---------|
| 部署无响应 | 检查 GitHub Secrets 是否配置正确、OSS/MNS 服务是否正常、RAM 权限是否足够 |
| 命令无法识别 | 确认 PR Comment 格式为 `iac terraform plan/apply`，注意前缀必须完全匹配 |
| `make build-package` 失败 | 确认仓库根目录存在 Makefile 且包含 `build-package` 目标 |
| profile 上传失败 | 检查 `deployments/[env]/profile.yaml` 中的 `access_key_id`/`access_key_secret` 是否与 GitHub Secrets 中的 Key 名一致 |
| 结果获取超时 | 默认轮询超时 600 秒，检查 IacService 控制台确认 Stack 是否正在执行 |
| 多环境部分失败 | 查看 GitHub Actions 日志，`shared-ci-upload-source-package` 会列出失败的 profile 名称 |
| 查看详细错误信息 | 查看 GitHub Actions 运行日志，或检查 OSS 中的触发文件和结果文件内容 |

## CI 依赖

GitHub Actions 运行时需要以下依赖：

| 依赖 | 用途 | 预置方式 |
|------|------|---------|
| **Python 3.12** | 运行 `upload_to_oss.py` 和 `parse_exec_result.py` 脚本 | 使用 `actions/setup-python@v5` 自动安装 |
| **alibabacloud-oss-v2** | 阿里云 OSS SDK，用于上传代码包和获取执行结果 | `pip install alibabacloud-oss-v2` |
| **PyYAML** | 解析 `profile.yaml` 和凭证文件 | `pip install PyYAML` |
| **make** | 执行 `make build-package` 构建源码包 | `ubuntu-latest` 镜像已预装 |
| **curl / jq** | 获取 PR 信息、解析 JSON 响应 | `ubuntu-latest` 镜像已预装 |

> **离线环境注意**：如 GitHub Actions 运行在自托管 Runner 且无法访问公网，需提前在 Runner 镜像中预装上述依赖，或将依赖包缓存到私有仓库/制品库中。

## 多环境配置

如需新增一个阿里云账号（例如新增 `test` 环境），需完成以下配置：

### 1. 创建 bootstrap 配置

```bash
mkdir -p bootstrap/terraform-test
cp bootstrap/terraform-dev/*.tf bootstrap/terraform-test/

cd bootstrap/terraform-test

# 修改 variables.tf 中的 bucket_name 和 ram_role_name，确保与其他环境不同
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

修改 `profile.yaml` 中的 `oss_bucket`、`oss_region`、`account_id` 为步骤 1 的输出值，修改 `profile.yaml` 中的 AK 变量名为新的 GitHub Secrets Key。

### 3. 配置 GitHub Secrets

在 GitHub 仓库 Settings → Secrets and variables → Actions 中添加：

| Secrets Key | Secrets Value |
|-------------|---------------|
| `TEST_ACCESS_KEY_ID` | 新账号的 AccessKey ID |
| `TEST_ACCESS_KEY_SECRET` | 新账号的 AccessKey Secret |

### 4. 声明 CI 环境变量

在 `.github/workflows/pull-request-comment.yml` 和 `scheduled-check.yml` 的 `env` 块中添加新账号的引用：

```yaml
env:
  # ... 其他环境
  TEST_ACCESS_KEY_ID: ${{ secrets.TEST_ACCESS_KEY_ID }}
  TEST_ACCESS_KEY_SECRET: ${{ secrets.TEST_ACCESS_KEY_SECRET }}
```

> **注意**：所有工作流文件（包括共享工作流）中如使用了硬编码的环境前缀（如 `DEV_`、`PROD_`），也需相应添加 `TEST_` 的引用。

### 5. 创建 Stack

到阿里云 IaC 控制台创建 Stack，选择步骤 1 中创建的 OSS Bucket 和 RAM Role。参考 [创建自动化服务台资源栈](#创建自动化服务台资源栈) 章节。

### 6. 验证配置

提交配置后，手动触发 **Scheduled Check** 工作流，确认新环境的源码包上传成功。

> **账号隔离建议**：每个阿里云账号对应独立的 RAM Role、OSS Bucket 和 MNS 资源，通过不同的 GitHub Secrets 管理凭证，实现完全隔离。推荐将不同环境划分到不同的阿里云主账号，通过阿里云资源目录（Resource Directory）进行统一治理。

---

# 附录

## 工作流设计详解

### pull-request-comment.yml

**触发条件**：PR 评论被创建或编辑时（`issue_comment: [created, edited]`）

**工作流程**：

1. **get_trigger_info** — 调用 `shared-ci-get-pull-request-info.yml`，解析评论中的命令、获取 PR 的 head SHA 和 base ref、推断受影响的 stacks
2. **process_trigger_file** — 调用 `shared-ci-upload-trigger-file.yml`，打包代码并上传触发文件到 OSS
3. **get_exec_result** — 轮询 OSS 执行结果，格式化后回写到 PR 评论

**支持的命令格式**：

```
iac terraform plan [-profile=<profile>] [-stack=<stack>]
iac terraform apply [-profile=<profile>] [-stack=<stack>]
```

> 当 PR 仅包含 `deployments/` 目录的变更时，工作流会自动从变更文件推断 profiles 和 stacks，此时 `-profile` 和 `-stack` 参数可选。如果 PR 包含其他目录的变更，则必须手动指定这两个参数。

### scheduled-check.yml

**触发条件**：手动触发（`workflow_dispatch`）或定时自动运行

**工作流程**：

1. **process_code** — 调用 `shared-ci-upload-source-package.yml`，处理所有 profiles（`profiles: all`）的源码包上传；若启用 `run_detect` 则额外创建检测触发文件
2. **get_exec_result** — 仅在 `run_detect=true` 或定时触发时执行，获取并输出执行结果

**主要用途**：

- **偏差检测（Drift Detection）**：通过 `run_detect=true` 触发，自动检测云上实际资源与 Terraform 配置的偏差
- **源码包初始化**：首次配置时上传源码包到 OSS，为 PR 部署做准备
- **代码完整性验证**：定期验证所有环境的代码可正常构建

> **代码来源**：默认上传 `main` 分支的代码。偏差检测会对比云上资源状态与 `main` 分支配置，发现偏差后生成检测报告。

### 共享工作流

**shared-ci-get-pull-request-info.yml**

获取 PR 详细信息并解析命令参数。主要功能：验证 PR 可合并性、提取 head SHA 和 base ref、解析 `-profile`/`-stack` 参数、从变更文件自动推断受影响的 stacks。

主要输出：`command`、`base_ref`、`head_sha`、`all_changed_stacks`

**shared-ci-upload-source-package.yml**

构建源码包并上传到 OSS，支持多 profile 批量处理。对每个 profile 执行 `make build-package PROFILE=<profile>` 构建代码包，通过 `upload_to_oss.py` 上传到 OSS。单个 profile 失败不影响其他 profile，全部处理完成后统一汇总失败信息。

**shared-ci-upload-trigger-file.yml**

上传源码包和触发文件到 OSS，启动 IacService 执行。解析 `all_changed_stacks` 参数，为每个 profile 创建包含执行命令、代码路径、变更 stacks 的触发文件（JSON 格式）。采用快速失败策略，任一 profile 失败时立即终止。

触发文件结构示例：

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
