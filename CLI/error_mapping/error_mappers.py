from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
import re

class CloudResourceType(Enum):
    VPC = "vpc"
    INSTANCE = "instance"
    CONTAINER = "container"
    CONFIGURATION = "configuration"
    SERVICE = "service"
    NETWORK = "network"
    COMPUTE = "compute"

class CloudErrorSeverity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

@dataclass
class CloudSourceLocation:
    line: int
    column: int
    block_type: str  # 'infrastructure', 'configuration', 'containers'
    resource_type: Optional[CloudResourceType] = None
    resource_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)  # Add this line

@dataclass
class CloudError:
    severity: CloudErrorSeverity
    message: str
    source_location: CloudSourceLocation
    suggestion: Optional[str] = None
    details: Optional[str] = None

class TerraformErrorMapper:
    """Maps Terraform error messages to CloudErrors"""
    
    def __init__(self, source_mapper):
        self.source_mapper = source_mapper

    def _parse_property_error(self, error_msg: str, context: Dict = None) -> Optional[CloudError]:
        """Handle errors related to invalid property names and syntax"""
        # First extract the invalid property and suggestion
        prop_match = re.search(r'"([^"]+)":\s*{', error_msg)
        suggestion_match = re.search(r'No argument or block type is named "[^"]+"\. (Did you mean.+?)\?', error_msg)
        
        if prop_match and suggestion_match:
            invalid_prop = prop_match.group(1)  # e.g., 'tas'
            suggestion = suggestion_match.group(1)  # e.g., 'Did you mean "tags"'
            
            # Look for this property in the .cloud file
            with open(self.source_mapper.cloud_file_path, 'r') as f:
                cloud_lines = f.readlines()
                
            for i, line in enumerate(cloud_lines, 1):
                if invalid_prop in line and any(
                    cloud_lines[j].strip().startswith('network') 
                    for j in range(max(0, i-5), i)
                ):
                    return CloudError(
                        severity=CloudErrorSeverity.ERROR,
                        message=suggestion,  # Use just the suggestion part
                        source_location=CloudSourceLocation(
                            line=i,
                            column=line.index(invalid_prop),
                            block_type='network',
                            block_name='vpc',
                            metadata={
                                'original_line': line.strip(),
                                'invalid_property': invalid_prop
                            }
                        ),
                        suggestion=f"Change '{invalid_prop}' to 'tags' in your configuration"
                    )

        return None
    
    def _parse_instance_error(self, error_msg: str, context: Dict = None) -> Optional[CloudError]:
        """Handle EC2 instance-related errors"""
        if context is None:
            context = {}

        # Get instance name from context if available
        instance_name = context.get('resource_name', 'instance')
        resource_id = f"aws_instance.{instance_name}"

        # Extract parameter name and value from error message
        param_match = re.search(r'expected\s+(\w+)\s+to\s+contain|invalid\s+(\w+):', error_msg)
        if param_match:
            param_name = param_match.group(1) or param_match.group(2)
            
            # Get the specific parameter's location
            location = self.source_mapper.get_param_location(resource_id, param_name)
            if location:
                return CloudError(
                    severity=CloudErrorSeverity.ERROR,
                    message=error_msg.split(f'with {resource_id}')[0].strip(),  # Use exact Terraform error
                    source_location=location,
                    suggestion="Check the parameter value meets AWS requirements"
                )

        # Handle general instance errors without specific parameter
        location = self.source_mapper.get_source_location(resource_id)
        if location:
            return CloudError(
                severity=CloudErrorSeverity.ERROR,
                message=error_msg.split(f'with {resource_id}')[0].strip(),  # Use exact Terraform error
                source_location=location,
                suggestion="Check the instance configuration"
            )

        return None
    
    def _parse_vpc_error(self, error_msg: str, context: Dict = None) -> Optional[CloudError]:
        """Handle VPC-related errors"""
        if context is None:
            context = {}

        # Extract parameter name and value from error message
        param_match = re.search(r'expected\s+(\w+)\s+to\s+contain', error_msg)
        if param_match:
            param_name = param_match.group(1)
            
            # Get the specific parameter's location
            location = self.source_mapper.get_param_location("aws_vpc.vpc", param_name)
            if location:
                return CloudError(
                    severity=CloudErrorSeverity.ERROR,
                    message=error_msg.split('with aws_vpc.vpc')[0].strip(),  # Use exact Terraform error
                    source_location=location,
                    suggestion="Check the parameter value meets AWS requirements"
                )

        # Handle general VPC errors without specific parameter
        location = self.source_mapper.get_source_location("aws_vpc.vpc")
        if location:
            return CloudError(
                severity=CloudErrorSeverity.ERROR,
                message=error_msg.split('with aws_vpc.vpc')[0].strip(),  # Use exact Terraform error
                source_location=location,
                suggestion="Check the VPC configuration"
            )

        return None
    
    def _parse_resource_error(self, error_msg: str, context: Dict = None) -> Optional[CloudError]:
        """Handle general resource configuration errors"""
        line_match = re.search(r'on [^:]+:(\d+)', error_msg)
        if line_match:
            tf_line = line_match.group(1)
            
            # Try to extract resource info
            resource_match = re.search(r'(aws_[a-z_]+)\.([a-z_]+)', error_msg)
            if resource_match:
                tf_resource_type = resource_match.group(1)
                resource_name = resource_match.group(2)
                
                # Map terraform resource type to cloud resource type
                resource_type_map = {
                    'aws_instance': CloudResourceType.COMPUTE,
                    'aws_vpc': CloudResourceType.NETWORK
                }
                
                # Get location from source mapper
                location = self.source_mapper.get_source_location(f"{tf_resource_type}.{resource_name}")
                if location:
                    # Read the original file to get the line content
                    with open(location.file, 'r') as f:
                        lines = f.readlines()
                        line_content = lines[location.line - 1].strip()
                        
                    return CloudError(
                        severity=CloudErrorSeverity.ERROR,
                        message=self._format_error_message(error_msg, tf_resource_type, resource_name),
                        source_location=CloudSourceLocation(
                            line=location.line,
                            column=location.column,
                            block_type='infrastructure',
                            resource_type=resource_type_map.get(tf_resource_type, CloudResourceType.COMPUTE),
                            resource_name=resource_name,
                            metadata={'original_line': line_content}
                        ),
                        suggestion=self._generate_suggestion(error_msg, tf_resource_type)
                    )
        
        return None
    
    def _parse_dependency_error(self, error_msg: str, context: Dict = None) -> Optional[CloudError]:
        """Handle resource dependency errors"""
        if context is None:
            context = {}
            
        if "depends on resource" in error_msg.lower():
            resource_match = re.search(r'resource "([^"]+)".*depends on', error_msg)
            dependency_match = re.search(r'depends on "([^"]+)"', error_msg)
            
            if resource_match and dependency_match:
                resource = resource_match.group(1)
                dependency = dependency_match.group(1)
                
                location = self.source_mapper.get_source_location(resource)
                if location:
                    return CloudError(
                        severity=CloudErrorSeverity.ERROR,
                        message=f"Resource dependency error: {resource} depends on {dependency} which doesn't exist",
                        source_location=CloudSourceLocation(
                            line=location.line,
                            column=location.column,
                            block_type='infrastructure',
                            resource_type=CloudResourceType.COMPUTE,
                            resource_name=resource,
                            metadata={
                                'dependency': dependency,
                                'resource': resource
                            }
                        ),
                        suggestion=f"Ensure {dependency} is defined before {resource} in your .cloud file",
                        details="Resources must be defined before they can be referenced"
                    )
        return None

    def _parse_size_error(self, error_msg: str, context: Dict = None) -> Optional[CloudError]:
        """Handle instance size errors"""
        if context is None:
            context = {}
            
        match = re.search(r'aws_instance\.([^\s]+).*size "([^"]+)"', error_msg)
        if match:
            instance_name, size = match.groups()
            location = self.source_mapper.get_source_location(f"aws_instance.{instance_name}")
            
            if location:
                return CloudError(
                    severity=CloudErrorSeverity.ERROR,
                    message=f"Invalid instance size '{size}' for compute resource '{instance_name}'",
                    source_location=CloudSourceLocation(
                        line=location.line,
                        column=location.column,
                        block_type='infrastructure',
                        resource_type=CloudResourceType.COMPUTE,
                        resource_name=instance_name,
                        metadata={'invalid_size': size}
                    ),
                    suggestion=f"Change size to a valid instance type",
                    details="Common sizes: t2.micro, t2.small, t2.medium"
                )
        return None
    
    def _format_error_message(self, error_msg: str, resource_type: str, resource_name: str) -> str:
        """Format error message to use cloud terminology"""
        msg = error_msg.replace('Error:', '').strip()
        msg = msg.replace('aws_instance', 'compute instance')
        msg = msg.replace('aws_vpc', 'network')
        return msg

    def _generate_suggestion(self, error_msg: str, resource_type: str) -> str:
        """Generate appropriate suggestion based on error type"""
        if resource_type == 'aws_vpc':
            return "Check your network configuration. Ensure CIDR blocks are properly formatted."
        elif resource_type == 'aws_instance':
            if 'instance_type' in error_msg:
                return "Use a valid instance type (e.g., 't2.micro', 't2.small')"
            elif 'subnet' in error_msg:
                return "Ensure the instance is being placed in a valid subnet"
        return "Check the configuration values in your .cloud file"

    def map_error(self, error_msg: str, context: Dict = None) -> Optional[CloudError]:
        """Map a Terraform error message to a CloudError"""
        if context is None:
            context = {}

        # Check for property/syntax errors first
        if "Error: Extraneous JSON object property" in error_msg:
            property_error = self._parse_property_error(error_msg, context)
            if property_error:
                return property_error

        # Check for AWS STS errors with region issues
        if "sts." in error_msg and ".amazonaws.com" in error_msg:
            region_location = self.source_mapper.get_source_location("aws_provider.region")
            if region_location:
                return CloudError(
                    severity=CloudErrorSeverity.ERROR,
                    message=error_msg.split('with provider')[0].strip(),
                    source_location=region_location,
                    suggestion="Check the AWS region format. It should be in the format 'us-west-2', not 'us-west2'"
                )

        # Check for provider configuration errors first
        if "configuring Terraform AWS Provider" in error_msg:
            provider_location = self.source_mapper.get_source_location("aws_provider")
            return CloudError(
                severity=CloudErrorSeverity.ERROR,
                message=error_msg.split('with provider')[0].strip(),
                source_location=provider_location or CloudSourceLocation(
                    line=1, column=1,  # Default to start of file for provider issues
                    block_type='provider',
                    block_name='aws'
                ),
                suggestion="Check your AWS provider configuration, especially the region format"
            )
        
        # Check for provider availability errors
        if "Failed to query available provider packages" in error_msg:
            provider_location = self.source_mapper.get_source_location("aws_provider")
            return CloudError(
                severity=CloudErrorSeverity.ERROR,
                message=error_msg.split('All modules')[0].strip(),
                source_location=provider_location or CloudSourceLocation(
                    line=1, column=1,  # Default to start of file for provider issues
                    block_type='provider',
                    block_name='aws'
                ),
                suggestion="Check your provider name. It should be 'aws' for AWS resources"
            )

        # Extract resource type from error message for resource-specific errors
        resource_type_match = re.search(r'with\s+(aws_\w+)\.(\w+)', error_msg)
        
        if resource_type_match:
            resource_type = resource_type_match.group(1)
            resource_name = resource_type_match.group(2)
            context['resource_name'] = resource_name

            if resource_type == 'aws_vpc':
                return self._parse_vpc_error(error_msg, context)
            elif resource_type == 'aws_instance':
                return self._parse_instance_error(error_msg, context)

        # Only try resource parsers if there's no clear provider error
        if not any(phrase in error_msg for phrase in [
            "provider packages",
            "configuring Terraform AWS Provider",
            "provider registry"
        ]):
            vpc_error = self._parse_vpc_error(error_msg, context)
            if vpc_error:
                return vpc_error
                
            instance_error = self._parse_instance_error(error_msg, context)
            if instance_error:
                return instance_error

        return None

class KubernetesErrorMapper:
    """Maps Kubernetes error messages to CloudErrors"""
    
    def __init__(self, source_mapper):
        self.source_mapper = source_mapper

    def _parse_container_config_error(self, error_msg: str) -> Optional[CloudError]:
        """Handle container configuration errors"""
        if "container configuration" in error_msg.lower():
            match = re.search(r'container/([^\s]+)', error_msg)
            if match:
                container_name = match.group(1)
                location = self.source_mapper.get_source_location(f"container/{container_name}")
                
                if location and location.metadata.get('image'):
                    return CloudError(
                        severity=CloudErrorSeverity.ERROR,
                        message=f"Invalid container configuration for '{container_name}'",
                        source_location=location,
                        suggestion=f"Check image '{location.metadata['image']}' and container settings",
                        details=error_msg
                    )
        return None
    
    def _parse_resource_quota_error(self, error_msg: str) -> Optional[CloudError]:
        """Handle resource quota/limit errors"""
        if any(term in error_msg.lower() for term in ['resource quota', 'exceeded', 'limit']):
            match = re.search(r'(Deployment|StatefulSet|DaemonSet)/([^\s]+)', error_msg)
            if match:
                resource_type = match.group(1)
                resource_name = match.group(2)
                
                location = self.source_mapper.get_source_location(f"container/{resource_name}")
                if location:
                    return CloudError(
                        severity=CloudErrorSeverity.ERROR,
                        message=f"Resource limits exceeded for container '{resource_name}'",
                        source_location=CloudSourceLocation(
                            line=location.line,
                            column=location.column,
                            block_type='containers',
                            resource_type=CloudResourceType.CONTAINER,
                            resource_name=resource_name
                        ),
                        suggestion="Reduce the resource requests/limits in your container configuration",
                        details=f"Original error: {error_msg}"
                    )
        return None

    def _parse_probe_error(self, error_msg: str) -> Optional[CloudError]:
        """Handle probe configuration errors"""
        if 'probe' in error_msg.lower():
            match = re.search(r'(Deployment|StatefulSet|DaemonSet)/([^\s]+)', error_msg)
            if match:
                resource_type = match.group(1)
                resource_name = match.group(2)
                
                location = self.source_mapper.get_source_location(f"container/{resource_name}")
                if location:
                    return CloudError(
                        severity=CloudErrorSeverity.ERROR,
                        message=f"Invalid probe configuration for container '{resource_name}'",
                        source_location=CloudSourceLocation(
                            line=location.line,
                            column=location.column,
                            block_type='containers',
                            resource_type=CloudResourceType.CONTAINER,
                            resource_name=resource_name
                        ),
                        suggestion="Check the health check configuration in your container block",
                        details=f"Original error: {error_msg}"
                    )
        return None

    def _parse_image_error(self, error_msg: str) -> Optional[CloudError]:
        """Handle container image errors"""
        if any(term in error_msg.lower() for term in ['image', 'pull']):
            match = re.search(r'(Deployment|StatefulSet|DaemonSet)/([^\s]+)', error_msg)
            if match:
                resource_type = match.group(1)
                resource_name = match.group(2)
                
                location = self.source_mapper.get_source_location(f"container/{resource_name}")
                if location:
                    return CloudError(
                        severity=CloudErrorSeverity.ERROR,
                        message=f"Container image error for '{resource_name}'",
                        source_location=CloudSourceLocation(
                            line=location.line,
                            column=location.column,
                            block_type='containers',
                            resource_type=CloudResourceType.CONTAINER,
                            resource_name=resource_name
                        ),
                        suggestion="Verify the image name and ensure it's accessible",
                        details=f"Original error: {error_msg}"
                    )
        return None

    def map_error(self, error_msg: str) -> Optional[CloudError]:
        """Map a Kubernetes error message to a CloudError"""
        # Try each error parser in sequence
        error = (self._parse_resource_quota_error(error_msg) or
                self._parse_probe_error(error_msg) or
                self._parse_image_error(error_msg))
        
        return error

class AnsibleErrorMapper:
    """Maps Ansible error messages to CloudErrors"""
    
    def __init__(self, source_mapper):
        self.source_mapper = source_mapper
        
    def _parse_package_dependency_error(self, error_msg: str) -> Optional[CloudError]:
        """Handle package dependency errors"""
        if "dependency" in error_msg.lower():
            match = re.search(r'package ([^\s]+) requires ([^\s]+)', error_msg)
            if match:
                package, dependency = match.groups()
                location = self.source_mapper.get_source_location("configuration/packages")
                
                if location and location.metadata.get('packages'):
                    return CloudError(
                        severity=CloudErrorSeverity.ERROR,
                        message=f"Package '{package}' requires dependency '{dependency}'",
                        source_location=location,
                        suggestion=f"Add '{dependency}' to your packages list",
                        details=f"Current packages: {', '.join(location.metadata['packages'])}"
                    )
        return None
    
    def _parse_package_error(self, error_msg: str) -> Optional[CloudError]:
        """Handle package installation errors"""
        if 'package' in error_msg.lower():
            match = re.search(r'package ([^\s]+)', error_msg)
            if match:
                package_name = match.group(1)
                
                location = self.source_mapper.get_source_location("configuration/main")
                if location:
                    return CloudError(
                        severity=CloudErrorSeverity.ERROR,
                        message=f"Failed to install package '{package_name}'",
                        source_location=CloudSourceLocation(
                            line=location.line,
                            column=location.column,
                            block_type='configuration',
                            resource_type=CloudResourceType.CONFIGURATION
                        ),
                        suggestion=f"Verify package name '{package_name}' is correct and available in the repository",
                        details=f"Original error: {error_msg}"
                    )
        return None

    def _parse_service_error(self, error_msg: str) -> Optional[CloudError]:
        """Handle service-related errors"""
        if 'service' in error_msg.lower():
            match = re.search(r'service ([^\s]+)', error_msg)
            if match:
                service_name = match.group(1)
                
                location = self.source_mapper.get_source_location("configuration/main")
                if location:
                    return CloudError(
                        severity=CloudErrorSeverity.ERROR,
                        message=f"Service operation failed for '{service_name}'",
                        source_location=CloudSourceLocation(
                            line=location.line,
                            column=location.column,
                            block_type='configuration',
                            resource_type=CloudResourceType.SERVICE
                        ),
                        suggestion=f"Check if service '{service_name}' is properly configured",
                        details=f"Original error: {error_msg}"
                    )
        return None

    def _parse_file_error(self, error_msg: str) -> Optional[CloudError]:
        """Handle file operation errors"""
        if any(term in error_msg.lower() for term in ['file', 'directory', 'permission']):
            match = re.search(r'path: ([^\s]+)', error_msg)
            if match:
                file_path = match.group(1)
                
                location = self.source_mapper.get_source_location("configuration/main")
                if location:
                    return CloudError(
                        severity=CloudErrorSeverity.ERROR,
                        message=f"File operation failed for '{file_path}'",
                        source_location=CloudSourceLocation(
                            line=location.line,
                            column=location.column,
                            block_type='configuration',
                            resource_type=CloudResourceType.CONFIGURATION
                        ),
                        suggestion="Check file paths and permissions in your configuration block",
                        details=f"Original error: {error_msg}"
                    )
        return None

    def map_error(self, error_msg: str) -> Optional[CloudError]:
        """Map an Ansible error message to a CloudError"""
        # Try each error parser in sequence
        error = (self._parse_package_error(error_msg) or
                self._parse_service_error(error_msg) or
                self._parse_file_error(error_msg))
        
        return error