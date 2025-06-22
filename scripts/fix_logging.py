#!/usr/bin/env python3
"""
Fix logging calls that use keyword arguments (not supported by standard Python logging).
"""

import re
import sys
from pathlib import Path

def fix_logging_in_file(file_path):
    """Fix logging calls in a single file."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Pattern to match logger calls with keyword arguments
    # Matches: self.logger.{level}("message", key=value, key2=value2)
    pattern = r'(self\.logger\.(info|debug|warning|error))\s*\(\s*"([^"]+)"\s*,\s*([^)]+)\)'
    
    def replace_logging(match):
        prefix = match.group(1)  # self.logger.{level}
        message = match.group(3)  # The message
        kwargs = match.group(4)  # The keyword arguments
        
        # Parse the kwargs
        kwargs_parts = []
        # Simple parsing - split by comma but be careful of nested structures
        parts = kwargs.split(',')
        for part in parts:
            if '=' in part:
                key_value = part.strip()
                key = key_value.split('=')[0].strip()
                value = key_value[len(key)+1:].strip()
                kwargs_parts.append(f"{key.title()}: {{{value}}}")
        
        # Create the new format string
        if kwargs_parts:
            new_message = f'"{message} - {", ".join(kwargs_parts)}"'
            return f'{prefix}(f{new_message})'
        else:
            return match.group(0)
    
    # Apply the replacement
    content = re.sub(pattern, replace_logging, content)
    
    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"Fixed: {file_path}")
        return True
    return False

def main():
    # Files to fix
    files_to_fix = [
        "agents/adk_base_agent.py",
        "agents/adk_icp_agent.py",
        "agents/adk_prospect_agent.py",
        "agents/adk_research_agent.py",
        "services/vertex_memory_service.py",
        "services/mock_memory_service.py",
        "adk_main.py",
    ]
    
    project_root = Path("/Users/bayramannakov/GH/onsa-icp-agent")
    
    fixed_count = 0
    for file_path in files_to_fix:
        full_path = project_root / file_path
        if full_path.exists():
            if fix_logging_in_file(full_path):
                fixed_count += 1
        else:
            print(f"File not found: {full_path}")
    
    print(f"\nFixed {fixed_count} files")

if __name__ == "__main__":
    main()