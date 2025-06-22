#!/usr/bin/env python3
"""Fix all remaining logging syntax errors."""

import re
import os

def fix_logging_errors(file_path):
    """Fix logging syntax errors in a file."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Fix patterns like: str(e") -> str(e)}
    content = re.sub(r'str\(e"\)', 'str(e)}', content)
    
    # Fix patterns like: len(something") -> len(something)}
    content = re.sub(r'(len\([^)]+)"\)', r'\1)}', content)
    
    # Fix patterns where there's a missing closing quote and parenthesis
    # Pattern: f"...{str(e)}" at end of line without closing parenthesis
    content = re.sub(r'(\s*self\.logger\.\w+\(f"[^"]+\{str\(e\)\}")\s*$', r'\1)', content, flags=re.MULTILINE)
    
    # Fix patterns where there's str(e) at end without closing }
    content = re.sub(r'(\s*self\.logger\.\w+\(f"[^"]+)str\(e\)$', r'\1{str(e)}', content, flags=re.MULTILINE)
    
    # Fix patterns where there's len(...) at end without closing }
    content = re.sub(r'(\s*self\.logger\.\w+\(f"[^"]+)(len\([^)]+\))$', r'\1{\2}', content, flags=re.MULTILINE)
    
    # Now ensure all logger calls have proper closing
    # Pattern: logger call that ends with }" but no closing )
    content = re.sub(r'(self\.logger\.\w+\(f"[^"]+\}")$', r'\1)', content, flags=re.MULTILINE)
    
    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"Fixed {file_path}")
        return True
    return False

def main():
    """Fix logging in all Python files."""
    files_to_fix = [
        'adk_main.py',
        'agents/adk_base_agent.py',
        'agents/adk_icp_agent.py',
        'agents/adk_prospect_agent.py',
        'agents/adk_research_agent.py',
        'services/vertex_memory_service.py'
    ]
    
    fixed_count = 0
    for file_path in files_to_fix:
        if os.path.exists(file_path):
            if fix_logging_errors(file_path):
                fixed_count += 1
    
    print(f"\nFixed {fixed_count} files")

if __name__ == "__main__":
    main()