from typing import List, Dict, Optional, Tuple
from ..error_mapping.error_mappers import *
from ..utils.key_management import KeyPairManager, modify_terraform_config
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
import time
import boto3
import getpass
import yaml

class CloudApplyExecutor:
    """Handles execution and error mapping for cloud apply operations"""
    
    def __init__(self, iac_path: str, cloud_file: str, source_mapper):
        self.iac_path = Path(iac_path)
        self.cloud_file = Path(cloud_file)
        self.source_mapper = source_mapper
        self.console = Console()
        self.key_manager = KeyPairManager(self.iac_path)

        # Initialize error mappers
        self.tf_mapper = TerraformErrorMapper(source_mapper)
        self.k8s_mapper = KubernetesErrorMapper(source_mapper)
        self.ansible_mapper = AnsibleErrorMapper(source_mapper)
        
        # Store collected errors and changes
        self.errors: List[CloudError] = []
        self.changes: List[str] = []

    def get_provider_info(terraform_config: dict) -> tuple[str, str]:
        """
        Extract provider type and region from terraform config
        Returns tuple of (provider_type, region)
        """
        if 'provider' not in terraform_config:
            return ('aws', 'us-east-1')  # Default fallback
            
        # Check for AWS provider
        if 'aws' in terraform_config['provider']:
            aws_config = terraform_config['provider']['aws']
            return ('aws', aws_config.get('region', 'us-east-1'))
            
        # Check for GCP provider
        if 'google' in terraform_config['provider']:
            gcp_config = terraform_config['provider']['google']
            return ('google', gcp_config.get('region', 'us-central1'))
            
        # Check for Azure provider
        if 'azurerm' in terraform_config['provider']:
            azure_config = terraform_config['provider']['azurerm']
            return ('azurerm', azure_config.get('location', 'eastus'))
            
        return ('aws', 'us-east-1')  # Default fallback

    def _execute_terraform_apply(self) -> Tuple[List[str], List[CloudError]]:
        """Execute terraform apply and map any errors"""
        changes = []
        errors = []
        tfvars_path = None
        tf_config_path = None
        original_config_backup = None
        
        try:
            # Read original terraform config
            terraform_config_path = self.iac_path / 'main.tf.json'
            with open(terraform_config_path) as f:
                terraform_config = json.load(f)
                
            # Get provider type and region
            provider_type, region = self.get_provider_info(terraform_config)
            
            # Check if we have any instances that need key pairs based on provider
            needs_key_pair = False
            if 'resource' in terraform_config:
                for resource_type, resources in terraform_config['resource'].items():
                    if ((provider_type == 'aws' and resource_type == 'aws_instance') or
                        (provider_type == 'google' and resource_type == 'google_compute_instance') or
                        (provider_type == 'azure' and resource_type == 'azurerm_linux_virtual_machine')):
                        for instance in resources.values():
                            # Check provider-specific key field names
                            if (provider_type == 'aws' and ('key_name' not in instance or not instance['key_name'])) or \
                            (provider_type == 'google' and ('metadata' not in instance or 'ssh-keys' not in instance['metadata'])) or \
                            (provider_type == 'azure' and ('admin_ssh_key' not in instance or not instance['admin_ssh_key'])):
                                needs_key_pair = True
                                break

            # Handle key pairs and outputs if needed
            modified_config = terraform_config.copy()
            
            if needs_key_pair:
                key_name = self.key_manager.setup_key_pair(region)
                modified_config = modify_terraform_config(terraform_config, key_name)
            
            # Ensure we have outputs for instances based on provider
            if 'resource' in modified_config:
                if 'output' not in modified_config:
                    modified_config['output'] = {}
                    
                # AWS EC2 instances
                if provider_type == 'aws' and 'aws_instance' in modified_config['resource']:
                    for instance_name in modified_config['resource']['aws_instance'].keys():
                        output_base = f"ec2_{instance_name}"
                        
                        # Add IP outputs if not exists
                        ip_output_name = f"{output_base}_public_ip"
                        if ip_output_name not in modified_config['output']:
                            modified_config['output'][ip_output_name] = {
                                "value": f"${{aws_instance.{instance_name}.public_ip}}",
                                "description": f"Public IP of EC2 instance {instance_name}"
                            }
                        private_ip_output_name = f"{output_base}_private_ip"
                        if private_ip_output_name not in modified_config['output']:
                            modified_config['output'][private_ip_output_name] = {
                                "value": f"${{aws_instance.{instance_name}.private_ip}}",
                                "description": f"Private IP of EC2 instance {instance_name}"
                            }
                            
                # Google Compute Engine instances
                elif provider_type == 'google' and 'google_compute_instance' in modified_config['resource']:
                    for instance_name in modified_config['resource']['google_compute_instance'].keys():
                        output_base = f"gce_{instance_name}"
                        
                        ip_output_name = f"{output_base}_public_ip"
                        if ip_output_name not in modified_config['output']:
                            modified_config['output'][ip_output_name] = {
                                "value": f"${{google_compute_instance.{instance_name}.network_interface[0].access_config[0].nat_ip}}",
                                "description": f"Public IP of GCE instance {instance_name}"
                            }
                        private_ip_output_name = f"{output_base}_private_ip"
                        if private_ip_output_name not in modified_config['output']:
                            modified_config['output'][private_ip_output_name] = {
                                "value": f"${{google_compute_instance.{instance_name}.network_interface[0].network_ip}}",
                                "description": f"Private IP of GCE instance {instance_name}"
                            }

            # Azure VMs
                elif provider_type == 'azure' and 'azurerm_linux_virtual_machine' in modified_config['resource']:
                    for instance_name in modified_config['resource']['azurerm_linux_virtual_machine'].keys():
                        output_base = f"vm_{instance_name}"
                        
                        ip_output_name = f"{output_base}_public_ip"
                        if ip_output_name not in modified_config['output']:
                            modified_config['output'][ip_output_name] = {
                                "value": f"${{azurerm_public_ip.{instance_name}.ip_address}}",
                                "description": f"Public IP of Azure VM {instance_name}"
                            }
                        private_ip_output_name = f"{output_base}_private_ip"
                        if private_ip_output_name not in modified_config['output']:
                            modified_config['output'][private_ip_output_name] = {
                                "value": f"${{azurerm_network_interface.{instance_name}.private_ip_address}}",
                                "description": f"Private IP of Azure VM {instance_name}"
                            }
            
            # Save modified config
            tf_config_path = self.iac_path / 'main.tf.json.tmp'
            tf_config_path.write_text(json.dumps(modified_config, indent=2))
            original_config_backup = terraform_config_path.with_suffix('.backup')
            terraform_config_path.rename(original_config_backup)
            tf_config_path.rename(terraform_config_path)
            
            # Create tfvars file with provider-specific defaults
            tfvars_content = {
                'region': region,  # Generic region variable
                'assume_role_arn': ''  # Keep for AWS backward compatibility
            }
            
            # Add provider-specific variables
            if provider_type == 'aws':
                tfvars_content['aws_region'] = region
            elif provider_type == 'google':
                tfvars_content['gcp_region'] = region
                tfvars_content['project_id'] = terraform_config['provider']['google'].get('project')
            elif provider_type == 'azure':
                tfvars_content['azure_location'] = region
                tfvars_content['subscription_id'] = terraform_config['provider']['azurerm'].get('subscription_id')

            # Add ssh_key_path if using key pairs
            if needs_key_pair:
                tfvars_content['ssh_key_path'] = str(self.key_manager.private_key_path)
            
            tfvars_path = self.iac_path / 'terraform.tfvars.json'
            tfvars_path.write_text(json.dumps(tfvars_content))
            
            # Initialize Terraform
            msg = "Initializing Terraform..."
            changes.append(msg)
            self.console.print(f"[blue]CLOUD:[/blue] {msg}")

            process = subprocess.Popen(
                ['terraform', 'init'],
                cwd=str(self.iac_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            stdout, stderr = process.communicate()

            if process.returncode != 0:
                error = self.tf_mapper.map_error(stderr)
                if error:
                    errors.append(error)
                return changes, errors

            # Run terraform apply
            msg = f"Starting infrastructure deployment in {provider_type.upper()} {region}..."
            changes.append(msg)
            self.console.print(f"[blue]CLOUD:[/blue] {msg}")

            process = subprocess.Popen(
                ['terraform', 'apply', '-auto-approve', '-no-color'],
                cwd=str(self.iac_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Stream stdout in real-time
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                
                line = line.strip()
                if line:
                    # Skip noisy lines
                    if any(skip in line.lower() for skip in 
                        ['terraform will perform',
                        'terraform used provider',
                        'terraform has made some changes']):
                        continue
                    
                    # Remove terraform word and format
                    line = re.sub(r'terraform\s+', '', line, flags=re.IGNORECASE)
                    
                    # Capture important status lines
                    if "Error:" in line:
                        msg = f"ERROR: {line}"
                        self.console.print(f"[red]CLOUD ERROR:[/red] {msg}")
                        changes.append(msg)
                        error_context = {'error_message': line}
                        error = self.tf_mapper.map_error(line, error_context)
                        if error:
                            errors.append(error)
                    elif "Apply complete!" in line:
                        stats = re.search(r'(\d+)\s+added,\s+(\d+)\s+changed,\s+(\d+)\s+destroyed', line)
                        if stats:
                            added, changed, destroyed = stats.groups()
                            changes.extend([
                                f"Added {added} resources",
                                f"Modified {changed} resources",
                                f"Removed {destroyed} resources"
                            ])
                    msg = line
                    self.console.print(f"[blue]CLOUD:[/blue] {msg}")
                    changes.append(msg)

            # Check for any errors in stderr
            stderr_output = process.stderr.read()
            if stderr_output:
                msg = f"ERROR: {stderr_output}"
                self.console.print(f"[red]CLOUD ERROR:[/red] {msg}")
                changes.append(msg)
                error = self.tf_mapper.map_error(stderr_output)
                if error:
                    errors.append(error)

            # Final status check
            if process.returncode != 0:
                msg = "Infrastructure deployment failed"
                self.console.print(f"[red]CLOUD ERROR:[/red] {msg}")
                changes.append(f"ERROR: {msg}")
            else:
                msg = "Infrastructure deployment complete"
                self.console.print(f"[blue]CLOUD:[/blue] {msg}")
                changes.append(msg)

        except Exception as e:
            errors.append(CloudError(
                severity=CloudErrorSeverity.ERROR,
                message=str(e),
                source_location=CloudSourceLocation(
                    line=1,
                    column=1,
                    block_type='infrastructure'
                )
            ))
        finally:
            # Cleanup
            if tfvars_path and tfvars_path.exists():
                tfvars_path.unlink()
            
            # Restore original config if backup exists
            if original_config_backup and original_config_backup.exists():
                if terraform_config_path.exists():
                    terraform_config_path.unlink()
                original_config_backup.rename(terraform_config_path)

        return changes, errors
    
    def _execute_kubernetes_apply(self) -> Tuple[List[str], List[CloudError]]:
        """Execute Kubernetes apply on cloud-managed clusters"""
        changes = []
        errors = []
        
        try:
            # Read terraform config to get provider info
            terraform_config_path = self.iac_path / 'main.tf.json'
            with open(terraform_config_path) as f:
                terraform_config = json.load(f)
            
            provider_type, region = self.get_provider_info(terraform_config)
            
            # Initialize cloud-specific clients
            if provider_type == 'aws':
                session = boto3.Session(region_name=region)
                cloud_client = session.client('eks')
            elif provider_type == 'google':
                from google.cloud import container_v1
                cloud_client = container_v1.ClusterManagerClient()
            elif provider_type == 'azure':
                from azure.mgmt.containerservice import ContainerServiceClient
                from azure.identity import DefaultAzureCredential
                cloud_client = ContainerServiceClient(
                    credential=DefaultAzureCredential(),
                    subscription_id=terraform_config['provider']['azurerm'].get('subscription_id')
                )
            else:
                raise Exception(f"Unsupported provider: {provider_type}")
                
            msg = f"Starting Kubernetes deployment to {provider_type.upper()} managed cluster..."
            changes.append(msg)
            self.console.print(f"[blue]CLOUD:[/blue] {msg}")

            # Get cluster name from Terraform output
            cluster_name = None
            try:
                tf_output = subprocess.check_output(
                    ['terraform', 'output', '-json'], 
                    cwd=str(self.iac_path)
                )
                outputs = json.loads(tf_output)
                
                # Get cluster name based on provider
                if provider_type == 'aws':
                    cluster_name = outputs.get('eks_cluster_name', {}).get('value')
                    if not cluster_name:
                        raise Exception("EKS cluster name not found in outputs")
                elif provider_type == 'google':
                    cluster_name = outputs.get('gke_cluster_name', {}).get('value')
                    if not cluster_name:
                        raise Exception("GKE cluster name not found in outputs")
                elif provider_type == 'azure':
                    cluster_name = outputs.get('aks_cluster_name', {}).get('value')
                    if not cluster_name:
                        raise Exception("AKS cluster name not found in outputs")
                    
            except Exception as e:
                errors.append(CloudError(
                    severity=CloudErrorSeverity.ERROR,
                    message=f"Failed to get cluster name: {str(e)}",
                    source_location=CloudSourceLocation(
                        line=1,
                        column=1,
                        block_type='containers'
                    )
                ))
                return changes, errors
            
            # Update kubeconfig for provider
            msg = f"Configuring kubectl for {provider_type.upper()}..."
            changes.append(msg)
            self.console.print(f"[blue]CLOUD:[/blue] {msg}")
            
            try:
                if provider_type == 'aws':
                    subprocess.run([
                        'aws', 'eks', 'update-kubeconfig',
                        '--name', cluster_name,
                        '--region', region
                    ], check=True)
                elif provider_type == 'google':
                    project_id = terraform_config['provider']['google'].get('project')
                    subprocess.run([
                        'gcloud', 'container', 'clusters', 'get-credentials',
                        cluster_name,
                        '--region', region,
                        '--project', project_id
                    ], check=True)
                elif provider_type == 'azure':
                    resource_group = outputs.get('aks_resource_group', {}).get('value')
                    if not resource_group:
                        raise Exception("AKS resource group not found in outputs")
                    subprocess.run([
                        'az', 'aks', 'get-credentials',
                        '--resource-group', resource_group,
                        '--name', cluster_name,
                        '--overwrite-existing'
                    ], check=True)
                    
            except subprocess.CalledProcessError as e:
                errors.append(CloudError(
                    severity=CloudErrorSeverity.ERROR,
                    message=f"Failed to update kubeconfig: {e}",
                    source_location=CloudSourceLocation(
                        line=1,
                        column=1,
                        block_type='containers'
                    )
                ))
                return changes, errors

            # Apply Kubernetes resources
            msg = "Applying Kubernetes resources..."
            changes.append(msg)
            self.console.print(f"[blue]CLOUD:[/blue] {msg}")

            process = subprocess.Popen(
                ['kubectl', 'apply', '-f', str(self.iac_path / 'resources.yml')],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Stream output
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                
                line = line.strip()
                if line:
                    msg = line
                    self.console.print(f"[blue]CLOUD:[/blue] {msg}")
                    changes.append(msg)

            if process.returncode != 0:
                error_output = process.stderr.read()
                error = self.k8s_mapper.map_error(error_output)
                if error:
                    errors.append(error)
                msg = "Kubernetes deployment failed"
                self.console.print(f"[red]CLOUD ERROR:[/red] {msg}")
                changes.append(f"ERROR: {msg}")
            else:
                msg = "Kubernetes deployment complete"
                self.console.print(f"[blue]CLOUD:[/blue] {msg}")
                changes.append(msg)

        except Exception as e:
            errors.append(CloudError(
                severity=CloudErrorSeverity.ERROR,
                message=str(e),
                source_location=CloudSourceLocation(
                    line=1,
                    column=1,
                    block_type='containers'
                )
            ))

        return changes, errors
    
    def _execute_ansible_apply(self) -> Tuple[List[str], List[CloudError]]:
        """Execute Ansible playbook on cloud instances"""
        changes = []
        errors = []
        
        try:
            # Read terraform config to get provider info
            terraform_config_path = self.iac_path / 'main.tf.json'
            with open(terraform_config_path) as f:
                terraform_config = json.load(f)
            
            provider_type, region = self.get_provider_info(terraform_config)
            
            # Get instance details from Terraform output
            msg = f"Getting {provider_type.upper()} instance information..."
            changes.append(msg)
            self.console.print(f"[blue]CLOUD:[/blue] {msg}")

            # Get terraform outputs and look for IPs based on provider
            tf_output = subprocess.check_output(
                ['terraform', 'output', '-json'], 
                cwd=str(self.iac_path)
            )
            outputs = json.loads(tf_output)
            
            # Get instance IPs based on provider
            instance_ips = []
            if provider_type == 'aws':
                # Check legacy format first
                instance_ips = outputs.get('ec2_instance_ips', {}).get('value', [])
                
                # Check new format if legacy not found
                if not instance_ips:
                    for output_name, output_data in outputs.items():
                        if (output_name.startswith('ec2_') and 
                            output_name.endswith('_public_ip')):
                            if isinstance(output_data, dict) and 'value' in output_data:
                                instance_ips.append(output_data['value'])
                                
            elif provider_type == 'google':
                for output_name, output_data in outputs.items():
                    if (output_name.startswith('gce_') and 
                        output_name.endswith('_public_ip')):
                        if isinstance(output_data, dict) and 'value' in output_data:
                            instance_ips.append(output_data['value'])
                            
            elif provider_type == 'azure':
                for output_name, output_data in outputs.items():
                    if (output_name.startswith('vm_') and 
                        output_name.endswith('_public_ip')):
                        if isinstance(output_data, dict) and 'value' in output_data:
                            instance_ips.append(output_data['value'])

            if not instance_ips:
                errors.append(CloudError(
                    severity=CloudErrorSeverity.ERROR,
                    message=f"No {provider_type.upper()} instances found in Terraform output",
                    source_location=CloudSourceLocation(
                        line=1,
                        column=1,
                        block_type='configuration'
                    )
                ))
                return changes, errors

            # Get SSH key info from outputs based on provider
            if provider_type == 'aws':
                key_path = outputs.get('ssh_key_path', {}).get('value', 
                    str(self.iac_path / '.keys/cloud-cli-key.pem'))
            elif provider_type == 'google':
                key_path = outputs.get('gcp_ssh_key_path', {}).get('value',
                    str(self.iac_path / '.keys/cloud-cli-key'))
            elif provider_type == 'azure':
                key_path = outputs.get('azure_ssh_key_path', {}).get('value',
                    str(self.iac_path / '.keys/cloud-cli-key'))
            
            key_path = Path(key_path)
            os.chmod(key_path, 0o600)  # Ensure correct permissions

            # Read existing inventory.yml
            inventory_path = self.iac_path / 'inventory.yml'
            if not inventory_path.exists():
                errors.append(CloudError(
                    severity=CloudErrorSeverity.ERROR,
                    message="inventory.yml not found",
                    source_location=CloudSourceLocation(
                        line=1, column=1, block_type='configuration'
                    )
                ))
                return changes, errors

            with open(inventory_path) as f:
                inventory_content = yaml.safe_load(f)

            # Update inventory based on cloud provider
            server_group = 'web_servers'  # default group name
            if provider_type == 'google':
                server_group = 'gcp_instances'
            elif provider_type == 'azure':
                server_group = 'azure_instances'

            # Check if inventory has variable placeholders
            all_servers = inventory_content.get('all', {}).get('children', {}).get(server_group, {})
            server_hosts = all_servers.get('hosts', {}).get(f'{provider_type}_hosts', {})
            
            if ('{{ host_ip }}' in str(server_hosts) and 
                '{{ ssh_key_path }}' in str(server_hosts)):
                
                # Add variables section if it doesn't exist
                if 'vars' not in all_servers:
                    all_servers['vars'] = {}
                
                # Update variables with actual values
                all_servers['vars'].update({
                    'host_ip': instance_ips[0],
                    'ssh_key_path': str(key_path)
                })
                
                # Add provider-specific variables
                if provider_type == 'google':
                    all_servers['vars'].update({
                        'ansible_user': outputs.get('gcp_ssh_user', {}).get('value', 'admin')
                    })
                elif provider_type == 'azure':
                    all_servers['vars'].update({
                        'ansible_user': outputs.get('azure_admin_username', {}).get('value', 'azureuser')
                    })
                
                # Write updated inventory
                with open(inventory_path, 'w') as f:
                    yaml.dump(inventory_content, f)

            # Add debug output
            self.console.print(f"[blue]CLOUD:[/blue] Using key at: {key_path}")
            self.console.print(f"[blue]CLOUD:[/blue] Key exists: {key_path.exists()}")

            # Get sudo password if needed
            sudo_pass = getpass.getpass("Enter sudo password for remote hosts: ")

            # Run Ansible playbook
            msg = f"Applying configuration to {provider_type.upper()} instances..."
            changes.append(msg)
            self.console.print(f"[blue]CLOUD:[/blue] {msg}")

            env = os.environ.copy()
            env['ANSIBLE_BECOME_PASS'] = sudo_pass

            process = subprocess.Popen(
                [
                    'ansible-playbook',
                    '-i', str(inventory_path),
                    str(self.iac_path / 'playbook.yml'),
                    '--diff'
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )

            # Stream output
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                
                line = line.strip()
                if line:
                    # Format special cases
                    if "TASK [" in line:
                        task_name = re.search(r'TASK \[(.*?)\]', line)
                        if task_name:
                            msg = f"Running task: {task_name.group(1)}"
                    elif "ok:" in line:
                        msg = f"Completed: {line.split('ok:')[1].strip()}"
                    elif "changed:" in line:
                        msg = f"Modified: {line.split('changed:')[1].strip()}"
                    elif "skipping:" in line:
                        msg = f"Skipped: {line.split('skipping:')[1].strip()}"
                    elif "failed:" in line:
                        msg = f"ERROR: {line.split('failed:')[1].strip()}"
                    else:
                        msg = line
                    
                    self.console.print(f"[blue]CLOUD:[/blue] {msg}")
                    changes.append(msg)

            if process.returncode != 0:
                error_output = process.stderr.read()
                error = self.ansible_mapper.map_error(error_output)
                if error:
                    errors.append(error)
                msg = "Configuration deployment failed"
                self.console.print(f"[red]CLOUD ERROR:[/red] {msg}")
                changes.append(f"ERROR: {msg}")
            else:
                msg = "Configuration deployment complete"
                self.console.print(f"[blue]CLOUD:[/blue] {msg}")
                changes.append(msg)

        except Exception as e:
            errors.append(CloudError(
                severity=CloudErrorSeverity.ERROR,
                message=str(e),
                source_location=CloudSourceLocation(
                    line=1,
                    column=1,
                    block_type='configuration'
                )
            ))

        return changes, errors
    
    def execute_apply(self) -> Tuple[List[str], List[CloudError]]:
        """Execute the full apply across all platforms"""
        all_changes = []
        all_errors = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=False  # Keep progress display visible
        ) as progress:
            try:
                # Apply infrastructure changes
                task = progress.add_task("[blue]Applying infrastructure changes...", total=1)
                changes, errors = self._execute_terraform_apply()
                all_changes.extend(changes)
                all_errors.extend(errors)
                progress.update(task, advance=1, completed=True)
                
                if not errors:  # Only continue if infrastructure deployment succeeded
                    # Apply container changes
                    task = progress.add_task("[blue]Applying container changes...", total=1)
                    changes, errors = self._execute_kubernetes_apply()
                    all_changes.extend(changes)
                    all_errors.extend(errors)
                    progress.update(task, advance=1, completed=True)
                    
                    # Apply configuration changes
                    task = progress.add_task("[blue]Applying configuration changes...", total=1)
                    changes, errors = self._execute_ansible_apply()
                    all_changes.extend(changes)
                    all_errors.extend(errors)
                    progress.update(task, advance=1, completed=True)
                else:
                    self.console.print("[red]Infrastructure deployment failed, skipping container and configuration changes[/red]")
            except Exception as e:
                all_errors.append(CloudError(
                    severity=CloudErrorSeverity.ERROR,
                    message=str(e),
                    source_location=CloudSourceLocation(
                        line=1,
                        column=1,
                        block_type='apply'
                    )
                ))
                self.console.print(f"[red]Error during apply: {str(e)}[/red]")
                
        # Display final status
        if all_errors:
            self.console.print("\n[red]Apply completed with errors[/red]")
        else:
            self.console.print("\n[green]Apply completed successfully[/green]")
            
        return all_changes, all_errors

    def display_apply_results(changes: List[str], errors: List[CloudError], console: Console):
        """Display the apply results in a formatted table"""
        # Display errors first if any
        if errors:
            console.print("\n[red]Errors occurred during apply:[/red]")
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
            console.print("\n[green]Applied changes:[/green]")
            changes_table = Table(show_header=True)
            changes_table.add_column("Component")
            changes_table.add_column("Action")
            changes_table.add_column("Details")
            
            for change in changes:
                if ":" in change:
                    component, details = change.split(":", 1)
                    if "ERROR" in component:
                        changes_table.add_row("Error", "Failed", details.strip())
                    else:
                        changes_table.add_row(
                            component.strip(),
                            "Applied",
                            details.strip()
                        )
                        
            console.print(changes_table)
        else:
            console.print("\n[yellow]No changes were applied[/yellow]")