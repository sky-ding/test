#!/usr/bin/env python3
"""
Production deployment script
Creates a deployable package with backend + built frontend
"""

import os
import shutil
import subprocess
from pathlib import Path

def main():
    root_dir = Path(__file__).parent.parent
    backend_dir = root_dir / 'backend'
    frontend_dir = root_dir / 'frontend'
    dist_dir = root_dir / 'dist'

    print('🚀 Starting production deployment...')

    # Step 1: Build frontend
    print('📦 Building frontend...')
    try:
        subprocess.run(['node', 'scripts/build-frontend.js'], cwd=root_dir, check=True)
        print('✅ Frontend build completed')
    except (subprocess.CalledProcessError, FileNotFoundError):
        print('⚠️  Node.js not found, skipping frontend build')
        print('   Make sure to run: node scripts/build-frontend.js')

    # Step 2: Create deployment directory
    print('📁 Creating deployment package...')
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir(parents=True)

    # Step 3: Copy backend files (flatten structure)
    print('🔄 Copying backend files...')
    # Copy backend/app/* to dist/
    backend_app_dir = backend_dir / 'app'
    for item in backend_app_dir.iterdir():
        if item.is_file():
            shutil.copy2(item, dist_dir / item.name)
        elif item.is_dir() and item.name != '__pycache__':
            copy_dir(item, dist_dir / item.name)

    # Copy other backend files
    for item in backend_dir.iterdir():
        if item.name not in ['app', '__pycache__']:
            if item.is_file():
                shutil.copy2(item, dist_dir / item.name)
            elif item.is_dir():
                copy_dir(item, dist_dir / item.name)

    # Step 4: Copy built frontend
    print('🔄 Copying frontend build...')
    frontend_dist = frontend_dir / 'dist'
    if frontend_dist.exists():
        copy_dir(frontend_dist, dist_dir / 'frontend')
    else:
        print('⚠️  Frontend dist not found, copying source files...')
        copy_dir(frontend_dir, dist_dir / 'frontend')

    # Step 5: Update main.py static file paths and imports
    print('🔄 Updating static file paths and imports...')
    main_py_path = dist_dir / 'main.py'
    if main_py_path.exists():
        content = main_py_path.read_text(encoding='utf-8')
        # Update frontend directory path
        content = content.replace(
            "frontend_dir = Path(__file__).parent.parent.parent / \"frontend\"",
            "frontend_dir = Path(__file__).parent / \"frontend\""
        )
        # Update imports from app.xxx to xxx
        content = content.replace('from app.', 'from ')
        main_py_path.write_text(content, encoding='utf-8')

    # Fix imports in all Python files
    print('🔄 Fixing imports in all Python files...')
    for py_file in dist_dir.rglob('*.py'):
        if py_file.name == '__init__.py':
            continue
        try:
            content = py_file.read_text(encoding='utf-8')
            # Replace from app.xxx import with from xxx import
            import os
            import re
            content = re.sub(r'from app\.(\w+) import', r'from \1 import', content)
            py_file.write_text(content, encoding='utf-8')
        except Exception as e:
            print(f'Warning: Could not fix imports in {py_file}: {e}')

    # Step 5: Copy deployment configs
    print('🔄 Copying deployment configs...')
    config_files = ['package.json', 'README.md', 'requirements.txt']
    for file in config_files:
        src = root_dir / file
        if src.exists():
            shutil.copy2(src, dist_dir / file)

    # Copy noah config if exists
    noah_dir = root_dir / 'noah'
    if noah_dir.exists():
        copy_dir(noah_dir, dist_dir / 'noah')

    print('✅ Deployment package created successfully!')
    print(f'📂 Package location: {dist_dir}')
    print('')
    print('🚀 To deploy:')
    print(f'   cd {dist_dir}')
    print('   python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8001')
    print('')
    print('📋 Package contents:')
    list_dir_contents(dist_dir)

def copy_dir(src, dest):
    """Copy directory recursively"""
    if not dest.exists():
        dest.mkdir(parents=True)

    for item in src.iterdir():
        if item.is_file():
            shutil.copy2(item, dest / item.name)
        elif item.is_dir():
            copy_dir(item, dest / item.name)

def list_dir_contents(dir_path, prefix=''):
    """List directory contents recursively"""
    for item in sorted(dir_path.iterdir()):
        relative_path = item.relative_to(dir_path.parent.parent if dir_path.parent.name == 'dist' else dir_path.parent)

        if item.is_dir():
            print(f'{prefix}📁 {relative_path}/')
            list_dir_contents(item, prefix + '  ')
        else:
            print(f'{prefix}📄 {relative_path}')

if __name__ == '__main__':
    main()
