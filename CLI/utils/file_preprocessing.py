import re
import json
import yaml
from pathlib import Path
from typing import Dict, Any, Union, Optional, Tuple

def find_cloud_file(path: Union[str, Path]) -> Optional[Path]:
    """
    Find a .cloud file in the given path. If path is a file, verify it's a .cloud file.
    Returns the path to the .cloud file or None if not found.
    """
    path = Path(path)
    
    if path.is_file():
        return path if path.suffix == '.cloud' else None
        
    # If it's a directory, look for .cloud files
    cloud_files = list(path.glob('*.cloud'))
    return cloud_files[0] if cloud_files else None

def load_referenced_file(file_path: Path, referenced_filename: str) -> Optional[str]:
    """
    Load and format the content of a referenced file.
    Returns the file content as a properly escaped string.
    """
    try:
        # Look for the referenced file in the same directory as the .cloud file
        referenced_file = file_path.parent / referenced_filename
        
        if not referenced_file.exists():
            print(f"Warning: Referenced file not found: {referenced_filename}")
            return None
            
        # First try to load as JSON
        try:
            with open(referenced_file) as f:
                content = json.load(f)
                # Convert to a JSON string with no extra escaping
                return json.dumps(content)
        except json.JSONDecodeError:
            # If not JSON, read as plain text
            with open(referenced_file) as f:
                content = f.read()
                # Escape special characters and ensure it's a valid string
                escaped_content = json.dumps(content)
                # Remove the outer quotes that json.dumps adds
                return escaped_content[1:-1]
                
    except Exception as e:
        print(f"Warning: Error processing referenced file {referenced_filename}: {str(e)}")
        return None
    
def preprocess_file_references(iac_path: str, cloud_file_path: Path) -> None:
    """
    Preprocess all IaC files to replace ${file("filename")} references with file contents
    """
    iac_dir = Path(iac_path)
    file_pattern = re.compile(r'\$\{file\(\\?"([^"]+)\\?"\)\}')
    
    # Process Terraform JSON files
    for tf_file in iac_dir.glob('*.tf.json'):
        try:
            with open(tf_file) as f:
                content = json.load(f)
            
            # Process the content recursively
            modified_content = process_dict_values(content, file_pattern, cloud_file_path)
            
            # Write back only if changes were made
            if content != modified_content:
                with open(tf_file, 'w') as f:
                    json.dump(modified_content, f, indent=2)
                    
        except Exception as e:
            print(f"Warning: Error processing Terraform file {tf_file}: {str(e)}")
    
    # Process Kubernetes YAML files
    for k8s_file in iac_dir.glob('*.yml'):
        if k8s_file.name == 'playbook.yml':  # Skip Ansible playbook
            continue
            
        try:
            with open(k8s_file) as f:
                content = list(yaml.safe_load_all(f))
            
            # Process each document in the YAML file
            modified_content = [process_dict_values(doc, file_pattern, cloud_file_path) for doc in content]
            
            # Write back only if changes were made
            if content != modified_content:
                with open(k8s_file, 'w') as f:
                    yaml.dump_all(modified_content, f)
                    
        except Exception as e:
            print(f"Warning: Error processing Kubernetes file {k8s_file}: {str(e)}")
    
    # Process Ansible YAML files
    playbook_file = iac_dir / 'playbook.yml'
    if playbook_file.exists():
        try:
            with open(playbook_file) as f:
                content = yaml.safe_load(f)
            
            modified_content = process_dict_values_ansible(content, file_pattern, cloud_file_path)
            
            # Write back only if changes were made
            if content != modified_content:
                with open(playbook_file, 'w') as f:
                    yaml.dump(modified_content, f)
                    
        except Exception as e:
            print(f"Warning: Error processing Ansible file {playbook_file}: {str(e)}")

def process_dict_values(data: Union[Dict, list, str, Any], pattern: re.Pattern, cloud_file_path: Path) -> Union[Dict, list, str, Any]:
    """
    Recursively process dictionary values to replace file references with file contents
    """
    if isinstance(data, dict):
        return {k: process_dict_values(v, pattern, cloud_file_path) for k, v in data.items()}
    elif isinstance(data, list):
        return [process_dict_values(item, pattern, cloud_file_path) for item in data]
    elif isinstance(data, str):
        match = pattern.search(data)
        if match:
            referenced_filename = match.group(1)
            file_content = load_referenced_file(cloud_file_path, referenced_filename)
            if file_content:
                return file_content  # Return the JSON object directly
        return data
    else:
        return data
    
def process_dict_values_ansible(
    data: Union[Dict, list, str, Any],
    pattern: re.Pattern,
    cloud_file_path: Path
) -> Union[Dict, list, str, Any]:
    if isinstance(data, dict):
        return {
            k: process_dict_values_ansible(v, pattern, cloud_file_path)
            for k, v in data.items()
        }
    elif isinstance(data, list):
        return [
            process_dict_values_ansible(item, pattern, cloud_file_path)
            for item in data
        ]
    elif isinstance(data, str):
        match = pattern.search(data)
        if match:
            referenced_filename = match.group(1)
            file_content = load_referenced_file(cloud_file_path, referenced_filename)
            if file_content is not None:
                # Escape double quotes inside the content to prevent YAML parsing issues
                safe_content = file_content.replace('"', '\\"')
                # Wrap in double quotes so the YAML dumper uses a standard double-quoted string
                return f"\"{safe_content}\""
        return data
    else:
        return data