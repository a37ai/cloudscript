from typing import List, Dict, Optional, Tuple
from ..error_mapping.error_mappers import *
from ..utils.key_management import KeyPairManager
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
        self.key_manager = KeyPairManager(self.iac_path)
        
        # Initialize error mapper
        self.tf_mapper = TerraformErrorMapper(source_mapper)
    
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
    
    def execute_destroy(self) -> Tuple[List[str], List[CloudError]]:
        """Execute infrastructure destruction"""
        changes = []
        errors = []
        tfvars_path = None

        try:
            # Read original terraform config to get provider info
            terraform_config_path = self.iac_path / 'main.tf.json'
            with open(terraform_config_path) as f:
                terraform_config = json.load(f)
                
            # Get provider info
            provider_type, region = self.get_provider_info(terraform_config)

            # Start destroy with streaming output
            msg = "Starting infrastructure destruction"
            self.console.print(f"[blue]CLOUD:[/blue] {msg}")
            changes.append(msg)
        
            # Create process with both stdout and stderr pipes
            process = subprocess.Popen(
                ['terraform', 'destroy', '-auto-approve'],
                cwd=str(self.iac_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,  # Line buffered
                text=True,
                universal_newlines=True
            )

            # Use separate threads to read stdout and stderr simultaneously
            from threading import Thread
            from queue import Queue, Empty

            def enqueue_output(out, queue):
                for line in iter(out.readline, ''):
                    queue.put(line)
                out.close()

            # Create queues for stdout and stderr
            stdout_q = Queue()
            stderr_q = Queue()

            # Start threads to read outputs
            stdout_thread = Thread(target=enqueue_output, args=(process.stdout, stdout_q))
            stderr_thread = Thread(target=enqueue_output, args=(process.stderr, stderr_q))
            stdout_thread.daemon = True
            stderr_thread.daemon = True
            stdout_thread.start()
            stderr_thread.start()

            # Process output from both streams
            while process.poll() is None:
                # Check stdout
                try:
                    while True:
                        line = stdout_q.get_nowait().strip()
                        if line:
                            # Skip noisy lines but keep important progress information
                            if not any(skip in line.lower() for skip in [
                                'terraform used provider',
                                'enter a value'
                            ]):
                                # Print all terraform plan/apply output
                                if any(key in line.lower() for key in [
                                    'destroying...',
                                    'destroyed',
                                    'plan:',
                                    'changes:',
                                    'destroy complete!'
                                ]):
                                    self.console.print(f"[blue]CLOUD:[/blue] {line}")
                                    changes.append(line)
                                else:
                                    # Print other relevant output without formatting
                                    print(line)
                except Empty:
                    pass

                # Check stderr
                try:
                    while True:
                        line = stderr_q.get_nowait().strip()
                        if line:
                            msg = f"ERROR: {line}"
                            self.console.print(f"[red]CLOUD ERROR:[/red] {msg}")
                            changes.append(msg)
                            error = self.tf_mapper.map_error(line)
                            if error:
                                errors.append(error)
                except Empty:
                    pass

            # Process remaining output after completion
            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)

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