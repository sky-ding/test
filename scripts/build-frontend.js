#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

/**
 * Build script for static frontend files
 * Copies all files from frontend/ to frontend/dist/
 */

const frontendDir = path.join(__dirname, '..', 'frontend');
const distDir = path.join(frontendDir, 'dist');

console.log('Building frontend...');

// Create dist directory if it doesn't exist
if (!fs.existsSync(distDir)) {
  fs.mkdirSync(distDir, { recursive: true });
  console.log(`Created directory: ${distDir}`);
}

// Copy all files from frontend to frontend/dist
try {
  const files = fs.readdirSync(frontendDir);
  
  files.forEach(file => {
    if (file === 'dist') return; // Skip dist directory itself
    
    const srcPath = path.join(frontendDir, file);
    const destPath = path.join(distDir, file);
    
    const stat = fs.statSync(srcPath);
    
    if (stat.isFile()) {
      fs.copyFileSync(srcPath, destPath);
      console.log(`Copied: ${file}`);
    } else if (stat.isDirectory()) {
      // Recursively copy directories
      copyDir(srcPath, destPath);
    }
  });
  
  console.log('Frontend build completed successfully!');
  console.log(`Static files are ready in: ${distDir}`);
} catch (error) {
  console.error('Build failed:', error.message);
  process.exit(1);
}

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
