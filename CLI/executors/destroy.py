from typing import List, Dict, Optional, Tuple
from ..error_mapping.error_mappers import *
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
import subprocess
from pathlib import Path
import json
import os
import re

class CloudDestroyExecutor:
    """Handles execution and error mapping for cloud destroy operations"""
    
    def __init__(self, iac_path: str, cloud_file: str, source_mapper):
        self.iac_path = Path(iac_path)
        self.cloud_file = Path(cloud_file)
        self.source_mapper = source_mapper
        self.console = Console()
        
        # Initialize error mapper
        self.tf_mapper = TerraformErrorMapper(source_mapper)
        
    def execute_destroy(self) -> Tuple[List[str], List[CloudError]]:
        """Execute infrastructure destruction"""
        changes = []
        errors = []
        tfvars_path = None

        try:
            # Create tfvars file with default values
            tfvars_content = {
                'aws_region': 'us-west-2',
                'assume_role_arn': ''
            }
            
            tfvars_path = self.iac_path / 'terraform.tfvars.json'
            tfvars_path.write_text(json.dumps(tfvars_content, indent=2))

            # Start destroy with streaming output
            msg = "Starting infrastructure destruction"
            self.console.print(f"[blue]CLOUD:[/blue] {msg}")
            changes.append(msg)
            
            process = subprocess.Popen(
                ['terraform', 'destroy', '-auto-approve', '-no-color', '-var-file=terraform.tfvars.json'],
                cwd=str(self.iac_path),
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
                            msg = f"Destroyed {destroyed} resources"
                            self.console.print(f"[blue]CLOUD:[/blue] {msg}")
                            changes.append(msg)
                    elif any(action in line for action in ["Destroying", "Destroyed"]):
                        msg = line
                        self.console.print(f"[blue]CLOUD:[/blue] {msg}")
                        changes.append(msg)

            # Check for any errors in stderr
            error_output = process.stderr.read()
            if error_output:
                for line in error_output.split('\n'):
                    if line.strip():
                        msg = f"ERROR: {line.strip()}"
                        self.console.print(f"[red]CLOUD ERROR:[/red] {msg}")
                        changes.append(msg)
                        error = self.tf_mapper.map_error(line.strip())
                        if error:
                            errors.append(error)

            if process.returncode == 0:
                msg = "Infrastructure destruction complete"
                self.console.print(f"[blue]CLOUD:[/blue] {msg}")
                changes.append(msg)
            else:
                msg = "ERROR: Infrastructure destruction failed"
                self.console.print(f"[red]CLOUD ERROR:[/red] {msg}")
                changes.append(msg)

        except Exception as e:
            msg = f"ERROR: {str(e)}"
            self.console.print(f"[red]CLOUD ERROR:[/red] {msg}")
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
            # Clean up tfvars file
            if tfvars_path and tfvars_path.exists():
                tfvars_path.unlink()

        return changes, errors