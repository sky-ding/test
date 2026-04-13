#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

/**
 * Production deployment script
 * Creates a deployable package with backend + built frontend
 */

const rootDir = path.join(__dirname, '..');
const backendDir = path.join(rootDir, 'backend');
const frontendDir = path.join(rootDir, 'frontend');
const distDir = path.join(rootDir, 'dist');

console.log('🚀 Starting production deployment...');

// Step 1: Build frontend
console.log('📦 Building frontend...');
try {
  execSync('node scripts/build-frontend.js', { cwd: rootDir, stdio: 'inherit' });
  console.log('✅ Frontend build completed');
} catch (error) {
  console.error('❌ Frontend build failed:', error.message);
  process.exit(1);
}

// Step 2: Create deployment directory
console.log('📁 Creating deployment package...');
if (fs.existsSync(distDir)) {
  fs.rmSync(distDir, { recursive: true, force: true });
}
fs.mkdirSync(distDir, { recursive: true });

// Step 3: Copy backend files
console.log('🔄 Copying backend files...');
copyDir(backendDir, path.join(distDir, 'backend'));

// Step 4: Copy built frontend
console.log('🔄 Copying frontend build...');
const frontendDist = path.join(frontendDir, 'dist');
if (fs.existsSync(frontendDist)) {
  copyDir(frontendDist, path.join(distDir, 'frontend'));
} else {
  console.warn('⚠️  Frontend dist not found, copying source files...');
  copyDir(frontendDir, path.join(distDir, 'frontend'));
}

// Step 5: Copy deployment configs
console.log('🔄 Copying deployment configs...');
const configFiles = ['package.json', 'README.md', 'requirements.txt'];
configFiles.forEach(file => {
  const src = path.join(rootDir, file);
  if (fs.existsSync(src)) {
    fs.copyFileSync(src, path.join(distDir, file));
  }
});

// Copy noah config if exists
const noahDir = path.join(rootDir, 'noah');
if (fs.existsSync(noahDir)) {
  copyDir(noahDir, path.join(distDir, 'noah'));
}

console.log('✅ Deployment package created successfully!');
console.log(`📂 Package location: ${distDir}`);
console.log('');
console.log('🚀 To deploy:');
console.log(`   cd ${distDir}`);
console.log('   python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8001');
console.log('');
console.log('📋 Package contents:');
listDirContents(distDir);

function copyDir(src, dest) {
  if (!fs.existsSync(dest)) {
    fs.mkdirSync(dest, { recursive: true });
  }

  const files = fs.readdirSync(src);
  files.forEach(file => {
    const srcPath = path.join(src, file);
    const destPath = path.join(dest, file);
    const stat = fs.statSync(srcPath);

    if (stat.isFile()) {
      fs.copyFileSync(srcPath, destPath);
    } else if (stat.isDirectory()) {
      copyDir(srcPath, destPath);
    }
  });
}

function listDirContents(dir, prefix = '') {
  const files = fs.readdirSync(dir);
  files.forEach(file => {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);
    const relativePath = path.relative(distDir, filePath);

    if (stat.isDirectory()) {
      console.log(`${prefix}📁 ${relativePath}/`);
      listDirContents(filePath, prefix + '  ');
    } else {
      console.log(`${prefix}📄 ${relativePath}`);
    }
  });
}
