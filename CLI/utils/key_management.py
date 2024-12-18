from pathlib import Path
import boto3
import os
import stat
import json
from typing import Dict

class KeyPairManager:
    def __init__(self, iac_path: Path):
        self.iac_path = iac_path
        self.key_dir = iac_path / '.keys'
        self.key_name = 'cloud-cli-key'
        self.private_key_path = self.key_dir / f'{self.key_name}.pem'
        
    def setup_key_pair(self, region: str) -> str:
        """Sets up and returns the key pair name to use for EC2 instances"""
        # Create key directory if it doesn't exist
        self.key_dir.mkdir(parents=True, exist_ok=True)
        print(f"Created key directory at: {self.key_dir}")
        
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
                    return self._create_new_key_pair(ec2)
                return self.key_name
            else:
                print("No existing key pair found, creating new one")
                # Key doesn't exist in AWS, create new one
                return self._create_new_key_pair(ec2)
                
        except Exception as e:
            print(f"Error in setup_key_pair: {str(e)}")
            raise Exception(f"Failed to setup key pair: {str(e)}")
    
    def _create_new_key_pair(self, ec2_client) -> str:
        """Creates a new key pair and saves the private key"""
        try:
            print(f"Creating new key pair: {self.key_name}")
            # Create new key pair in AWS
            key_pair = ec2_client.create_key_pair(KeyName=self.key_name)
            print("Successfully created key pair in AWS")
            
            # Save private key material
            self.private_key_path.write_text(key_pair['KeyMaterial'])
            print(f"Saved private key to: {self.private_key_path}")
            
            # Set correct permissions on private key file
            self.private_key_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
            print("Set private key permissions")
            
            return self.key_name
        except Exception as e:
            print(f"Error in _create_new_key_pair: {str(e)}")
            raise
    
    def cleanup(self):
        """Removes local key files"""
        if self.private_key_path.exists():
            self.private_key_path.unlink()
        if self.key_dir.exists():
            self.key_dir.rmdir()


def modify_terraform_config(config: Dict, key_name: str) -> Dict:
    """Modifies terraform config to use the managed key pair"""
    # Deep copy to avoid modifying original
    import copy
    new_config = copy.deepcopy(config)
    
    # Update EC2 instance configurations to use our key pair
    if 'resource' in new_config:
        for resource_type, resources in new_config['resource'].items():
            if resource_type == 'aws_instance':
                for instance in resources.values():
                    instance['key_name'] = key_name
    
    return new_config