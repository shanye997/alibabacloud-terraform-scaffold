# Stack Syntax Reference / 资源栈语法说明

This document provides a detailed description of the YAML configuration file syntax for Alibaba Cloud IacService Stacks, including the Stack Component Schema and Stack Deployment Schema.

本文档详细介绍阿里云自动化服务台资源栈的 YAML 配置文件语法规范，包括 Stack Component Schema 和 Stack Deployment Schema。

---

## Stack Component Schema

Stack Component describes the structure and variable declarations of a Stack, defining how to invoke underlying components to build complete solutions. It supports the following schema fields:

Stack Component 用于描述资源栈的结构和变量声明，定义如何调用底层组件来构建完整的解决方案。支持以下 schema：

- `format_version`: Specifies the template version / 指定模板的版本
- `description`: Describes the template / 描述所写模板
- `component`: Declares the components referenced by the Stack / 声明 Stack 所要引用的组件
- `variable`: Declares variables defined in the Stack / 声明 Stack 中所定义的变量
- `provider`: Declares the provider configurations the Stack depends on / 声明 Stack 所依赖的 provider 的配置
- `required_providers`: Declares the provider definitions the Stack depends on / 声明 Stack 所依赖的 provider 定义
- `local`: Declares common parameters for Stack deployment / 声明 Stack 在部署时的公共参数
- `output`: Declares outputs defined in the Stack / 声明 Stack 中所定义的出参

### format_version

Specifies the template version for better template management and upgrades. Format: `<pop code>/<pop version>`.

指定模板的版本，用于后续对模板进行更好的管理和升级。格式遵循：`<pop code>/<pop version>`。

**Current version / 当前版本：** `IaCService/2021-08-06`

### description

Describes the template.

用于描述所写模板。

### variable

Declares variables defined in the Stack.

用来声明 Stack 中所定义的变量。

**Fields / 字段说明：**

| Field / 字段 | Description / 描述 | Required / 必填 | Type / 类型 | Example / 示例值 |
|------|------|------|------|--------|
| name | Unique identifier in the template / 变量在模板中的唯一标识 | Yes / 是 | string | unique_variable_name |
| type | Variable type / 变量的类型 | Yes / 是 | string | string |
| description | Variable description / 变量的描述 | No / 否 | string | Description of the purpose of this variable |
| default | Default value / 变量的默认值 | No / 否 | any | "Default variable value" |
| sensitive | Whether the value is sensitive / 变量值是否敏感 | No / 否 | bool | false |
| nullable | Whether the variable allows null / 变量是否允许为空 | No / 否 | bool | false |
| ephemeral | Whether to mark the value as ephemeral / 是否将变量值标记为动态值 | No / 否 | bool | false |

**Example / 示例：**

```yaml
variable:
  - name: region
    type: string
    description: "阿里云区域"
    
  - name: vpc_name
    type: string
    description: "VPC 名称"
    
  - name: vpc_cidr
    type: string
    description: "VPC CIDR 块"
    default: "10.0.0.0/8"
    
  - name: tags
    type: map(string)
    description: "资源标签"
    default: {}
    
  - name: zone_ids
    type: list(string)
    description: "可用区 ID 列表"
    
  - name: vswitch_cidrs
    type: list(string)
    description: "交换机 CIDR 列表"
```

### required_providers

Declares the provider definitions the Stack depends on.

用来声明 Stack 中所依赖的 provider 定义。

**Fields / 字段说明：**

| Field / 字段 | Description / 描述 | Required / 必填 | Type / 类型 | Example / 示例值 |
|------|------|------|------|--------|
| name | Provider identifier / provider 的标识 | Yes / 是 | string | aws |
| source | Provider source path / provider 的路径 | Yes / 是 | string | hashicorp/aws |
| version | Provider version / provider 的版本 | No / 否 | string | ~> 5.7.0 |

**Example / 示例：**

```yaml
required_providers:
  - name: alicloud
    source: hashicorp/alicloud
    version: "~> 1.251.0"
```

### provider

Declares the provider configurations the Stack depends on.

用来声明 Stack 所依赖的 provider 的配置。

**Fields / 字段说明：**

| Field / 字段 | Description / 描述 | Required / 必填 | Type / 类型 | Example / 示例值 |
|------|------|------|------|--------|
| type | Provider type / provider 的类型 | Yes / 是 | string | aws |
| name | Provider identifier in code / 同一类 provider 在代码中的标识 | Yes / 是 | string | configurations |
| config | Detailed provider configuration / provider 的详细配置 | No / 否 | map | {region = each.value} |
| for_each | Loop configuration (not yet supported) / 支持循环配置（一期暂不支持） | No / 否 | string | var.regions |

**Example / 示例：**

```yaml
provider:
  - type: alicloud
    name: this
    config:
      region: var.region
```

### component

Declares the components referenced by the Stack.

用来声明 Stack 所要引用的组件。

**Fields / 字段说明：**

| Field / 字段 | Description / 描述 | Required / 必填 | Type / 类型 | Example / 示例值 |
|------|------|------|------|--------|
| name | Unique component identifier in the template / component 在模板中的唯一标识 | Yes / 是 | string | "s3" |
| source | Module referenced by the component / component 所引用的 Module | Yes / 是 | string | "./s3" |
| version | Version of the public Module referenced / component 所引用的公共 Module 版本 | No / 否 | string | |
| inputs | Key-value pairs defining input parameters / KV 形式定义所要传入 component 的入参值 | No / 否 | map | {region = each.value} |
| providers | Key-value pairs defining dependent providers / KV 形式定义 component 所依赖的 provider | Yes / 是 | map | {aws = provider.aws.configurations[each.value]} |
| depends_on | Names of other components this depends on / component 所依赖的其他 components 的名称 | No / 否 | list(string) | ["component.vpc"] |
| for_each | Loop configuration / 支持循环配置 | No / 否 | string | var.regions |

**Example / 示例:**

```yaml
component:
  - name: vpc
    source: "../modules/vpc"
    inputs:
      vpc_name: var.vpc_name
      vpc_cidr: var.vpc_cidr
      vpc_description: created by terraform
      tags: merge(var.tags, {created_by = "tf"})
    providers:
      alicloud: provider.alicloud.this
      
  - name: vswitch
    source: "../modules/vswitch"
    inputs:
      vswitch_name: var.vpc_name-vswitch
      vpc_id: component.vpc.vpc_id
      vswitch_cidrs: var.vswitch_cidrs
      zone_ids: var.zone_ids
    providers:
      alicloud: provider.alicloud.this
    depends_on:
      - component.vpc
```

### output

Declares the outputs defined in the Stack.

用来声明 Stack 中所定义的出参。

**Fields / 字段说明：**

| Field / 字段 | Description / 描述 | Required / 必填 | Type / 类型 | Example / 示例值 |
|------|------|------|------|--------|
| name | Unique output identifier in the template / 出参在模板中的唯一标识 | Yes / 是 | string | unique_name_of_output |
| type | Output type / 出参的类型 | Yes / 是 | string | string |
| description | Output description / 出参的描述 | No / 否 | string | Description of the purpose of this output |
| value | Output value / 出参的值 | Yes / 是 | any | component.component_name.some_value |
| sensitive | Whether the output value is sensitive / 出参值是否敏感 | No / 否 | bool | false |
| ephemeral | Whether to remove the output from state / 是否将出参从 state 中移除 | No / 否 | bool | false |

**Example / 示例：**

```yaml
output:
  - name: vpc_id
    type: string
    description: "The id of vpc created"
    value: "${component.vpc.vpc_id}"
    
  - name: vswitch_ids
    type: list(string)
    description: "The ids of all vswitches"
    value: "${component.vswitch.vswitch_ids}"
```

### local

Declares common parameters for Stack deployment.

用来声明 Stack 在部署时的一些公共参数。

**Example / 示例：**

```yaml
local:
  service_name: "forum"
  owner: "Community Team"
  common_tags:
    Environment: "${var.environment}"
    Owner: "${local.owner}"
```

---

## Stack Component Full Example / Stack Component 完整示例

```yaml
format_version: IaCService/2021-08-06
description: 创建 vpc & vswitch

variable:
  - name: region
    type: string
    description: "阿里云区域"
    
  - name: vpc_name
    type: string
    description: "VPC 名称"
    
  - name: vpc_cidr
    type: string
    description: "VPC CIDR 块"
    
  - name: tags
    type: map(string)
    description: "资源标签"
    default: {}
    
  - name: zone_ids
    type: list(string)
    description: "可用区 ID 列表"
    
  - name: vswitch_cidrs
    type: list(string)
    description: "交换机 CIDR 列表"

required_providers:
  - name: alicloud
    source: hashicorp/alicloud
    version: "~> 1.251.0"

provider:
  - type: alicloud
    name: this
    config:
      region: var.region

component:
  - name: vpc
    source: "../modules/vpc"
    inputs:
      vpc_name: var.vpc_name
      vpc_cidr: var.vpc_cidr
      vpc_description: created by terraform
      tags: merge(var.tags, {created_by = "tf"})
    providers:
      alicloud: provider.alicloud.this
      
  - name: vswitch
    source: "../modules/vswitch"
    inputs:
      vswitch_name: var.vpc_name-vswitch
      vpc_id: component.vpc.vpc_id
      vswitch_cidrs: var.vswitch_cidrs
      zone_ids: var.zone_ids
    providers:
      alicloud: provider.alicloud.this
    depends_on:
      - component.vpc

output:
  - name: vpc_id
    type: string
    description: "The id of vpc created"
    value: component.vpc.vpc_id
    
  - name: vswitch_ids
    type: list(string)
    description: "The ids of all vswitches"
    value: component.vswitch.vswitch_ids
```

---

## Stack Deployment Schema

Stack Deployment describes the actual deployment parameters of a Stack in a specific environment, assigning concrete values to the variables declared in the Stack Component. It supports the following schema fields:

Stack Deployment 用于描述资源栈在特定环境下的实际部署参数，将 Stack Component 中声明的变量赋予具体值。支持以下 schema：

- `format_version`: Specifies the template version / 指定模板的版本
- `description`: Describes the template / 描述所写模板
- `deployment`: Declares the deployment configurations / 声明 Stack 所依赖的 deployment 的配置
- `store`: Declares parameter set references for deployment / 声明 Stack 在部署时对参数集的引用
- `locals`: Declares common parameters for deployment / 声明 Stack 在部署时的公共参数
- `orchestrate`: Declares specific behaviors during deployment / 声明 Stack 在部署时的具体行为
- `publish_output`: Declares publishable outputs / 声明 Stack 可以发布的出参
- `upstream_input`: Declares importable inputs / 声明 Stack 可以导入的入参

### format_version

Specifies the template version for better template management and upgrades. Format: `<pop code>/<pop version>`.

指定模板的版本，用于后续对模板进行更好的管理和升级。格式遵循：`<pop code>/<pop version>`。

**Current version / 当前版本：** `IaCService/2021-08-06`

### description

Describes the template.

用于描述所写模板。

### deployment

Declares the deployment configurations the Stack depends on.

用来声明 Stack 所依赖的 deployment 的配置。

**Fields / 字段说明：**

| Field / 字段 | Description / 描述 | Required / 必填 | Type / 类型 | Example / 示例值 |
|------|------|------|------|--------|
| inputs | Input parameters for deployment / 部署时的入参 | Yes / 是 | map | {region = "cn-hangzhou"} |

**Example / 示例：**

```yaml
deployment:
  - name: development
    inputs:
      region: "cn-hangzhou"
      vpc_name: "vpc-dev"
      vpc_cidr: "192.168.0.0/16"
      tags:
        environment: "development"
      zone_ids: ["cn-hangzhou-j", "cn-hangzhou-k"]
      vswitch_cidrs: ["192.168.1.0/24", "192.168.2.0/24"]
      
  - name: production
    inputs:
      region: "cn-beijing"
      vpc_name: "vpc-prod"
      vpc_cidr: "192.168.0.0/16"
      tags:
        environment: "production"
      zone_ids: ["cn-beijing-l", "cn-beijing-k"]
      vswitch_cidrs: ["192.168.1.0/24", "192.168.2.0/24"]
```

### locals

Declares common parameters for Stack deployment.

用来声明 Stack 在部署时的一些公共参数。

**Example / 示例：**

```yaml
locals:
  service_name: "forum"
  owner: "Community Team"
  common_tags:
    Environment: "Production"
    Owner: "${local.owner}"
```

### publish_output

Declares the outputs that a Stack can publish.

用来声明 Stack 可以发布的出参。

**Fields / 字段说明：**

| Field / 字段 | Description / 描述 | Required / 必填 | Type / 类型 | Example / 示例值 |
|------|------|------|------|--------|
| description | Output description / 出参的描述 | No / 否 | string | Description of the purpose of this output |
| value | Output value / 出参的值 | Yes / 是 | any | deployment.deployment_name.some_value |

**Example / 示例：**

```yaml
publish_output:
  - name: prod_vpc_id
    description: "The id of production vpc"
    value: deployment.production.vpc_id
```

### upstream_input

Declares the inputs that a Stack can import from upstream Stacks.

用来声明 Stack 可以导入的入参。

**Fields / 字段说明：**

| Field / 字段 | Description / 描述 | Required / 必填 | Type / 类型 | Example / 示例值 |
|------|------|------|------|--------|
| name | Reference input name / 引用入参名称 | Yes / 是 | string | upstream_stack_name |
| type | Input type, currently only supports "stack" / 入参的类型，当前只支持 "stack" | Yes / 是 | string | stack |
| source | Input value, the ARN of the Stack / 入参的值，为 stack 的 arn | Yes / 是 | string | app.terraform.io/{organization_name}/{project_name}/{upstream_stack_name} |

**Example / 示例：**

```yaml
upstream_input:
  - name: upstream_stack
    type: stack
    source: "iac.aliyuncs.com/{AccountId}/{StackName}"

deployment:
  - name: application
    inputs:
      vpc_id: upstream_input.upstream_stack.vpc_id
```

---

## Stack Deployment Full Example / Stack Deployment 完整示例

```yaml
format_version: IaCService/2021-08-06
description: 创建开发和生产环境

upstream_input:
  - name: upstream_stack
    type: stack
    source: "iac.aliyuncs.com/{AccountId}/{StackName}"

deployment:
  - name: development
    inputs:
      region: "cn-hangzhou"
      vpc_name: "vpc-dev"
      vpc_cidr: "192.168.0.0/16"
      tags:
        environment: "development"
      zone_ids: ["cn-hangzhou-j", "cn-hangzhou-k"]
      vswitch_cidrs: ["192.168.1.0/24", "192.168.2.0/24"]
      
  - name: production
    inputs:
      region: "cn-beijing"
      # vpc_name: "vpc-prod"
      vpc_name: upstream_input.upstream_stack.vpc_name
      vpc_cidr: "192.168.0.0/16"
      tags:
        environment: "production"
      zone_ids: ["cn-beijing-l", "cn-beijing-k"]
      vswitch_cidrs: ["192.168.1.0/24", "192.168.2.0/24"]

publish_output:
  - name: prod_vpc_id
    description: "The id of production vpc"
    value: deployment.production.vpc_id
```
