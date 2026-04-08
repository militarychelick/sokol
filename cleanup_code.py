# -*- coding: utf-8 -*-
"""SOKOL v8.0 - Code Cleanup Script"""
import os
import re
import glob

def cleanup_version_comments():
    """Remove old version comments and update to v8.0"""
    files_to_update = [
        'sokol/__init__.py',
        'sokol/gui_main.py',
        'sokol/tools/__init__.py',
        'sokol/tools/info_hub.py',
        'sokol/tools/stem.py'
    ]
    
    for file_path in files_to_update:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Update version comments
            content = re.sub(r'SOKOL v\d+\.\d+', 'SOKOL v8.0', content)
            content = re.sub(r'v\d+\.\d+', 'v8.0', content)
            
            # Remove old version references
            content = re.sub(r'Two-phase architecture', 'Multi-agent architecture', content)
            content = re.sub(r'Autonomous AI Agent', 'Multi-Agent AI System', content)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated: {file_path}")

def remove_deprecated_functions():
    """Remove or mark deprecated functions"""
    deprecated_patterns = [
        (r'# v7\.\d+:.*\n', ''),  # Old version comments
        (r'v7\.\d+ Fix:', 'v8.0 Updated:'),
        (r'v7\.\d+ New:', 'v8.0 Feature:'),
    ]
    
    for root, dirs, files in os.walk('sokol'):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    original_content = content
                    for pattern, replacement in deprecated_patterns:
                        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
                    
                    if content != original_content:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        print(f"Cleaned: {file_path}")
                        
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")

def update_config_comments():
    """Update config.py comments for v8.0"""
    config_path = 'sokol/config.py'
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Update version references
        content = re.sub(r'v7\.\d+', 'v8.0', content)
        content = re.sub(r'llama3 \(8B\) -> llama3\.2:3b', 'qwen2.5:1.5b for AMD GPU', content)
        content = re.sub(r'3-5x faster inference', 'GPU-accelerated inference', content)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated config: {config_path}")

def remove_old_backup_files():
    """Remove old backup files"""
    backup_patterns = [
        '*_old.py',
        '*_backup.py',
        '*_deprecated.py'
    ]
    
    for pattern in backup_patterns:
        for file_path in glob.glob(pattern):
            try:
                os.remove(file_path)
                print(f"Removed backup: {file_path}")
            except Exception as e:
                print(f"Could not remove {file_path}: {e}")

if __name__ == "__main__":
    print("SOKOL v8.0 - Code Cleanup")
    print("=" * 40)
    
    print("1. Updating version comments...")
    cleanup_version_comments()
    
    print("\n2. Removing deprecated functions...")
    remove_deprecated_functions()
    
    print("\n3. Updating config comments...")
    update_config_comments()
    
    print("\n4. Removing backup files...")
    remove_old_backup_files()
    
    print("\nCleanup completed!")
