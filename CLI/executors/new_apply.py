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
            
            # Check if we have any EC2 instances that need key pairs
            needs_key_pair = False
            if 'resource' in terraform_config:
                for resource_type, resources in terraform_config['resource'].items():
                    if resource_type == 'aws_instance':
                        for instance in resources.values():
                            if 'key_name' not in instance or not instance['key_name']:
                                needs_key_pair = True
                                break
            
            # Handle EC2 key pairs and outputs if needed
            provider_type, region = self.get_provider_info(terraform_config)
            modified_config = terraform_config.copy()
            
            if needs_key_pair:
                key_name = self.key_manager.setup_key_pair(region)
                modified_config = modify_terraform_config(terraform_config, key_name)
            
            # Ensure we have outputs for any EC2 instances
            if 'resource' in modified_config and 'aws_instance' in modified_config['resource']:
                if 'output' not in modified_config:
                    modified_config['output'] = {}
                    
                # Add outputs for each EC2 instance
                for instance_name in modified_config['resource']['aws_instance'].keys():
                    output_base = f"ec2_{instance_name}"
                    
                    # Add IP output if not exists
                    ip_output_name = f"{output_base}_public_ip"
                    if ip_output_name not in modified_config['output']:
                        modified_config['output'][ip_output_name] = {
                            "value": f"${{aws_instance.{instance_name}.public_ip}}",
                            "description": f"Public IP of EC2 instance {instance_name}"
                        }
                    
                    # Add private IP output if not exists
                    private_ip_output_name = f"{output_base}_private_ip"
                    if private_ip_output_name not in modified_config['output']:
                        modified_config['output'][private_ip_output_name] = {
                            "value": f"${{aws_instance.{instance_name}.private_ip}}",
                            "description": f"Private IP of EC2 instance {instance_name}"
                        }
            
            # Save modified config
            tf_config_path = self.iac_path / 'main.tf.json.tmp'
            tf_config_path.write_text(json.dumps(modified_config, indent=2))
            original_config_backup = terraform_config_path.with_suffix('.backup')
            terraform_config_path.rename(original_config_backup)
            tf_config_path.rename(terraform_config_path)
            
            # Create tfvars file with defaults
            tfvars_content = {
                'aws_region': region,
                'assume_role_arn': ''
            }
            
            # Only add ssh_key_path if we're using key pairs
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
            # Initialize AWS session
            with open(self.iac_path / 'main.tf.json') as f:
                terraform_config = json.load(f)
            provider_type, region = self.get_provider_info(terraform_config)
            session = boto3.Session(region_name=region)
            eks = session.client('eks')
            
            msg = "Starting Kubernetes deployment to EKS..."
            changes.append(msg)
            self.console.print(f"[blue]CLOUD:[/blue] {msg}")

            # Get EKS cluster name from Terraform output
            cluster_name = None
            try:
                tf_output = subprocess.check_output(
                    ['terraform', 'output', '-json'], 
                    cwd=str(self.iac_path)
                )
                outputs = json.loads(tf_output)
                
                cluster_name = outputs['webapp_eks_cluster_main_id']['value']
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
                        line=1,
                        column=1,
                        block_type='containers'
                    )
                ))
                return changes, errors

            # Update kubeconfig for EKS
            msg = "Configuring kubectl for EKS..."
            changes.append(msg)
            self.console.print(f"[blue]CLOUD:[/blue] {msg}")
            
            try:
                with open(self.iac_path / 'main.tf.json') as f:
                    terraform_config = json.load(f)
                provider_type, region = self.get_provider_info(terraform_config)

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

            self.console.print(f"[blue]CLOUD:[/blue] Using kubectl config file: {os.getenv('KUBECONFIG', 'default')}")
            self.console.print(f"[blue]CLOUD:[/blue] Checking cluster connectivity...")
            try:
                check_cluster = subprocess.run(
                    ['kubectl', 'cluster-info'],
                    capture_output=True,
                    text=True
                )
                self.console.print(f"[blue]CLOUD:[/blue] Cluster info: {check_cluster.stdout}")
            except Exception as e:
                self.console.print(f"[red]CLOUD:[/red] Failed to get cluster info: {str(e)}")

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
        """Execute Ansible playbook on AWS instances"""
        changes = []
        errors = []
        
        try:
            # Initialize AWS clients
            session = boto3.Session()
            ec2_client = session.client('ec2')
            
            # Get EC2 instance details from Terraform output
            msg = "Getting EC2 instance information..."
            changes.append(msg)
            self.console.print(f"[blue]CLOUD:[/blue] {msg}")

            # Get terraform outputs and look for IPs in all possible output formats
            tf_output = subprocess.check_output(
                ['terraform', 'output', '-json'], 
                cwd=str(self.iac_path)
            )
            outputs = json.loads(tf_output)
            
            # First check the legacy format
            instance_ips = outputs.get('ec2_instance_ips', {}).get('value', [])
            
            # If no IPs found in legacy format, check for new format
            if not instance_ips:
                instance_ips = []
                for output_name, output_data in outputs.items():
                    if output_name.startswith('ec2_') and output_name.endswith('_public_ip'):
                        if isinstance(output_data, dict) and 'value' in output_data:
                            instance_ips.append(output_data['value'])

            if not instance_ips:
                errors.append(CloudError(
                    severity=CloudErrorSeverity.ERROR,
                    message="No EC2 instances found in Terraform output",
                    source_location=CloudSourceLocation(
                        line=1,
                        column=1,
                        block_type='configuration'
                    )
                ))
                return changes, errors

            # Get VPC information from EC2 instances
            instance_id = None
            # First try the new format
            instance_id = outputs.get('webapp_web_server_id', {}).get('value')
            
            # If not found, try the legacy format
            if not instance_id:
                for output_name, output_data in outputs.items():
                    if output_name.startswith('ec2_') and output_name.endswith('_id'):
                        if isinstance(output_data, dict) and 'value' in output_data:
                            instance_id = output_data['value']
                            break

            self.console.print(f"[blue]CLOUD:[/blue] Found instance ID: {instance_id}")
            
            # Debug all terraform outputs
            self.console.print(f"[blue]CLOUD:[/blue] Available Terraform outputs:")
            for k, v in outputs.items():
                self.console.print(f"[blue]CLOUD:[/blue] - {k}: {v}")

            if not instance_id:
                self.console.print(f"[red]CLOUD:[/red] No instance ID found in Terraform outputs")
                errors.append(CloudError(
                    severity=CloudErrorSeverity.ERROR,
                    message="Could not find EC2 instance ID in Terraform outputs",
                    source_location=CloudSourceLocation(
                        line=1, column=1, block_type='configuration'
                    )
                ))
                return changes, errors
            
            if instance_id:
                self.console.print(f"[blue]CLOUD:[/blue] Getting VPC info for instance {instance_id}")
                instance_info = ec2_client.describe_instances(InstanceIds=[instance_id])
                vpc_id = instance_info['Reservations'][0]['Instances'][0]['VpcId']
                subnet_id = instance_info['Reservations'][0]['Instances'][0]['SubnetId']
                security_groups = instance_info['Reservations'][0]['Instances'][0]['SecurityGroups']
                self.console.print(f"[blue]CLOUD:[/blue] Found VPC: {vpc_id}, Subnet: {subnet_id}")


                for sg in security_groups:
                    sg_rules = ec2_client.describe_security_group_rules(
                        Filters=[{'Name': 'group-id', 'Values': [sg['GroupId']]}]
                    )
                    self.console.print(f"[blue]CLOUD:[/blue] Security group rules for {sg['GroupId']}:")
                    for rule in sg_rules['SecurityGroupRules']:
                        if not rule.get('IsEgress'):  # Only show inbound rules
                            self.console.print(f"[blue]CLOUD:[/blue] Port {rule.get('FromPort')}-{rule.get('ToPort')} {rule.get('IpProtocol')}")

                # Read current terraform config
                with open(self.iac_path / 'main.tf.json') as f:
                    terraform_config = json.load(f)

                # Modify terraform config to include necessary networking resources
                modified_config = self._modify_terraform_config_for_networking(
                    terraform_config,
                    vpc_id,
                    subnet_id,
                    security_groups[0]['GroupId']
                )

                # Write modified config
                with open(self.iac_path / 'main.tf.json', 'w') as f:
                    json.dump(modified_config, f, indent=2)

                # Re-run terraform apply
                changes_tf, errors_tf = self._execute_terraform_apply()
                changes.extend(changes_tf)
                errors.extend(errors_tf)

                if errors_tf:
                    return changes, errors
                
                # Test SSH connection before running Ansible
                key_path = outputs.get('ssh_key_path', {}).get('value', str(self.iac_path / '.keys/cloud-cli-key.pem'))
                key_path = Path(key_path)
                os.chmod(key_path, 0o600)  # Ensure correct permissions
                
                # Add debug output
                self.console.print(f"[blue]CLOUD:[/blue] Using key at: {key_path}")
                self.console.print(f"[blue]CLOUD:[/blue] Key exists: {key_path.exists()}")


                try:
                    self.console.print(f"[blue]CLOUD:[/blue] Testing SSH connection to {instance_ips[0]}...")
                    ssh_test = subprocess.run(
                        ['ssh', '-i', str(key_path), '-o', 'StrictHostKeyChecking=no', 
                        '-o', 'ConnectTimeout=10', f'ubuntu@{instance_ips[0]}', 'echo "SSH test successful"'],
                        capture_output=True,
                        text=True
                    )
                    if ssh_test.returncode == 0:
                        self.console.print(f"[blue]CLOUD:[/blue] SSH connection successful")
                    else:
                        self.console.print(f"[reed]CLOUD:[/red] SSH connection failed: {ssh_test.stderr}")
                except Exception as e:
                    self.console.print(f"[red]CLOUD:[/red] SSH test error: {str(e)}")

                # Debug networking setup
                self.console.print(f"[blue]CLOUD:[/blue] Debugging network configuration...")
                
                # Check subnet configuration
                subnet_info = ec2_client.describe_subnets(SubnetIds=[subnet_id])
                self.console.print(f"[blue]CLOUD:[/blue] Subnet {subnet_id} configuration:")
                self.console.print(f"[blue]CLOUD:[/blue] - MapPublicIpOnLaunch: {subnet_info['Subnets'][0].get('MapPublicIpOnLaunch')}")
                self.console.print(f"[blue]CLOUD:[/blue] - AvailableIpAddressCount: {subnet_info['Subnets'][0].get('AvailableIpAddressCount')}")
                
                # Check route table configuration
                route_tables = ec2_client.describe_route_tables(
                    Filters=[{'Name': 'association.subnet-id', 'Values': [subnet_id]}]
                )
                self.console.print(f"[blue]CLOUD:[/blue] Route table configuration:")
                for rt in route_tables['RouteTables']:
                    for route in rt['Routes']:
                        self.console.print(f"[blue]CLOUD:[/blue] - Route: {route.get('DestinationCidrBlock')} -> {route.get('GatewayId', 'local')}")

                # Check security group rules in detail
                for sg in security_groups:
                    sg_info = ec2_client.describe_security_groups(GroupIds=[sg['GroupId']])
                    self.console.print(f"[blue]CLOUD:[/blue] Security group {sg['GroupId']} rules:")
                    for rule in sg_info['SecurityGroups'][0]['IpPermissions']:
                        from_port = rule.get('FromPort', 'All')
                        to_port = rule.get('ToPort', 'All')
                        protocol = rule.get('IpProtocol', 'All')
                        ip_ranges = [r['CidrIp'] for r in rule.get('IpRanges', [])]
                        self.console.print(f"[blue]CLOUD:[/blue] - Ports: {from_port}-{to_port}, Protocol: {protocol}, IPs: {ip_ranges}")

                # Try to connect with netcat to verify port 22 is open
                try:
                    self.console.print(f"[blue]CLOUD:[/blue] Testing TCP connection to port 22...")
                    nc_test = subprocess.run(
                        ['nc', '-zv', '-w', '5', instance_ips[0], '22'],
                        capture_output=True,
                        text=True
                    )
                    self.console.print(f"[blue]CLOUD:[/blue] Netcat test result: {nc_test.stderr}")
                except Exception as e:
                    self.console.print(f"[red]CLOUD:[/red] Netcat test error: {str(e)}")

                self.console.print(f"[blue]CLOUD:[/blue] Checking IGW for VPC {vpc_id}")
                # Check if IGW exists and is attached
                igw_response = ec2_client.describe_internet_gateways(
                    Filters=[{'Name': 'attachment.vpc-id', 'Values': [vpc_id]}]
                )

                # Get route table for subnet
                route_tables = ec2_client.describe_route_tables(
                    Filters=[
                        {'Name': 'association.subnet-id', 'Values': [subnet_id]}
                    ]
                )

                if not route_tables['RouteTables']:
                    # If no specific route table, get main route table
                    route_tables = ec2_client.describe_route_tables(
                        Filters=[
                            {'Name': 'vpc-id', 'Values': [vpc_id]},
                            {'Name': 'association.main', 'Values': ['true']}
                        ]
                    )

                route_table_id = route_tables['RouteTables'][0]['RouteTableId']

                # Check if internet route exists
                internet_route_exists = False
                for route in route_tables['RouteTables'][0]['Routes']:
                    if route.get('DestinationCidrBlock') == '0.0.0.0/0':
                        internet_route_exists = True
                        break
                        
                # Set up security group rules
                instance_info = ec2_client.describe_instances(InstanceIds=[instance_id])
                security_groups = instance_info['Reservations'][0]['Instances'][0]['SecurityGroups']
                
                for sg in security_groups:
                    # Check if SSH rule exists
                    sg_rules = ec2_client.describe_security_group_rules(
                        Filters=[{'Name': 'group-id', 'Values': [sg['GroupId']]}]
                    )
                    
                    ssh_rule_exists = False
                    for rule in sg_rules['SecurityGroupRules']:
                        if (rule.get('IpProtocol') == 'tcp' and 
                            rule.get('FromPort') == 22 and 
                            rule.get('ToPort') == 22 and 
                            rule.get('IsEgress') is False):
                            ssh_rule_exists = True
                            break

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

            # Check if inventory has variable placeholders
            web_servers = inventory_content.get('all', {}).get('children', {}).get('web_servers', {})
            web_server_hosts = web_servers.get('hosts', {}).get('web_server_hosts', {})
            
            if ('{{ host_ip }}' in str(web_server_hosts) and 
                '{{ ssh_key_path }}' in str(web_server_hosts)):
                
                # Add variables section if it doesn't exist
                if 'vars' not in web_servers:
                    web_servers['vars'] = {}
                
                # Update variables with actual values
                web_servers['vars'].update({
                    'host_ip': instance_ips[0],
                    'ssh_key_path': str(key_path)
                })
                
                # Write updated inventory
                with open(inventory_path, 'w') as f:
                    yaml.dump(inventory_content, f)

            # Add debug output
            self.console.print(f"[blue]CLOUD:[/blue] Using key at: {key_path}")
            self.console.print(f"[blue]CLOUD:[/blue] Key exists: {key_path.exists()}")

            # Get sudo password
            self.console.print("\n[yellow]CLOUD: Please enter sudo password for remote hosts:[/yellow]")
            sudo_pass = getpass.getpass("Sudo password: ")
            
            # Run Ansible playbook
            msg = "Applying configuration to EC2 instances..."
            changes.append(msg)
            self.console.print(f"[blue]CLOUD:[/blue] {msg}")

            env = os.environ.copy()
            env['ANSIBLE_BECOME_PASS'] = sudo_pass

            # Verify paths before running
            self.console.print(f"[blue]CLOUD:[/blue] Using inventory: {inventory_path}")
            self.console.print(f"[blue]CLOUD:[/blue] Using playbook: {self.iac_path / 'playbook.yml'}")

            process = subprocess.Popen(
                [
                    'ansible-playbook',
                    '-i', str(inventory_path),
                    str(self.iac_path / 'playbook.yml'),
                    '--diff',
                    # '-vvv'  # Add verbose output
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )
            
            self.console.print("[blue]CLOUD:[/blue] Ansible playbook process started")

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

            self.console.print(f"[blue]CLOUD:[/blue] Process completed with return code: {process.returncode}")

            if process.returncode != 0:
                error_output = process.stderr.read()
                self.console.print(f"[red]CLOUD ERROR:[/red] Error output: {error_output}")
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
            self.console.print(f"[red]CLOUD ERROR:[/red] Exception occurred: {str(e)}")
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
    
    def _modify_terraform_config_for_networking(self, terraform_config: dict, vpc_id: str, subnet_id: str, security_group_id: str) -> dict:
        """
        Modifies terraform configuration to ensure required networking resources exist
        Returns modified terraform config
        """
        # Create deep copy to avoid modifying original
        config = json.loads(json.dumps(terraform_config))
        
        # Initialize resource section if doesn't exist
        if 'resource' not in config:
            config['resource'] = {}

        # Remove any old data sources to prevent conflicts
        if 'data' in config and 'aws_route_table' in config['data']:
            del config['data']['aws_route_table']

        # Check/add internet gateway
        if 'aws_internet_gateway' not in config['resource']:
            config['resource']['aws_internet_gateway'] = {
                'main': {
                    'vpc_id': vpc_id,
                    'tags': {
                        'Name': 'main',
                        'ManagedBy': 'terraform'
                    }
                }
            }

        # Add route table without inline routes
        if 'aws_route_table' not in config['resource']:
            config['resource']['aws_route_table'] = {
                'main': {
                    'vpc_id': vpc_id,
                    'tags': {
                        'Name': 'main',
                        'ManagedBy': 'terraform'
                    }
                }
            }
            
        # Add separate route resource
        if 'aws_route' not in config['resource']:
            config['resource']['aws_route'] = {
                'internet_access': {
                    'route_table_id': '${aws_route_table.main.id}',
                    'destination_cidr_block': '0.0.0.0/0',
                    'gateway_id': '${aws_internet_gateway.main.id}'
                }
            }
            
        # Add route table association
        if 'aws_route_table_association' not in config['resource']:
            config['resource']['aws_route_table_association'] = {
                'main': {
                    'subnet_id': subnet_id,
                    'route_table_id': '${aws_route_table.main.id}'
                }
            }

        # We'll skip adding the security group rule since it already exists
        # if 'aws_security_group_rule' not in config['resource']:
        #     config['resource']['aws_security_group_rule'] = {
        #         'allow_ssh': {
        #             'type': 'ingress',
        #             'from_port': 22,
        #             'to_port': 22,
        #             'protocol': 'tcp',
        #             'cidr_blocks': ['0.0.0.0/0'],
        #             'security_group_id': security_group_id
        #         }
        #     }

        return config

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
            
            if not errors:  # Only continue if infrastructure deployment succeeded
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