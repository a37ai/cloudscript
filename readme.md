<a id="readme-top"></a>

<!-- PROJECT SHIELDS -->
[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]
[![LinkedIn][linkedin-shield]][linkedin-url]

<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://cloudscript.ai"><img src="resources/logo.png" alt="Logo" width="300"></a><p align="center" style="margin-top: 0; font-size: 1.5em;"><i>an <a href="https://a37.ai">a37.ai</a> product</i></p>
  <hr style="width: 100%; margin: 1em auto;">

  <p align="center">
    <!-- The future of IaC -->
    <!-- <br /> -->
    <a href="https://docs.cloudscript.ai"><strong>Explore the docs »</strong></a>
    <br />
<!--     <br /> -->
<!--     <a href="https://github.com/othneildrew/Best-README-Template">View Demo</a>
    &middot; -->
    <a href="https://github.com/o37-autoforge/cloud/issues/new?labels=bug&template=bug-report---.md">Report Bug</a>
    &middot;
    <a href="https://github.com/o37-autoforge/cloud/issues/new?labels=enhancement&template=feature-request---.md">Request Feature</a>
  </p>
</div>



<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-cloudscript">About Cloudscript</a>
      <ul>
        <li><a href="#key-features">Key Features</a></li>
      </ul>
    </li>
    <li>
      <a href="#language-components-overview">Language Components Overview</a>
      <!-- <ul>
        <li><a href="#service">Service</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul> -->
    </li>
    <li><a href="#cloudscript-cli">Cloudscript CLI</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>

<!-- ABOUT CLOUDSCRIPT -->
# About Cloudscript

Cloudscript is an Infrastructure as Code (IaC) language designed to simplify the deployment and management of cloud resources, applications, and configurations. With Cloudscript, you can combine the functionality of Terraform, Ansible, and Kubernetes into a single, cohesive .cloud file for seamless orchestration.

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
 
<p align="right">(<a href="#readme-top">back to top</a>)</p>

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
 
<p align="right">(<a href="#readme-top">back to top</a>)</p>

# Cloudscript CLI

- **`cloud convert [file path]`**
  - Converts your .cloud file into the appropriate Terraform, Ansible and Kubernetes files within an IaC directory.
  - Ensures valid syntax for the .cloud file.

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

# Preview the deployment plan
cloud plan my_infrastructure.cloud

# Deploy all resources
cloud apply my_infrastructure.cloud

# Destroy all resources
cloud destroy my_infrastructure.cloud
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONTRIBUTING -->
# Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request
   
### Top contributors:

<a href="https://github.com/o37-autoforge/cloud/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=o37-autoforge/cloud" alt="contrib.rocks image" />
</a>

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- LICENSE -->
# License

Distributed under the MIT License. See `LICENSE.txt` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONTACT -->
# Contact

[a37.ai](https://a37.ai) - [team@tryforge.ai](mailto:team@tryforge.ai)

Project Link: [https://github.com/o37-autoforge/cloud/](https://github.com/o37-autoforge/cloud/)

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/o37-autoforge/cloud.svg?style=for-the-badge
[contributors-url]: https://github.com/o37-autoforge/cloud/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/o37-autoforge/cloud.svg?style=for-the-badge
[forks-url]: https://github.com/o37-autoforge/cloud/network/members
[stars-shield]: https://img.shields.io/github/stars/o37-autoforge/cloud.svg?style=for-the-badge
[stars-url]: https://github.com/o37-autoforge/cloud/stargazers
[issues-shield]: https://img.shields.io/github/issues/o37-autoforge/cloud.svg?style=for-the-badge
[issues-url]: https://github.com/o37-autoforge/cloud/issues
[license-shield]: https://img.shields.io/github/license/o37-autoforge/cloud.svg?style=for-the-badge
[license-url]: https://github.com/o37-autoforge/cloud/blob/master/LICENSE.txt
[linkedin-shield]: https://img.shields.io/badge/-LinkedIn-black.svg?style=for-the-badge&logo=linkedin&colorB=555
[linkedin-url]: https://linkedin.com/in/othneildrew
[product-screenshot]: images/screenshot.png
[Next.js]: https://img.shields.io/badge/next.js-000000?style=for-the-badge&logo=nextdotjs&logoColor=white
[Next-url]: https://nextjs.org/
[React.js]: https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB
[React-url]: https://reactjs.org/
[Vue.js]: https://img.shields.io/badge/Vue.js-35495E?style=for-the-badge&logo=vuedotjs&logoColor=4FC08D
[Vue-url]: https://vuejs.org/
[Angular.io]: https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white
[Angular-url]: https://angular.io/
[Svelte.dev]: https://img.shields.io/badge/Svelte-4A4A55?style=for-the-badge&logo=svelte&logoColor=FF3E00
[Svelte-url]: https://svelte.dev/
[Laravel.com]: https://img.shields.io/badge/Laravel-FF2D20?style=for-the-badge&logo=laravel&logoColor=white
[Laravel-url]: https://laravel.com
[Bootstrap.com]: https://img.shields.io/badge/Bootstrap-563D7C?style=for-the-badge&logo=bootstrap&logoColor=white
[Bootstrap-url]: https://getbootstrap.com
[JQuery.com]: https://img.shields.io/badge/jQuery-0769AD?style=for-the-badge&logo=jquery&logoColor=white
[JQuery-url]: https://jquery.com 

