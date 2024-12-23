from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
import json
import os
import subprocess
import getpass
import yaml
import boto3
import re
from rich.console import Console
from botocore.exceptions import ClientError
import botocore

from ..error_mapping.error_mappers import CloudError, CloudErrorSeverity, CloudSourceLocation

class AnsibleDeploymentError(Exception):
    """Custom exception for ansible deployment failures"""
    pass

class UnsupportedOSError(Exception):
    """Raised when an unsupported OS is detected in the Ansible playbook"""
    pass


class AnsibleExecutor:
    """Handles execution of Ansible configurations for cloud resources"""
    
    def __init__(self, iac_path: str, cloud_file: str, ansible_mapper, console: Console):
        self.iac_path = Path(iac_path)
        self.cloud_file = Path(cloud_file)
        self.ansible_mapper = ansible_mapper
        self.console = console

    def _get_os_user(self) -> str:
        """
        Determine OS user by first checking playbook.yml, then checking platform details
        """
        # OS user mappings
        os_users = {
            'Ubuntu': 'ubuntu',
            'Debian': 'debian',
            'Amazon': 'ec2-user',
            'RedHat': 'ec2-user',
            'RHEL': 'ec2-user',
            'CentOS': 'centos',
            'Rocky': 'rocky',
            'AlmaLinux': 'almalinux',
            'Fedora': 'fedora',
            'SUSE': 'sles',
            'openSUSE': 'opensuse',
            'Oracle': 'opc',
            'OracleLinux': 'opc'
        }
        
        # First try to get user from playbook
        playbook_path = self.iac_path / 'playbook.yml'
        if playbook_path.exists():
            try:
                with open(playbook_path) as f:
                    playbook = yaml.safe_load(f)
                
                def search_tasks_recursively(tasks):
                    """Helper function to search through nested tasks"""
                    for task in tasks:
                        if 'when' in task:
                            condition = task['when']
                            if isinstance(condition, str) and 'ansible_distribution' in condition:
                                match = re.search(r"ansible_distribution\s*==\s*'([^']+)'", condition)
                                if match:
                                    return match.group(1)
                        
                        if 'block' in task:
                            result = search_tasks_recursively(task['block'])
                            if result:
                                return result

                for play in playbook:
                    if 'tasks' in play:
                        os_name = search_tasks_recursively(play['tasks'])
                        if os_name and os_name in os_users:
                            print(f"Found OS user from playbook: {os_users[os_name]} for OS: {os_name}")
                            return os_users[os_name]
                            
            except Exception as e:
                print(f"Error reading playbook: {str(e)}")

        # If playbook check fails, try to get from terraform config
        try:
            with open(self.iac_path / 'main.tf.json') as f:
                tf_config = json.load(f)

            # Check for GCP instances first
            if 'resource' in tf_config and 'google_compute_instance' in tf_config['resource']:
                print("Found GCP instance, checking boot disk image...")
                
                for instance in tf_config['resource']['google_compute_instance'].values():
                    if 'boot_disk' in instance and isinstance(instance['boot_disk'], list):
                        for disk in instance['boot_disk']:
                            if 'initialize_params' in disk and 'image' in disk['initialize_params']:
                                image_name = disk['initialize_params']['image'].lower()
                                print(f"Found GCP boot disk image: {image_name}")
                                
                                # Common GCP image patterns
                                if 'debian' in image_name:
                                    return 'debian'
                                elif 'ubuntu' in image_name:
                                    return 'ubuntu'
                                elif any(x in image_name for x in ['rhel', 'red-hat', 'redhat']):
                                    return 'root'
                                elif 'centos' in image_name:
                                    return 'centos'
                                elif 'cos' in image_name:  # Container-Optimized OS
                                    return 'chronos'
                                elif any(x in image_name for x in ['sles', 'suse']):
                                    return 'root'
                                
                                # Parse image name against known OS names
                                for os_name in os_users.keys():
                                    if os_name.lower() in image_name:
                                        return os_users[os_name]
                                
                                print(f"Unknown GCP image: {image_name}, defaulting to debian")
                                return 'debian'

            # Check for AWS instances
            elif 'resource' in tf_config and 'aws_instance' in tf_config['resource']:
                # Get region from terraform config
                region = 'us-east-1'  # Default fallback
                if 'provider' in tf_config and 'aws' in tf_config['provider']:
                    provider_config = tf_config['provider']['aws']
                    if isinstance(provider_config, dict):
                        region = provider_config.get('region', 'us-east-1')
                    elif isinstance(provider_config, list) and provider_config:
                        region = provider_config[0].get('region', 'us-east-1')
                
                print(f"Using region from terraform config: {region}")
                
                session = boto3.Session(region_name=region)
                ec2 = session.client('ec2', region_name=region)
                
                for instance in tf_config['resource']['aws_instance'].values():
                    if 'ami' in instance:
                        ami_id = instance['ami']
                        print(f"Found AMI ID in terraform config: {ami_id}")
                        
                        try:
                            print(f"Making AWS API call to describe image: {ami_id}")
                            response = ec2.describe_images(ImageIds=[ami_id])
                            
                            if response['Images']:
                                image = response['Images'][0]
                                os_name = image.get('Name', '').lower()
                                platform = image.get('Platform', '').lower()
                                platform_details = image.get('PlatformDetails', '').lower()
                                
                                print(f"Found AMI details: Name={os_name}, Platform={platform}, PlatformDetails={platform_details}")
                                
                                if platform == 'windows':
                                    return 'Administrator'
                                elif 'amazon linux 2' in os_name or 'amzn2' in os_name:
                                    return 'ec2-user'
                                elif 'ubuntu' in os_name:
                                    return 'ubuntu'
                                elif any(x in os_name for x in ['red hat', 'rhel']):
                                    return 'ec2-user'
                                elif 'centos' in os_name:
                                    return 'centos'
                                elif 'debian' in os_name:
                                    return 'admin'
                                elif 'suse' in os_name:
                                    return 'ec2-user'
                                elif os_name.startswith('amzn-'):
                                    return 'ec2-user'
                                elif os_name.startswith('al20') or os_name.startswith('al2023'):
                                    return 'ec2-user'
                                else:
                                    print(f"Unknown OS in AMI name: {os_name}, defaulting to ec2-user")
                                    return 'ec2-user'
                            
                        except botocore.exceptions.ClientError as e:
                            print(f"AWS API error: {str(e)}")
                            if 'AuthFailure' in str(e):
                                print("Authentication failed - please check AWS credentials")
                            elif 'InvalidAMIID.NotFound' in str(e):
                                print(f"AMI {ami_id} not found in region {region}")
                        
        except Exception as e:
            print(f"Error in OS user detection: {str(e)}")

        # Final fallback based on provider
        if 'provider' in tf_config and 'google' in tf_config['provider']:
            print("No user determination methods succeeded, falling back to default for GCP: debian")
            return 'debian'
        else:
            print("No user determination methods succeeded, falling back to default: ec2-user")
            return 'ec2-user'

    def _resolve_key_path(self) -> Path:
        """
        Resolve SSH key path by checking multiple locations and provider types
        """
        try:
            # First check terraform config
            with open(self.iac_path / 'main.tf.json') as f:
                terraform_config = json.load(f)
                
            # Check if this is a GCP configuration
            if 'provider' in terraform_config and 'google' in terraform_config['provider']:
                # For GCP, look for the SSH key in .keys directory
                key_path = self.iac_path / '.keys' / 'cloud-cli-key'
                if key_path.exists():
                    return key_path
            
            # Original AWS EC2 key handling
            if 'resource' in terraform_config:
                for resource_type, resources in terraform_config['resource'].items():
                    if resource_type == 'aws_instance':
                        for instance in resources.values():
                            if 'key_name' in instance and instance['key_name']:
                                specified_key = self.iac_path / '.keys' / f"{instance['key_name']}.pem"
                                if specified_key.exists():
                                    return specified_key
                                else:
                                    raise Exception(
                                        f"Specified key '{instance['key_name']}' not found in .keys directory. "
                                        f"Please place '{instance['key_name']}.pem' in the {self.iac_path / '.keys'} folder."
                                    )
                                    
        except Exception as e:
            self.console.print(f"[yellow]CLOUD:[/yellow] Warning reading terraform config: {str(e)}")

        # Look for any key file in .keys directory
        keys_dir = self.iac_path / '.keys'
        if keys_dir.exists():
            # Look for GCP key first
            gcp_keys = list(keys_dir.glob('cloud-cli-key'))
            if gcp_keys:
                return gcp_keys[0]
                
            # Then look for AWS .pem files
            pem_files = list(keys_dir.glob('*.pem'))
            if pem_files:
                return pem_files[0]

        raise Exception(
            f"No SSH key found in {keys_dir}. "
            "Please place your SSH private key in this directory."
        )
    
    def _get_instance_public_ip(self, instance_name: str, tf_outputs: dict) -> Optional[str]:
        """Get public IP from terraform outputs"""
        # Debug print outputs
        self.console.print(f"[blue]CLOUD:[/blue] Available outputs:")
        for k, v in tf_outputs.items():
            self.console.print(f"[blue]CLOUD:[/blue] - {k}: {v}")

        # Check if this is a GCP instance first
        gcp_output_key = f"instance_ip"  # The output key we defined for GCP
        if gcp_output_key in tf_outputs and tf_outputs[gcp_output_key].get('value'):
            self.console.print(f"[blue]CLOUD:[/blue] Found GCP instance IP in output: {gcp_output_key}")
            return tf_outputs[gcp_output_key]['value']

        # Original AWS IP lookup logic
        for output_name, output_data in tf_outputs.items():
            if ('public_ip' in output_name and 
                isinstance(output_data, dict) and 
                'value' in output_data):
                self.console.print(f"[blue]CLOUD:[/blue] Found public IP in output: {output_name}")
                return output_data['value']
                
        return None

    def _test_ansible_access(self, host_ip: str, key_path: Path) -> bool:
        """Test if we can access the host via SSH"""
        try:
            self.console.print(f"[blue]CLOUD:[/blue] Testing SSH connection to {host_ip}...")
            
            # Ensure key has correct permissions
            os.chmod(key_path, 0o600)

            # Determine if this is a GCP instance from terraform config
            with open(self.iac_path / 'main.tf.json') as f:
                terraform_config = json.load(f)
            is_gcp = 'google' in terraform_config.get('provider', {})
            
            # Get appropriate OS user based on provider
            os_user = 'debian' if is_gcp else self._get_os_user()
            
            # Try SSH connection
            ssh_test = subprocess.run(
                ['ssh', '-i', str(key_path), 
                 '-o', 'StrictHostKeyChecking=no',
                 '-o', 'ConnectTimeout=10',
                 f'{os_user}@{host_ip}',
                 'echo "SSH test successful"'],
                capture_output=True,
                text=True
            )
            
            if ssh_test.returncode == 0:
                self.console.print(f"[blue]CLOUD:[/blue] SSH connection successful")
                return True
            else:
                self.console.print(f"[yellow]CLOUD:[/yellow] SSH connection failed: {ssh_test.stderr}")
                return False
                
        except Exception as e:
            self.console.print(f"[yellow]CLOUD:[/yellow] SSH test error: {str(e)}")
            return False

    def _try_direct_ansible_deploy(self, host_ip: str, key_path: Path) -> Tuple[List[str], List[CloudError]]:
        """Attempt direct ansible deployment without additional setup"""
        changes = []
        errors = []
        
        try:
            # Determine if this is a GCP deployment from terraform config
            with open(self.iac_path / 'main.tf.json') as f:
                terraform_config = json.load(f)
            is_gcp = 'google' in terraform_config.get('provider', {})
            
            # Get appropriate OS user
            os_user = 'debian' if is_gcp else self._get_os_user()

            # Generate inventory
            inventory = {
                'all': {
                    'hosts': {
                        'web_server_hosts': {
                            'ansible_host': host_ip,
                            'ansible_user': os_user,
                            'ansible_ssh_private_key_file': str(key_path),
                            'ansible_ssh_common_args': '-o StrictHostKeyChecking=no'
                        }
                    }
                }
            }
            
            # Write inventory file
            inventory_path = self.iac_path / 'inventory.yml'
            with open(inventory_path, 'w') as f:
                yaml.dump(inventory, f)

            # Run ansible playbook
            self.console.print(f"[blue]CLOUD:[/blue] Attempting direct ansible deployment...")
            
            process = subprocess.Popen(
                [
                    'ansible-playbook',
                    '-i', str(inventory_path),
                    str(self.iac_path / 'playbook.yml'),
                    '--diff',
                    # '-vv'  # Added verbosity for debugging
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Process output
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

            # Check for errors in stderr
            stderr_output = process.stderr.read()
            if stderr_output:
                self.console.print(f"[yellow]CLOUD:[/yellow] Ansible stderr: {stderr_output}")
            
            # Check for errors
            if process.returncode != 0:
                error = self.ansible_mapper.map_error(stderr_output)
                if error:
                    errors.append(error)
                raise AnsibleDeploymentError("Direct ansible deployment failed")
                
            return changes, errors
            
        except Exception as e:
            if not isinstance(e, AnsibleDeploymentError):
                errors.append(CloudError(
                    severity=CloudErrorSeverity.ERROR,
                    message=str(e),
                    source_location=CloudSourceLocation(
                        line=1, column=1, block_type='configuration'
                    )
                ))
            return changes, errors

    # def _try_direct_ansible_deploy(self, host_ip: str, key_path: Path) -> Tuple[List[str], List[CloudError]]:
    #     """Attempt direct ansible deployment without additional setup"""
    #     changes = []
    #     errors = []
        
    #     try:
    #         # Determine if this is a GCP or AWS deployment from terraform config
    #         with open(self.iac_path / 'main.tf.json') as f:
    #             terraform_config = json.load(f)
    #         is_gcp = 'google' in terraform_config.get('provider', {})
            
    #         # Get appropriate OS user
    #         os_user = 'debian' if is_gcp else self._get_os_user()

    #         # Generate inventory
    #         inventory = {
    #             'all': {
    #                 'children': {
    #                     'web_servers': {
    #                         'hosts': {
    #                             'web_server_hosts': {
    #                                 'ansible_host': host_ip,
    #                                 'ansible_user': os_user,
    #                                 'ansible_ssh_private_key_file': str(key_path),
    #                                 'ansible_ssh_common_args': '-o StrictHostKeyChecking=no'
    #                             }
    #                         }
    #                     }
    #                 }
    #             }
    #         }
            
    #         # Write inventory file
    #         inventory_path = self.iac_path / 'inventory.yml'
    #         with open(inventory_path, 'w') as f:
    #             yaml.dump(inventory, f)

    #         # Run ansible playbook
    #         self.console.print(f"[blue]CLOUD:[/blue] Attempting direct ansible deployment...")
            
    #         process = subprocess.Popen(
    #             [
    #                 'ansible-playbook',
    #                 '-i', str(inventory_path),
    #                 str(self.iac_path / 'playbook.yml'),
    #                 '--diff'
    #             ],
    #             stdout=subprocess.PIPE,
    #             stderr=subprocess.PIPE,
    #             text=True
    #         )
            
    #         # Process output
    #         while True:
    #             line = process.stdout.readline()
    #             if not line and process.poll() is not None:
    #                 break
                
    #             line = line.strip()
    #             if line:
    #                 # Format special cases
    #                 if "TASK [" in line:
    #                     task_name = re.search(r'TASK \[(.*?)\]', line)
    #                     if task_name:
    #                         msg = f"Running task: {task_name.group(1)}"
    #                 elif "ok:" in line:
    #                     msg = f"Completed: {line.split('ok:')[1].strip()}"
    #                 elif "changed:" in line:
    #                     msg = f"Modified: {line.split('changed:')[1].strip()}"
    #                 elif "skipping:" in line:
    #                     msg = f"Skipped: {line.split('skipping:')[1].strip()}"
    #                 elif "failed:" in line:
    #                     msg = f"ERROR: {line.split('failed:')[1].strip()}"
    #                 else:
    #                     msg = line
                    
    #                 self.console.print(f"[blue]CLOUD:[/blue] {msg}")
    #                 changes.append(msg)
            
    #         # Check for errors
    #         if process.returncode != 0:
    #             stderr_output = process.stderr.read()
    #             error = self.ansible_mapper.map_error(stderr_output)
    #             if error:
    #                 errors.append(error)
    #             raise AnsibleDeploymentError("Direct ansible deployment failed")
                
    #         return changes, errors
            
    #     except Exception as e:
    #         if not isinstance(e, AnsibleDeploymentError):
    #             errors.append(CloudError(
    #                 severity=CloudErrorSeverity.ERROR,
    #                 message=str(e),
    #                 source_location=CloudSourceLocation(
    #                     line=1, column=1, block_type='configuration'
    #                 )
    #             ))
    #         raise

    def _setup_network_access(self, instance_id: str) -> Tuple[dict, str, str, List[dict]]:
        """
        Setup network access for the instance
        Returns tuple of (terraform_config, vpc_id, subnet_id, security_groups)
        """
        try:
            # Check if this is a GCP instance
            with open(self.iac_path / 'main.tf.json') as f:
                terraform_config = json.load(f)
            if 'provider' in terraform_config and 'google' in terraform_config['provider']:
                return terraform_config, None, None, None

            region = terraform_config.get('provider', {}).get('aws', {}).get('region', 'us-east-1')
            self.console.print(f"[blue]CLOUD:[/blue] Using AWS region: {region}")

            # Initialize AWS session
            session = boto3.Session(region_name=region)
            ec2_client = session.client('ec2', region_name=region)
            
            # Get instance info
            self.console.print(f"[blue]CLOUD:[/blue] Getting VPC info for instance {instance_id}")
            instance_info = ec2_client.describe_instances(InstanceIds=[instance_id])
            
            # Extract network info
            vpc_id = instance_info['Reservations'][0]['Instances'][0]['VpcId']
            subnet_id = instance_info['Reservations'][0]['Instances'][0]['SubnetId']
            security_groups = instance_info['Reservations'][0]['Instances'][0]['SecurityGroups']
            
            self.console.print(f"[blue]CLOUD:[/blue] Found VPC: {vpc_id}, Subnet: {subnet_id}")
            
            # Initialize resource section if needed
            if 'resource' not in terraform_config:
                terraform_config['resource'] = {}
                
            resources = terraform_config['resource']
            
            # Add Security Group if needed
            if 'aws_security_group' not in resources:
                resources['aws_security_group'] = {
                    'allow_ssh': {
                        'name': "allow_ssh",
                        'description': "Allow SSH inbound traffic",
                        'vpc_id': vpc_id,
                        'ingress': [{
                            'description': "SSH from anywhere",
                            'from_port': 22,
                            'to_port': 22,
                            'protocol': "tcp",
                            'cidr_blocks': ["0.0.0.0/0"],
                            'ipv6_cidr_blocks': [],
                            'prefix_list_ids': [],
                            'security_groups': [],
                            'self': False
                        }],
                        'egress': [{
                            'description': "Allow all outbound traffic",
                            'from_port': 0,
                            'to_port': 0,
                            'protocol': "-1",
                            'cidr_blocks': ["0.0.0.0/0"],
                            'ipv6_cidr_blocks': [],
                            'prefix_list_ids': [],
                            'security_groups': [],
                            'self': False
                        }],
                        'tags': {
                            'Name': "allow_ssh",
                            'ManagedBy': "terraform"
                        }
                    }
                }
                
                # Update EC2 instance to use the security group
                if 'aws_instance' in resources:
                    for instance in resources['aws_instance'].values():
                        instance['vpc_security_group_ids'] = ["${aws_security_group.allow_ssh.id}"]
            
            # Add Internet Gateway if needed
            if 'aws_internet_gateway' not in resources:
                resources['aws_internet_gateway'] = {
                    'main': {
                        'vpc_id': vpc_id,
                        'tags': {
                            'Name': 'main',
                            'ManagedBy': 'terraform'
                        }
                    }
                }

            # Add route table
            if 'aws_route_table' not in resources:
                resources['aws_route_table'] = {
                    'main': {
                        'vpc_id': vpc_id,
                        'tags': {
                            'Name': 'main',
                            'ManagedBy': 'terraform'
                        }
                    }
                }
                
            # Add internet route
            if 'aws_route' not in resources:
                resources['aws_route'] = {
                    'internet_access': {
                        'route_table_id': '${aws_route_table.main.id}',
                        'destination_cidr_block': '0.0.0.0/0',
                        'gateway_id': '${aws_internet_gateway.main.id}'
                    }
                }
                
            # Add route table association
            if 'aws_route_table_association' not in resources:
                resources['aws_route_table_association'] = {
                    'main': {
                        'subnet_id': subnet_id,
                        'route_table_id': '${aws_route_table.main.id}'
                    }
                }

            # Also ensure ALB has a security group if it exists
            if 'aws_lb' in resources:
                if 'aws_security_group' not in resources:
                    resources['aws_security_group'] = {}
                
                if 'alb' not in resources['aws_security_group']:
                    resources['aws_security_group']['alb'] = {
                        'name': "alb_security_group",
                        'description': "Security group for ALB",
                        'vpc_id': vpc_id,
                        'ingress': [{
                            'description': "HTTP from anywhere",
                            'from_port': 80,
                            'to_port': 80,
                            'protocol': "tcp",
                            'cidr_blocks': ["0.0.0.0/0"],
                            'ipv6_cidr_blocks': [],
                            'prefix_list_ids': [],
                            'security_groups': [],
                            'self': False
                        }],
                        'egress': [{
                            'description': "Allow all outbound traffic",
                            'from_port': 0,
                            'to_port': 0,
                            'protocol': "-1",
                            'cidr_blocks': ["0.0.0.0/0"],
                            'ipv6_cidr_blocks': [],
                            'prefix_list_ids': [],
                            'security_groups': [],
                            'self': False
                        }],
                        'tags': {
                            'Name': "alb_security_group",
                            'ManagedBy': "terraform"
                        }
                    }
                
                # Add security group to ALB
                for alb in resources['aws_lb'].values():
                    if 'security_groups' not in alb:
                        alb['security_groups'] = ["${aws_security_group.alb.id}"]

            return terraform_config, vpc_id, subnet_id, security_groups

        except Exception as e:
            self.console.print(f"[red]CLOUD ERROR:[/red] Failed to setup network access: {str(e)}")
            raise

    def _verify_network_setup(self, vpc_id: str, subnet_id: str) -> None:
        """Verify network setup is correct"""
        # Skip verification for GCP instances
        if not vpc_id or not subnet_id:
            return

        with open(self.iac_path / 'main.tf.json') as f:
            terraform_config = json.load(f)
            
        region = 'us-east-1'  # Default fallback
        if 'provider' in terraform_config and 'aws' in terraform_config['provider']:
            provider_config = terraform_config['provider']['aws']
            if isinstance(provider_config, dict):
                region = provider_config.get('region', 'us-east-1')
            elif isinstance(provider_config, list) and provider_config:
                region = provider_config[0].get('region', 'us-east-1')

        self.console.print(f"[blue]CLOUD:[/blue] Using AWS region: {region}")

        # Original AWS network setup
        session = boto3.Session(region_name=region)
        ec2_client = session.client('ec2', region_name=region)
            
        # Check subnet configuration
        subnet_info = ec2_client.describe_subnets(SubnetIds=[subnet_id])
        self.console.print(f"[blue]CLOUD:[/blue] Subnet {subnet_id} configuration:")
        self.console.print(f"[blue]CLOUD:[/blue] - MapPublicIpOnLaunch: {subnet_info['Subnets'][0].get('MapPublicIpOnLaunch')}")
        self.console.print(f"[blue]CLOUD:[/blue] - AvailableIpAddressCount: {subnet_info['Subnets'][0].get('AvailableIpAddressCount')}")
        
        # Check route tables
        route_tables = ec2_client.describe_route_tables(
            Filters=[{'Name': 'association.subnet-id', 'Values': [subnet_id]}]
        )
        self.console.print(f"[blue]CLOUD:[/blue] Route table configuration:")
        for rt in route_tables['RouteTables']:
            for route in rt['Routes']:
                self.console.print(f"[blue]CLOUD:[/blue] - Route: {route.get('DestinationCidrBlock')} -> {route.get('GatewayId', 'local')}")
                
        # Check Internet Gateway
        igw_response = ec2_client.describe_internet_gateways(
            Filters=[{'Name': 'attachment.vpc-id', 'Values': [vpc_id]}]
        )
        if not igw_response['InternetGateways']:
            raise Exception("No Internet Gateway found for VPC")

    def _apply_network_changes(self) -> Tuple[List[str], List[CloudError]]:
        """Apply network changes using terraform"""
        changes = []
        errors = []
        
        msg = "Applying network configuration changes..."
        self.console.print(f"[blue]CLOUD:[/blue] {msg}")
        changes.append(msg)
        
        process = subprocess.Popen(
            ['terraform', 'apply', '-auto-approve'],
            cwd=str(self.iac_path),
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
                    msg = f"ERROR: {stderr_line}"
                    self.console.print(f"[red]CLOUD ERROR:[/red] {msg}")
                    changes.append(msg)
        
        if process.returncode != 0:
            error = CloudError(
                severity=CloudErrorSeverity.ERROR,
                message=f"Failed to apply network changes",
                source_location=CloudSourceLocation(
                    line=1, column=1, block_type='configuration'
                )
            )
            errors.append(error)
                
        return changes, errors
    
    def execute_ansible_apply(self, mappings: Dict[str, str]) -> Tuple[List[str], List[CloudError]]:
        """
        Execute ansible configuration based on resource mappings
        Returns tuple of (changes, errors)
        """
        changes = []
        errors = []
        
        try:
            # Get terraform outputs
            try:
                tf_output = subprocess.check_output(
                    ['terraform', 'output', '-json'],
                    cwd=str(self.iac_path)
                )
                tf_outputs = json.loads(tf_output)
            except Exception as e:
                self.console.print(f"[red]CLOUD ERROR:[/red] Failed to get terraform outputs: {str(e)}")
                return [], [CloudError(
                    severity=CloudErrorSeverity.ERROR,
                    message=f"Failed to get terraform outputs: {str(e)}",
                    source_location=CloudSourceLocation(
                        line=1, column=1, block_type='configuration'
                    )
                )]

            # Determine if we're working with GCP or AWS
            with open(self.iac_path / 'main.tf.json') as f:
                terraform_config = json.load(f)
            is_gcp = 'google' in terraform_config.get('provider', {})

            # Process each mapping
            for resource_path, config_path in mappings.items():
                self.console.print(f"[blue]CLOUD:[/blue] Processing mapping: {resource_path} -> {config_path}")
                
                # Get resource name from path
                resource_parts = resource_path.split('.')
                if len(resource_parts) < 3:
                    continue
                    
                resource_name = resource_parts[2]  # e.g., 'web_server'
                
                # Get instance public IP
                public_ip = self._get_instance_public_ip(resource_name, tf_outputs)
                if not public_ip:
                    self.console.print(f"[red]CLOUD ERROR:[/red] No public IP found for {resource_name}")
                    continue
                    
                # Get SSH key path
                key_path = self._resolve_key_path()
                
                # First try: Direct ansible deployment
                try:
                    # Test SSH access
                    if self._test_ansible_access(public_ip, key_path):
                        # Try direct deployment
                        deployment_changes, deployment_errors = self._try_direct_ansible_deploy(
                            public_ip, 
                            key_path
                        )
                        changes.extend(deployment_changes)
                        errors.extend(deployment_errors)
                        if not deployment_errors:
                            continue  # Success! Move to next mapping
                            
                except Exception as e:
                    self.console.print(f"[yellow]CLOUD:[/yellow] Direct deployment failed: {str(e)}")
                
                # If direct deployment failed and this is AWS, try with network setup
                if not is_gcp:
                    self.console.print(f"[blue]CLOUD:[/blue] Direct deployment failed, attempting with network setup...")
                    
                    # Get instance ID for AWS
                    instance_id = None
                    for output_name, output_data in tf_outputs.items():
                        if (output_name.endswith('_id') and 
                            resource_name in output_name and 
                            isinstance(output_data, dict)):
                            instance_id = output_data.get('value')
                            break
                            
                    if not instance_id:
                        self.console.print(f"[red]CLOUD ERROR:[/red] No instance ID found for {resource_name}")
                        continue
                    
                    try:
                        # Setup network access for AWS
                        terraform_config, vpc_id, subnet_id, security_groups = self._setup_network_access(
                            instance_id
                        )
                        
                        if vpc_id:  # Only proceed with network changes for AWS
                            # Write modified terraform config
                            with open(self.iac_path / 'main.tf.json', 'w') as f:
                                json.dump(terraform_config, f, indent=2)
                                
                            # Apply network changes
                            network_changes, network_errors = self._apply_network_changes()
                            changes.extend(network_changes)
                            errors.extend(network_errors)
                            
                            if network_errors:
                                continue
                                
                            # Verify network setup
                            self._verify_network_setup(vpc_id, subnet_id)
                            
                            # Wait briefly for network changes to take effect
                            self.console.print(f"[blue]CLOUD:[/blue] Waiting for network changes to propagate...")
                            import time
                            time.sleep(10)
                        
                        # Try deployment again
                        if self._test_ansible_access(public_ip, key_path):
                            deployment_changes, deployment_errors = self._try_direct_ansible_deploy(
                                public_ip,
                                key_path
                            )
                            changes.extend(deployment_changes)
                            errors.extend(deployment_errors)
                        else:
                            msg = f"Still cannot access {public_ip} after network setup"
                            self.console.print(f"[red]CLOUD ERROR:[/red] {msg}")
                            errors.append(CloudError(
                                severity=CloudErrorSeverity.ERROR,
                                message=msg,
                                source_location=CloudSourceLocation(
                                    line=1, column=1, block_type='configuration'
                                )
                            ))
                            
                    except Exception as e:
                        self.console.print(f"[red]CLOUD ERROR:[/red] Network setup failed: {str(e)}")
                        errors.append(CloudError(
                            severity=CloudErrorSeverity.ERROR,
                            message=str(e),
                            source_location=CloudSourceLocation(
                                line=1, column=1, block_type='configuration'
                            )
                        ))

        except Exception as e:
            self.console.print(f"[red]CLOUD ERROR:[/red] Exception during ansible apply: {str(e)}")
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