#!/bin/bash
set -e

echo "Building frontend..."
cd web-client
npm install
npm run build
cd ..

echo "Build complete!"
