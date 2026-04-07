# IacService IAM Policy Reference / IacService IAM 权限策略参考

## 1. RAM User Policies / RAM 用户权限策略

### 1.1 IacService Full Access Policy / 自动化服务台完全访问策略

Suggested policy name: `IaCServiceStackFullAccess`. Grant this policy when initializing and configuring IacService resources (Stacks, Modules, Detect Configs, etc.).

策略名称建议：`IaCServiceStackFullAccess`，用于初始化配置自动化服务台资源（资源栈、模块、检测配置等）时授予。

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "iacservice:CreateStack",
        "iacservice:UpdateStack",
        "iacservice:RefreshStack",
        "iacservice:DeleteStack",
        "iacservice:GetStack",
        "iacservice:ListStacks",
        "iacservice:ListStackConfigs"
      ],
      "Resource": "acs:iacservice:*:*:stack/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "iacservice:CreateModule",
        "iacservice:ListModules",
        "iacservice:GetModule",
        "iacservice:UpdateModuleAttribute",
        "iacservice:DeleteModule",
        "iacservice:UploadModule",
        "iacservice:CreateModuleVersion",
        "iacservice:GetModuleVersion",
        "iacservice:ListModuleVersion"
      ],
      "Resource": "acs:iacservice:*:*:module/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "iacservice:CreateDetectConfig",
        "iacservice:UpdateDetectConfig",
        "iacservice:DeleteDetectConfig",
        "iacservice:GetDetectConfig",
        "iacservice:ListDetectConfigs"
      ],
      "Resource": "acs:iacservice:*:*:detectconfig/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "iacservice:AssociateDetectConfig",
        "iacservice:DissociateDetectConfig",
        "iacservice:GetTerraformStateDetection",
        "iacservice:DetectTerraformState",
        "iacservice:ListDetectConfigRelations",
        "iacservice:GetStackDeployments",
        "iacservice:ListJobs",
        "iacservice:GetTask",
        "iacservice:GetJob",
        "iacservice:ListResources"
      ],
      "Resource": "*"
    }
  ]
}
```

### 1.2 VCS Minimum Privilege Policy / VCS 侧最小权限策略

Suggested policy name: `IaCServiceStackTriggerAccess`. This is the minimum set of permissions required for CI/CD pipelines to call IacService, including uploading modules, triggering Stack execution, and retrieving execution results.

策略名称建议：`IaCServiceStackTriggerAccess`，CI/CD 流水线调用 IacService 所需的最小权限，包括上传模块、触发资源栈执行及获取执行结果。

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "iacservice:UploadModule",
      "Resource": "acs:iacservice:*:*:module/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "iacservice:GetStackExecutionResult",
        "iacservice:TriggerStackExecution"
      ],
      "Resource": "acs:iacservice:*:*:stack/*"
    }
  ]
}
```

## 2. RAM Role Trust Policy / RAM 角色信任策略

### 2.1 IacService Execution Role Trust Policy / 自动化服务台执行角色信任策略

Allows the IacService service (`iac.aliyuncs.com`) to assume this role to execute Terraform templates.

允许自动化服务台服务（`iac.aliyuncs.com`）扮演该角色执行 Terraform 模板。

**Steps:**

1. Create a new RAM Role in the RAM Console.
2. Configure the following trust policy:
3. Attach the permission policies required for executing Terraform templates to this role. For example, add ECS-related permissions if the template includes ECS instances, add VPC-related permissions if it includes VPC resources, and so on.

**创建步骤：**

1. 在 RAM 控制台创建新的 RAM 角色。
2. 配置以下信任策略：
3. 为该角色添加执行 Terraform 模板所需的权限策略。例如，模板包含 ECS 实例则需添加 ECS 相关权限，包含 VPC 资源则需添加 VPC 相关权限，以此类推。

```json
{
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Effect": "Allow",
      "Principal": {
        "Service": [
          "iac.aliyuncs.com"
        ]
      }
    }
  ],
  "Version": "1"
}
```
