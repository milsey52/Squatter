#!/bin/bash
set -ex

echo "========================================="
echo "Building frontend..."
echo "========================================="

cd web-client

echo "Current directory: $(pwd)"
echo "Running npm install..."
npm install --verbose

echo "Running npm run build..."
npm run build

cd ..

echo "========================================="
echo "Build complete!"
echo "========================================="
