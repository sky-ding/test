#!/usr/bin/env python3
"""
Production deployment script
Creates a deployable package with backend + built frontend
"""

import shutil
import subprocess
from pathlib import Path


def main():
    root_dir = Path(__file__).parent.parent
    backend_dir = root_dir / 'backend'
    frontend_dir = root_dir / 'frontend'
    dist_dir = root_dir / 'dist'

    print('Starting production deployment...')

    # Step 1: Build frontend
    print('Building frontend...')
    try:
        subprocess.run(['node', 'scripts/build-frontend.js'], cwd=root_dir, check=True)
        print('Frontend build completed')
    except FileNotFoundError:
        print('Node.js not found, skipping frontend build')
        print('   Make sure to run: node scripts/build-frontend.js')
    except subprocess.CalledProcessError as exc:
        print('Frontend build failed: {}'.format(exc))
        print('   Skipping frontend build and copying frontend source files')

    # Step 2: Create deployment directory
    print('Creating deployment package...')
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir(parents=True)

    # Step 3: Copy backend application
    print('Copying backend application...')
    copy_dir(backend_dir / 'app', dist_dir / 'app')

    # Copy backend data if present
    backend_data_dir = backend_dir / 'data'
    if backend_data_dir.exists():
        print('Copying backend data...')
        copy_dir(backend_data_dir, dist_dir / 'data')

    # Step 4: Copy built frontend
    print('Copying frontend build...')
    frontend_dist = frontend_dir / 'dist'
    if frontend_dist.exists():
        copy_dir(frontend_dist, dist_dir / 'frontend')
    else:
        print('Frontend dist not found, copying source files...')
        copy_dir(frontend_dir, dist_dir / 'frontend')

    # Step 5: Copy deployment configs
    print('Copying deployment configs...')
    for file_name in ['package.json', 'README.md']:
        src = root_dir / file_name
        if src.exists():
            shutil.copy2(src, dist_dir / file_name)

    backend_requirements = backend_dir / 'requirements.txt'
    if backend_requirements.exists():
        shutil.copy2(backend_requirements, dist_dir / 'requirements.txt')

    # Copy noah config if exists
    noah_dir = root_dir / 'noah'
    if noah_dir.exists():
        copy_dir(noah_dir, dist_dir / 'noah')

    print('Deployment package created successfully!')
    print('Package location: {}'.format(dist_dir))
    print('')
    print('To deploy:')
    print('   cd {}'.format(dist_dir))
    print('   python -m uvicorn app.main:app --host 0.0.0.0 --port 8001')
    print('')
    print('Package contents:')
    list_dir_contents(dist_dir, dist_dir)


def copy_dir(src, dest):
    """Copy directory recursively"""
    if not dest.exists():
        dest.mkdir(parents=True)

    for item in sorted(src.iterdir()):
        if item.name == '__pycache__':
            continue

        if item.is_file():
            shutil.copy2(item, dest / item.name)
        elif item.is_dir():
            copy_dir(item, dest / item.name)


def list_dir_contents(dir_path, base_dir=None, prefix=''):
    """List directory contents recursively"""
    base_dir = base_dir or dir_path

    for item in sorted(dir_path.iterdir()):
        relative_path = item.relative_to(base_dir)

        if item.is_dir():
            print('{}{}/'.format(prefix, relative_path))
            list_dir_contents(item, base_dir, prefix + '  ')
        else:
            print('{}{}'.format(prefix, relative_path))


if __name__ == '__main__':
    main()
