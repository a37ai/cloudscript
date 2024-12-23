from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import click
import hcl2
import yaml
import os
import json
import re
from pathlib import Path
import subprocess
from datetime import datetime
import sys
import logging
import traceback
import time
from .executors.plan import CloudPlanExecutor
from .executors.apply import CloudApplyExecutor
from .executors.destroy import CloudDestroyExecutor
from .utils.file_preprocessing import preprocess_file_references, find_cloud_file
from typing import List, Dict, Optional, Tuple
from .error_mapping.error_mappers import *
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from transpiler.full import convert_enhanced_hcl_to_standard
from converter.full import main_convert


class MessageType(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SUCCESS = "SUCCESS"
    SUGGESTION = "SUGGESTION"

class ResourceType(Enum):
    COMPUTE = "compute"
    NETWORK = "network"
    STORAGE = "storage"
    DATABASE = "database"
    CONTAINER = "container"
    SERVICE = "service"

@dataclass
class SourceCodeLocation:
    file: str
    line: int
    column: int
    block_type: str  # 'service', 'infrastructure', 'configuration', 'containers', etc.
    block_name: str  # name of the service, container, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)



@dataclass
class ValidationMessage:
    type: MessageType
    source: str  # 'terraform', 'kubernetes', 'ansible', or 'cross-validation'
    message: str
    details: Optional[str] = None
    resource: Optional[str] = None
    source_location: Optional[SourceCodeLocation] = None
    suggestion: Optional[str] = None

@dataclass
class ConfigFile:
    path: str
    type: str  # 'cloud', 'terraform', 'kubernetes', or 'ansible'
    content: dict
    source_map: Dict[str, SourceCodeLocation] = None  # Maps resource IDs to source locations

class CloudSourceMapper:
    """Maps transpiled resources back to .cloud source code locations"""
    
    def __init__(self, cloud_file_path: str):
        self.cloud_file_path = cloud_file_path
        self.source_map = {}
        self._parse_source_file()

    def _parse_source_file(self):
        """Parse the .cloud file and create source mappings"""
        with open(self.cloud_file_path, 'r') as f:
            content = f.read()
            lines = content.split('\n')
            
            current_block = None
            current_block_name = None
            block_stack = []
            brace_count = 0
            in_vpc_block = False
            in_instance_block = False
            in_providers_block = False
            in_aws_block = False
            instance_name = None
        
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Track block properties
            if '=' in stripped:
                # Extract property name
                prop_name = stripped.split('=')[0].strip()
                
                if in_vpc_block:
                    self._add_mapping(
                        "aws_vpc.vpc.property",
                        line_num,
                        line.index(prop_name),
                        'network',
                        'vpc',
                        {
                            'property_name': prop_name,
                            'original_line': stripped,
                            'block_type': 'vpc'
                        }
                    )
                elif in_instance_block and 'instance_name' in locals():
                    self._add_mapping(
                        f"aws_instance.{instance_name}.property",
                        line_num,
                        line.index(prop_name),
                        'compute',
                        instance_name,
                        {
                            'property_name': prop_name,
                            'original_line': stripped,
                            'block_type': 'instance'
                        }
                    )

            # Track providers block
            if stripped == 'providers {':
                in_providers_block = True
                continue
                
            if in_providers_block:
                if stripped == 'aws {':
                    in_aws_block = True
                    continue
                    
                if in_aws_block:
                    # Track AWS provider parameters
                    if 'region' in stripped:
                        region_match = re.search(r'region\s*=\s*"([^"]+)"', stripped)
                        if region_match:
                            self._add_mapping(
                                "aws_provider.region",
                                line_num,
                                line.index('region'),
                                'provider',
                                'aws',
                                {
                                    'region': region_match.group(1),
                                    'original_line': stripped
                                }
                            )
                    elif 'provider' in stripped:
                        provider_match = re.search(r'provider\s*=\s*"([^"]+)"', stripped)
                        if provider_match:
                            self._add_mapping(
                                "aws_provider.name",
                                line_num,
                                line.index('provider'),
                                'provider',
                                'aws',
                                {
                                    'provider_name': provider_match.group(1),
                                    'original_line': stripped
                                }
                            )
                    
                if stripped == '}':
                    if in_aws_block:
                        in_aws_block = False
                    else:
                        in_providers_block = False
                        
        # All possible parameters to track
        vpc_params = [
            'cidr_block', 'instance_tenancy', 'enable_dns_support', 'enable_dns_hostnames',
            'enable_classiclink', 'enable_classiclink_dns_support', 'enable_network_address_usage_metrics',
            'ipv6_cidr_block', 'ipv6_association_id', 'ipv6_cidr_block_network_border_group',
            'dhcp_options_id', 'default_security_group_id', 'default_route_table_id',
            'default_network_acl_id', 'main_route_table_id', 'owner_id', 'tags'
        ]
        
        instance_params = [
            'ami', 'instance_type', 'key_name', 'availability_zone', 'placement_group',
            'subnet_id', 'vpc_security_group_ids', 'user_data', 'iam_instance_profile',
            'associate_public_ip_address', 'private_ip', 'secondary_private_ips',
            'ipv6_addresses', 'ebs_optimized', 'monitoring', 'source_dest_check',
            'disable_api_termination', 'instance_initiated_shutdown_behavior',
            'placement_partition_number', 'tenancy', 'host_id', 'cpu_core_count',
            'cpu_threads_per_core', 'tags'
        ]
        
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Track braces for nested block handling
            brace_count += stripped.count('{')
            brace_count -= stripped.count('}')
            
            # Track service blocks
            if stripped.startswith('service'):
                match = re.search(r'service\s+"([^"]+)"', stripped)
                if match:
                    service_name = match.group(1)
                    block_stack.append(('service', service_name))
                    self._add_mapping(f"service/{service_name}", 
                                    line_num, line.index('service'), 
                                    'service', service_name)

            # Track infrastructure section
            elif stripped == 'infrastructure {':
                current_block = 'infrastructure'
                self._add_mapping(f"infrastructure/{block_stack[-1][1]}" if block_stack else "infrastructure/main",
                                line_num, line.index('infrastructure'),
                                'infrastructure', block_stack[-1][1] if block_stack else 'main')

            # Track VPC block
            elif current_block == 'infrastructure' and 'network' in stripped.lower() and '{' in stripped:
                in_vpc_block = True
                vpc_start_line = line_num
            elif in_vpc_block:
                # Track all VPC parameters
                for param in vpc_params:
                    if param in stripped:
                        value_match = re.search(rf'{param}\s*=\s*"([^"]*)"', stripped)
                        if value_match:
                            self._add_mapping(
                                "aws_vpc.vpc",
                                line_num,
                                line.index(param),
                                'network',
                                'vpc',
                                {
                                    'parameter': param,
                                    'value': value_match.group(1),
                                    'vpc_start_line': vpc_start_line,
                                    'original_line': stripped
                                }
                            )
                if '}' in stripped:
                    in_vpc_block = False

            # Track Instance block
            elif current_block == 'infrastructure' and 'compute' in stripped.lower() and '{' in stripped:
                in_instance_block = True
                instance_start_line = line_num
                instance_name_match = re.search(r'name\s*=\s*"([^"]*)"', stripped)
                instance_name = instance_name_match.group(1) if instance_name_match else "instance"
            elif in_instance_block:
                # Track all Instance parameters
                for param in instance_params:
                    if param in stripped:
                        value_match = re.search(rf'{param}\s*=\s*"([^"]*)"', stripped)
                        if value_match:
                            self._add_mapping(
                                f"aws_instance.{instance_name}",
                                line_num,
                                line.index(param),
                                'compute',
                                instance_name,
                                {
                                    'parameter': param,
                                    'value': value_match.group(1),
                                    'instance_start_line': instance_start_line,
                                    'original_line': stripped
                                }
                            )
                if '}' in stripped:
                    in_instance_block = False

            # Check if we're exiting the current block
            if '}' in stripped:
                if brace_count == 0:
                    current_block = None
                    if block_stack:
                        block_stack.pop()

    def _add_mapping(self, resource_id: str, line: int, column: int, 
                    block_type: str, block_name: str, metadata: dict = None):
        """Add a source mapping for a resource with additional metadata"""
        # Create mapping key that includes parameter name if present
        mapping_key = resource_id
        if metadata and 'parameter' in metadata:
            mapping_key = f"{resource_id}.{metadata['parameter']}"
            
        self.source_map[mapping_key] = SourceCodeLocation(
            file=self.cloud_file_path,
            line=line,
            column=column,
            block_type=block_type,
            block_name=block_name,
            metadata=metadata or {}
        )

    def get_infrastructure_line(self, resource_type: str, value: str) -> Optional[SourceCodeLocation]:
        """Find line number for a specific infrastructure configuration value"""
        if resource_type == 'vpc':
            # Check all VPC parameter mappings
            for mapping_key, location in self.source_map.items():
                if mapping_key.startswith('aws_vpc.vpc.') and location.metadata.get('value') == value:
                    return location
        elif resource_type == 'instance':
            # Check all instance parameter mappings
            for mapping_key, location in self.source_map.items():
                if mapping_key.startswith('aws_instance.') and location.metadata.get('value') == value:
                    return location
        return None

    def get_source_location(self, resource_id: str) -> Optional[SourceCodeLocation]:
        """Get source location for a resource ID with rich error context"""
        # First try exact match
        location = self.source_map.get(resource_id)
        
        if not location:
            # Try to find parameter-specific mapping
            for mapping_key, loc in self.source_map.items():
                if mapping_key.startswith(resource_id + '.'):
                    location = loc
                    break
        
        if location:
            # Handle context for VPC resources
            if resource_id.startswith('aws_vpc.vpc'):
                with open(self.cloud_file_path, 'r') as f:
                    lines = f.readlines()
                    start_line = location.metadata.get('vpc_start_line', location.line)
                    context = ''.join(lines[start_line-1:location.line])
                    location.metadata['block_context'] = context
            # Handle context for Instance resources
            elif resource_id.startswith('aws_instance.'):
                with open(self.cloud_file_path, 'r') as f:
                    lines = f.readlines()
                    start_line = location.metadata.get('instance_start_line', location.line)
                    context = ''.join(lines[start_line-1:location.line])
                    location.metadata['block_context'] = context
            return location
        return None

    def get_param_location(self, resource_id: str, param_name: str) -> Optional[SourceCodeLocation]:
        """Get source location for a specific parameter of a resource"""
        mapping_key = f"{resource_id}.{param_name}"
        return self.source_map.get(mapping_key)

    def _suggest_kubernetes_fix(self, issue: ValidationMessage) -> str:
        """Generate suggestions for Kubernetes-related issues"""
        if "resource limits" in issue.message.lower():
            return (f"In your .cloud file at service '{issue.source_location.block_name}', "
                   f"add resource limits to your container definition:\n"
                   f"resources = {{\n"
                   f"  limits = {{ cpu = \"500m\", memory = \"512Mi\" }}\n"
                   f"  requests = {{ cpu = \"250m\", memory = \"256Mi\" }}\n"
                   f"}}")
        
        if "probe" in issue.message.lower():
            return (f"In your .cloud file at service '{issue.source_location.block_name}', "
                   f"add health checks to your container:\n"
                   f"health_check = {{\n"
                   f"  http_get = {{ path = \"/health\", port = 80 }}\n"
                   f"  initial_delay_seconds = 15\n"
                   f"  period_seconds = 20\n"
                   f"}}")

        if "image tag" in issue.message.lower():
            return (f"In your .cloud file at service '{issue.source_location.block_name}', "
                   f"specify a concrete version for your container image:\n"
                   f"image = \"nginx:1.21.6\"  # Replace 'latest' with specific version")

        return "No specific suggestion available for this Kubernetes issue"

    def _suggest_terraform_fix(self, issue: ValidationMessage) -> str:
        """Generate suggestions for Terraform-related issues"""
        if "instance type" in issue.message.lower():
            return (f"In your .cloud file at service '{issue.source_location.block_name}', "
                   f"update the instance size:\n"
                   f"size = \"t2.small\"  # or t2.medium for more resources")

        if "security group" in issue.message.lower():
            return (f"In your .cloud file at service '{issue.source_location.block_name}', "
                   f"add or update security group rules:\n"
                   f"security_groups = {{\n"
                   f"  ingress = [\n"
                   f"    {{ port = 80, cidr_blocks = [\"10.0.0.0/8\"] }}\n"
                   f"  ]\n"
                   f"}}")

        return "No specific suggestion available for this Terraform issue"

    def _suggest_ansible_fix(self, issue: ValidationMessage) -> str:
        """Generate suggestions for Ansible-related issues"""
        if "package" in issue.message.lower():
            return (f"In your .cloud file at service '{issue.source_location.block_name}', "
                   f"specify package versions:\n"
                   f"packages = {{\n"
                   f"  nginx = \"1.18.0\"\n"
                   f"  python3 = \"3.8.10\"\n"
                   f"}}")

        if "service" in issue.message.lower():
            return (f"In your .cloud file at service '{issue.source_location.block_name}', "
                   f"ensure services are properly configured:\n"
                   f"services = {{\n"
                   f"  running = [\"nginx\"]\n"
                   f"  enabled = [\"nginx\"]\n"
                   f"}}")

        return "No specific suggestion available for this Ansible issue"

    def suggest_fix(self, issue: ValidationMessage) -> str:
        """Generate a suggestion for fixing an issue in the .cloud code"""
        if not issue.source_location:
            return "Unable to provide specific suggestion - source location unknown"
            
        if issue.source == "kubernetes":
            return self._suggest_kubernetes_fix(issue)
        elif issue.source == "terraform":
            return self._suggest_terraform_fix(issue)
        elif issue.source == "ansible":
            return self._suggest_ansible_fix(issue)
            
        return "No specific suggestion available"

class CloudOrchestrator:
    def __init__(self, iac_path: str, cloud_file_path: str):
        self.iac_path = iac_path
        self.cloud_file_path = cloud_file_path
        self.configs: Dict[str, ConfigFile] = {}
        self.source_mapper = CloudSourceMapper(cloud_file_path)
        self.load_configurations()

    def load_configurations(self):
        """Load all configuration files from the IAC directory"""
        # Load original .cloud file
        with open(self.cloud_file_path, 'r') as f:
            self.configs['cloud'] = ConfigFile(
                self.cloud_file_path,
                'cloud',
                self._parse_cloud_file(f.read())
            )
        
        # # Load transpiled files
        # print(f"Looking for configs in: {self.iac_path}")

        for file in os.listdir(self.iac_path):
            # print(f"Found file: {file}")

            file_path = os.path.join(self.iac_path, file)
            
            if file.endswith('.tf.json'):
                with open(file_path, 'r') as f:
                    content = json.load(f)
                self.configs['terraform'] = ConfigFile(file_path, 'terraform', content)
            
            elif file == 'playbook.yml':  # Explicitly check for playbook.yml
                with open(file_path, 'r') as f:
                    content = list(yaml.safe_load_all(f))
                    self.configs['ansible'] = ConfigFile(file_path, 'ansible', content)
        
            elif file == 'resources.yml':
                with open(file_path, 'r') as f:
                    documents = list(yaml.safe_load_all(f))
                    self.configs['kubernetes'] = ConfigFile(file_path, 'kubernetes', documents)

    def _parse_cloud_file(self, content: str) -> dict:
        """Parse .cloud file content into structured format"""
        parsed = {
            'raw_content': content,
            'services': {},
            'types': {}
        }
        
        lines = content.split('\n')
        current_service = None
        current_type = None
        current_block = None
        
        for line_num, line in enumerate(lines):
            stripped = line.strip()
            
            # Parse type definitions
            if stripped.startswith('type '):
                type_match = re.match(r'type\s+(\w+)\s*{', stripped)
                if type_match:
                    current_type = type_match.group(1)
                    current_block = 'type'
                    parsed['types'][current_type] = {}
                    
            # Parse service definitions
            elif stripped.startswith('service '):
                service_match = re.match(r'service\s+"([^"]+)"', stripped)
                if service_match:
                    current_service = service_match.group(1)
                    current_block = 'service'
                    parsed['services'][current_service] = {
                        'infrastructure': {},
                        'configuration': {},
                        'containers': []
                    }
                    
            # Track infrastructure block
            elif stripped == 'infrastructure {':
                current_block = 'infrastructure'
                
            # Track configuration block
            elif stripped == 'configuration {':
                current_block = 'configuration'
                
            # Track containers block
            elif stripped.startswith('containers ='):
                current_block = 'containers'
                
            # Store content in appropriate section
            if current_service and current_block:
                if current_block in ['infrastructure', 'configuration', 'containers']:
                    parsed['services'][current_service][current_block] = line
                    
        return parsed

    def validate_cloud_syntax(self) -> List[ValidationMessage]:
        """Validate .cloud file syntax"""
        messages = []
        content = self.configs['cloud'].content['raw_content']
        lines = content.split('\n')
        
        block_stack = []
        current_service = None
        brace_count = 0
        
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            
            if not stripped or stripped.startswith('#'):
                continue
                    
            # Handle service declarations
            if line.startswith('service'):
                if not re.match(r'service\s+"[^"]+"\s*{', stripped):
                    messages.append(ValidationMessage(
                        type=MessageType.ERROR,
                        source="cloud",
                        message="Invalid service declaration syntax",
                        details=f"Line {line_num}: {line}",
                        source_location=SourceCodeLocation(
                            file=self.cloud_file_path,
                            line=line_num,
                            column=1,
                            block_type="service",
                            block_name="unknown"
                        ),
                        suggestion='Use format: service "name" {'
                    ))
                else:
                    service_name = re.search(r'service\s+"([^"]+)"', stripped).group(1)
                    block_stack.append(('service', service_name))

            # Count braces
            if '{' in stripped:
                brace_count += 1
            if '}' in stripped:
                brace_count -= 1
                if block_stack and brace_count == 0:
                    block_stack.pop()
        
        # Only report unclosed blocks if there are actually unclosed braces
        if brace_count > 0 and block_stack:
            block_details = []
            for block_type, block_name in block_stack:
                if block_type == 'service':
                    block_details.append(f"{block_type} '{block_name}'")
            
            if block_details:
                messages.append(ValidationMessage(
                    type=MessageType.ERROR,
                    source="cloud",
                    message="Unclosed blocks detected",
                    details=f"Missing closing braces for: {', '.join(block_details)}",
                    suggestion="Ensure all blocks are properly closed with }"
                ))
        
        return messages
        
    def validate_terraform_output(self) -> List[ValidationMessage]:
        """Validate the transpiled Terraform configuration"""
        messages = []
        tf_config = self.configs.get('terraform')
        
        if not tf_config:
            return messages
            
        content = tf_config.content
        
        # Validate provider configuration
        if 'provider' not in content:
            messages.append(ValidationMessage(
                type=MessageType.ERROR,
                source="terraform",
                message="Missing provider configuration",
                source_location=self.source_mapper.get_source_location("service/main"),
                suggestion="Add provider configuration to your service block"
            ))
        
        # Validate instance configurations
        if 'resource' in content:
            resources = content['resource']
            if 'aws_instance' in resources:
                for instance_name, instance in resources['aws_instance'].items():
                    # Check instance type
                    if instance.get('instance_type') == 't2.micro':
                        messages.append(ValidationMessage(
                            type=MessageType.WARNING,
                            source="cloud",
                            message="Consider using a larger instance type for production",
                            resource=f"aws_instance.{instance_name}",
                            source_location=self.source_mapper.get_source_location(f"aws_instance.{instance_name}"),
                            suggestion="Update the size in your Instance type to 't2.small' or larger"
                        ))
                    
                    # Check root volume encryption
                    if not instance.get('root_block_device', {}).get('encrypted', False):
                        messages.append(ValidationMessage(
                            type=MessageType.WARNING,
                            source="cloud",
                            message="Root volume encryption not enabled",
                            resource=f"aws_instance.{instance_name}",
                            source_location=self.source_mapper.get_source_location(f"aws_instance.{instance_name}"),
                            suggestion="Add root_block_device.encrypted = true to your compute block"
                        ))
                    
                    # Check security groups
                    if not instance.get('vpc_security_group_ids'):
                        messages.append(ValidationMessage(
                            type=MessageType.ERROR,
                            source="cloud",
                            message="Instance missing security group",
                            resource=f"aws_instance.{instance_name}",
                            source_location=self.source_mapper.get_source_location(f"aws_instance.{instance_name}"),
                            suggestion="Add security group configuration to your compute block"
                        ))
        
        # Validate security groups
        if 'aws_security_group' in resources:
            for sg_name, sg in resources['aws_security_group'].items():
                # Check for overly permissive rules
                for rule in sg.get('ingress', []):
                    if rule.get('cidr_blocks') == ['0.0.0.0/0'] and rule.get('to_port') != 80:
                        messages.append(ValidationMessage(
                            type=MessageType.WARNING,
                            source="cloud",
                            message=f"Security group has wide-open access on port {rule.get('to_port')}",
                            resource=f"aws_security_group.{sg_name}",
                            source_location=self.source_mapper.get_source_location(f"aws_security_group.{sg_name}"),
                            suggestion="Restrict security group access to specific IP ranges"
                        ))
        
        return messages

    def validate_kubernetes_output(self) -> List[ValidationMessage]:
        """Validate the transpiled Kubernetes configuration"""
        messages = []
        k8s_config = self.configs.get('kubernetes')
        
        if not k8s_config:
            return messages
            
        for doc in k8s_config.content:
            kind = doc.get('kind')
            metadata = doc.get('metadata', {})
            name = metadata.get('name', 'unknown')
            
            if kind == 'Deployment':
                spec = doc.get('spec', {})
                template = spec.get('template', {})
                containers = template.get('spec', {}).get('containers', [])
                
                for container in containers:
                    # Check resource limits
                    if 'resources' not in container:
                        messages.append(ValidationMessage(
                            type=MessageType.WARNING,
                            source="cloud",
                            message="Container missing resource limits",
                            resource=f"Deployment/{name}",
                            source_location=self.source_mapper.get_source_location(f"containers/{name}"),
                            suggestion="Add resource limits to your container definition"
                        ))
                    elif container.get('resources'):
                        resources = container['resources']
                        if not resources.get('limits') or not resources.get('requests'):
                            messages.append(ValidationMessage(
                                type=MessageType.WARNING,
                                source="cloud",
                                message="Container missing resource requests or limits",
                                resource=f"Deployment/{name}",
                                source_location=self.source_mapper.get_source_location(f"containers/{name}"),
                                suggestion="Specify both requests and limits in your resource configuration"
                            ))
                    
                    # Check probes
                    if 'livenessProbe' not in container and 'readinessProbe' not in container:
                        messages.append(ValidationMessage(
                            type=MessageType.WARNING,
                            source="cloud",
                            message="Container missing health probes",
                            resource=f"Deployment/{name}",
                            source_location=self.source_mapper.get_source_location(f"containers/{name}"),
                            suggestion="Add health check configuration to your container"
                        ))
                    
                    # Check image tag
                    image = container.get('image', '')
                    if ':latest' in image:
                        messages.append(ValidationMessage(
                            type=MessageType.WARNING,
                            source="cloud",
                            message="Container using 'latest' tag",
                            resource=f"Deployment/{name}",
                            source_location=self.source_mapper.get_source_location(f"containers/{name}"),
                            suggestion="Specify a concrete version instead of 'latest' tag"
                        ))
        
        return messages

    def validate_ansible_output(self) -> List[ValidationMessage]:
        """Validate the transpiled Ansible configuration"""
        messages = []
        ansible_config = self.configs.get('ansible')
        
        if not ansible_config:
            return messages
                
        for playbook in ansible_config.content:
            # Safely check become with get() since playbook is now a dict
            if isinstance(playbook, dict) and not playbook.get('become'):
                messages.append(ValidationMessage(
                    type=MessageType.WARNING,
                    source="cloud",
                    message="Playbook not using privilege escalation",
                    source_location=self.source_mapper.get_source_location("configuration/main"),
                    suggestion="Add become: true to your configuration block"
                ))
            
            # Validate tasks
            tasks = playbook.get('tasks', []) if isinstance(playbook, dict) else []
            for task in tasks:
                # Check for name
                if not task.get('name'):
                    messages.append(ValidationMessage(
                        type=MessageType.WARNING,
                        source="cloud",
                        message="Task missing name",
                        source_location=self.source_mapper.get_source_location("configuration/main"),
                        suggestion="Add descriptive names to all tasks in your configuration"
                    ))
                
                # Check for package versions
                if task.get('apt') or task.get('yum'):
                    packages = task.get('apt', {}).get('name', []) if task.get('apt') else task.get('yum', {}).get('name', [])
                    if isinstance(packages, list) and not any('=' in pkg for pkg in packages):
                        messages.append(ValidationMessage(
                            type=MessageType.WARNING,
                            source="cloud",
                            message="Package versions not specified",
                            source_location=self.source_mapper.get_source_location("configuration/main"),
                            suggestion="Specify package versions in your packages list"
                        ))
        
        return messages

    def suggest_improvements(self) -> List[ValidationMessage]:
        """Suggest improvements for the .cloud configuration"""
        messages = []
        
        # Collect all validations
        messages.extend(self.validate_cloud_syntax())
        messages.extend(self.validate_terraform_output())
        messages.extend(self.validate_kubernetes_output())
        messages.extend(self.validate_ansible_output())
        
        # Add high-level suggestions
        cloud_content = self.configs['cloud'].content['raw_content']
        
        # Check for missing health checks
        if 'health_check' not in cloud_content:
            messages.append(ValidationMessage(
                type=MessageType.SUGGESTION,
                source="cloud",
                message="Consider adding health checks to your services",
                suggestion="Add health_check blocks to your container definitions"
            ))
        
        # Check for missing resource limits
        if 'resources' not in cloud_content:
            messages.append(ValidationMessage(
                type=MessageType.SUGGESTION,
                source="cloud",
                message="Consider adding resource limits",
                suggestion="Add resource limits to your compute and container definitions"
            ))
        
        return messages

    def destroy_terraform(self) -> List[str]:
        """Destroy Terraform resources with proper var handling"""
        tfvars_path = None
        changes = []
        try:
            # Create tfvars file with default values
            tfvars_content = {
                'aws_region': 'us-west-2',
                'assume_role_arn': ''
            }
            
            tfvars_path = os.path.join(self.iac_path, 'terraform.tfvars.json')
            with open(tfvars_path, 'w') as f:
                json.dump(tfvars_content, f, indent=2)

            # Start destroy with streaming output
            msg = format_cloud_message("Starting infrastructure destruction")
            print(msg)
            changes.append(msg)
            
            process = subprocess.Popen(
                ['terraform', 'destroy', '-auto-approve', '-no-color', '-var-file=terraform.tfvars.json'],
                cwd=self.iac_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
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
                        'terraform has made some changes',
                        'enter a value']):
                        continue
                    
                    # Remove the word terraform and format
                    line = re.sub(r'terraform\s+', '', line, flags=re.IGNORECASE)
                    
                    if "Destroy complete!" in line:
                        stats = re.search(r'(\d+)\s+destroyed', line)
                        if stats:
                            destroyed = stats.group(1)
                            msg = format_cloud_message(f"Destroyed {destroyed} resources")
                            print(msg)
                            changes.append(msg)
                    elif any(action in line for action in ["Destroying", "Destroyed"]):
                        msg = format_cloud_message(line)
                        print(msg)
                        changes.append(msg)

            # Check for any errors in stderr
            error_output = process.stderr.read()
            if error_output:
                for line in error_output.split('\n'):
                    if line.strip():
                        msg = format_cloud_message(f"ERROR: {line.strip()}")
                        print(msg)
                        changes.append(msg)

            if process.returncode == 0:
                msg = format_cloud_message("Infrastructure destruction complete")
                print(msg)
                changes.append(msg)
            else:
                msg = format_cloud_message("ERROR: Infrastructure destruction failed")
                print(msg)
                changes.append(msg)

            return changes

        except Exception as e:
            msg = format_cloud_message(f"ERROR: {str(e)}")
            print(msg)
            return [msg]
        finally:
            # Clean up tfvars file
            if tfvars_path and os.path.exists(tfvars_path):
                try:
                    os.remove(tfvars_path)
                except Exception:
                    pass

    def destroy_kubernetes(self) -> bool:
        """Delete Kubernetes resources"""
        try:
            subprocess.run(['kubectl', 'delete', '-f', self.configs['kubernetes'].path],
                        check=True)
            return True
        except subprocess.CalledProcessError:
            return False
    
def format_cloud_message(message: str) -> str:
    """Format cloud messages with blue CLOUD prefix"""
    if not message.strip():
        return ""
        
    # Strip any existing CLOUD prefix to avoid duplication
    if message.startswith("CLOUD:"):
        message = message[6:].strip()
    elif message.startswith("CLOUD ERROR:"):
        message = "ERROR: " + message[12:].strip()
        return click.style("CLOUD:", fg="blue") + click.style(f" {message}", fg="red")
    elif message.startswith("CLOUD WARNING:"):
        message = "WARNING: " + message[14:].strip()
        return click.style("CLOUD:", fg="blue") + click.style(f" {message}", fg="yellow")
        
    return click.style("CLOUD:", fg="blue") + f" {message}"

def format_message(msg: ValidationMessage) -> str:
    """Format a validation message with color and styling"""
    icon_map = {
        MessageType.ERROR: click.style("✗", fg="red"),
        MessageType.WARNING: click.style("⚠", fg="yellow"),
        MessageType.INFO: click.style("ℹ", fg="blue"),
        MessageType.SUCCESS: click.style("✓", fg="green"),
        MessageType.SUGGESTION: click.style("→", fg="cyan")
    }
    
    # Format location info if available
    location = ""
    if msg.source_location:
        location = click.style(
            f" ({msg.source_location.file}:{msg.source_location.line})",
            fg="bright_black"
        )
    
    # Format source identifier
    source_color = {
        "terraform": "blue",
        "kubernetes": "cyan",
        "ansible": "green",
        "cloud": "blue",
        "cross-validation": "yellow"
    }.get(msg.source, "white")
    
    source_text = click.style(f"[{msg.source.upper()}]", fg=source_color)
    
    # Format base message
    timestamp = datetime.now().strftime("%H:%M:%S")
    base = f"{icon_map[msg.type]} {timestamp} {source_text} {msg.message}{location}"
    
    # Add resource information if present
    if msg.resource:
        base += f"\n  {click.style('├─', fg='bright_black')} Resource: {msg.resource}"
    
    # Add details if present
    if msg.details:
        detail_lines = msg.details.split('\n')
        for i, line in enumerate(detail_lines):
            connector = '└─' if i == len(detail_lines) - 1 and not msg.suggestion else '├─'
            base += f"\n  {click.style(connector, fg='bright_black')} {line}"
    
    # Add suggestion if present
    if msg.suggestion:
        suggestion_lines = msg.suggestion.split('\n')
        for i, line in enumerate(suggestion_lines):
            connector = '└─' if i == len(suggestion_lines) - 1 else '├─'
            if i == 0:
                base += f"\n  {click.style(connector, fg='cyan')} Suggestion: {line}"
            else:
                base += f"\n  {click.style('│ ', fg='cyan')}{line}"
    
    return base


def print_validation_summary(messages: List[ValidationMessage]):
    """Print a summary of validation results"""
    errors = sum(1 for msg in messages if msg.type == MessageType.ERROR)
    warnings = sum(1 for msg in messages if msg.type == MessageType.WARNING)
    suggestions = sum(1 for msg in messages if msg.type == MessageType.SUGGESTION)
    
    click.echo("\n=== Validation Summary ===")
    click.echo(f"Critical Issues: {click.style(str(errors), fg='red' if errors else 'green')}")
    click.echo(f"Warnings: {click.style(str(warnings), fg='yellow' if warnings else 'green')}")
    click.echo(f"Suggestions: {click.style(str(suggestions), fg='blue')}")
    
    if errors:
        click.echo(click.style("\n✗ Validation failed! Please fix critical issues before proceeding.", fg="red", bold=True))
    elif warnings:
        click.echo(click.style("\n⚠ Validation completed with warnings. Review them before proceeding.", fg="yellow"))
    else:
        click.echo(click.style("\n✓ All validations passed successfully!", fg="green", bold=True))

def confirm_destruction() -> bool:
    """Get confirmation for destroying resources"""
    click.echo(click.style("\n!!! WARNING !!!", fg="red", bold=True))
    click.echo(click.style("You are about to DESTROY all infrastructure resources!", fg="red"))
    click.echo(click.style("This action cannot be undone and may result in data loss!", fg="red"))
    
    confirmation = click.prompt(
        click.style('\nType "DESTROY" to confirm destruction of all resources', fg="red", bold=True),
        type=str
    )
    
    return confirmation == "DESTROY"

def run_with_spinner(message: str):
    """Decorator to show a spinner during long-running operations"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with click.progressbar(length=100, label=message) as bar:
                try:
                    result = func(*args, **kwargs)
                    bar.update(100)
                    return result
                except Exception as e:
                    bar.update(100)
                    raise e
        return wrapper
    return decorator

def get_resource_changes(before: dict, after: dict) -> List[str]:
    """Compare before and after states to determine changes"""
    changes = []
    
    # Compare resources
    for resource_type in set(before.keys()) | set(after.keys()):
        before_resources = before.get(resource_type, {})
        after_resources = after.get(resource_type, {})
        
        # Find added resources
        for name in set(after_resources.keys()) - set(before_resources.keys()):
            changes.append(f"➕ Add {resource_type}.{name}")
        
        # Find removed resources
        for name in set(before_resources.keys()) - set(after_resources.keys()):
            changes.append(f"➖ Remove {resource_type}.{name}")
        
        # Find modified resources
        for name in set(before_resources.keys()) & set(after_resources.keys()):
            if before_resources[name] != after_resources[name]:
                changes.append(f"📝 Modify {resource_type}.{name}")
    
    return changes


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
            # Format location with line number and context
            location_str = ""
            if error.source_location:
                location_base = f"{error.source_location.block_type}:{error.source_location.line}"
                
                # Include original content if available
                if hasattr(error.source_location, 'metadata') and error.source_location.metadata:
                    original_line = error.source_location.metadata.get('original_line', '')
                    if original_line:
                        # Truncate line content if too long
                        if len(original_line) > 30:
                            original_line = original_line[:27] + "..."
                        location_str = f"{location_base}\n└─ {original_line}"
                    else:
                        location_str = location_base

            # Clean and format error message
            message = error.message
            # Remove any mention of terraform/Terraform
            message = re.sub(r'[Tt]erraform\s+', '', message)
            # Add CLOUD prefix
            message = f"[blue]CLOUD:[/blue] {message}"

            error_table.add_row(
                str(error.severity.value),
                location_str or "",
                message,
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

@click.group()
def cli():
    """Cloud Infrastructure Management CLI"""
    pass

@cli.command()
def help():
    """Display help information about cloud CLI commands"""
    click.echo("\nCloud CLI - Infrastructure Management Tool\n")
    
    # General usage
    click.echo("USAGE:")
    click.echo("  cloud [OPTIONS] COMMAND [ARGS]\n")
    
    # Commands section
    click.echo("COMMANDS:")
    click.echo("  convert   Convert .cloud configuration to standard infrastructure code")
    click.echo("  plan      Show execution plan for .cloud configuration")
    click.echo("  apply     Apply .cloud configuration to AWS infrastructure")
    click.echo("  destroy   Destroy all infrastructure defined in .cloud file")
    click.echo("  help      Display this help message\n")
    
    # Common options section
    click.echo("COMMON OPTIONS:")
    click.echo("  --iac-path=PATH    Path to generated IAC directory (default: ./IaC)")
    click.echo("  --auto-approve     Skip interactive approval (available for apply/destroy)")
    click.echo("\n")
    
    # Example usage section
    click.echo("EXAMPLES:")
    click.echo("  cloud convert ./project")
    click.echo("  cloud plan ./project --iac-path=./IaC")
    click.echo("  cloud apply ./project --iac-path=./infrastructure --auto-approve")
    click.echo("  cloud destroy ./project --auto-approve")
    click.echo("\n")
    
    # Additional help info
    click.echo("Run 'cloud COMMAND --help' for more information about a command")
    
    return 0

@cli.command()
@click.argument('path', type=click.Path(exists=True))
@click.option('--iac-path', default='./IaC', help='Path to generated IAC directory')
def convert(path, iac_path):
    """Convert .cloud configuration to standard infrastructure code"""
    # Find .cloud file
    cloud_file = find_cloud_file(path)
    if not cloud_file:
        click.echo(click.style("\nError: No .cloud file found in the specified path.", fg="red"))
        return 1
    
    # Display warning message
    click.echo(click.style("\n⚠️  WARNING ⚠️", fg="yellow", bold=True))
    click.echo(click.style(
        "\nConverting will:\n"
        "1. Overwrite all existing content in the IaC directory\n"
        "2. Make the 'cloud destroy' command unable to destroy resources that were previously deployed\n"
        "\nAny deployed resources not captured in the new IaC files will need to be manually tracked and destroyed.",
        fg="yellow"
    ))
    
    # Prompt for confirmation
    confirmation = click.prompt(
        "\nTo proceed with conversion, please type CONVERT",
        type=str,
        default="",
        show_default=False
    )
    
    if confirmation != "CONVERT":
        click.echo(click.style("\nConversion cancelled.", fg="yellow"))
        return 1
    
    click.echo(click.style("\n=== Converting Cloud Configuration ===", fg="blue", bold=True))
    
    try:
        # Run conversion
        with click.progressbar(length=1, label='Converting configuration') as bar:
            main_convert(convert_enhanced_hcl_to_standard(str(cloud_file)))
            bar.update(1)
        
        # Preprocess file references
        preprocess_file_references(iac_path, cloud_file)
        
        click.echo(click.style("\n✓ Successfully converted cloud configuration!", fg="green"))
        return 0
        
    except Exception as e:
        click.echo(click.style(f"\n✗ Conversion failed: {str(e)}", fg="red"))
        return 1

# @cli.command()
# @click.argument('cloud-file', type=click.Path(exists=True))
# @click.option('--iac-path', default='./IaC', help='Path to generated IAC directory')
# def validate(cloud_file, iac_path):
#     """Validate .cloud file and generated infrastructure code"""
#     click.echo(click.style("\n=== Cloud Configuration Validation ===", fg="blue", bold=True))
    
#     orchestrator = CloudOrchestrator(iac_path, cloud_file)
    
#     # Collect all validation messages
#     messages = []
    
#     with click.progressbar(length=4, label='Running validations') as bar:
#         # Validate .cloud syntax
#         syntax_messages = orchestrator.validate_cloud_syntax()
#         messages.extend(syntax_messages)
#         bar.update(1)
        
#         # Validate Terraform output
#         tf_messages = orchestrator.validate_terraform_output()
#         messages.extend(tf_messages)
#         bar.update(1)
        
#         # Validate Kubernetes output
#         k8s_messages = orchestrator.validate_kubernetes_output()
#         messages.extend(k8s_messages)
#         bar.update(1)
        
#         # Validate Ansible output
#         ansible_messages = orchestrator.validate_ansible_output()
#         messages.extend(ansible_messages)
#         bar.update(1)
    
#     # Group messages by type
#     errors = [msg for msg in messages if msg.type == MessageType.ERROR]
#     warnings = [msg for msg in messages if msg.type == MessageType.WARNING]
#     suggestions = [msg for msg in messages if msg.type == MessageType.SUGGESTION]
    
#     # Print results grouped by type
#     if errors:
#         click.echo("\nCritical Issues:")
#         for msg in errors:
#             click.echo(format_message(msg))
    
#     if warnings:
#         click.echo("\nWarnings:")
#         for msg in warnings:
#             click.echo(format_message(msg))
    
#     if suggestions:
#         click.echo("\nSuggested Improvements:")
#         for msg in suggestions:
#             click.echo(format_message(msg))
    
#     # Print summary
#     print_validation_summary(messages)
    
#     return 1 if errors else 0


@cli.command()
@click.argument('path', type=click.Path(exists=True))
@click.option('--iac-path', default='./IaC', help='Path to generated IAC directory')
def plan(path, iac_path):
    """Show execution plan for .cloud configuration"""
    # Find .cloud file
    cloud_file = find_cloud_file(path)
    if not cloud_file:
        click.echo(click.style("\nError: No .cloud file found in the specified path.", fg="red"))
        return 1
        
    # Preprocess file references
    preprocess_file_references(iac_path, cloud_file)
    
    # Continue with existing plan logic
    executor = CloudPlanExecutor(iac_path, str(cloud_file), CloudSourceMapper(str(cloud_file)))
    changes, errors = executor.execute_plan()
    
    # Just show basic error messages
    if errors:
        # click.echo(click.style("\nErrors occurred during planning:", fg="red"))
        return 1
    
    # Show changes if any
    if changes:
        click.echo("\nPlanned changes:")
        for change in changes:
            click.echo(f"  {change}")
    else:
        click.echo("\nNo changes detected")
    
    return 0

@cli.command()
@click.argument('path', type=click.Path(exists=True))
@click.option('--iac-path', default='./IaC', help='Path to generated IAC directory')
@click.option('--auto-approve', is_flag=True, help='Skip interactive approval')
def apply(path, iac_path, auto_approve):
    """Apply .cloud configuration to AWS infrastructure"""
    # Find .cloud file
    cloud_file = find_cloud_file(path)
    if not cloud_file:
        click.echo(click.style("\nError: No .cloud file found in the specified path.", fg="red"))
        return 1
    
    # Preprocess file references
    preprocess_file_references(iac_path, cloud_file)
    
    executor = CloudApplyExecutor(iac_path, str(cloud_file), CloudSourceMapper(str(cloud_file)))
    
    # First run a plan to show what will change
    if not auto_approve:
        plan_executor = CloudPlanExecutor(iac_path, str(cloud_file), CloudSourceMapper(str(cloud_file)))
        plan_changes, plan_errors = plan_executor.execute_plan()
        
        if plan_errors:
            click.echo(click.style("\nPlan contains errors. Please fix them before applying.", fg="red"))
            return 1
            
        if not click.confirm("\nDo you want to apply these changes?"):
            click.echo("\nApply cancelled.")
            return 0
    
    # Execute the apply
    changes, errors = executor.execute_apply()
    
    # Show basic results
    if errors:
        # click.echo(click.style("\nErrors occurred during apply:", fg="red"))
        return 1
        
    # if changes:
    #     click.echo("\nApplied changes:")
    #     for change in changes:
    #         click.echo(f"  {change}")
    
    return 0

@cli.command()
@click.argument('path', type=click.Path(exists=True))
@click.option('--iac-path', default='./IaC', help='Path to generated IAC directory')
@click.option('--auto-approve', is_flag=True, help='Skip interactive approval')
def destroy(path, iac_path, auto_approve):
    """Destroy all infrastructure defined in .cloud file"""
    # Find .cloud file
    cloud_file = find_cloud_file(path)
    if not cloud_file:
        click.echo(click.style("\nError: No .cloud file found in the specified path.", fg="red"))
        return 1

    # Preprocess file references
    preprocess_file_references(iac_path, cloud_file)
    
    click.echo(click.style("\n=== Cloud Infrastructure Destruction ===", fg="red", bold=True))
    
    if not auto_approve and not confirm_destruction():
        click.echo("\nDestruction cancelled.")
        return 0
    
    executor = CloudDestroyExecutor(iac_path, str(cloud_file), CloudSourceMapper(str(cloud_file)))
    
    changes, errors = executor.execute_destroy()
    
    if errors:
        click.echo(click.style("\n✗ Infrastructure destruction failed.", fg="red"))
        return 1
    else:
        click.echo(click.style("\n✓ Successfully destroyed all infrastructure!", fg="green"))
        return 0
    
class CloudError(Exception):
    """Custom exception for Cloud CLI errors"""
    pass

def setup_logging():
    """Configure logging for the CLI"""
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.path.expanduser('~'), '.cloud', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Set up file handler
    log_file = os.path.join(log_dir, 'cloud.log')
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    
    # Set up console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    
    # Create formatters and add them to the handlers
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    file_handler.setFormatter(file_formatter)
    console_handler.setFormatter(console_formatter)
    
    # Get the root logger and add handlers
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

def check_dependencies():
    """Check if required CLI tools are installed"""
    dependencies = {
        'terraform': 'terraform --version',
        'kubectl': 'kubectl version --client',
        'ansible': 'ansible --version',
        'ansible-playbook': 'ansible-playbook --version'
    }
    
    missing = []
    for tool, command in dependencies.items():
        try:
            subprocess.run(command.split(), capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing.append(tool)
    
    if missing:
        click.echo(click.style("\nMissing required dependencies:", fg="red"))
        for tool in missing:
            click.echo(f"  • {tool}")
        click.echo("\nPlease install the missing dependencies and try again.")
        sys.exit(1)

def version_callback(ctx, param, value):
    """Print version information"""
    if not value or ctx.resilient_parsing:
        return
    click.echo("Cloud CLI v1.0.0")
    ctx.exit()

def init_config_dir():
    """Initialize configuration directory"""
    config_dir = os.path.join(os.path.expanduser('~'), '.cloud')
    os.makedirs(config_dir, exist_ok=True)
    
    # Create default configuration if it doesn't exist
    config_file = os.path.join(config_dir, 'config.yaml')
    if not os.path.exists(config_file):
        default_config = {
            'default_iac_path': './IaC',
            'auto_approve': False,
            'colors': True,
            'log_level': 'INFO'
        }
        with open(config_file, 'w') as f:
            yaml.dump(default_config, f)

@click.group()
@click.option('--debug/--no-debug', default=False, help='Enable debug mode')
@click.option('--version', is_flag=True, callback=version_callback,
              expose_value=False, is_eager=True, help='Show version information')
def main(debug):
    """Cloud Infrastructure Management CLI

    This CLI tool helps manage infrastructure defined in .cloud files by validating,
    planning, and applying changes across Terraform, Kubernetes, and Ansible.
    """
    try:
        # Initialize everything we need
        init_config_dir()
        setup_logging()
        check_dependencies()
        
        # Set debug mode
        if debug:
            logging.getLogger().setLevel(logging.DEBUG)
            click.echo(click.style("Debug mode enabled", fg="yellow"))
    
    except Exception as e:
        click.echo(click.style(f"\nError during initialization: {str(e)}", fg="red"))
        sys.exit(1)

# Add commands to the main group
# main.add_command(validate)
# main.add_command(lint)
main.add_command(convert)
main.add_command(plan)
main.add_command(apply)
main.add_command(destroy)
main.add_command(help)


@main.command()
def init():
    """Initialize a new .cloud project"""
    if os.path.exists('IaC'):
        click.echo(click.style("Error: IaC directory already exists", fg="red"))
        sys.exit(1)
    
    # Create project structure
    os.makedirs('IaC')
    
    # Create template .cloud file
    template = '''# Example .cloud configuration
service "example" {
  type = "application"
  
  infrastructure {
    compute = [
      {
        type = Instance
        name = "web_server"
        size = "t2.micro"
      }
    ]
  }
  
  configuration {
    packages = ["nginx"]
    services = {
      running = ["nginx"]
      enabled = ["nginx"]
    }
  }
  
  containers = [
    {
      name = "web"
      image = "nginx:1.21"
      ports = [80]
      health_check = {
        http_get = {
          path = "/"
          port = 80
        }
      }
    }
  ]
}
'''
    
    with open('service.cloud', 'w') as f:
        f.write(template)
    
    click.echo(click.style("\n✓ Initialized new .cloud project!", fg="green"))
    click.echo("\nCreated:")
    click.echo("  • IaC/")
    click.echo("  • service.cloud")
    click.echo("\nNext steps:")
    click.echo("1. Edit service.cloud to define your infrastructure")
    click.echo("2. Run 'cloud validate' to check your configuration")
    click.echo("3. Run 'cloud plan' to see what will be created")

@main.command()
def completion():
    """Generate shell completion script"""
    # Detect shell
    shell = os.environ.get('SHELL', '').split('/')[-1]
    
    if shell == 'bash':
        script = '''
_cloud_completion() {
    local IFS=$'\n'
    local response

    response=$(env COMP_WORDS="${COMP_WORDS[*]}" COMP_CWORD=$COMP_CWORD _CLOUD_COMPLETE=bash_complete $1)

    for completion in $response; do
        IFS=',' read type value <<< "$completion"
        
        if [[ $type == 'dir' ]]; then
            COMPREPLY=()
            compopt -o dirnames
        elif [[ $type == 'file' ]]; then
            COMPREPLY=()
            compopt -o default
        else
            COMPREPLY+=($value)
        fi
    done

    return 0
}

complete -F _cloud_completion cloud
'''
    elif shell == 'zsh':
        script = '''
#compdef cloud

_cloud() {
    local -a completions
    local -a completions_with_descriptions
    local -a response
    
    response=("${(@f)$(env COMP_WORDS="${words[*]}" COMP_CWORD=$((CURRENT-1)) _CLOUD_COMPLETE=zsh_complete cloud)}")

    for type message in ${(ps:\n:)response}; do
        if [[ $type == 'dir' ]]; then
            _path_files -/
        elif [[ $type == 'file' ]]; then
            _path_files -f
        else
            completions+=( "${message}" )
        fi
    done

    if [ -n "$completions" ]; then
        _describe -t cloud "cloud commands" completions
    fi
}

compdef _cloud cloud
'''
    else:
        click.echo(f"Shell completion not supported for {shell}")
        return

    click.echo(script)
    click.echo(f"\n# Add this to your ~/.{shell}rc:")
    click.echo(f"# source <(cloud completion)")

if __name__ == '__main__':
    main()