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
from .ansible_executor import AnsibleExecutor


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
        
        # Initialize executors
        self.ansible_executor = AnsibleExecutor(
            iac_path,
            cloud_file,
            self.ansible_mapper,
            self.console
        )
        
        # Store collected errors and changes
        self.errors: List[CloudError] = []
        self.changes: List[str] = []

    def get_provider_info(self, terraform_config: dict) -> tuple[str, str]:
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
            
            needs_key_pair = False
            provider_type = None
            if 'resource' in terraform_config:
                for resource_type, resources in terraform_config['resource'].items():
                    if resource_type == 'aws_instance':
                        provider_type = 'aws'
                        for instance in resources.values():
                            if 'key_name' not in instance:
                                needs_key_pair = True
                                break
                        if needs_key_pair:
                            break  # Exit the outer loop if we found AWS needs a key
                    elif resource_type == 'google_compute_instance':
                        provider_type = 'google'
                        for instance in resources.values():
                            # Consider key needed if no metadata at all or no ssh-keys in metadata
                            if 'metadata' not in instance:
                                needs_key_pair = True
                                break
                            metadata = instance.get('metadata', {})
                            if not metadata or 'ssh-keys' not in metadata:
                                needs_key_pair = True
                                break
                        if needs_key_pair:
                            break  # Exit the outer loop if we found GCP needs a key

            # Handle key pairs and outputs if needed
            provider_type, region = self.get_provider_info(terraform_config)
            modified_config = terraform_config.copy()

            if needs_key_pair:
                key_name = self.key_manager.setup_key_pair(region, provider_type)
                # Construct full path to the key
                key_path = str(self.iac_path / '.keys' / key_name)
                modified_config = modify_terraform_config(terraform_config, key_path, provider_type, os_user=self.ansible_executor._get_os_user())
            
            if 'resource' in modified_config:
                if 'output' not in modified_config:
                    modified_config['output'] = {}
                
                # AWS EC2 instances
                if 'aws_instance' in modified_config['resource']:
                    for instance_name in modified_config['resource']['aws_instance'].keys():
                        output_base = f"ec2_{instance_name}"
                        
                        # Add IP outputs
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
                # GCP Compute instances
                if 'google_compute_instance' in modified_config['resource']:
                    for instance_name in modified_config['resource']['google_compute_instance'].keys():
                        output_base = f"gcp_{instance_name}"
                        
                        # Add IP outputs
                        ip_output_name = f"{output_base}_public_ip"
                        if ip_output_name not in modified_config['output']:
                            modified_config['output'][ip_output_name] = {
                                "value": f"${{google_compute_instance.{instance_name}.network_interface.0.access_config.0.nat_ip}}",
                                "description": f"Public IP of GCP instance {instance_name}"
                            }
                        
                        private_ip_output_name = f"{output_base}_private_ip"
                        if private_ip_output_name not in modified_config['output']:
                            modified_config['output'][private_ip_output_name] = {
                                "value": f"${{google_compute_instance.{instance_name}.network_interface.0.network_ip}}",
                                "description": f"Private IP of GCP instance {instance_name}"
                            }
                    
            # Save modified config
            tf_config_path = self.iac_path / 'main.tf.json.tmp'
            tf_config_path.write_text(json.dumps(modified_config, indent=2))
            original_config_backup = terraform_config_path.with_suffix('.backup')
            terraform_config_path.rename(original_config_backup)
            tf_config_path.rename(terraform_config_path)
            
            # # Create tfvars file with defaults
            # tfvars_content = {
            #     'aws_region': region,
            #     'assume_role_arn': ''
            # }
            
            # # Only add ssh_key_path if we're using key pairs
            # if needs_key_pair:
            #     tfvars_content['ssh_key_path'] = str(self.key_manager.private_key_path)
            
            # tfvars_path = self.iac_path / 'terraform.tfvars.json'
            # tfvars_path.write_text(json.dumps(tfvars_content))
            
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
            msg = "Starting infrastructure deployment..."
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
        """Execute Kubernetes apply on AWS EKS"""
        changes = []
        errors = []
        
        try:
            # Get terraform outputs
            tf_output = subprocess.check_output(
                ['terraform', 'output', '-json'], 
                cwd=str(self.iac_path)
            )
            outputs = json.loads(tf_output)

            # Get terraform config to determine provider
            with open(self.iac_path / 'main.tf.json') as f:
                terraform_config = json.load(f)
            provider_type, region = self.get_provider_info(terraform_config)

            if provider_type == 'google':
                msg = "Starting Kubernetes deployment to GKE..."
                changes.append(msg)
                self.console.print(f"[blue]CLOUD:[/blue] {msg}")

                # Get GKE cluster info from Terraform output
                try:
                    # Using project and zone from provider config
                    project = terraform_config["provider"]["google"]["project"]
                    zone = terraform_config["provider"]["google"]["zone"]

                    cluster_name = None
                    try:
                        gke_cluster_output_key = next(
                            (key for key in outputs.keys() if key.endswith('_gke_cluster_id')),
                            None
                        )
                        if gke_cluster_output_key:
                            cluster_name = outputs[gke_cluster_output_key]['value']
                        else:
                            raise Exception("No GKE cluster output found. Expected output key ending with '_gke_cluster_id'")
                        self.console.print(f"[blue]CLOUD:[/blue] Using cluster name: {cluster_name}")

                        if not cluster_name:
                            self.console.print(f"[red]CLOUD:[/red] No cluster name found in Terraform outputs")
                            self.console.print(f"[blue]CLOUD:[/blue] Available Terraform outputs:")
                            for k, v in outputs.items():
                                self.console.print(f"[blue]CLOUD:[/blue] - {k}: {v}")
                                
                    except Exception as e:
                        errors.append(CloudError(
                            severity=CloudErrorSeverity.ERROR,
                            message=f"Failed to get GKE cluster name from Terraform output: {str(e)}",
                            source_location=CloudSourceLocation(
                                line=1, column=1, block_type='containers'
                            )
                        ))
                        return changes, errors
                                        
                    self.console.print(f"[blue]CLOUD:[/blue] Using cluster name: {cluster_name}")
                    
                    msg = f"Configuring kubectl for GKE cluster in project {project}, zone {zone}..."
                    changes.append(msg)
                    self.console.print(f"[blue]CLOUD:[/blue] {msg}")

                    # Configure kubectl to use GKE cluster
                    subprocess.run([
                        'gcloud', 'container', 'clusters', 'get-credentials',
                        cluster_name,
                        f'--zone={zone}',
                        f'--project={project}'
                    ], check=True)

                    msg = "Successfully configured kubectl for GKE"
                    changes.append(msg)
                    self.console.print(f"[blue]CLOUD:[/blue] {msg}")

                    # Verify cluster connectivity
                    self.console.print(f"[blue]CLOUD:[/blue] Verifying GKE cluster connectivity...")
                    try:
                        check_cluster = subprocess.run(
                            ['kubectl', 'cluster-info'],
                            capture_output=True,
                            text=True
                        )
                        if check_cluster.returncode == 0:
                            msg = "Successfully connected to GKE cluster"
                            self.console.print(f"[blue]CLOUD:[/blue] {msg}")
                            changes.append(msg)
                        else:
                            raise Exception(f"Failed to connect to cluster: {check_cluster.stderr}")
                    except Exception as e:
                        self.console.print(f"[red]CLOUD ERROR:[/red] Cluster connectivity check failed: {str(e)}")
                        errors.append(CloudError(
                            severity=CloudErrorSeverity.ERROR,
                            message=f"Cluster connectivity check failed: {str(e)}",
                            source_location=CloudSourceLocation(
                                line=1, column=1, block_type='containers'
                            )
                        ))
                        return changes, errors

                    # Now proceed with applying Kubernetes resources
                    msg = "Applying Kubernetes resources to GKE cluster..."
                    changes.append(msg)
                    self.console.print(f"[blue]CLOUD:[/blue] {msg}")

                    # Apply resources
                    try:
                        process = subprocess.Popen(
                            ['kubectl', 'apply', '-f', str(self.iac_path / 'resources.yml')],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            bufsize=1,
                            universal_newlines=True
                        )

                    

                        # Stream output in real-time
                        while True:
                            stdout_line = process.stdout.readline()
                            stderr_line = process.stderr.readline()
                            
                            if not stdout_line and not stderr_line and process.poll() is not None:
                                break
                                
                            if stdout_line:
                                stdout_line = stdout_line.strip()
                                if stdout_line:
                                    msg = stdout_line
                                    self.console.print(f"[blue]CLOUD:[/blue] {msg}")
                                    changes.append(msg)
                                    
                            if stderr_line:
                                stderr_line = stderr_line.strip()
                                if stderr_line:
                                    msg = f"WARN: {stderr_line}"
                                    self.console.print(f"[yellow]CLOUD:[/yellow] {msg}")
                                    changes.append(msg)

                        # Check final status
                        if process.returncode != 0:
                            raise Exception(f"kubectl apply failed with return code {process.returncode}")

                        msg = "Successfully applied Kubernetes resources to GKE cluster"
                        self.console.print(f"[blue]CLOUD:[/blue] {msg}")
                        changes.append(msg)

                    except Exception as e:
                        self.console.print(f"[red]CLOUD ERROR:[/red] Failed to apply Kubernetes resources: {str(e)}")
                        errors.append(CloudError(
                            severity=CloudErrorSeverity.ERROR,
                            message=f"Failed to apply Kubernetes resources: {str(e)}",
                            source_location=CloudSourceLocation(
                                line=1, column=1, block_type='containers'
                            )
                        ))
                        return changes, errors

                except Exception as e:
                    self.console.print(f"[red]CLOUD ERROR:[/red] Failed to configure GKE access: {str(e)}")
                    errors.append(CloudError(
                        severity=CloudErrorSeverity.ERROR,
                        message=f"Failed to configure GKE access: {str(e)}",
                        source_location=CloudSourceLocation(
                            line=1, column=1, block_type='containers'
                        )
                    ))
                    return changes, errors

            else:
                msg = "Starting Kubernetes deployment to EKS..."
                changes.append(msg)
                self.console.print(f"[blue]CLOUD:[/blue] {msg}")

                # Initialize AWS session
                session = boto3.Session(region_name=region)
                eks = session.client('eks')
                
                # Get EKS cluster name from Terraform output
                cluster_name = None
                try:
                    cluster_output_key = next(
                        (key for key in outputs.keys() if key.endswith('_eks_cluster_main_id')),
                        None
                    )
                    if cluster_output_key:
                        cluster_name = outputs[cluster_output_key]['value']
                    else:
                        raise Exception("No EKS cluster output found. Expected output key ending with '_eks_cluster_main_id'")
                    self.console.print(f"[blue]CLOUD:[/blue] Using cluster name: {cluster_name}")

                    if not cluster_name:
                        self.console.print(f"[red]CLOUD:[/red] No cluster name found in Terraform outputs")
                        self.console.print(f"[blue]CLOUD:[/blue] Available Terraform outputs:")
                        for k, v in outputs.items():
                            self.console.print(f"[blue]CLOUD:[/blue] - {k}: {v}")
                            
                except Exception as e:
                    errors.append(CloudError(
                        severity=CloudErrorSeverity.ERROR,
                        message=f"Failed to get EKS cluster name from Terraform output: {str(e)}",
                        source_location=CloudSourceLocation(
                            line=1, column=1, block_type='containers'
                        )
                    ))
                    return changes, errors

                # Update kubeconfig for EKS
                msg = "Configuring kubectl for EKS..."
                changes.append(msg)
                self.console.print(f"[blue]CLOUD:[/blue] {msg}")
                
                try:
                    subprocess.run([
                        'aws', 'eks', 'update-kubeconfig',
                        '--name', cluster_name,
                        '--region', region
                    ], check=True)
                    
                except subprocess.CalledProcessError as e:
                    errors.append(CloudError(
                        severity=CloudErrorSeverity.ERROR,
                        message=f"Failed to update kubeconfig: {e}",
                        source_location=CloudSourceLocation(
                            line=1, column=1, block_type='containers'
                        )
                    ))
                    return changes, errors

            # self.console.print(f"[blue]CLOUD:[/blue] Using kubectl config file: {os.getenv('KUBECONFIG', 'default')}")
            
            # try:
            #     with open(self.iac_path / 'main.tf.json') as f:
            #         terraform_config = json.load(f)
            #     provider_type, region = self.get_provider_info(terraform_config)

            #     subprocess.run([
            #         'aws', 'eks', 'update-kubeconfig',
            #         '--name', cluster_name,
            #         '--region', region
            #     ], check=True)
                
            # except subprocess.CalledProcessError as e:
            #     errors.append(CloudError(
            #         severity=CloudErrorSeverity.ERROR,
            #         message=f"Failed to update kubeconfig: {e}",
            #         source_location=CloudSourceLocation(
            #             line=1,
            #             column=1,
            #             block_type='containers'
            #         )
            #     ))
            #     return changes, errors

            # Apply Kubernetes resources
            msg = "Applying Kubernetes resources..."
            changes.append(msg)
            self.console.print(f"[blue]CLOUD:[/blue] {msg}")

            # self.console.print(f"[blue]CLOUD:[/blue] Using kubectl config file: {os.getenv('KUBECONFIG', 'default')}")
            # self.console.print(f"[blue]CLOUD:[/blue] Checking cluster connectivity...")
            # try:
            #     check_cluster = subprocess.run(
            #         ['kubectl', 'cluster-info'],
            #         capture_output=True,
            #         text=True
            #     )
            #     self.console.print(f"[blue]CLOUD:[/blue] Cluster info: {check_cluster.stdout}")
            # except Exception as e:
            #     self.console.print(f"[red]CLOUD:[/red] Failed to get cluster info: {str(e)}")

            process = subprocess.Popen(
                ['kubectl', 'apply', '-f', str(self.iac_path / 'resources.yml'), '--v=6'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Stream output
            while True:
                stdout_line = process.stdout.readline()
                stderr_line = process.stderr.readline()
                
                if not stdout_line and not stderr_line and process.poll() is not None:
                    break
                    
                if stdout_line:
                    stdout_line = stdout_line.strip()
                    if stdout_line:
                        msg = stdout_line
                        self.console.print(f"[blue]CLOUD:[/blue] {msg}")
                        changes.append(msg)
                        
                if stderr_line:
                    stderr_line = stderr_line.strip()
                    if stderr_line:
                        msg = f"WARN: {stderr_line}"
                        self.console.print(f"[yellow]CLOUD:[/yellow] {msg}")
                        changes.append(msg)

            # Capture any remaining output
            stdout_remainder = process.stdout.read()
            stderr_remainder = process.stderr.read()

            if stdout_remainder:
                stdout_remainder = stdout_remainder.strip()
                if stdout_remainder:
                    self.console.print(f"[blue]CLOUD:[/blue] Additional output: {stdout_remainder}")
                    changes.append(stdout_remainder)
            
            if stderr_remainder:
                stderr_remainder = stderr_remainder.strip()
                if stderr_remainder:
                    self.console.print(f"[yellow]CLOUD:[/yellow] Additional warnings/errors: {stderr_remainder}")
                    changes.append(f"WARN: {stderr_remainder}")

            self.console.print(f"[blue]CLOUD:[/blue] Kubernetes deployment finished with return code: {process.returncode}")

            if process.returncode != 0:
                error_output = stderr_remainder or stderr_line or "Unknown error occurred"
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
            self.console.print(f"[red]CLOUD ERROR:[/red] Exception during Kubernetes deployment: {str(e)}")
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
        """Execute ansible configuration and map any errors"""
        try:
            # Read mappings file
            mappings_file = self.iac_path / 'mappings.json'
            if not mappings_file.exists():
                return [], [CloudError(
                    severity=CloudErrorSeverity.ERROR,
                    message="mappings.json not found",
                    source_location=CloudSourceLocation(
                        line=1, column=1, block_type='configuration'
                    )
                )]
                
            with open(mappings_file) as f:
                mappings = json.load(f)
                
            # Execute ansible configurations
            return self.ansible_executor.execute_ansible_apply(mappings)
            
        except Exception as e:
            return [], [CloudError(
                severity=CloudErrorSeverity.ERROR,
                message=str(e),
                source_location=CloudSourceLocation(
                    line=1, column=1, block_type='configuration'
                )
            )]
    
    # def _modify_terraform_config_for_networking(self, terraform_config: dict, vpc_id: str, subnet_id: str, security_group_id: str) -> dict:
    #     """
    #     Modifies terraform configuration to ensure required networking resources exist
    #     Returns modified terraform config
    #     """
    #     # Create deep copy to avoid modifying original
    #     config = json.loads(json.dumps(terraform_config))
        
    #     # Initialize resource section if doesn't exist
    #     if 'resource' not in config:
    #         config['resource'] = {}

    #     # Remove any old data sources to prevent conflicts
    #     if 'data' in config and 'aws_route_table' in config['data']:
    #         del config['data']['aws_route_table']

    #     # Check/add internet gateway
    #     if 'aws_internet_gateway' not in config['resource']:
    #         config['resource']['aws_internet_gateway'] = {
    #             'main': {
    #                 'vpc_id': vpc_id,
    #                 'tags': {
    #                     'Name': 'main',
    #                     'ManagedBy': 'terraform'
    #                 }
    #             }
    #         }

    #     # Add route table without inline routes
    #     if 'aws_route_table' not in config['resource']:
    #         config['resource']['aws_route_table'] = {
    #             'main': {
    #                 'vpc_id': vpc_id,
    #                 'tags': {
    #                     'Name': 'main',
    #                     'ManagedBy': 'terraform'
    #                 }
    #             }
    #         }
            
    #     # Add separate route resource
    #     if 'aws_route' not in config['resource']:
    #         config['resource']['aws_route'] = {
    #             'internet_access': {
    #                 'route_table_id': '${aws_route_table.main.id}',
    #                 'destination_cidr_block': '0.0.0.0/0',
    #                 'gateway_id': '${aws_internet_gateway.main.id}'
    #             }
    #         }
            
    #     # Add route table association
    #     if 'aws_route_table_association' not in config['resource']:
    #         config['resource']['aws_route_table_association'] = {
    #             'main': {
    #                 'subnet_id': subnet_id,
    #                 'route_table_id': '${aws_route_table.main.id}'
    #             }
    #         }

    #     # We'll skip adding the security group rule since it already exists
    #     # if 'aws_security_group_rule' not in config['resource']:
    #     #     config['resource']['aws_security_group_rule'] = {
    #     #         'allow_ssh': {
    #     #             'type': 'ingress',
    #     #             'from_port': 22,
    #     #             'to_port': 22,
    #     #             'protocol': 'tcp',
    #     #             'cidr_blocks': ['0.0.0.0/0'],
    #     #             'security_group_id': security_group_id
    #     #         }
    #     #     }

    #     return config

    def execute_apply(self) -> Tuple[List[str], List[CloudError]]:
        """Execute the full apply across all platforms"""
        all_changes = []
        all_errors = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            # Apply infrastructure changes
            task = progress.add_task("Applying infrastructure changes...", total=None)
            changes, errors = self._execute_terraform_apply()
            all_changes.extend(changes)
            all_errors.extend(errors)
            progress.update(task, completed=True)
            
            # if not errors:  # Only continue if infrastructure deployment succeeded
            # Apply container changes
            task = progress.add_task("Applying container changes...", total=None)
            changes, errors = self._execute_kubernetes_apply()
            all_changes.extend(changes)
            all_errors.extend(errors)
            progress.update(task, completed=True)
            
            # Apply configuration changes
            task = progress.add_task("Applying configuration changes...", total=None)
            changes, errors = self._execute_ansible_apply()
            all_changes.extend(changes)
            all_errors.extend(errors)
            # self.console.print(f"[blue]CLOUD:[/blue] PLAY [Configure webapp] ********************************************************")
            # self.console.print(f"[blue]CLOUD:[/blue] Running tasks")
            # self.console.print(f"[blue]CLOUD:[/blue] Successfully Updated Configuration")
            progress.update(task, completed=True)
        
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