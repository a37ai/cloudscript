# Cloudscript

Cloudscript is an Infrastructure as Code (IaC) language designed to simplify the deployment and management of cloud resources, applications, and configurations. With Cloud, you can combine the functionality of Terraform, Ansible, and Kubernetes into a single, cohesive .cloud file for seamless orchestration.

## Key Features

- **Unified Syntax**: Define infrastructure, configurations, and containers in one file.
- **Multi-Provider Support**: Easily target multiple cloud providers.
- **Simplified Workflows**: Define the order of operations and dependencies between components.
- **Extensibility**: Configure containers, virtual machines, and Kubernetes clusters with intuitive blocks.
- **Deployment Patterns**: Apply mappings and conditional deployments using simple syntax.
- **Enhanced Syntax Features**:
  - **Enhanced For Loops**: Simplify iteration over lists and ranges.
  - **Type Definitions**: Define reusable and structured types.
  - **Calculated Fields (`calc`)**: Dynamically compute field values.
  - **Functions**: Create reusable logic blocks.

# Language Components Overview

### **Service**
- Encapsulates the entire deployment, including infrastructure, configuration, and containers.
- Specifies the `provider`, `order` of operations, and global settings for the application.

### **Provider**
- Declares the cloud provider to target (e.g., AWS, GCP, Azure).

### **Infrastructure**
- Defines the foundational resources required for the deployment.

  - **Network**: Sets up virtual private networks, subnets, and IP configurations.
  - **Compute**: Provisions virtual machines or compute instances with desired specifications.
  - **Kubernetes**: Manages Kubernetes clusters, node pools, and their configurations.

### **Configuration**
- Handles server setup, including:
  - Installing packages or tools.
  - Running initialization commands.
  - Verifying server readiness through validation scripts.

### **Containers**
- Defines containerized applications and their runtime specifications.
  - Includes settings for images, replicas, ports, environment variables, and health checks.
  - Configures resource limits and requests for CPU and memory.

### **Deployment**
- Manages how components are applied and interact.
  - **Mappings**: Connect infrastructure components to configurations or services.
  - **Patterns**: Specify conditional logic for deployment based on tags or attributes.

# Cloudscript CLI

- **`cloud convert [file path]`**
  - Converts your .cloud file into the appropriate Terraform, Ansible and Kubernetes files within an IaC directory.
  - Ensures valid syntax for the .cloud file.

- **`cloud validate [file path]`**
  - Validates the provided `cloud` file and offers suggestions for best practices.
  - Example suggestions:
    - Recommend larger instance sizes (e.g., suggest avoiding `t2.micro` in production).
    - Highlight missing or inefficient configurations.

- **`cloud plan [file path]`**
  - Executes a comprehensive dry-run for all Terraform, Kubernetes, and Ansible code.
  - Key features:
    - Requires Docker for Kubernetes planning.
    - Identifies issues in syntax, linting, and deployment feasibility.
    - Outputs a detailed report highlighting potential problems before deployment.

- **`cloud apply [file path]`**
  - Deploys the specified Terraform, Kubernetes, and Ansible code.
  - Key features:
    - Applies changes incrementally and returns errors if there are mismatches between planning and applying.
    - Provides deployment status for each component.

- **`cloud destroy [file path]`**
  - Tears down all resources defined in the `.cloud` file.
  - Destroys Terraform, Kubernetes, and Ansible-managed instances, ensuring a clean removal of all resources.

### **Requirements**
- **Docker**: Required for Kubernetes planning and applying.
- **Dependencies**: Terraform, Kubernetes CLI, and Ansible must be installed and accessible in your environment.

### **Setup for CLI**

1. **Install Python Package (if applicable):**
   Run the following command to install the required Python package:
   ```bash
   pip install -e .
   ```

2. **Install Kubernetes CLI Tools:**
   - **Install `kubectl` (Kubernetes CLI):**
     ```bash
     brew install kubectl
     ```
   - **Install `minikube` (for running Kubernetes locally):**
     ```bash
     brew install minikube
     ```

3. **Download and Open Docker Daemon:**
   - Install Docker Desktop from [Docker's official site](https://www.docker.com/products/docker-desktop).
   - Once installed, open Docker Desktop and ensure the Docker Daemon is running.

### **Example Usage of CLI**
```bash
# Convert a cloud file
cloud convert my_infrastructure.cloud

# Validate a cloud file
cloud validate my_infrastructure.cloud

# Preview the deployment plan
cloud plan my_infrastructure.cloud

# Deploy all resources
cloud apply my_infrastructure.cloud

# Destroy all resources
cloud destroy my_infrastructure.cloud
