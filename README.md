# Alibaba Cloud IacService Stack Multi-Account Management Scaffold

A scaffold project for managing Alibaba Cloud IacService Stacks across multiple accounts, providing standardized code organization and complete integration examples with various version control systems (VCS).

> **🌐 Language**：[中文文档](README-CN.md) | [English Docs](README.md)

## Table of Contents

- [Project Overview](#project-overview)
- [IacService Stack](#iac-service-stack)
- [Repository Structure](#repository-structure)
- [Core Concepts](#core-concepts)
- [VCS Integration](#vcs-integration)
- [FAQ](#faq)
- [Related Resources](#related-resources)
- [Contributing](#contributing)

## Project Overview

This scaffold adopts a multi-environment management architecture, supporting:
- Multi-environment isolation (Dev, Staging, Prod)
- Component-based modular configuration
- Integration with Alibaba Cloud IacService
- Complete CI/CD solutions for GitHub and Alibaba Cloud DevOps

## IacService Stack

**Stack** is a core concept of Alibaba Cloud IacService, designed to address the challenge of balancing unified management and environment isolation when using Terraform templates across multiple environments, accounts, and regions in enterprise scenarios. It splits code into components, enhancing flexibility while maintaining reusability, and manages multiple environments as a whole to help enterprises achieve rapid validation, deployment, and replication. Each Stack represents a complete business scenario or solution.

Stacks are designed with a "define once, deploy many" approach — a single Stack definition can be deployed to different environments with different parameter inputs. Two schemas are used to configure the Stack Definition and Stack Deployment respectively.

### tfcomponent.yaml - Stack Component Definition
Describes infrastructure components and their relationships, defining "what to deploy", including:
- **variable**: Defines input variables that users need to provide
- **local**: Defines local variables for internal computation and transformation
- **required_providers**: Declares required Terraform Providers and their versions
- **provider**: Configures Provider parameters (e.g., region, credentials)
- **component**: References specific cloud product components
- **output**: Defines outputs after Stack execution

### tfdeploy.yaml - Stack Deployment Configuration
Describes how to deploy these components in different environments, defining "how to deploy", including:
- **deployment**: List of deployment instances, supporting multi-environment and multi-instance
- **locals**: Defines deployment-level local variables
- **publish_output**: Configures output publishing strategy
- **upstream_input**: References outputs from upstream Stacks as inputs

📚 **Detailed Syntax Reference**: See [Stack Syntax Reference](docs/stack-syntax.md) for complete YAML syntax, field descriptions, and best practices.

## Repository Structure

```
alibabacloud-terraform-scaffold/
├── modules/                        # Module definitions
│   ├── vpc/
│   ├── sls-project/
│   └── ... (other modules)
├── components/                     # Component definitions
│   ├── account-factory/
│   ├── guardrails/
│   ├── identity/
│   └── ... (other components)
├── stacks/                         # Stack definitions
│   ├── account-factory/
│   │   └── tfcomponent.yaml
│   ├── guardrails/
│   ├── identity/
│   └── ... (other stacks)
├── deployments/                    # Per-account custom configurations
│   ├── dev-account/               # Development environment
│   │   ├── profile.yaml          # Authentication information
│   │   ├── account-factory/
│   │   │   └── tfdeploy.yaml
│   │   ├── guardrails/
│   │   │   ├── tfdeploy.yaml
│   │   │   └── config.yaml
│   │   └── ... (other stack configs)
│   ├── staging-account/           # Staging environment
│   │   ├── profile.yaml
│   │   └── ...
│   └── prod-account/              # Production environment
│       ├── profile.yaml
│       └── ...
├── ci-templates/                   # VCS integration template directory
│   ├── oss-mns-relay/             # OSS MNS relay connection mode
│   │   ├── github/                # GitHub integration
│   │   │   ├── .github/workflows/ # GitHub workflows
│   │   │   ├── bootstrap/         # Environment initialization config
│   │   │   └── scripts/           # CI/CD helper scripts
│   │   └── alibaba-cloud-devops/         # Alibaba Cloud DevOps integration
│   │       ├── bootstrap/         # Environment initialization config
│   │       └── scripts/           # CI/CD helper scripts
│   └── direct-iacservice/         # Direct IacService connection mode
│       └── alibaba-cloud-devops/         # Alibaba Cloud DevOps integration
│           └── scripts/           # CI/CD helper scripts
├── docs/                           # Documentation directory
│   ├── iam-policies.md            # RAM policy reference
│   └── stack-syntax.md            # Stack syntax reference
├── Makefile                        # Build script
├── .gitignore                      # Git ignore rules
├── README.md                       # Project documentation (English)
└── README-CN.md                    # Project documentation (Chinese)
```

**Note:** The repository is organized into two main parts:
1. **Code Structure**: Includes core directories `modules/`, `components/`, `stacks/`, `deployments/`, defining Terraform modules, components, Stacks, and multi-environment deployment configurations
2. **VCS Integration Examples**: The `ci-templates/` directory provides complete integration examples and templates for various version control systems (GitHub, Alibaba Cloud DevOps, etc.)

## Core Concepts

### 1. Modules
The `modules/` directory defines reusable Terraform modules at the finest-grained layer. A piece of infrastructure is typically abstracted into a Module when it meets the following criteria:

- Responsible for creating and configuring a single product
- Uses 2 or more Terraform Resources or Datasources

Each module directory contains:
- `variables.tf`: Input variable definitions
- `main.tf`: Module resource definitions
- `outputs.tf`: Output definitions
- `README.md`: Module documentation

### 2. Components
The `components/` directory defines foundational components, which can be thought of as higher-level Modules. Components are developed the same way as Terraform Modules. For example, functional modules or sub-modules of a Landing Zone can be abstracted as a Component.

Each component directory contains:
- `variables.tf`: Input variable definitions
- `main.tf`: Component resource definitions
- `outputs.tf`: Output definitions
- `README.md`: Component documentation


### 3. Stack
The `stacks/` directory defines reusable Stack templates that combine multiple Components into complete solutions.

**Core file:**
- **tfcomponent.yaml**: The Stack definition file, declaring how to invoke underlying components
  - `variable`: Defines user-provided variables
  - `required_providers`: Declares required Terraform Providers and version constraints
  - `provider`: Configures specific Provider parameters (e.g., region, credentials)
  - `component`: References components defined in `components/`
  - `output`: Defines outputs after Stack execution

Each Stack directory contains:
- `tfcomponent.yaml`: Stack configuration file

> **💡 File Placement**: In multi-environment CI management mode, `tfcomponent.yaml` is stored in the `stacks/` directory, while `tfdeploy.yaml` is stored in each environment directory under `deployments/<env>/`, enabling a single Stack definition to be reused across multiple environments.

### 4. Deployment
The `deployments/` directory is a configuration layer extracted to meet the need for unified management across multiple accounts. It stores `tfdeploy.yaml` separately by account, enabling a single Stack template to be reused and isolated across multiple account environments.

**Core files:**

**profile.yaml** - Environment-level credentials and configuration, containing three types of variables:

| Type | Variable | Description |
|------|----------|-------------|
| **Identity Variables** | `access_key_id` | Access Key ID |
| (for uploading code and triggering execution) | `access_key_secret` | Access Key Secret |
| **IacService CI Variables** | `code_module_id` | Direct mode: Code Module ID |
| (for associating IacService resources) | `oss_bucket` | OSS relay mode: OSS Bucket name |
| | `oss_region` | OSS relay mode: OSS region |
| **Normal Variables** | - | Other custom configurations |

- **tfdeploy.yaml**: Actual deployment parameters for a Stack under a specific account
  - `deployment`: List of deployment instances, supporting multiple instances per account
  - `inputs`: Provides concrete values for variables declared in `tfcomponent.yaml`
  - **Placement rule**: The file path must match the relative path of the corresponding `tfcomponent.yaml` in the `stacks/` directory. For example, `stacks/my-vpc/tfcomponent.yaml` corresponds to `deployments/dev/my-vpc/tfdeploy.yaml`

Each environment directory contains:
- `profile.yaml`: Environment credentials configuration file
- Multiple subdirectories named after Stacks, each containing an independent `tfdeploy.yaml`

## VCS Integration

VCS integration embeds the IaC change lifecycle into existing code collaboration workflows, using PR/MR as the change gate while delegating Terraform plan and apply to IacService, achieving versioned, auditable, and traceable infrastructure changes without introducing additional operational toolchains.

This scaffold provides multiple VCS integration implementations, organized by **connection mode** and **VCS platform**:

| Connection Mode | GitHub | Alibaba Cloud DevOps |
|----------------|--------|----------------|
| **Direct IacService** | 🚧 Planned | ✅ [View Docs](ci-templates/direct-iacservice/alibaba-cloud-devops/README.md) |
| **OSS MNS Relay (Not Recommended)** | ✅ [View Docs](ci-templates/oss-mns-relay/github/README.md) | ✅ [View Docs](ci-templates/oss-mns-relay/alibaba-cloud-devops/README.md) |



### Direct IacService Mode
Deploys directly via Alibaba Cloud IacService API, with shorter link chain and lower latency.

- **Alibaba Cloud DevOps**: See [`ci-templates/direct-iacservice/alibaba-cloud-devops/`](ci-templates/direct-iacservice/alibaba-cloud-devops/README.md)

> 📝 **Work in Progress**: Support for more VCS platforms and connection modes is being developed. Feel free to [submit an Issue](https://github.com/alibabacloud-automation/alibabacloud-terraform-scaffold/issues/new) with your requirements.

### OSS MNS Relay Mode (Not Recommended)
Implements event-driven deployment workflows through Alibaba Cloud OSS and MNS services, suitable for scenarios requiring decoupling of VCS events from deployment execution.

- **GitHub**: See [`ci-templates/oss-mns-relay/github/`](ci-templates/oss-mns-relay/github/README.md)
- **Alibaba Cloud DevOps**: See [`ci-templates/oss-mns-relay/alibaba-cloud-devops/`](ci-templates/oss-mns-relay/alibaba-cloud-devops/README.md)


## FAQ

### Q: What is the difference between Stack and Deployment?
A: A Stack is a template (class), while a Deployment is an instance (object). A single Stack can create multiple Deployment instances across different environments. For example, the same VPC Stack can create instances with different configurations in dev, staging, and prod environments.

### Q: How are sensitive credentials managed?
A:
- `profile.yaml` uses variable names (e.g., `DEV_ACCESS_KEY_ID`) as placeholders — no actual keys are stored
- Actual AccessKeys are stored in the CI platform's encrypted variables (GitHub uses Secrets, Alibaba Cloud DevOps uses pipeline variables)
- During CI/CD execution, actual values are automatically injected via variable name references

### Q: Are bootstrap, scripts, and .github/workflows required?
A: These directories are located under `ci-templates/oss-mns-relay/github/` and are specific to the GitHub + OSS MNS relay integration. If using other VCS platforms (e.g., GitLab, Alibaba Cloud DevOps), you can use corresponding implementations, but similar functionality is required (code packaging/upload, deployment triggering, result reporting).

### Q: Does it support native Terraform configuration?
A: This scaffold is based on Alibaba Cloud IacService and uses YAML configuration (tfcomponent.yaml, tfdeploy.yaml). For native Terraform HCL configuration, refer to the .tf files in the `ci-templates/oss-mns-relay/github/bootstrap` directory.

### Q: Can a single tfdeploy.yaml define multiple deployments?
A: Yes. The `deployment` field in tfdeploy.yaml is an array that can define multiple deployment instances, each with independent names and parameter configurations.

### Q: How can I test a Stack locally?
A: You can upload Stack and Deployment configurations directly through the Alibaba Cloud IacService console or CLI tool for testing. No CI/CD pipeline is required.

## Related Resources

- [Alibaba Cloud Terraform Provider](https://registry.terraform.io/providers/aliyun/alicloud/latest/docs)
- [Terraform Documentation](https://www.terraform.io/docs)

## Contributing

Contributions via Issues and Pull Requests are welcome to help improve this scaffold.
