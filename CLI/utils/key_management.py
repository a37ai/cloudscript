from pathlib import Path
import boto3
import os
import stat
import json
from typing import Dict, Tuple
import subprocess
import yaml
import re

class UnsupportedOSError(Exception):
    """Raised when an unsupported OS is detected in the Ansible playbook"""
    pass


class KeyPairManager:
    def __init__(self, iac_path: Path):
        self.iac_path = iac_path
        self.key_dir = iac_path / '.keys'
        self.key_name = 'cloud-cli-key'
        self.private_key_path = self.key_dir / f'{self.key_name}'  # No .pem for GCP
        self.public_key_path = self.key_dir / f'{self.key_name}.pub'
        
    def setup_key_pair(self, region: str, provider: str = 'aws') -> str:
        """Sets up and returns the key pair name to use for cloud instances"""
        # Create key directory if it doesn't exist
        self.key_dir.mkdir(parents=True, exist_ok=True)
        print(f"Created key directory at: {self.key_dir}")
        
        if provider == 'aws':
            return self._setup_aws_key_pair(region)
        elif provider == 'google':
            return self._setup_gcp_key_pair()
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def _setup_gcp_key_pair(self) -> str:
        """Sets up SSH key pair for GCP instances"""
        try:
            # Check if we already have the key pair
            if self.private_key_path.exists() and self.public_key_path.exists():
                print("Found existing GCP SSH key pair")
                return self.key_name

            print(f"Generating new SSH key pair for GCP")
            
            # Generate new SSH key pair using ssh-keygen
            subprocess.run([
                'ssh-keygen',
                '-t', 'rsa',
                '-b', '2048',
                '-f', str(self.private_key_path),
                '-N', ''  # Empty passphrase
            ], check=True)
            
            print("Successfully generated SSH key pair")
            
            # Set correct permissions
            self.private_key_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
            self.public_key_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
            
            print("Set key permissions")
            return self.key_name
            
        except Exception as e:
            print(f"Error in _setup_gcp_key_pair: {str(e)}")
            raise

    def _setup_aws_key_pair(self, region: str) -> str:
        """Sets up and returns the key pair name to use for EC2 instances"""
        # Initialize boto3 EC2 client
        ec2 = boto3.client('ec2', region_name=region)
        print(f"Initialized EC2 client in region: {region}")
        
        try:
            # Check if key pair exists in AWS
            print(f"Checking for existing key pair: {self.key_name}")
            existing_keys = ec2.describe_key_pairs(
                Filters=[{'Name': 'key-name', 'Values': [self.key_name]}]
            )['KeyPairs']
            
            if existing_keys:
                print("Found existing key pair")
                # If key exists in AWS but not locally, we need to recreate it
                if not self.private_key_path.exists():
                    print("Local key not found, recreating key pair")
                    # Delete existing key pair in AWS
                    ec2.delete_key_pair(KeyName=self.key_name)
                    return self._create_new_aws_key_pair(ec2)
                return self.key_name
            else:
                print("No existing key pair found, creating new one")
                # Key doesn't exist in AWS, create new one
                return self._create_new_aws_key_pair(ec2)
                
        except Exception as e:
            print(f"Error in setup_key_pair: {str(e)}")
            raise Exception(f"Failed to setup key pair: {str(e)}")
    
    def _create_new_aws_key_pair(self, ec2_client) -> str:
        """Creates a new AWS key pair and saves the private key"""
        try:
            print(f"Creating new key pair: {self.key_name}")
            # Create new key pair in AWS
            key_pair = ec2_client.create_key_pair(KeyName=self.key_name)
            print("Successfully created key pair in AWS")
            
            # Save private key material
            self.private_key_path.with_suffix('.pem').write_text(key_pair['KeyMaterial'])
            print(f"Saved private key to: {self.private_key_path}")
            
            # Set correct permissions on private key file
            self.private_key_path.with_suffix('.pem').chmod(stat.S_IRUSR | stat.S_IWUSR)
            print("Set private key permissions")
            
            return self.key_name
        except Exception as e:
            print(f"Error in _create_new_aws_key_pair: {str(e)}")
            raise
    
    def get_public_key_content(self) -> str:
        """Returns the content of the public key file"""
        if self.public_key_path.exists():
            return self.public_key_path.read_text().strip()
        raise FileNotFoundError(f"Public key not found at {self.public_key_path}")
    
    def cleanup(self):
        """Removes local key files"""
        for suffix in ['.pem', '', '.pub']:
            key_path = self.private_key_path.with_suffix(suffix)
            if key_path.exists():
                key_path.unlink()
        if self.key_dir.exists():
            self.key_dir.rmdir()

def modify_terraform_config(config: Dict, key_name: str, provider: str = 'aws', os_user: str = 'ubuntu') -> Dict:
    # Deep copy to avoid modifying original
    import copy
    import os
    from pathlib import Path
    new_config = copy.deepcopy(config)
    
    if provider == 'aws':
        key_basename = Path(key_name).stem.replace('.pem', '')

        # AWS logic remains the same
        if 'resource' in new_config:
            for resource_type, resources in new_config['resource'].items():
                if resource_type == 'aws_instance':
                    for instance in resources.values():
                        instance['key_name'] = key_basename
    elif provider == 'google':
        try:
            # Convert key_name to absolute path if it's relative
            key_path = Path(key_name)
            if not key_path.is_absolute():
                key_path = Path.cwd() / key_path
            
            # Get the public key path and content
            public_key_path = key_path.with_suffix('.pub')
            print(f"Looking for public key at: {public_key_path}")

            if not public_key_path.exists():
                raise FileNotFoundError(f"Public key not found at {public_key_path}")
                
            # Read the public key content
            with open(public_key_path, 'r') as f:
                public_key = f.read().strip()
            print(f"Successfully read public key")

            if 'resource' in new_config:
                for resource_type, resources in new_config['resource'].items():
                    if resource_type == 'google_compute_instance':
                        for instance_name, instance in resources.items():
                            print(f"Adding SSH key to instance: {instance.get('name', 'unnamed')}")
                            if 'metadata' not in instance:
                                instance['metadata'] = {}
                            # Add the public key to metadata with correct format
                            instance['metadata']['ssh-keys'] = f"{os_user}:{public_key}"
                            
                            # Add required firewall tags
                            if 'tags' not in instance:
                                instance['tags'] = []
                            if "http-server" not in instance['tags']:
                                instance['tags'].append("http-server")
                            if "https-server" not in instance['tags']:
                                instance['tags'].append("https-server")
                            print(f"Updated instance configuration")
                            
        except Exception as e:
            print(f"Error adding SSH key to instance metadata: {str(e)}")
            print(f"Current working directory: {os.getcwd()}")
            print(f"key_name parameter: {key_name}")
            raise

    return new_config