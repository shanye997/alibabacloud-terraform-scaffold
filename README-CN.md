# 阿里云自动化服务台（IacService）资源栈多账号管理脚手架

这是一个用来管理多账号下阿里云自动化服务台资源栈的脚手架项目，提供了标准化的代码组织架构和与各类版本控制系统（VCS）集成的完整示例。

> **🌐 语言**：[中文文档](README-CN.md) | [English Docs](README.md)

## 目录

- [项目概述](#项目概述)
- [自动化服务台资源栈](#自动化服务台资源栈)
- [仓库结构](#仓库结构)
- [代码结构核心概念](#代码结构核心概念)
- [VCS 集成方案](#vcs-集成方案)
- [常见问题](#常见问题)
- [相关资源](#相关资源)
- [贡献指南](#贡献指南)

## 项目概述

本脚手架采用多环境管理架构，支持：
- 多环境隔离（Dev、Staging、Prod）
- 基于组件的模块化配置
- 与阿里云 IacService 集成
- GitHub 和阿里云云效 的完整 CI/CD 方案

## 自动化服务台资源栈

**资源栈（Stack）** 是阿里云自动化服务台的核心概念，旨在解决 Terraform 模版在多环境、多账号、多 Region 等企业级场景中难以平衡统一管理与环境隔离的矛盾。它通过组件将代码进行拆分，在保证可复用性的基础上增强了灵活性，同时将多个环境作为一个整体进行管理，帮助企业实现快速验证、部署和复制。每个资源栈代表一个完整的业务场景或解决方案。

Stack 的设计是"一次定义，多次部署"，即一份 Stack 定义可以通过不同的参数输入完成不同环境的部署。因此，需要通过两份 Schema 分别完成 Stack Definition 和 Stack Deployment 的配置。

### tfcomponent.yaml - 资源栈模板定义 (Stack Component)
描述基础设施的组件和它们之间的关系，定义了"要部署什么"，包括:
- **variable**: 定义用户需要提供的输入变量
- **local**: 定义本地变量，用于在模板内部进行计算和转换
- **required_providers**: 声明所需的 Terraform Provider 及其版本
- **provider**: 配置 Provider 的参数 (如区域、凭证)
- **component**: 引用具体的云产品组件
- **output**: 定义资源栈执行后的输出结果

### tfdeploy.yaml - 资源栈部署配置 (Stack Deployment)
描述在不同环境中如何部署这些组件，定义了"如何部署"，包括:
- **deployment**: 部署实例列表，支持多环境多实例
- **locals**: 定义部署级别的本地变量
- **publish_output**: 配置输出发布策略
- **upstream_input**: 引用上游资源栈的输出作为输入

📚 **详细语法规范**：请参阅 [资源栈语法说明](docs/stack-syntax.md)，了解完整的 YAML 语法、字段说明和最佳实践。

## 仓库结构

```
alibabacloud-terraform-scaffold/
├── modules/                        # 模块定义
│   ├── vpc/
│   ├── sls-project/
│   └── ... (其他模块)
├── components/                     # 组件定义
│   ├── account-factory/
│   ├── guardrails/
│   ├── identity/
│   └── ... (其他组件)
├── stacks/                         # Stack 定义
│   ├── account-factory/
│   │   └── tfcomponent.yaml
│   ├── guardrails/
│   ├── identity/
│   └── ... (其他 stacks)
├── deployments/                    # 各账号自定义配置
│   ├── dev-account/               # 开发环境
│   │   ├── profile.yaml          # 身份认证信息
│   │   ├── account-factory/
│   │   │   └── tfdeploy.yaml
│   │   ├── guardrails/
│   │   │   ├── tfdeploy.yaml
│   │   │   └── config.yaml
│   │   └── ... (其他 stacks 配置)
│   ├── staging-account/           # 预发布环境
│   │   ├── profile.yaml
│   │   └── ...
│   └── prod-account/              # 生产环境
│       ├── profile.yaml
│       └── ...
├── ci-templates/                   # VCS 集成模板目录
│   ├── oss-mns-relay/             # OSS MNS 中转连接模式
│   │   ├── github/                # GitHub 集成方案
│   │   │   ├── .github/workflows/ # GitHub 工作流
│   │   │   ├── bootstrap/         # 环境初始化配置
│   │   │   └── scripts/           # CI/CD 辅助脚本
│   │   └── alibaba-cloud-devops/         # 阿里云云效 集成方案
│   │       ├── bootstrap/         # 环境初始化配置
│   │       └── scripts/           # CI/CD 辅助脚本
│   └── direct-iacservice/         # 直接连接自动化服务台模式
│       └── alibaba-cloud-devops/         # 阿里云云效 集成方案
│           └── scripts/           # CI/CD 辅助脚本
├── docs/                           # 文档目录
│   ├── iam-policies.md            # RAM 权限策略参考
│   └── stack-syntax.md            # 资源栈语法说明
├── Makefile                        # 构建脚本
├── .gitignore                      # Git 忽略规则
├── README.md                       # 项目说明文档（英文）
└── README-CN.md                    # 项目说明文档（中文）
```

**说明：** 当前仓库主要分为两部分内容：
1. **代码结构**：包括 `modules/`、`components/`、`stacks/`、`deployments/` 等核心目录，定义了 Terraform 模块、组件、资源栈和多环境部署配置
2. **VCS 集成示例**：`ci-templates/` 目录提供了与各类版本控制系统（GitHub、阿里云云效 等）集成的完整示例和模板

## 代码结构核心概念

### 1. Modules（模块定义）
`modules/` 目录定义可重用的 Terraform 模块，位于最底层的细粒度模块层。通常满足以下条件才被抽象为一个 Module：

- 负责单个产品的创建和配置
- 使用到的 Terraform Resource 或 Datasource 数量 >= 2

每个模块目录包含：
- `variables.tf`: 输入变量定义
- `main.tf`: 模块资源定义
- `outputs.tf`: 输出定义
- `README.md`: 模块说明文档

### 2. Components（组件定义）
`components/` 目录定义基础组件，可以认为是更高维度的 Module。Component 的开发方式和 Terraform Module 一样。例如 Landing Zone 的功能模块或子模块可以抽象为一个 Component。

每个组件目录包含：
- `variables.tf`: 输入变量定义
- `main.tf`: 组件资源定义
- `outputs.tf`: 输出定义
- `README.md`: 组件说明文档


### 3. Stack（资源栈定义）
`stacks/` 目录定义可重用的资源栈模板，用于组合多个 Components 形成完整的解决方案。

**核心文件:**
- **tfcomponent.yaml**: 资源栈的定义文件，声明如何调用底层组件
  - `variable`: 定义用户传入的变量
  - `required_providers`: 声明所需的 Terraform Provider 及其版本约束
  - `provider`: 配置 Provider 的具体参数（如区域、凭证等）
  - `component`: 引用 `components/` 中定义的组件
  - `output`: 定义资源栈执行后的输出结果

每个资源栈目录包含:
- `tfcomponent.yaml`: 资源栈配置文件

> **💡 文件存放**：在多环境 CI 管理模式下，`tfcomponent.yaml` 存放在 `stacks/` 目录下，而 `tfdeploy.yaml` 存放在 `deployments/<env>/` 的每个环境目录下，实现一份 Stack 定义在多环境中复用。

### 4. Deployment（部署实例）
`deployments/` 目录是为了满足多账号下统一管理的需求而抽取的配置层，将 `tfdeploy.yaml` 按照账号分别存储，实现一套资源栈模板在多账号环境下的复用和隔离。

**核心文件:**

**profile.yaml** - 环境级别的凭证和配置，包含三类变量：

| 类型 | 变量名 | 说明 |
|------|--------|------|
| **身份变量** | `access_key_id` | 访问密钥 ID |
| （用于上传代码和触发执行） | `access_key_secret` | 访问密钥 Secret |
| **自动化服务台 CI 变量** | `code_module_id` | 直连模式：Code 模块 ID |
| （用于关联自动化服务台上资源） | `oss_bucket` | OSS 中转模式：OSS Bucket 名称 |
| | `oss_region` | OSS 中转模式：OSS 区域 |
| **普通变量** | - | 其他自定义配置 |

- **tfdeploy.yaml**: 资源栈在特定账号下的实际部署参数
  - `deployment`: 部署实例列表，支持单账号多实例部署
  - `inputs`: 为 `tfcomponent.yaml` 中声明的变量提供具体值
  - **存放规则**：文件路径必须与 `stacks/` 目录中对应的 `tfcomponent.yaml` 保持相对路径一致，例如 `stacks/my-vpc/tfcomponent.yaml` 对应 `deployments/dev/my-vpc/tfdeploy.yaml`

每个环境目录包含：
- `profile.yaml`: 环境凭证配置文件
- 多个以资源栈命名的子目录，每个子目录包含独立的 `tfdeploy.yaml`

## VCS 集成方案

通过 VCS 集成，将基础设施即代码（IaC）的变更生命周期纳入既有的代码协作工作流，以 PR/MR 作为变更的准入门控，由自动化服务台承接 Terraform 的计划与执行，从而在不引入额外运维工具链的前提下实现基础设施变更的版本化、可审计与可追溯。

本脚手架提供多种 VCS 集成方案的实现，按 **连接模式** 和 **VCS 平台** 两个维度组织：

| 连接模式 | GitHub | 阿里云云效 |
|---------|--------|------------|
| **直连自动化服务台** | 🚧 规划中 | ✅ [查看文档](ci-templates/direct-iacservice/alibaba-cloud-devops/README-CN.md) |
| **OSS MNS 中转 (不推荐)** | ✅ [查看文档](ci-templates/oss-mns-relay/github/README-CN.md) | ✅ [查看文档](ci-templates/oss-mns-relay/alibaba-cloud-devops/README-CN.md) |



### 直连自动化服务台模式
直接调用阿里云 IacService API 进行部署，链路更短、延迟更低。

- **阿里云云效**：详见 [`ci-templates/direct-iacservice/alibaba-cloud-devops/`](ci-templates/direct-iacservice/alibaba-cloud-devops/README-CN.md)

> 📝 **持续完善中**：更多 VCS 平台和连接模式的支持正在编写中，欢迎 [提交 Issue](https://github.com/alibabacloud-automation/alibabacloud-terraform-scaffold/issues/new) 反馈需求。

### OSS MNS 中转模式（不推荐）
通过阿里云 OSS 和 MNS 服务实现事件驱动的部署流程，适用于需要解耦 VCS 事件与部署执行的场景。

- **GitHub**：详见 [`ci-templates/oss-mns-relay/github/`](ci-templates/oss-mns-relay/github/README-CN.md)
- **阿里云云效**：详见 [`ci-templates/oss-mns-relay/alibaba-cloud-devops/`](ci-templates/oss-mns-relay/alibaba-cloud-devops/README-CN.md)


## 常见问题

### Q: Stack 和 Deployment 的区别是什么？
A: Stack 是模板（类），Deployment 是实例（对象）。一个 Stack 可以在不同环境中创建多个 Deployment 实例。例如，同一个 VPC Stack 可以在 dev、staging、prod 环境分别创建不同配置的实例。

### Q: 如何管理敏感信息？
A:
- `profile.yaml` 中使用变量名称（如 `DEV_ACCESS_KEY_ID`）作为占位符，不存放实际密钥
- 实际的 AccessKey 存储在 CI 平台的加密变量中（GitHub 使用 Secrets，云效使用流水线变量）
- CI/CD 运行时通过变量名引用，自动注入实际值

### Q: bootstrap、scripts、.github/workflows 是必需的吗？
A: 这些目录位于 `ci-templates/oss-mns-relay/github/` 下，是 GitHub + OSS MNS 中转集成方案的特定实现。如果使用其他 VCS（如 GitLab、阿里云云效），可以使用对应的实现方式，但需要实现类似的功能（代码打包上传、触发部署、结果回写）。

### Q: 是否支持 Terraform 原生配置？
A: 本脚手架基于阿里云 IacService，使用 YAML 格式配置（tfcomponent.yaml、tfdeploy.yaml）。如需使用原生 Terraform HCL 配置，可以参考 `ci-templates/oss-mns-relay/github/bootstrap` 目录中的 .tf 文件。

### Q: 一个 tfdeploy.yaml 可以定义多个部署吗？
A: 可以。tfdeploy.yaml 中的 `deployment` 是一个数组，可以定义多个部署实例，每个实例有独立的名称和参数配置。

### Q: 如何在本地测试 Stack？
A: 可以直接通过阿里云 IacService 控制台或 CLI 工具，上传 Stack 和 Deployment 配置进行测试。不需要依赖 CI/CD 流程。

## 相关资源

- [阿里云 Terraform Provider](https://registry.terraform.io/providers/aliyun/alicloud/latest/docs)
- [Terraform 官方文档](https://www.terraform.io/docs)

## 贡献指南

欢迎提交 Issue 和 Pull Request 来改进这个脚手架。


