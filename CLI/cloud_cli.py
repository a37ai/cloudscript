from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
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
        current_service = None
        in_infrastructure = False
        in_configuration = False
        in_containers = False
        
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Track service blocks
            if stripped.startswith('service'):
                match = re.search(r'service\s+"([^"]+)"', stripped)
                if match:
                    current_service = match.group(1)
                    self._add_mapping(f"service/{current_service}", 
                                    line_num, line.index('service'), 
                                    'service', current_service)

            # Track infrastructure section
            elif stripped == 'infrastructure {':
                in_infrastructure = True
                self._add_mapping(f"infrastructure/{current_service}",
                                line_num, line.index('infrastructure'),
                                'infrastructure', current_service)

            elif stripped == 'configuration {':
                in_configuration = True
                self._add_mapping(f"configuration/{current_service}",
                                line_num, line.index('configuration'),
                                'configuration', current_service)

            elif stripped.startswith('containers'):
                in_containers = True
                self._add_mapping(f"containers/{current_service}",
                                line_num, line.index('containers'),
                                'containers', current_service)

            # Track compute instances
            elif in_infrastructure and 'type = Instance' in stripped:
                instance_context = '\n'.join(lines[max(0, line_num-3):min(len(lines), line_num+3)])
                name_match = re.search(r'name\s*=\s*"([^"]+)"', instance_context)
                if name_match:
                    instance_name = name_match.group(1)
                    self._add_mapping(f"aws_instance.{instance_name}",
                                    line_num, line.index('type'),
                                    'compute', instance_name)
                    # Map security group if present
                    if 'security_groups' in instance_context:
                        self._add_mapping(f"aws_security_group.{instance_name}",
                                        line_num, line.index('security_groups'),
                                        'security_group', instance_name)

            # Track containers
            elif in_containers and 'name = ' in stripped:
                name_match = re.search(r'name\s*=\s*"([^"]+)"', stripped)
                if name_match:
                    container_name = name_match.group(1)
                    self._add_mapping(f"container/{container_name}",
                                    line_num, line.index('name'),
                                    'container', container_name)
                    # Also map the Kubernetes deployment
                    self._add_mapping(f"Deployment/{container_name}",
                                    line_num, line.index('name'),
                                    'deployment', container_name)

            # Track block ends
            elif stripped == '}':
                if in_containers:
                    in_containers = False
                elif in_configuration:
                    in_configuration = False
                elif in_infrastructure:
                    in_infrastructure = False
                else:
                    current_service = None

    def _add_mapping(self, resource_id: str, line: int, column: int, 
                    block_type: str, block_name: str):
        """Add a source mapping for a resource"""
        self.source_map[resource_id] = SourceCodeLocation(
            file=self.cloud_file_path,
            line=line,
            column=column,
            block_type=block_type,
            block_name=block_name
        )

    def get_source_location(self, resource_id: str) -> Optional[SourceCodeLocation]:
        """Get source location for a resource ID"""
        return self.source_map.get(resource_id)

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


    def _get_terraform_plan(self) -> List[str]:
        """Get formatted Terraform plan output"""
        tfvars_path = None
        try:
            def format_terraform_output(line: str) -> str:
                """Format output as CLOUD comment with terraform word removed"""
                # Remove ANSI color codes and trim
                line = re.sub(r'\x1b\[[0-9;]*m', '', line.strip())
                if not line:
                    return None
                    
                # Remove the word "terraform" (case insensitive)
                line = re.sub(r'terraform\s+', '', line, flags=re.IGNORECASE)
                
                # Replace symbols with cleaner text
                line = line.replace('+ ', 'Will create ')
                line = line.replace('- ', 'Will destroy ')
                line = line.replace('~ ', 'Will modify ')
                line = line.replace('# ', '')
                
                # Skip lines that are just provider info or lock file info
                if any(skip in line.lower() for skip in 
                    ['used the selected providers',
                    'has created a lock file',
                    'note: objects have changed']):
                    return None
                    
                # If it's a change line but not a resource declaration, indent it
                if (line.startswith('Will ') and 
                    not any(x in line.lower() for x in ['resource', 'data', 'module'])):
                    return f"CLOUD:   {line}"
                    
                return f"CLOUD: {line}"

            # Create tfvars file
            tfvars_content = {
                'aws_region': 'us-west-2',
                'assume_role_arn': ''
            }
            
            tfvars_path = os.path.join(self.iac_path, 'terraform.tfvars.json')
            with open(tfvars_path, 'w') as f:
                json.dump(tfvars_content, f, indent=2)

            changes = []
            
            # Run terraform init
            init_result = subprocess.run(
                ['terraform', 'init'],
                cwd=self.iac_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )
            
            # Format initialization output
            for line in init_result.stdout.split('\n'):
                if line.strip():
                    if "successfully initialized" in line.lower():
                        changes.append(format_cloud_message("CLOUD: Initialization complete"))
                    elif "Installing" in line or "installed" in line:
                        formatted = format_terraform_output(line)
                        if formatted:
                            changes.append(format_cloud_message(formatted))
            
            # Run terraform plan
            plan_result = subprocess.run(
                ['terraform', 'plan', '-no-color', '-var-file=terraform.tfvars.json'],
                cwd=self.iac_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=60
            )
            
            # Process plan output
            for line in plan_result.stdout.split('\n'):
                if line.strip():
                    formatted = format_terraform_output(line)
                    if formatted:
                        changes.append(format_cloud_message(formatted))
            
            # If no changes were found, add a summary
            if not any('Will ' in change for change in changes):
                changes.append(format_cloud_message("CLOUD: No infrastructure changes required"))
            else:
                changes.append(format_cloud_message("CLOUD: Infrastructure changes detected"))
                
            return changes
            
        except subprocess.TimeoutExpired:
            return ["CLOUD ERROR: Operation timed out"]
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else "Unknown error occurred"
            # Remove word terraform from error message too
            error_msg = re.sub(r'terraform\s+', '', error_msg, flags=re.IGNORECASE)
            return [f"CLOUD ERROR: {error_msg}"]
        except Exception as e:
            error_msg = str(e)
            # Remove word terraform from error message too
            error_msg = re.sub(r'terraform\s+', '', error_msg, flags=re.IGNORECASE)
            return [f"CLOUD ERROR: {error_msg}"]
        finally:
            # Clean up tfvars file
            if tfvars_path and os.path.exists(tfvars_path):
                try:
                    os.remove(tfvars_path)
                except Exception:
                    pass

    def _get_kubernetes_plan(self) -> List[str]:
        """Get formatted Kubernetes plan output"""
        changes = []
        
        def format_kubectl_output(output_line: str) -> str:
            """Format kubectl output into CLOUD comments"""
            line = re.sub(r'\x1b\[[0-9;]*m', '', output_line).strip()
            if not line:
                return None
                
            # Extract resource info
            resource_match = re.search(r'(deployment|service|pod|configmap|secret)\.?(?:[^\s]+)?\s+"([^"]+)"', line, re.IGNORECASE)
            
            if resource_match:
                resource_type, name = resource_match.groups()
                
                if "created" in line.lower():
                    return f"CLOUD: Would create {resource_type} '{name}' in containers.app.web_frontend"
                elif "configured" in line.lower():
                    return f"CLOUD: Would update {resource_type} '{name}' in containers.app.web_frontend"
                elif "unchanged" in line.lower():
                    return f"CLOUD: No changes needed for {resource_type} '{name}'"
                elif "deleted" in line.lower():
                    return f"CLOUD: Would delete {resource_type} '{name}'"
                    
            # Handle validation errors
            if "error" in line.lower():
                error_type = None
                if "resources" in line.lower():
                    error_type = "resource configuration"
                elif "probe" in line.lower() or "health" in line.lower():
                    error_type = "health check configuration"
                elif "port" in line.lower():
                    error_type = "port configuration"
                elif "env" in line.lower():
                    error_type = "environment variables"
                    
                if error_type:
                    return f"CLOUD ERROR: Invalid {error_type} in containers.app.web_frontend"
                return f"CLOUD ERROR: {line}"

            return None

        try:
            # Check if minikube is already running
            try:
                subprocess.run(['minikube', 'status'], 
                            check=True,
                            capture_output=True,
                            timeout=10)  # 10 second timeout
                changes.append(format_cloud_message("CLOUD: Using existing Kubernetes cluster"))
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                # Try to stop any existing cluster first
                try:
                    subprocess.run(['minikube', 'stop'], 
                                check=False,  # Don't check return code
                                capture_output=True,
                                timeout=30)
                except Exception:
                    pass  # Ignore any errors here

                changes.append(format_cloud_message("CLOUD: Starting new Kubernetes cluster"))
                try:
                    # Start minikube with a timeout
                    subprocess.run(['minikube', 'start', '--wait=false'], 
                                check=True,
                                capture_output=True,
                                timeout=60)  # 60 second timeout
                except subprocess.TimeoutExpired:
                    return ["CLOUD ERROR: Timeout while starting Kubernetes cluster"]
                except subprocess.CalledProcessError as e:
                    return [f"CLOUD ERROR: Failed to start Kubernetes cluster: {e.stderr.decode() if e.stderr else ''}"]

            # Wait for cluster to be ready
            max_retries = 5
            retry_delay = 2
            for i in range(max_retries):
                try:
                    # Try to validate cluster is responding
                    subprocess.run(['kubectl', 'get', 'nodes'], 
                                check=True,
                                capture_output=True,
                                timeout=10)
                    changes.append(format_cloud_message("CLOUD: Kubernetes cluster is ready"))
                    break
                except Exception:
                    if i == max_retries - 1:
                        return ["CLOUD ERROR: Kubernetes cluster failed to become ready"]
                    time.sleep(retry_delay)

            # Now do the validation
            changes.append(format_cloud_message("CLOUD: Validating Kubernetes configuration"))
            
            # Client-side validation
            try:
                result = subprocess.run(
                    ['kubectl', 'apply', '--dry-run=client', '-f', self.configs['kubernetes'].path],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=30
                )
                
                for line in result.stdout.split('\n'):
                    formatted = format_kubectl_output(line)
                    if formatted:
                        changes.append(format_cloud_message(formatted))
                        
            except subprocess.TimeoutExpired:
                return ["CLOUD ERROR: Timeout during configuration validation"]
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr if e.stderr else "Unknown error during validation"
                return [f"CLOUD ERROR: {error_msg}"]

            # Only do server-side validation if client-side passes
            if not any("ERROR" in change for change in changes):
                try:
                    result = subprocess.run(
                        ['kubectl', 'apply', '--dry-run=server', '-f', self.configs['kubernetes'].path],
                        capture_output=True,
                        text=True,
                        check=True,
                        timeout=30
                    )
                    
                    for line in result.stdout.split('\n'):
                        formatted = format_kubectl_output(line)
                        if formatted:
                            changes.append(format_cloud_message(formatted))
                            
                except subprocess.TimeoutExpired:
                    return ["CLOUD ERROR: Timeout during server validation"]
                except subprocess.CalledProcessError as e:
                    error_msg = e.stderr if e.stderr else "Unknown error during server validation"
                    return [f"CLOUD ERROR: {error_msg}"]

            if not any("ERROR" in change for change in changes):
                changes.append(format_cloud_message("CLOUD: Kubernetes configuration is valid"))

        except FileNotFoundError:
            return ["CLOUD ERROR: Required tools (minikube or kubectl) not found"]
        except Exception as e:
            return [f"CLOUD ERROR: Unexpected error: {str(e)}"]
        finally:
            try:
                # Don't stop the cluster, just let user know we're keeping it running
                changes.append(format_cloud_message("CLOUD: Keeping Kubernetes cluster running for future operations"))
            except Exception:
                pass

        return changes

    def _get_ansible_plan(self) -> List[str]:
        """Get formatted Ansible plan output using ansible's built-in validation"""
        inventory_path = None  # Define this at the start
        try:
            # Find ansible-playbook and ansible-lint
            ansible_playbook_path = None
            ansible_lint_path = None
            
            # Check common system paths and virtualenv path
            potential_paths = [
                os.path.join(sys.prefix, 'bin', 'ansible-playbook'),  # virtualenv path
                '/usr/local/bin/ansible-playbook',
                '/usr/bin/ansible-playbook', 
                '/opt/homebrew/bin/ansible-playbook'
            ]
            
            for path in potential_paths:
                if os.path.isfile(path):
                    ansible_playbook_path = path
                    break
                    
            if not ansible_playbook_path:
                # Try using which command as fallback
                try:
                    ansible_playbook_path = subprocess.check_output(['which', 'ansible-playbook'], 
                                                                text=True).strip()
                except subprocess.CalledProcessError:
                    return ["CLOUD ERROR: Ansible not installed. Required for server configuration."]
                    
            def format_as_cloud_comment(output_line: str) -> str:
                """Formats ansible output as standardized CLOUD comment"""
                # Strip ANSI color codes
                line = re.sub(r'\x1b\[[0-9;]*m', '', output_line)
                line = line.strip()
                
                if not line:
                    return None
                    
                # Standardize task names
                if "TASK [" in line:
                    task_name = re.search(r'TASK \[(.*?)\]', line)
                    if task_name:
                        return f"CLOUD: Executing {task_name.group(1)}"
                        
                # Standardize changes
                if "changed:" in line:
                    return f"CLOUD: Making change: {line.split('changed:')[1].strip()}"
                    
                # Standardize skipped tasks
                if "skipping:" in line:
                    return f"CLOUD: Skipping: {line.split('skipping:')[1].strip()}"
                    
                # Standardize ok/success messages
                if "ok:" in line or "success" in line.lower():
                    return f"CLOUD: Success: {line.split(':')[1].strip()}"
                    
                # Handle verification outputs
                if "Verify" in line:
                    return f"CLOUD: Verifying: {line}"
                    
                # Handle installation messages
                if "Installing" in line:
                    return f"CLOUD: Installing: {line.split('Installing')[1].strip()}"
                    
                # Handle configuration messages
                if "Configuring" in line:
                    return f"CLOUD: Configuring: {line.split('Configuring')[1].strip()}"
                    
                # Handle errors and warnings
                if "ERROR" in line.upper() or "WARN" in line.upper():
                    return f"CLOUD ERROR: {line}"
                    
                # Debug messages
                if "DEBUG" in line:
                    msg = line.split('DEBUG', 1)[1].strip()
                    # Remove the "msg:" prefix if it exists
                    msg = msg.replace("msg:", "").strip()
                    return f"CLOUD DEBUG: {msg}"
                    
                # Default format for other lines
                return f"CLOUD: {line}"

            changes = []

            # Create temporary inventory file
            inventory_path = os.path.join(self.iac_path, 'inventory.ini')
            with open(inventory_path, 'w') as f:
                f.write("localhost ansible_connection=local\n[all]\nlocalhost")

            # Add a line break before password prompt
            print("\n", flush=True)
            
            # Get sudo password with custom prompt
            sudo_pass = click.prompt('Sudo password',
                                hide_input=True,
                                type=str)

            # Set up environment with sudo password
            env = os.environ.copy()
            env['ANSIBLE_BECOME_PASS'] = sudo_pass
            
            # Run ansible-playbook check
            process = subprocess.Popen(
                [
                    ansible_playbook_path,
                    '--check',
                    '--diff',
                    '-i', inventory_path,
                    self.configs['ansible'].path
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )
            
            # Get the output
            stdout, stderr = process.communicate()
            
            # Process all output and convert to CLOUD format
            if stderr:
                # Process error lines
                for line in stderr.split('\n'):
                    if line.strip() and "Python interpreter" not in line:
                        formatted = format_as_cloud_comment(line)
                        if formatted:
                            changes.append(format_cloud_message(formatted))
            
            if stdout:
                # Process standard output lines
                for line in stdout.split('\n'):
                    # Skip unnecessary lines
                    if any(skip in line for skip in ['PLAY [', 'PLAY RECAP', 'GATHERING FACTS']):
                        continue
                        
                    if line.strip():
                        formatted = format_as_cloud_comment(line)
                        if formatted:
                            changes.append(format_cloud_message(formatted))
            
            # If no changes detected, add a summary
            if not changes:
                changes.append(format_cloud_message("CLOUD: No changes required in configuration"))
            else:
                # Add a summary at the end
                changes.append(format_cloud_message("CLOUD: Configuration validation complete"))
                
            return changes

        except Exception as e:
            return [f"CLOUD ERROR: {str(e)}"]
            
        finally:
            # Clean up temporary inventory file
            if inventory_path and os.path.exists(inventory_path):
                try:
                    os.remove(inventory_path)
                except Exception:
                    pass  # Ignore cleanup errors
    
    def _format_resource_line(self, line: str) -> str:
        """Format a resource line from Terraform plan"""
        parts = line.strip().split(' ')
        if len(parts) >= 3:
            resource_type = parts[1]
            resource_name = parts[2].strip('"')
            return f"{resource_type}.{resource_name}"
        return line.strip()

    def _format_attribute_line(self, line: str) -> str:
        """Format an attribute line from Terraform plan"""
        parts = line.strip().split(' = ')
        if len(parts) >= 2:
            attr_name = parts[0].strip('+ - ~ ')
            attr_value = parts[1]
            return f"{attr_name} = {attr_value}"
        return line.strip()

    def _format_kubernetes_line(self, line: str) -> str:
        """Format a Kubernetes resource line"""
        parts = line.split('/')
        if len(parts) >= 2:
            resource_type = parts[0].strip()
            resource_name = '/'.join(parts[1:]).split(' ')[0]
            return f"{resource_type}/{resource_name}"
        return line.strip()

    def _parse_ansible_stats(self, line: str) -> dict:
        """Parse Ansible stats line"""
        stats = {
            'changed': 0,
            'failed': 0,
            'unreachable': 0
        }
        
        parts = line.split(':')[1].split()
        for part in parts:
            if '=' in part:
                key, value = part.split('=')
                if key in stats:
                    stats[key] = int(value)
        
        return stats

    def apply_terraform(self) -> List[str]:
        """Apply Terraform changes with immediate output"""
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

            # Print initial message
            msg = format_cloud_message("Starting infrastructure deployment")
            print(msg)
            changes.append(msg)
            
            process = subprocess.Popen(
                ['terraform', 'apply', '-auto-approve', '-no-color', '-var-file=terraform.tfvars.json'],
                cwd=self.iac_path,
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
                        'terraform has made some changes',
                        'enter a value']):
                        continue
                    
                    # Remove the word terraform and format
                    line = re.sub(r'terraform\s+', '', line, flags=re.IGNORECASE)
                    
                    if "Apply complete!" in line:
                        stats = re.search(r'(\d+)\s+added,\s+(\d+)\s+changed,\s+(\d+)\s+destroyed', line)
                        if stats:
                            added, changed, destroyed = stats.groups()
                            if int(added) > 0:
                                msg = format_cloud_message(f"Added {added} resources")
                                print(msg)
                                changes.append(msg)
                            if int(changed) > 0:
                                msg = format_cloud_message(f"Modified {changed} resources")
                                print(msg)
                                changes.append(msg)
                            if int(destroyed) > 0:
                                msg = format_cloud_message(f"Removed {destroyed} resources")
                                print(msg)
                                changes.append(msg)
                    elif any(action in line for action in ["Creating", "Modifying", "Destroying"]):
                        msg = format_cloud_message(line)
                        print(msg)
                        changes.append(msg)
                    elif "still creating" in line.lower():
                        msg = format_cloud_message(f"Still creating... {line}")
                        print(msg)
                        changes.append(msg)
                    elif "completed" in line.lower():
                        msg = format_cloud_message(line)
                        print(msg)
                        changes.append(msg)

            # Check for any errors in stderr
            for line in process.stderr.readlines():
                line = line.strip()
                if line:
                    error_msg = re.sub(r'terraform\s+', '', line, flags=re.IGNORECASE)
                    msg = format_cloud_message(f"ERROR: {error_msg}")
                    print(msg)
                    changes.append(msg)

            # Check final process status
            if process.returncode != 0:
                msg = format_cloud_message("ERROR: Infrastructure deployment failed")
                print(msg)
                changes.append(msg)
            else:
                if not any("Added" in change or "Modified" in change or "Removed" in change for change in changes):
                    msg = format_cloud_message("No changes were applied")
                    print(msg)
                    changes.append(msg)
                msg = format_cloud_message("Infrastructure deployment complete")
                print(msg)
                changes.append(msg)
            
            return changes

        except Exception as e:
            error_msg = str(e)
            error_msg = re.sub(r'terraform\s+', '', error_msg, flags=re.IGNORECASE)
            msg = format_cloud_message(f"ERROR: {error_msg}")
            print(msg)
            return [msg]
        finally:
            # Clean up tfvars file
            if tfvars_path and os.path.exists(tfvars_path):
                try:
                    os.remove(tfvars_path)
                except Exception:
                    pass

    def apply_kubernetes(self) -> List[str]:
        """Apply Kubernetes resources with formatted output"""
        changes = []
        
        # First verify if kubectl is installed
        try:
            subprocess.run(['kubectl', 'version', '--client'], 
                        capture_output=True, check=True)
            msg = format_cloud_message("kubectl verification successful")
            print(msg)
            changes.append(msg)
        except (subprocess.CalledProcessError, FileNotFoundError):
            msg = format_cloud_message("ERROR: kubectl not installed")
            print(msg)
            return [msg]
            
        # Check if minikube is installed and running
        try:
            minikube_status = subprocess.run(['minikube', 'status'], 
                                        capture_output=True, text=True)
            if minikube_status.returncode != 0:
                # Start minikube if it's not running
                msg = format_cloud_message("Starting Kubernetes cluster...")
                print(msg)
                changes.append(msg)
                
                process = subprocess.Popen(
                    ['minikube', 'start'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    universal_newlines=True
                )
                
                # Stream minikube start output
                for line in process.stdout:
                    if line.strip():
                        msg = format_cloud_message(line.strip())
                        print(msg)
                        changes.append(msg)
                        
                if process.wait() == 0:
                    msg = format_cloud_message("Kubernetes cluster started successfully")
                    print(msg)
                    changes.append(msg)
                else:
                    msg = format_cloud_message("ERROR: Failed to start Kubernetes cluster")
                    print(msg)
                    return [msg]
                    
        except FileNotFoundError:
            msg = format_cloud_message("ERROR: minikube not installed")
            print(msg)
            return [msg]
                
        try:
            # Do client-side validation first
            msg = format_cloud_message("Validating Kubernetes configuration...")
            print(msg)
            changes.append(msg)
            
            result = subprocess.run(
                ['kubectl', 'apply', '--dry-run=client', '-f', self.configs['kubernetes'].path],
                capture_output=True, text=True, check=True
            )
            msg = format_cloud_message("Client-side validation successful")
            print(msg)
            changes.append(msg)
            
            # Then do server-side validation
            result = subprocess.run(
                ['kubectl', 'apply', '--dry-run=server', '-f', self.configs['kubernetes'].path],
                capture_output=True, text=True, check=True
            )
            msg = format_cloud_message("Server-side validation successful")
            print(msg)
            changes.append(msg)
            
            # Actually apply the resources
            msg = format_cloud_message("Applying Kubernetes resources...")
            print(msg)
            changes.append(msg)
            
            process = subprocess.Popen(
                ['kubectl', 'apply', '-f', self.configs['kubernetes'].path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                universal_newlines=True
            )
            
            # Stream the apply output
            for line in process.stdout:
                if line.strip():
                    if 'created' in line.lower():
                        msg = format_cloud_message(f"Created {line.split()[0]}")
                    elif 'configured' in line.lower():
                        msg = format_cloud_message(f"Updated {line.split()[0]}")
                    elif 'unchanged' in line.lower():
                        msg = format_cloud_message(f"Unchanged {line.split()[0]}")
                    else:
                        msg = format_cloud_message(line.strip())
                    print(msg)
                    changes.append(msg)
            
            if process.wait() != 0:
                error_output = process.stderr.read()
                msg = format_cloud_message(f"ERROR: Failed to apply resources: {error_output}")
                print(msg)
                return [msg]
            
            msg = format_cloud_message("Kubernetes resources deployed successfully")
            print(msg)
            changes.append(msg)
            
            return changes
            
        except subprocess.CalledProcessError as e:
            if "connection refused" in str(e.stderr).lower():
                msg = format_cloud_message("ERROR: Cannot connect to Kubernetes cluster")
                print(msg)
                return [msg]
            msg = format_cloud_message(f"ERROR: {e.stderr}")
            print(msg)
            return [msg]
    
    def apply_ansible(self) -> List[str]:
        """Apply Ansible changes with formatted output"""
        changes = []
        try:
            msg = format_cloud_message("Starting configuration deployment")
            print(msg)
            changes.append(msg)

            # Run ansible-playbook with streaming output
            process = subprocess.Popen(
                ['ansible-playbook', self.configs['ansible'].path],
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
                    # Skip unnecessary lines
                    if any(skip in line for skip in ['PLAY RECAP', 'GATHERING FACTS']):
                        continue
                        
                    # Format special cases
                    if "TASK [" in line:
                        task_name = re.search(r'TASK \[(.*?)\]', line)
                        if task_name:
                            msg = format_cloud_message(f"Running task: {task_name.group(1)}")
                    elif "ok:" in line:
                        msg = format_cloud_message(f"Completed: {line.split('ok:')[1].strip()}")
                    elif "changed:" in line:
                        msg = format_cloud_message(f"Modified: {line.split('changed:')[1].strip()}")
                    elif "skipping:" in line:
                        msg = format_cloud_message(f"Skipped: {line.split('skipping:')[1].strip()}")
                    elif "failed:" in line:
                        msg = format_cloud_message(f"ERROR: {line.split('failed:')[1].strip()}")
                    else:
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

            # Check final status
            if process.returncode == 0:
                msg = format_cloud_message("Configuration deployment completed successfully")
                print(msg)
                changes.append(msg)
                return changes
            else:
                msg = format_cloud_message("ERROR: Configuration deployment failed")
                print(msg)
                changes.append(msg)
                return changes

        except Exception as e:
            msg = format_cloud_message(f"ERROR: {str(e)}")
            print(msg)
            return [msg]
        
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

def format_plan_output(plan_messages: List[str], title: str, color: str) -> str:
    """Format plan output with consistent styling"""
    output = [click.style(f"\n=== {title} ===", fg=color, bold=True)]
    
    for msg in plan_messages:
        if msg.startswith(('➕', '📝', '➖')):
            output.append(click.style(msg, fg=color))
        else:
            output.append(f"  {msg}")
    
    return '\n'.join(output)

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


def parse_terraform_changes(tf_changes: List[str]) -> int:
    """Count actual Terraform plan changes"""
    count = 0
    for line in tf_changes:
        # Count resource changes (create, modify, destroy)
        if line.strip().startswith(('➕ Create:', '📝 Modify:', '➖ Destroy:')):
            count += 1
        # Count errors
        elif line.strip().startswith('Error:'):
            count += 1
    return count

def parse_kubernetes_changes(k8s_changes: List[str]) -> int:
    """Count actual Kubernetes changes"""
    count = 0
    for line in k8s_changes:
        # Count actual resource changes/validations
        if line.strip().startswith(('➕ Create:', '📝 Configure:', '✓ ')):
            count += 1
        # Count errors
        elif line.strip().startswith('Error:'):
            count += 1
    return count

def parse_ansible_changes(ansible_changes: List[str]) -> int:
    """Count actual Ansible changes and errors"""
    count = 0
    in_play_recap = False
    
    for line in ansible_changes:
        line = line.strip()
        # Count failed tasks
        if 'failed:' in line and '[' not in line:  # Avoid counting the play recap line
            count += 1
        # Count errors
        elif line.startswith(('❌', '⚠️')):
            count += 1
        # Count actual changes from check output
        elif line.startswith('changed:'):
            count += 1
    return count

def print_plan_summary(tf_changes: List[str], k8s_changes: List[str], ansible_changes: List[str]):
    """Print a summary of planned changes"""
    tf_count = parse_terraform_changes(tf_changes)
    k8s_count = parse_kubernetes_changes(k8s_changes)
    ansible_count = parse_ansible_changes(ansible_changes)
    total_changes = tf_count + k8s_count + ansible_count
    
    click.echo("\n=== Plan Summary ===")
    click.echo(f"Terraform Changes: {click.style(str(tf_count), fg='blue')}")
    click.echo(f"Kubernetes Changes: {click.style(str(k8s_count), fg='cyan')}")
    click.echo(f"Ansible Changes: {click.style(str(ansible_count), fg='green')}")
    click.echo(f"Total Changes: {click.style(str(total_changes), fg='yellow', bold=True)}")

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
    
@click.group()
def cli():
    """Cloud Infrastructure Management CLI"""
    pass

@cli.command()
@click.argument('cloud-file', type=click.Path(exists=True))
@click.option('--iac-path', default='./IaC', help='Path to generated IAC directory')
def validate(cloud_file, iac_path):
    """Validate .cloud file and generated infrastructure code"""
    click.echo(click.style("\n=== Cloud Configuration Validation ===", fg="blue", bold=True))
    
    orchestrator = CloudOrchestrator(iac_path, cloud_file)
    
    # Collect all validation messages
    messages = []
    
    with click.progressbar(length=4, label='Running validations') as bar:
        # Validate .cloud syntax
        syntax_messages = orchestrator.validate_cloud_syntax()
        messages.extend(syntax_messages)
        bar.update(1)
        
        # Validate Terraform output
        tf_messages = orchestrator.validate_terraform_output()
        messages.extend(tf_messages)
        bar.update(1)
        
        # Validate Kubernetes output
        k8s_messages = orchestrator.validate_kubernetes_output()
        messages.extend(k8s_messages)
        bar.update(1)
        
        # Validate Ansible output
        ansible_messages = orchestrator.validate_ansible_output()
        messages.extend(ansible_messages)
        bar.update(1)
    
    # Group messages by type
    errors = [msg for msg in messages if msg.type == MessageType.ERROR]
    warnings = [msg for msg in messages if msg.type == MessageType.WARNING]
    suggestions = [msg for msg in messages if msg.type == MessageType.SUGGESTION]
    
    # Print results grouped by type
    if errors:
        click.echo("\nCritical Issues:")
        for msg in errors:
            click.echo(format_message(msg))
    
    if warnings:
        click.echo("\nWarnings:")
        for msg in warnings:
            click.echo(format_message(msg))
    
    if suggestions:
        click.echo("\nSuggested Improvements:")
        for msg in suggestions:
            click.echo(format_message(msg))
    
    # Print summary
    print_validation_summary(messages)
    
    return 1 if errors else 0

# @cli.command()
# @click.argument('cloud-file', type=click.Path(exists=True))
# @click.option('--iac-path', default='./IaC', help='Path to generated IAC directory')
# @click.option('--fix', is_flag=True, help='Automatically apply suggested fixes')
# def lint(cloud_file, iac_path, fix):
#     """Lint .cloud file and suggest improvements"""
#     click.echo(click.style("\n=== Cloud Configuration Linting ===", fg="blue", bold=True))
    
#     orchestrator = CloudOrchestrator(iac_path, cloud_file)
#     suggestions = orchestrator.suggest_improvements()
    
#     if not suggestions:
#         click.echo(click.style("\n✓ No improvements suggested - your code looks great!", fg="green"))
#         return 0
    
#     # Group suggestions by type
#     style_suggestions = []
#     security_suggestions = []
#     performance_suggestions = []
#     best_practice_suggestions = []
    
#     for suggestion in suggestions:
#         if "style" in suggestion.message.lower():
#             style_suggestions.append(suggestion)
#         elif any(keyword in suggestion.message.lower() for keyword in ["security", "encryption", "permission"]):
#             security_suggestions.append(suggestion)
#         elif any(keyword in suggestion.message.lower() for keyword in ["performance", "resource", "scaling"]):
#             performance_suggestions.append(suggestion)
#         else:
#             best_practice_suggestions.append(suggestion)
    
#     # Print suggestions by category
#     if security_suggestions:
#         click.echo("\nSecurity Improvements:")
#         for msg in security_suggestions:
#             click.echo(format_message(msg))
    
#     if performance_suggestions:
#         click.echo("\nPerformance Improvements:")
#         for msg in performance_suggestions:
#             click.echo(format_message(msg))
    
#     if style_suggestions:
#         click.echo("\nStyle Improvements:")
#         for msg in style_suggestions:
#             click.echo(format_message(msg))
    
#     if best_practice_suggestions:
#         click.echo("\nBest Practice Improvements:")
#         for msg in best_practice_suggestions:
#             click.echo(format_message(msg))
    
#     if fix:
#         click.echo("\nApplying automatic fixes...")
#         # TODO: Implement automatic fixing
#         click.echo(click.style("Automatic fixing is not yet implemented", fg="yellow"))
    
#     return 0

@cli.command()
@click.argument('cloud-file', type=click.Path(exists=True))
@click.option('--iac-path', default='./IaC', help='Path to generated IAC directory')
def plan(cloud_file, iac_path):
    """Show execution plan for .cloud configuration"""
    click.echo(click.style("\n=== Cloud Infrastructure Plan ===", fg="blue", bold=True))
    
    orchestrator = CloudOrchestrator(iac_path, cloud_file)
    
    # First validate
    messages = orchestrator.validate_cloud_syntax()
    if any(msg.type == MessageType.ERROR for msg in messages):
        click.echo("\nValidation Errors:")
        for msg in messages:
            if msg.type == MessageType.ERROR:
                click.echo(format_message(msg))
        return 1
    
    # Get plans
    with click.progressbar(length=3, label='Generating plans') as bar:
        tf_changes = orchestrator._get_terraform_plan()
        bar.update(1)
        
        k8s_changes = orchestrator._get_kubernetes_plan()
        # k8s_changes = "Random"
        # bar.update(1)
        
        ansible_changes = orchestrator._get_ansible_plan()
        bar.update(1)
    
    # Print plans
    if tf_changes:
        click.echo(format_plan_output(tf_changes, "Terraform Changes", "blue"))
    
    if k8s_changes:
        click.echo(format_plan_output(k8s_changes, "Kubernetes Changes", "cyan"))
    
    if ansible_changes:
        click.echo(format_plan_output(ansible_changes, "Ansible Changes", "green"))
    
    # Print summary
    # print_plan_summary(tf_changes, ansible_changes)
    print_plan_summary(tf_changes, k8s_changes, ansible_changes)
    
    return 0

@cli.command()
@click.argument('cloud-file', type=click.Path(exists=True))
@click.option('--iac-path', default='./IaC', help='Path to generated IAC directory')
@click.option('--auto-approve', is_flag=True, help='Skip interactive approval')
def apply(cloud_file, iac_path, auto_approve):
    """Apply .cloud configuration"""
    click.echo(click.style("\n=== Cloud Infrastructure Apply ===", fg="blue", bold=True))
    
    orchestrator = CloudOrchestrator(iac_path, cloud_file)
    
    # Validate first
    messages = orchestrator.validate_cloud_syntax()
    if any(msg.type == MessageType.ERROR for msg in messages):
        click.echo("\nValidation Errors:")
        for msg in messages:
            if msg.type == MessageType.ERROR:
                click.echo(format_message(msg))
        return 1
    
    # # Show plan
    # tf_changes = orchestrator._get_terraform_plan()
    # k8s_changes = orchestrator._get_kubernetes_plan()
    # ansible_changes = orchestrator._get_ansible_plan()
    
    # click.echo("\nPlanned Changes:")
    # if tf_changes:
    #     click.echo(format_plan_output(tf_changes, "Terraform Changes", "blue"))
    # if k8s_changes:
    #     click.echo(format_plan_output(k8s_changes, "Kubernetes Changes", "cyan"))
    # if ansible_changes:
    #     click.echo(format_plan_output(ansible_changes, "Ansible Changes", "green"))
    
    # print_plan_summary(tf_changes, k8s_changes, ansible_changes)
    
    # Get confirmation
    if not auto_approve:
        click.confirm("\nDo you want to apply these changes?", abort=True)
    
    # Apply changes
    success = True
    with click.progressbar(length=3, label='Applying changes') as bar:
        # Apply Terraform changes
        # if tf_changes:
        if not orchestrator.apply_terraform():
            click.echo(click.style("\n✗ Terraform apply failed!", fg="red"))
            success = False
        bar.update(1)

        # Apply Kubernetes changes
        # if success and k8s_changes:
        if not orchestrator.apply_kubernetes():
            click.echo(click.style("\n✗ Kubernetes apply failed!", fg="red"))
            success = False
        bar.update(1)
        
        # Apply Ansible changes
        # if success and ansible_changes:
        if not orchestrator.apply_ansible():
            click.echo(click.style("\n✗ Ansible apply failed!", fg="red"))
            success = False
        bar.update(1)
        

    if success:
        click.echo(click.style("\n✓ Successfully applied all changes!", fg="green"))
        return 0
    else:
        click.echo(click.style("\n✗ Some changes failed to apply. Review the errors above.", fg="red"))
        return 1

@cli.command()
@click.argument('cloud-file', type=click.Path(exists=True))
@click.option('--iac-path', default='./IaC', help='Path to generated IAC directory')
@click.option('--auto-approve', is_flag=True, help='Skip interactive approval')
def destroy(cloud_file, iac_path, auto_approve):
    """Destroy all infrastructure defined in .cloud file"""
    click.echo(click.style("\n=== Cloud Infrastructure Destruction ===", fg="red", bold=True))
    
    if not auto_approve and not confirm_destruction():
        click.echo("\nDestruction cancelled.")
        return 0
    
    orchestrator = CloudOrchestrator(iac_path, cloud_file)
    
    success = True
    with click.progressbar(length=3, label='Destroying infrastructure') as bar:
        # Destroy Kubernetes resources first
        if 'kubernetes' in orchestrator.configs:
            if not orchestrator.destroy_kubernetes():
                click.echo(click.style("\n✗ Kubernetes destroy failed!", fg="red"))
                success = False
        bar.update(1)
        
        # Run Ansible cleanup if available
        if success and 'ansible' in orchestrator.configs:
            cleanup_path = orchestrator.configs['ansible'].path.replace('.yml', '-cleanup.yml')
            if os.path.exists(cleanup_path):
                try:
                    subprocess.run(['ansible-playbook', cleanup_path], check=True)
                except subprocess.CalledProcessError:
                    click.echo(click.style("\n✗ Ansible cleanup failed!", fg="red"))
                    success = False
        bar.update(1)
        
        # Destroy Terraform resources last
        if success and 'terraform' in orchestrator.configs:
            if not orchestrator.destroy_terraform():
                click.echo(click.style("\n✗ Terraform destroy failed!", fg="red"))
                success = False
        bar.update(1)
    
    if success:
        click.echo(click.style("\n✓ Successfully destroyed all infrastructure!", fg="green"))
        return 0
    else:
        click.echo(click.style("\n✗ Some resources failed to destroy. Review the errors above.", fg="red"))
        return 1
    
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
main.add_command(validate)
# main.add_command(lint)
main.add_command(plan)
main.add_command(apply)
main.add_command(destroy)

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