from typing import List, Dict, Optional, Tuple
from ..error_mapping.error_mappers import *
import click
import re
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
import subprocess
from pathlib import Path
import json
import os
import sys
from pathlib import Path
import time

class CloudPlanExecutor:
    """Handles execution and error mapping for cloud plan operations"""
    
    def __init__(self, iac_path: str, cloud_file: str, source_mapper):
        self.iac_path = Path(iac_path)
        self.cloud_file = Path(cloud_file)
        self.source_mapper = source_mapper
        self.console = Console()
        
        # Initialize error mappers
        self.tf_mapper = TerraformErrorMapper(source_mapper)
        self.k8s_mapper = KubernetesErrorMapper(source_mapper)
        self.ansible_mapper = AnsibleErrorMapper(source_mapper)
        
        # Store collected errors
        self.errors: List[CloudError] = []
        
    def _execute_terraform_plan(self) -> Tuple[List[str], List[CloudError]]:
        """Execute terraform plan and map any errors"""
        changes = []
        errors = []
        current_block = None
        current_resource = None
        error_context = {}
        
        try:
            # # Create tfvars file with defaults
            # tfvars_content = {
            #     'aws_region': 'us-west-2',
            #     'assume_role_arn': ''
            # }
            
            # tfvars_path = self.iac_path / 'terraform.tfvars.json'
            # tfvars_path.write_text(json.dumps(tfvars_content))

            # Parse Terraform config to build context
            tf_config_path = self.iac_path / 'main.tf.json'
            if tf_config_path.exists():
                with open(tf_config_path) as f:
                    tf_config = json.load(f)
                    if 'resource' in tf_config:
                        error_context['resources'] = tf_config['resource']

            # Debug output
            # self.console.print("[blue]CLOUD:[/blue] Executing Terraform commands...")

            # Run terraform init first
            process = subprocess.Popen(
                ['terraform', 'init'],
                cwd=str(self.iac_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate()
            
            # # Debug output
            self.console.print(f"[blue]CLOUD:[/blue] Terraform init stdout: {stdout}")
            self.console.print(f"[blue]CLOUD:[/blue] Terraform init stderr: {stderr}")


            if process.returncode != 0:
                # self.console.print(f"[blue]CLOUD:[/blue] Terraform init failed with return code: {process.returncode}")
                error = self.tf_mapper.map_error(stderr)
                if error:
                    errors.append(error)
                return changes, errors

            # Run terraform plan
            process = subprocess.Popen(
                ['terraform', 'plan', '-no-color'],
                cwd=str(self.iac_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate()

            # # Debug output
            self.console.print(f"[blue]CLOUD:[/blue] Terraform plan stdout: {stdout}")
            self.console.print(f"[blue]CLOUD:[/blue] Terraform plan stderr: {stderr}")

            # Process output
            if process.returncode != 0:
                # Try to extract context from error message
                resource_match = re.search(r'Error: .* "([^"]+)" "([^"]+)"', stderr)
                if resource_match:
                    error_context['current_resource_type'] = resource_match.group(1)
                    error_context['current_resource_name'] = resource_match.group(2)
                    
                error = self.tf_mapper.map_error(stderr, error_context)
                if error:
                    errors.append(error)
            else:
                # Parse successful plan output
                for line in stdout.splitlines():
                    if 'resource "' in line:
                        match = re.search(r'resource "([^"]+)" "([^"]+)"', line)
                        if match:
                            resource_type, resource_name = match.groups()
                            # Update current context
                            current_block = 'infrastructure'
                            current_resource = f"{resource_type}.{resource_name}"
                            error_context['current_block'] = current_block
                            error_context['current_resource'] = current_resource
                            
                            if resource_type == 'aws_instance':
                                cloud_change = f"CREATE: compute '{resource_name}' in infrastructure block"
                                changes.append(cloud_change)
                                self.console.print(f"[blue]CLOUD:[/blue] {cloud_change}")
                            elif resource_type == 'aws_vpc':
                                cloud_change = f"CREATE: network '{resource_name}' in infrastructure block"
                                changes.append(cloud_change)
                                self.console.print(f"[blue]CLOUD:[/blue] {cloud_change}")

        except Exception as e:
            self.console.print(f"[blue]CLOUD:[/blue] Exception in terraform plan: {str(e)}")
            # Try to get source location from context
            source_location = None
            if current_resource:
                source_location = self.source_mapper.get_source_location(current_resource)
            
            if not source_location:
                source_location = CloudSourceLocation(
                    line=1,
                    column=1,
                    block_type='infrastructure',
                    resource_type=CloudResourceType.COMPUTE,  # Add this
                    resource_name=current_resource,  # Add this
                    metadata={'error_context': error_context}  # Now this will work
                )
                
        # finally:
        #     # Cleanup
        #     if tfvars_path.exists():
        #         tfvars_path.unlink()
                
        return changes, errors

    def _execute_kubernetes_plan(self) -> Tuple[List[str], List[CloudError]]:
        """Execute Kubernetes dry-run and map any errors"""
        changes = []
        errors = []
        
        try:
            self.console.print("\n[blue]CLOUD:[/blue] Executing Kubernetes commands...")

            # Check if Docker is running first
            try:
                docker_check = subprocess.run(
                    ['docker', 'info'],
                    capture_output=True,
                    text=True
                )
                if docker_check.returncode != 0:
                    error = CloudError(
                        severity=CloudErrorSeverity.ERROR,
                        message="Docker is not running",
                        source_location=CloudSourceLocation(
                            line=1,
                            column=1,
                            block_type='containers',
                            resource_type=CloudResourceType.CONTAINER,
                            resource_name="all"
                        ),
                        suggestion="Start Docker before running Kubernetes plan"
                    )
                    errors.append(error)
                    return changes, errors
            except FileNotFoundError:
                error = CloudError(
                    severity=CloudErrorSeverity.ERROR,
                    message="Docker is not installed",
                    source_location=CloudSourceLocation(
                        line=1,
                        column=1,
                        block_type='containers'
                    ),
                    suggestion="Install Docker to proceed with Kubernetes plan"
                )
                errors.append(error)
                return changes, errors

            # First, check if minikube is installed
            try:
                # Stop any existing minikube cluster first
                self.console.print("[blue]CLOUD:[/blue] Stopping any existing Minikube cluster...")
                stop_process = subprocess.run(
                    ['minikube', 'stop'],
                    capture_output=True,
                    text=True
                )
                self.console.print(f"[blue]CLOUD:[/blue] Stop output: {stop_process.stdout}")

                # Delete the cluster to ensure clean state
                self.console.print("[blue]CLOUD:[/blue] Deleting existing Minikube cluster...")
                delete_process = subprocess.run(
                    ['minikube', 'delete'],
                    capture_output=True,
                    text=True
                )
                self.console.print(f"[blue]CLOUD:[/blue] Delete output: {delete_process.stdout}")

                self.console.print("[blue]CLOUD:[/blue] Starting fresh Minikube cluster...")
                start_process = subprocess.Popen(
                    ['minikube', 'start', '--driver=docker', '--force'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )

                # Capture output while checking for completion
                while True:
                    stdout_line = start_process.stdout.readline()
                    stderr_line = start_process.stderr.readline()
                    
                    if stdout_line:
                        self.console.print(f"[blue]CLOUD:[/blue] Minikube: {stdout_line.strip()}")
                    if stderr_line:
                        self.console.print(f"[blue]CLOUD:[/blue] Minikube error: {stderr_line.strip()}")
                    
                    # Check if process has completed
                    retcode = start_process.poll()
                    if retcode is not None:
                        # Get any remaining output
                        remaining_stdout, remaining_stderr = start_process.communicate()
                        if remaining_stdout:
                            self.console.print(f"[blue]CLOUD:[/blue] Minikube: {remaining_stdout.strip()}")
                        if remaining_stderr:
                            self.console.print(f"[blue]CLOUD:[/blue] Minikube error: {remaining_stderr.strip()}")
                            
                        if retcode != 0:
                            error = CloudError(
                                severity=CloudErrorSeverity.ERROR,
                                message=f"Failed to start Minikube cluster: {remaining_stderr if remaining_stderr else ''}",
                                source_location=CloudSourceLocation(
                                    line=1,
                                    column=1,
                                    block_type='containers'
                                ),
                                suggestion="Check Docker is running and has sufficient resources"
                            )
                            errors.append(error)
                            return changes, errors
                        break
                    
                    # Only break if we have a returncode (process completed)
                    # Otherwise keep reading output
                    if not stdout_line and not stderr_line and retcode is not None:
                        break

            except FileNotFoundError:
                error = CloudError(
                    severity=CloudErrorSeverity.ERROR,
                    message="Minikube is not installed",
                    source_location=CloudSourceLocation(
                        line=1,
                        column=1,
                        block_type='containers'
                    ),
                    suggestion="Install Minikube to proceed with Kubernetes plan"
                )
                errors.append(error)
                return changes, errors

            self.console.print("\n[blue]CLOUD:[/blue] Waiting for Kubernetes cluster to be ready...")
            max_retries = 5
            retry_delay = 5  # seconds
            for attempt in range(max_retries):
                try:
                    process = subprocess.run(
                        ['kubectl', 'get', 'nodes'],
                        capture_output=True,
                        text=True
                    )
                    self.console.print(f"[blue]CLOUD:[/blue] kubectl get nodes stdout: {process.stdout}")
                    self.console.print(f"[blue]CLOUD:[/blue] kubectl get nodes stderr: {process.stderr}")

                    if process.returncode == 0:
                        self.console.print("[blue]CLOUD:[/blue] Kubernetes cluster is ready.")
                        break
                    else:
                        self.console.print(f"[blue]CLOUD:[/blue] Kubernetes cluster not ready. Attempt {attempt + 1} of {max_retries}. Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                except Exception as e:
                    self.console.print(f"[blue]CLOUD:[/blue] Error checking Kubernetes cluster status: {str(e)}")
                    time.sleep(retry_delay)
            else:
                error = CloudError(
                    severity=CloudErrorSeverity.ERROR,
                    message="Kubernetes cluster failed to become ready",
                    source_location=CloudSourceLocation(
                        line=1,
                        column=1,
                        block_type='containers'
                    ),
                    suggestion="Ensure Minikube started correctly and Kubernetes components are running"
                )
                errors.append(error)
                return changes, errors

            # Validate Kubernetes configuration with dry-run
            self.console.print("\n[blue]CLOUD:[/blue] Validating Kubernetes configuration with dry-run...")
            process = subprocess.run(
                ['kubectl', 'apply', '--dry-run=server', '-f', str(self.iac_path / 'resources.yml')],
                capture_output=True,
                text=True
            )

            # Debug output
            self.console.print(f"[blue]CLOUD:[/blue] Kubectl apply stdout: {process.stdout}")
            self.console.print(f"[blue]CLOUD:[/blue] Kubectl apply stderr: {process.stderr}")

            if process.returncode != 0:
                self.console.print(f"[blue]CLOUD:[/blue] Kubectl apply failed with return code: {process.returncode}")
                error = self.k8s_mapper.map_error(process.stderr)
                if error:
                    errors.append(error)
            else:
                # Parse successful validation output
                for line in process.stdout.splitlines():
                    if any(resource in line.lower() for resource in ['deployment', 'service', 'pod', 'configmap', 'horizontalpodautoscaler']):
                        self.console.print(f"[blue]CLOUD:[/blue] Found change line: {line}")
                        match = re.search(r'(deployment|service|pod|configmap|horizontalpodautoscaler)[/.]([^\s]+)', line, re.IGNORECASE)
                        if match:
                            resource_type, resource_name = match.groups()
                            if "created" in line.lower():
                                cloud_change = f"CREATE: {resource_type} '{resource_name}' in containers block"
                            elif "configured" in line.lower() or "unchanged" in line.lower():
                                cloud_change = f"MODIFY: {resource_type} '{resource_name}' in containers block"
                            elif "deleted" in line.lower():
                                cloud_change = f"DELETE: {resource_type} '{resource_name}' in containers block"
                            else:
                                cloud_change = f"UPDATE: {resource_type} '{resource_name}' in containers block"
                            self.console.print(f"[blue]CLOUD:[/blue] Converted to cloud change: {cloud_change}")
                            changes.append(cloud_change)

        except Exception as e:
            self.console.print(f"[blue]CLOUD:[/blue] Exception in kubernetes plan: {str(e)}")
            error = CloudError(
                severity=CloudErrorSeverity.ERROR,
                message=f"Failed to validate Kubernetes configuration: {str(e)}",
                source_location=CloudSourceLocation(
                    line=1,
                    column=1,
                    block_type='containers'
                )
            )
            errors.append(error)

        finally:
            # Cleanup
            try:
                subprocess.run(['minikube', 'stop'], check=False, capture_output=True)
                subprocess.run(['minikube', 'delete'], check=False, capture_output=True)
            except Exception as e:
                self.console.print(f"[blue]CLOUD:[/blue] Error during cleanup: {str(e)}")
                
        return changes, errors

    def _execute_ansible_check(self) -> Tuple[List[str], List[CloudError]]:
        """Execute ansible check mode using a prebuilt Docker container with Ansible and map any errors."""
        changes = []
        errors = []
        inventory_path = None
        task_name = None
        temp_inventory_path = None

        try:
            self.console.print("\n[blue]CLOUD:[/blue] Setting up Docker environment for Ansible...")

            # Ensure Docker is installed
            try:
                subprocess.run(["docker", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except subprocess.CalledProcessError:
                error = CloudError(
                    severity=CloudErrorSeverity.ERROR,
                    message="Docker is not installed or not running. Required for configuration validation.",
                    source_location=CloudSourceLocation(
                        line=1,
                        column=1,
                        block_type='configuration'
                    ),
                    suggestion="Install and start Docker to proceed with Ansible checks."
                )
                errors.append(error)
                return changes, errors

            # Convert relative IaC path to absolute path
            absolute_iac_path = Path(self.iac_path).resolve()
            self.console.print(f"[blue]CLOUD:[/blue] Resolved IaC path: {absolute_iac_path}")

            # Validate if playbook.yml exists
            playbook_path = absolute_iac_path / "playbook.yml"
            if not playbook_path.exists():
                error = CloudError(
                    severity=CloudErrorSeverity.ERROR,
                    message=f"Playbook file not found at {playbook_path}",
                    source_location=CloudSourceLocation(
                        line=1,
                        column=1,
                        block_type='configuration'
                    ),
                    suggestion="Ensure the playbook.yml file exists in the IaC directory."
                )
                errors.append(error)
                return changes, errors

            # Create temporary inventory file for local testing
            inventory_content = """
all:
    hosts:
        localhost:
            ansible_connection: local
    children:
        web_servers:
            hosts:
                localhost
"""
            temp_inventory_path = absolute_iac_path / 'temp_inventory.yml'
            with open(temp_inventory_path, 'w') as f:
                f.write(inventory_content)
            self.console.print(f"[blue]CLOUD:[/blue] Created temporary inventory at {temp_inventory_path}")

            # Pull and start the container using the geerlingguy Docker image
            container_name = "ansible_ubuntu_test"
            try:
                self.console.print("\n[blue]CLOUD:[/blue] Pulling geerlingguy/docker-ubuntu2204-ansible Docker image...")
                subprocess.run(["docker", "pull", "geerlingguy/docker-ubuntu2204-ansible"], check=True)

                self.console.print("\n[blue]CLOUD:[/blue] Starting Docker container...")
                subprocess.run([
                    "docker", "run", "-d", "--rm", "--name", container_name,
                    "-v", f"{absolute_iac_path}:/workspace",  # Mount IaC directory
                    "-w", "/workspace",
                    "geerlingguy/docker-ubuntu2204-ansible", "sleep", "3600"
                ], check=True)

                # Ensure package cache is updated and necessary repositories are added in the container
                self.console.print("\n[blue]CLOUD:[/blue] Updating package cache and adding Docker repository...")
                subprocess.run([
                    "docker", "exec", container_name, "bash", "-c",
                    "apt-get update && apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release && "
                    "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add - && "
                    "add-apt-repository 'deb [arch=amd64] https://download.docker.com/linux/ubuntu focal stable' && "
                    "apt-get update"
                ], check=True)

                # Get sudo password with proper prompt
                import getpass
                self.console.print("\n[blue]CLOUD:[/blue] Sudo password required for configuration checks:")
                sudo_pass = getpass.getpass()

                # Run Ansible playbook check inside the container
                self.console.print("\n[blue]CLOUD:[/blue] Running Ansible playbook check in the container...")
                process = subprocess.Popen(
                    [
                        "docker", "exec", "-e", f"ANSIBLE_BECOME_PASS={sudo_pass}", container_name,
                        "ansible-playbook", "--diff",
                        "-i", "/workspace/temp_inventory.yml",
                        "/workspace/playbook.yml"
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                stdout, stderr = process.communicate()

                # Debug output
                self.console.print(f"[blue]CLOUD:[/blue] Ansible check stdout: {stdout}")
                self.console.print(f"[blue]CLOUD:[/blue] Ansible check stderr: {stderr}")

                if process.returncode != 0:
                    self.console.print(f"[blue]CLOUD:[/blue] Ansible check failed with return code: {process.returncode}")

                    # If the error is due to service management, start Nginx manually
                    error_output = stdout + stderr
                    if "Could not find the requested service nginx" in error_output:
                        self.console.print("\n[blue]CLOUD:[/blue] Manually starting Nginx in the container...")
                        subprocess.run([
                            "docker", "exec", container_name, "bash", "-c",
                            "nginx -g 'daemon off;' &"
                        ], check=False)

                        # Re-run Ansible to validate
                        process = subprocess.Popen(
                            [
                                "docker", "exec", "-e", f"ANSIBLE_BECOME_PASS={sudo_pass}", container_name,
                                "ansible-playbook", "--check", "--diff",
                                "-i", "/workspace/temp_inventory.yml",
                                "/workspace/playbook.yml"
                            ],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True
                        )
                        stdout, stderr = process.communicate()
                        self.console.print(f"[blue]CLOUD:[/blue] Re-run Ansible check stdout: {stdout}")
                        self.console.print(f"[blue]CLOUD:[/blue] Re-run Ansible check stderr: {stderr}")

                    # Handle other errors
                    if process.returncode != 0:
                        error = CloudError(
                            severity=CloudErrorSeverity.ERROR,
                            message=f"Failed to execute Ansible playbook: {stderr}",
                            source_location=CloudSourceLocation(
                                line=1,
                                column=1,
                                block_type='configuration'
                            )
                        )
                        errors.append(error)

                else:
                    # Parse successful check output
                    for line in stdout.splitlines():
                        if "TASK [" in line:
                            match = re.search(r'TASK \[(.*?)\]', line)
                            if match:
                                task_name = match.group(1)
                        elif "changed:" in line:
                            if "item=" in line:
                                match = re.search(r'item=([\w-]+)', line)
                                if match:
                                    item = match.group(1)
                                    if task_name and task_name.lower().startswith("install"):
                                        cloud_change = f"CREATE: package '{item}' in configuration block"
                                    else:
                                        cloud_change = f"MODIFY: package '{item}' in configuration block"
                                    changes.append(cloud_change)
                                    self.console.print(f"[blue]CLOUD:[/blue] {cloud_change}")
                            elif "service=" in line or "name=" in line:
                                match = re.search(r'(service|name)=([\w-]+)', line)
                                if match:
                                    service_name = match.group(2)
                                    cloud_change = f"MODIFY: service '{service_name}' in configuration block"
                                    changes.append(cloud_change)
                                    self.console.print(f"[blue]CLOUD:[/blue] {cloud_change}")

            except subprocess.CalledProcessError as e:
                self.console.print(f"[blue]CLOUD:[/blue] Error during Docker or Ansible execution: {str(e)}")
                error = CloudError(
                    severity=CloudErrorSeverity.ERROR,
                    message=f"Failed to execute Ansible check in Docker: {str(e)}",
                    source_location=CloudSourceLocation(
                        line=1,
                        column=1,
                        block_type='configuration'
                    )
                )
                errors.append(error)
        except Exception as e:
            error = CloudError(
                severity=CloudErrorSeverity.ERROR,
                message=f"Unexpected error during Docker setup: {str(e)}",
                source_location=CloudSourceLocation(
                    line=1,
                    column=1,
                    block_type='configuration'
                )
            )
            errors.append(error)
            self.console.print(f"[blue]CLOUD:[/blue] Unexpected error during Docker setup: {str(e)}")
        
        finally:
            # Cleanup
            self.console.print("\n[blue]CLOUD:[/blue] Cleaning up Docker environment...")
            subprocess.run(["docker", "stop", container_name], check=False)
            # Delete temporary inventory file
            if temp_inventory_path and temp_inventory_path.exists():
                temp_inventory_path.unlink()
                self.console.print(f"[blue]CLOUD:[/blue] Deleted temporary inventory at {temp_inventory_path}")

        return changes, errors

    def _convert_tf_change_to_cloud(self, tf_line: str) -> Optional[str]:
        """Convert Terraform change line to cloud format"""
        # Example: "+ aws_instance.web_server" -> "CREATE: compute 'web_server' in infrastructure block"
        match = re.match(r'^\s*([-+~])\s*([\w_]+)\.([\w_]+)', tf_line)
        if match:
            operation, resource_type, resource_name = match.groups()
            op_map = {'+': 'CREATE', '-': 'DELETE', '~': 'MODIFY'}
            
            if resource_type == 'aws_instance':
                return f"{op_map[operation]}: compute '{resource_name}' in infrastructure block"
            elif resource_type == 'aws_vpc':
                return f"{op_map[operation]}: network '{resource_name}' in infrastructure block"
                
        return None

    def _convert_k8s_change_to_cloud(self, k8s_line: str) -> Optional[str]:
        """Convert Kubernetes change line to cloud format"""
        # Example: "deployment.apps/web-app created" -> "CREATE: container 'web-app' in containers block"
        match = re.match(r'^([\w\.]+)/([\w-]+)\s+(created|configured|unchanged)', k8s_line)
        if match:
            resource_type, resource_name, action = match.groups()
            
            action_map = {
                'created': 'CREATE',
                'configured': 'MODIFY',
                'unchanged': 'NO CHANGE'
            }
            
            return f"{action_map[action]}: container '{resource_name}' in containers block"
        
        return None

    def _convert_ansible_change_to_cloud(self, ansible_line: str) -> Optional[str]:
        """Convert Ansible change line to cloud format"""
        # Example: "changed: [localhost] => (item=nginx)" -> "MODIFY: package 'nginx' in configuration block"
        if "changed:" in ansible_line:
            if "item=" in ansible_line:
                match = re.search(r'item=([\w-]+)', ansible_line)
                if match:
                    item = match.group(1)
                    return f"MODIFY: package '{item}' in configuration block"
            else:
                # Handle other types of changes
                return "MODIFY: configuration settings"
                
        return None

    def execute_plan(self) -> Tuple[List[str], List[CloudError]]:
        """Execute the full plan across all platforms"""
        all_changes = []
        all_errors = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            # Plan infrastructure changes
            task = progress.add_task("Planning infrastructure changes...", total=None)
            changes, errors = self._execute_terraform_plan()
            all_changes.extend(changes)
            all_errors.extend(errors)
            progress.update(task, completed=True)
            
            # Plan container changes
            task = progress.add_task("Planning container changes...", total=None)
            changes, errors = self._execute_kubernetes_plan()
            # all_changes.extend(changes)
            # all_errors.extend(errors)
            progress.update(task, completed=True)
            
            # Plan configuration changes
            task = progress.add_task("Planning configuration changes...", total=None)
            changes, errors = self._execute_ansible_check()
            # all_changes.extend(changes)
            # all_errors.extend(errors)
            progress.update(task, completed=True)
            
        return all_changes, all_errors

def display_plan_results(changes: List[str], errors: List[CloudError], console: Console):
    """Display the plan results in a formatted table"""
    # Display errors first if any
    if errors:
        console.print("\n[red]Errors found during planning:[/red]")
        error_table = Table(show_header=True)
        error_table.add_column("Severity")
        error_table.add_column("Location")
        error_table.add_column("Message")
        error_table.add_column("Suggestion")
        
        for error in errors:
            error_table.add_row(
                str(error.severity.value),
                f"{error.source_location.block_type}:{error.source_location.line}",
                error.message,
                error.suggestion or ""
            )
            
        console.print(error_table)
        
    # Display changes
    if changes:
        console.print("\n[green]Planned changes:[/green]")
        changes_table = Table(show_header=True)
        changes_table.add_column("Action")
        changes_table.add_column("Resource")
        changes_table.add_column("Block")
        
        for change in changes:
            # Parse the change string
            parts = change.split(":", 1)
            if len(parts) == 2:
                action = parts[0]
                details = parts[1].strip()
                
                # Extract resource and block
                match = re.match(r"(.+) in (.+) block", details)
                if match:
                    resource, block = match.groups()
                    changes_table.add_row(action, resource, block)
                    
        console.print(changes_table)
    else:
        console.print("\n[yellow]No changes detected[/yellow]")
        