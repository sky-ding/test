#!/usr/bin/env python3
"""
Production deployment script
Creates a deployable package with backend + built frontend
"""

import os
import shutil
import subprocess


def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    backend_dir = os.path.join(root_dir, 'backend')
    frontend_dir = os.path.join(root_dir, 'frontend')
    dist_dir = os.path.join(root_dir, 'dist')

    print('Starting production deployment...')

    # Step 1: Build frontend
    print('Building frontend...')
    try:
        subprocess.check_call(['node', 'scripts/build-frontend.js'], cwd=root_dir)
        print('Frontend build completed')
    except OSError:
        print('Node.js not found, skipping frontend build')
        print('   Make sure to run: node scripts/build-frontend.js')
    except subprocess.CalledProcessError as exc:
        print('Frontend build failed: {}'.format(exc))
        print('   Skipping frontend build and copying frontend source files')

    # Step 2: Create deployment directory
    print('Creating deployment package...')
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)
    os.makedirs(dist_dir)

    # Step 3: Copy backend application
    print('Copying backend application...')
    copy_dir(os.path.join(backend_dir, 'app'), os.path.join(dist_dir, 'app'))

    # Copy backend data if present
    backend_data_dir = os.path.join(backend_dir, 'data')
    if os.path.exists(backend_data_dir):
        print('Copying backend data...')
        copy_dir(backend_data_dir, os.path.join(dist_dir, 'data'))

    # Step 4: Copy built frontend
    print('Copying frontend build...')
    frontend_dist = os.path.join(frontend_dir, 'dist')
    if os.path.exists(frontend_dist):
        copy_dir(frontend_dist, os.path.join(dist_dir, 'frontend'))
    else:
        print('Frontend dist not found, copying source files...')
        copy_dir(frontend_dir, os.path.join(dist_dir, 'frontend'))

    # Step 5: Copy deployment configs
    print('Copying deployment configs...')
    # Note: README.md and package.json are in blacklist and should not be included in deployment package
    # for file_name in ['package.json', 'README.md']:
    #     src = os.path.join(root_dir, file_name)
    #     if os.path.exists(src):
    #         shutil.copy2(src, os.path.join(dist_dir, file_name))

    backend_requirements = os.path.join(backend_dir, 'requirements.txt')
    if os.path.exists(backend_requirements):
        shutil.copy2(backend_requirements, os.path.join(dist_dir, 'requirements.txt'))

    # Copy noah config if exists
    noah_dir = os.path.join(root_dir, 'noah')
    if os.path.exists(noah_dir):
        copy_dir(noah_dir, os.path.join(dist_dir, 'noah'))

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
    if not os.path.exists(dest):
        os.makedirs(dest)

    for item in sorted(os.listdir(src)):
        src_path = os.path.join(src, item)
        dest_path = os.path.join(dest, item)

        if os.path.isfile(src_path):
            shutil.copy2(src_path, dest_path)
        elif os.path.isdir(src_path) and item != '__pycache__':
            copy_dir(src_path, dest_path)


def list_dir_contents(dir_path, base_dir=None, prefix=''):
    """List directory contents recursively"""
    base_dir = base_dir or dir_path

    for item in sorted(os.listdir(dir_path)):
        item_path = os.path.join(dir_path, item)
        relative_path = os.path.relpath(item_path, base_dir)

        if os.path.isdir(item_path):
            print('{}{}/'.format(prefix, relative_path))
            list_dir_contents(item_path, base_dir, prefix + '  ')
        else:
            print('{}{}'.format(prefix, relative_path))


if __name__ == '__main__':
    main()
