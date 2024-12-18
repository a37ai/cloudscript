from .data_and_types import Service, IaCGenerator
from typing import List, Dict, Any, Union, Tuple
from .data_and_types import *
import yaml
import re

class AnsibleGenerator(IaCGenerator):
    def generate(self, services: List[Service]) -> str:
        """
        Generates a single comprehensive Ansible playbook with tasks grouped in blocks.
        """
        playbook = []
        inventory = {'all': {'hosts': {}}}

        for service in services:
            play = self._create_play(service)
            if play['tasks'] or play.get('pre_tasks') or play.get('post_tasks'):
                playbook.append(play)

            # Update inventory
            self._update_inventory(service, inventory)

        self._remove_group_keys(playbook)

        # Write inventory file
        with open('IaCnew/inventory.yml', 'w') as f:
            yaml.dump(inventory, f, sort_keys=False)

        return yaml.dump(playbook, sort_keys=False)

    # def generate(self, services: List[Service]) -> str:
    #     """
    #     Generates a single comprehensive Ansible playbook with tasks grouped in blocks.
    #     Writes a hard-coded inventory.yml file.
    #     """
    #     playbook = []

    #     for service in services:
    #         play = self._create_play(service)
    #         if play['tasks'] or play.get('pre_tasks') or play.get('post_tasks'):
    #             playbook.append(play)

    #     self._remove_group_keys(playbook)

    #     # Write hardcoded inventory file
    #     hardcoded_inventory = {
    #         'all': {
    #             'children': {
    #                 'web_servers': {
    #                     'hosts': {
    #                         'web_server_hosts': {
    #                             'ansible_host': '{{ host_ip }}',
    #                             'ansible_ssh_common_args': '-o StrictHostKeyChecking=no',
    #                             'ansible_ssh_private_key_file': '{{ ssh_key_path }}',
    #                             'ansible_user': 'ubuntu'
    #                         }
    #                     }
    #                 }
    #             },
    #             'hosts': {}
    #         }
    #     }

    #     with open('IaC/inventory.yml', 'w') as f:
    #         yaml.dump(hardcoded_inventory, f, sort_keys=False)

    #     return yaml.dump(playbook, sort_keys=False)

    def _create_play(self, service: Service) -> Dict[str, Any]:
        """Creates a play for a service with tasks organized in blocks."""
        play = {
            'name': f"Configure {service.name}",
            'hosts': "{{ target_servers | default('all') }}",
            'become': True,
            'tasks': [],
            'handlers': [],
            'vars': {
                'target_web_servers': "web_servers",
                'target_db_servers': "db_servers"
            }
        }

        if service.configuration:
            # Merge with existing vars if any
            if service.configuration.variables:
                play['vars'].update(service.configuration.variables)

            tasks, handlers = self._process_configuration_tasks(service.configuration)
            ordered_tasks = self._order_tasks(tasks, service.configuration.task_order)
            play['tasks'].extend(ordered_tasks)
            play['handlers'].extend(handlers)

        return play
    
    def _order_tasks(self, tasks: List[Tuple[str, Dict[str, Any]]], task_order: List[str]) -> List[Dict[str, Any]]:
        grouped_tasks = {group: [] for group in task_order}
        other_tasks = []

        for group, task in tasks:
            if group in grouped_tasks:
                grouped_tasks[group].append(task)
            else:
                other_tasks.append(task)

        ordered_tasks = []
        for group in task_order:
            if grouped_tasks[group]:
                block = {
                    'name': f"{group.replace('_', ' ').capitalize()} tasks",
                    'block': grouped_tasks[group]
                }
                ordered_tasks.append(block)

        if other_tasks:
            block = {
                'name': 'Other tasks',
                'block': other_tasks
            }
            ordered_tasks.append(block)

        return ordered_tasks

    def _process_configuration_tasks(self, config: ConfigurationSpec) -> List[Tuple[str, Dict[str, Any]]]:
        """Process all tasks and retain their groups."""
        tasks = []
        handlers = []

        # Add package installation task
        if config.packages:
            package_task = {
                'name': 'Install required packages',
                'package': {
                    'name': '{{ item }}',
                    'state': 'present',
                    'update_cache': True
                },
                'loop': config.packages,
                'check_mode': False
            }
            tasks.append(('packages', package_task))

        # Process files
        for file_path, content in config.files.items():
            file_task = self._create_file_task(file_path, content)
            group = file_task.get('group', 'other')
            tasks.append((group, file_task))

            # Collect handlers if notify is present
            if 'notify' in file_task:
                for handler_name in file_task['notify']:
                    handler_task = {
                        'name': handler_name,
                        'service': {
                            'name': handler_name.split()[-1],
                            'state': 'restarted'
                        },
                        'listen': handler_name
                    }
                    handlers.append(handler_task)

        # Process services
        for service_name, actions in config.services.items():
            service_tasks = self._create_service_tasks(service_name, actions)
            for task in service_tasks:
                group = task.get('group', 'other')
                tasks.append((group, task))

        # Process tasks
        for task in config.tasks:
            processed_task = self._process_task(task)
            group = processed_task.get('group', 'other')
            tasks.append((group, processed_task))

        # Process verifications
        for verification in config.verifications:
            verify_tasks = self._create_verification_tasks(verification)
            for verify_task in verify_tasks:
                group = verify_task.get('group', 'other')
                tasks.append((group, verify_task))

        # Process commands
        for command in config.commands:
            command_task = self._create_command_task(command)
            group = command_task.get('group', 'other')
            tasks.append((group, command_task))

        # print(f"Adding task '{task['name']}' to group '{group}'")
        # tasks.append((group, task))
        return tasks, handlers
   
    def _process_block(self, block: Dict[str, Any]) -> Dict[str, Any]:
        """Process block structures properly."""
        processed_block = {
            'name': block['name']
        }
        
        if 'tasks' in block:
            processed_block['block'] = [self._process_task(task) for task in block['tasks']]
        
        if 'rescue' in block:
            processed_block['rescue'] = [self._process_task(task) for task in block['rescue']]
        
        if 'always' in block:
            processed_block['always'] = [self._process_task(task) for task in block['always']]
            
        return processed_block
    
    def _process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single task."""
        processed_task = {
            'name': task.get('name', 'Execute task')
        }

        # Handle module and args
        for key, value in task.items():
            if key != 'name':
                processed_task[key] = value

        return processed_task

    def _process_blocks(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process block structures with error handling."""
        processed_blocks = []
        
        for block in blocks:
            processed_block = {
                'name': block['name'],
                'block': [],
                'rescue': [],
                'always': []
            }

            # Process main tasks
            if 'tasks' in block:
                for task in block['tasks']:
                    processed_task = self._process_task(task)
                    # Add block-specific conditions for database tasks
                    if 'mysql' in str(task).lower():
                        processed_task['when'] = ["inventory_hostname in groups['db_servers']"]
                    processed_block['block'].append(processed_task)

            # Process rescue tasks
            if 'rescue' in block:
                for task in block['rescue']:
                    processed_task = self._process_task(task)
                    processed_block['rescue'].append(processed_task)

            # Process always tasks
            if 'always' in block:
                for task in block['always']:
                    processed_task = self._process_task(task)
                    processed_block['always'].append(processed_task)

            processed_blocks.append(processed_block)

        return processed_blocks

    def _process_handlers(self, handlers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process handlers with listen directives."""
        processed_handlers = []
        
        for handler in handlers:
            processed_handler = self._process_task(handler)
            if 'listen' in handler:
                processed_handler['listen'] = handler['listen']
            processed_handlers.append(processed_handler)

        return processed_handlers

    def _process_include_vars(self, include_vars: Dict[str, Any]) -> Dict[str, Any]:
        """Process dynamic variable inclusion."""
        return {
            'name': 'Include variables',
            'include_vars': include_vars['file'],
            'when': include_vars.get('when')
        }

    def _create_file_task(self, file_path: str, content: Any) -> Dict[str, Any]:
        """Create a file task without hard-coded values."""
        task = {
            'name': f'Create/modify {file_path}',
            'copy': {
                'dest': file_path
            }
        }
        if isinstance(content, dict):
            copy_params = task['copy']
            for key in ['content', 'template']:
                if key in content:
                    copy_params[key] = content[key]
            for param in ['mode', 'owner', 'group']:
                if param in content:
                    copy_params[param] = content[param]
            if 'notify' in content:
                task['notify'] = content['notify']
            if 'when' in content:
                task['when'] = content['when']
            if 'task_group' in content:
                task['group'] = content['task_group']
        else:
            task['copy']['content'] = str(content)
        return task

    def _create_service_tasks(self, service_name: str, actions: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Create Ansible service tasks based on the service actions defined in the HCL input.

        Args:
            service_name (str): The name of the service to configure.
            actions (Dict[str, Any]): A dictionary containing actions and attributes for the service.

        Returns:
            List[Dict[str, Any]]: A list of Ansible task dictionaries.
        """
        tasks = []

        # Extract the task group for grouping tasks in Ansible playbook
        group = actions.get('task_group', 'other')

        # Extract any conditional 'when' statements
        when = actions.get('when')

        # Extract the 'state' list which defines desired states for the service
        state_list = actions.get('state', [])

        # Normalize state_list to be a list
        if isinstance(state_list, str):
            state_list = [state_list]
        elif not isinstance(state_list, list):
            state_list = []

        # Handle 'enabled' and 'disabled' states separately
        enabled = None
        if 'enabled' in state_list:
            enabled = 'yes'
            state_list.remove('enabled')
        elif 'disabled' in state_list:
            enabled = 'no'
            state_list.remove('disabled')

        # Create tasks for each state in state_list
        for state in state_list:
            register_name = f"{service_name}_{state}_result"
            task = {
                'name': f"Ensure {service_name} is {state}",
                'service': {
                    'name': service_name,
                    'state': state
                },
                'register': register_name,
                'retries': 3,
                'delay': 5,
                'failed_when': f"{register_name} is failed",
                'changed_when': f"{register_name} is changed",
            }

            # Add 'enabled' parameter if applicable
            if enabled is not None:
                task['service']['enabled'] = enabled

            # Add 'when' condition if specified
            if when:
                task['when'] = when

            # Assign the group for task ordering
            task['group'] = group

            # Append the task to the tasks list
            tasks.append(task)

        # If only 'enabled' or 'disabled' is specified without any state
        if enabled is not None and not state_list:
            register_name = f"{service_name}_enabled_result"
            task = {
                'name': f"Ensure {service_name} is {'enabled' if enabled == 'yes' else 'disabled'}",
                'service': {
                    'name': service_name,
                    'enabled': enabled
                },
                'register': register_name,
                'retries': 3,
                'delay': 5,
                'failed_when': f"{register_name} is failed",
                'changed_when': f"{register_name} is changed",
            }

            # Add 'when' condition if specified
            if when:
                task['when'] = when

            # Assign the group for task ordering
            task['group'] = group

            # Append the task to the tasks list
            tasks.append(task)

        return tasks

    def _create_command_task(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Create a command task with better error handling."""
        task = {
            'name': command.get('name', 'Run command'),
            'command': command['command'],
            'register': 'command_result',
            'changed_when': command.get('changed_when', False),  # Most commands don't change state
            'failed_when': command.get('failed_when', 'command_result.rc != 0'),
            'ignore_errors': command.get('ignore_errors', False)
        }
        
        if 'environment' in command:
            task['environment'] = command['environment']
        if 'when' in command:
            task['when'] = command['when']
        if 'retries' in command:
            task.update({
                'retries': command['retries'],
                'delay': command.get('delay', 5),
                'until': command.get('until', 'command_result.rc == 0')
            })
        
        return task

    def _create_verification_tasks(self, verification: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create verification tasks."""
        tasks = []
        name = verification.get('name', 'Verify something').replace('Check ', '')

        # Determine register_name
        if 'register' in verification:
            register_name = verification['register']
        else:
            # Try to extract variable name from 'until' condition
            until = verification.get('until', '')
            # Simple parsing to extract variable name before '.'
            if until:
                until_variable = until.split('.')[0]
                register_name = until_variable
            else:
                # Default register name
                register_name = f"{name.lower().replace(' ', '_').replace('-', '_').replace('.', '_')}_result"

        module_name = verification.get('module', 'command')
        module_params = {}
        # Exclude keys that are not module parameters
        exclude_keys = ['name', 'module', 'retries', 'delay', 'until', 'group', 'failed_when', 'changed_when', 'register']
        for key, value in verification.items():
            if key not in exclude_keys:
                module_params[key] = value

        verification_task = {
            'name': f"Verify {name}",
            module_name: module_params,
            'register': register_name,
            'failed_when': verification.get('failed_when'),
            'changed_when': verification.get('changed_when', False),
            'retries': verification.get('retries', 1),
            'delay': verification.get('delay', 5),
            'until': verification.get('until'),
        }

        # Remove None values from the task
        verification_task = {k: v for k, v in verification_task.items() if v is not None}

        # Assign group
        group = verification.get('group', 'other')
        verification_task['group'] = group

        tasks.append(verification_task)
        return tasks

    def _update_inventory(self, service: Service, inventory: Dict[str, Any]):
        """Update inventory with service hosts and proper grouping."""
        if 'children' not in inventory['all']:
            inventory['all']['children'] = {}

        for component in service.infrastructure:
            if component.component_type == "compute":
                host_group = f"{component.name}_hosts"
                
                # Determine server type and create appropriate group
                server_type = 'web_servers' if 'web' in component.name else 'db_servers'
                if server_type not in inventory['all']['children']:
                    inventory['all']['children'][server_type] = {'hosts': {}}
                
                # Add host to appropriate group
                inventory['all']['children'][server_type]['hosts'][host_group] = {
                    'ansible_host': component.attributes.get('public_ip', '127.0.0.1'),
                    'ansible_user': component.attributes.get('ssh_user', 'ubuntu'),
                    'ansible_ssh_private_key_file': component.attributes.get('ssh_key_file', ''),
                    'ansible_ssh_common_args': '-o StrictHostKeyChecking=no'
                }

    def _create_retried_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Create a task with retry logic and consistent register names."""
        register_name = f"{task['name'].lower().replace(' ', '_')}_result"
        
        processed_task = {
            'name': task['name'],
            'command': task['command'],
            'register': register_name
        }
        
        if 'retries' in task:
            processed_task.update({
                'retries': task['retries'],
                'delay': task.get('delay', 5),
                'until': f"{register_name} is success"
            })
        
        # Add other task attributes
        for key in ['when', 'delegate_to', 'run_once', 'environment']:
            if key in task:
                processed_task[key] = task[key]
                
        return processed_task
    
    def _create_mysql_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Create MySQL-related tasks with proper conditions."""
        processed_task = {
            'name': task['name'],
            'mysql_db': task.get('mysql_db', {}),
            'when': "inventory_hostname in groups['db_servers']"
        }
        
        if 'state' in task.get('mysql_db', {}):
            if task['mysql_db']['state'] == 'dump':
                processed_task['delegate_to'] = task.get('delegate_to', 'localhost')
                processed_task['register'] = 'mysql_backup_result'
                processed_task['failed_when'] = 'mysql_backup_result.failed'
        
        return processed_task
    
    def _remove_group_keys(self, playbook: List[Dict[str, Any]]) -> None:
        """Recursively remove 'group' keys from tasks in the playbook."""
        for play in playbook:
            self._remove_group_keys_from_tasks(play.get('tasks', []))
            self._remove_group_keys_from_tasks(play.get('pre_tasks', []))
            self._remove_group_keys_from_tasks(play.get('post_tasks', []))
            self._remove_group_keys_from_tasks(play.get('handlers', []))

    def _remove_group_keys_from_tasks(self, tasks: List[Dict[str, Any]]) -> None:
        """Helper function to remove 'group' keys from a list of tasks."""
        for task in tasks:
            if 'group' in task:
                del task['group']
            # Recursively remove 'group' from nested tasks in blocks
            if 'block' in task:
                self._remove_group_keys_from_tasks(task['block'])
            if 'rescue' in task:
                self._remove_group_keys_from_tasks(task['rescue'])
            if 'always' in task:
                self._remove_group_keys_from_tasks(task['always'])

class NewAnsibleGenerator(IaCGenerator):
    def generate(self, services: List[Any]) -> str:
        playbook = []
        print("Starting playbook generation...")

        for service_index, service in enumerate(services):
            print(f"\nProcessing service {service_index + 1}/{len(services)}: {service}")
            
            if not service.configuration:
                print("  - No configuration found for this service. Skipping.")
                continue

            config_data = getattr(service.configuration, 'configuration', [])
            print(f"  - Retrieved configuration data: {config_data}")
            
            if not config_data:
                print("  - Configuration data is empty. Skipping.")
                continue

            for config_block_index, config_block in enumerate(config_data):
                print(f"  - Processing config block {config_block_index + 1}/{len(config_data)}: {config_block}")
                
                if 'play' not in config_block:
                    print("    - 'play' key not found in config block. Skipping.")
                    continue

                for play_block_index, play_block in enumerate(config_block['play']):
                    print(f"    - Processing play block {play_block_index + 1}/{len(config_block['play'])}: {play_block}")
                    
                    for play_id, play_config in play_block.items():
                        print(f"      - Processing play '{play_id}': {play_config}")
                        
                        play = self._process_play(play_config)
                        if play:
                            print(f"        - Generated play: {play}")
                            playbook.append(play)
                        else:
                            print("        - Play processing returned None. Skipping.")

        print("\nPlaybook generation completed.")
        self._format_file_references(playbook)
        print("Generated playbook structure:")
        print(yaml.dump(playbook, sort_keys=False, indent=2, default_flow_style=False))

        playbook_yaml = yaml.dump(playbook, sort_keys=False, indent=2, default_flow_style=False)

        inventory_generator = InventoryFromPlaybook()
        inventory = inventory_generator.generate_inventory(playbook)

        with open('IaC/inventory.yml', 'w') as f:
            yaml.dump(inventory, f, sort_keys=False)
        
        return playbook_yaml

    def _process_play(self, play_config: Dict[str, Any]) -> Dict[str, Any]:
        print(f"    Processing play configuration: {play_config}")
        
        play = {
            'name': play_config.get('name', 'Unnamed play'),
            'hosts': play_config.get('hosts', 'all'),
            'become': play_config.get('become', False)
        }
        print(f"      - Initialized play with name='{play['name']}', hosts='{play['hosts']}', become={play['become']}")

        # Process vars
        if 'vars' in play_config:
            play['vars'] = play_config['vars']
            print(f"      - Added vars: {play['vars']}")

        # Process tasks sections
        tasks = []
        for section in ['pre_task', 'task', 'post_task']:
            print(f"      - Processing section: {section}")
            section_tasks = self._process_tasks_section(play_config.get(section, []))
            print(f"        - Tasks in section '{section}': {section_tasks}")
            if section_tasks:
                if section == 'task':
                    tasks.extend(section_tasks)
                    print(f"        - Extended 'tasks' with section '{section}' tasks.")
                else:
                    play[f'{section}s'] = section_tasks
                    print(f"        - Added '{section}s' to play: {section_tasks}")

        # Process handlers
        handlers = self._process_handlers(play_config.get('handler', []))
        print(f"      - Processed handlers: {handlers}")
        if handlers:
            play['handlers'] = handlers
            print("        - Added handlers to play.")

        if tasks:
            play['tasks'] = tasks
            print("        - Added tasks to play.")

        print(f"      - Final play structure: {play}")
        return play

    def _process_tasks_section(self, tasks_config: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        print(f"        Processing tasks section: {tasks_config}")
        processed_tasks = []
        for task_index, task_dict in enumerate(tasks_config):
            print(f"          - Processing task {task_index + 1}/{len(tasks_config)}: {task_dict}")
            
            if 'block' in task_dict:
                print("            - Task contains a 'block'. Processing block.")
                block = self._process_block(task_dict)
                if block:
                    print(f"              - Processed block: {block}")
                    processed_tasks.append(block)
                else:
                    print("              - Block processing returned None. Skipping.")
            else:
                print("            - Task does not contain a 'block'. Processing single task.")
                task = self._process_task(task_dict)
                if task:
                    print(f"              - Processed task: {task}")
                    processed_tasks.append(task)
                else:
                    print("              - Task processing returned None. Skipping.")
        print(f"        Completed processing tasks section. Processed tasks: {processed_tasks}")
        return processed_tasks

    def _process_task(self, task_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        print(f"              Processing single task: {task_config}")
        
        if not task_config:
            print("                - Empty task configuration. Returning None.")
            return None

        task = {'name': task_config.get('name', 'Unnamed task')}
        print(f"                - Initialized task with name='{task['name']}'")

        # Process module and parameters
        for key, value in task_config.items():
            if key not in ['name', 'when', 'register', 'notify', 'ignore_errors', 
                          'changed_when', 'failed_when', 'retries', 'delay', 'loop']:
                print(f"                - Processing module/key: {key} with value: {value}")
                # Handle cases where the module is represented as a list
                if isinstance(value, list):
                    if len(value) == 1 and isinstance(value[0], dict):
                        task[key] = value[0]
                        print(f"                  - Assigned module '{key}' as a single dictionary.")
                    else:
                        task[key] = value
                        print(f"                  - Assigned module '{key}' as a list.")
                else:
                    task[key] = value

        # Add task attributes
        for attr in ['when', 'register', 'notify', 'ignore_errors', 'changed_when', 
                     'failed_when', 'retries', 'delay', 'loop']:
            if attr in task_config:
                print(f"                - Adding attribute '{attr}' with value: {task_config[attr]}")
                task[attr] = task_config[attr]

        print(f"                - Final task structure: {task}")
        return task

    def _process_block(self, block_config: Dict[str, Any]) -> Dict[str, Any]:
        print(f"              Processing block: {block_config}")
        
        block = {'name': block_config.get('name', 'Unnamed block')}
        print(f"                - Initialized block with name='{block['name']}'")

        # Correctly process 'block' within the block
        if 'block' in block_config:
            print("                - Processing 'block' within the block.")
            # Assuming block_config['block'] is a list of dicts with 'task' keys
            tasks_in_block = []
            for blk in block_config['block']:
                if 'task' in blk:
                    print(f"                  - Extracting tasks from: {blk['task']}")
                    tasks_in_block.extend(blk['task'])
            print(f"                - Extracted tasks from 'block': {tasks_in_block}")
            block['block'] = self._process_tasks_section(tasks_in_block)
            print(f"                - Added 'block' to block: {block['block']}")

        # Process rescue and always sections if present
        for section in ['rescue', 'always']:
            if section in block_config:
                print(f"                - Processing section '{section}' within the block.")
                section_tasks = self._process_tasks_section(block_config[section])
                block[section] = section_tasks
                print(f"                - Added '{section}' to block: {section_tasks}")

        print(f"                - Final block structure: {block}")
        return block

    def _process_handlers(self, handlers_config: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        print(f"      - Processing handlers: {handlers_config}")
        processed_handlers = []
        for handler_index, handler_dict in enumerate(handlers_config):
            print(f"        - Processing handler {handler_index + 1}/{len(handlers_config)}: {handler_dict}")
            
            handler = self._process_task(handler_dict)
            if handler:
                print(f"          - Processed handler: {handler}")
                # Add 'listen' key without removing the 'name'
                handler['listen'] = handler['name']
                print(f"            - Added 'listen': {handler['listen']}")
                processed_handlers.append(handler)
            else:
                print("          - Handler processing returned None. Skipping.")
        
        print(f"      - Completed processing handlers. Processed handlers: {processed_handlers}")
        return processed_handlers
    
    def _format_file_references(self, data):
        """Recursively format file() references in the playbook."""
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str) and "file(" in value:
                    # Replace file("something") with "${file(\"something\")}"
                    file_match = re.search(r'file\("([^"]+)"\)', value)
                    if file_match:
                        # Format without extra quotes - YAML dumper will add the outer quotes
                        data[key] = '${file("nginx.conf")}'
                else:
                    self._format_file_references(value)
        elif isinstance(data, list):
            for item in data:
                self._format_file_references(item)

class InventoryFromPlaybook:
    def generate_inventory(self, playbook: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate inventory structure based on playbook analysis"""
        inventory = {
            'all': {
                'hosts': {},
                'children': {}
            }
        }
        groups = set()
        # Analyze playbook to find all group references
        for play in playbook:
            self._analyze_play(play, groups)
            
        # Create the groups and add default host configurations
        for group in groups:
            if 'web' in group.lower():
                inventory['all']['children'][group] = {
                    'hosts': {
                        f"{group.lower().replace('_servers', '')}_server_hosts": {
                            'ansible_host': '{{ host_ip }}',
                            'ansible_user': 'ubuntu',
                            'ansible_ssh_common_args': '-o StrictHostKeyChecking=no',
                            'ansible_ssh_private_key_file': '{{ ssh_key_path }}'
                        }
                    }
                }
        return inventory

    def _analyze_play(self, play: Dict[str, Any], groups: set):
        """Analyze a play for group references"""
        # Check vars for group references
        for var_name, var_value in play.get('vars', {}).items():
            if 'servers' in var_name:
                group = var_value if isinstance(var_value, str) else str(var_value)
                groups.add(group)

        # Check tasks for group references
        for task in play.get('tasks', []):
            if isinstance(task, dict):
                when_condition = task.get('when', '')
                if isinstance(when_condition, str) and 'groups[' in when_condition:
                    group = self._extract_group_from_condition(when_condition)
                    if group:
                        groups.add(group)

    def _extract_group_from_condition(self, condition: str) -> Optional[str]:
        """Extract group name from a when condition"""
        if "groups['" in condition:
            start = condition.find("groups['") + 8
            end = condition.find("']", start)
            if start > 7 and end != -1:
                return condition[start:end]
        return None

    def _extract_group_name(self, condition: str) -> Optional[str]:
        """Extract group name from conditions like 'inventory_hostname in groups['web_servers']'"""
        if 'groups[' in condition:
            start = condition.find("groups['") + 7
            end = condition.find("']", start)
            if start > 6 and end > start:
                return condition[start:end]
        return None

    def _extract_group_from_var(self, var_name: str) -> Optional[str]:
        """Extract group name from variable names like 'target_web_servers'"""
        if 'servers' in var_name:
            parts = var_name.split('_')
            if len(parts) >= 2:
                return f"{parts[-2]}_{parts[-1]}"
        return None

    def _ensure_group_exists(self, inventory: Dict[str, Any], group_name: str):
        """Ensure a group exists in the inventory structure"""
        if group_name not in inventory['all']['children']:
            inventory['all']['children'][group_name] = {
                'hosts': {}
            }

    def assign_hosts_to_groups(self, inventory: Dict[str, Any], host_mappings: Dict[str, Dict[str, str]]):
        """Assign actual hosts to the discovered groups"""
        for group_name, hosts in host_mappings.items():
            if group_name in inventory['all']['children']:
                inventory['all']['children'][group_name]['hosts'].update(hosts)