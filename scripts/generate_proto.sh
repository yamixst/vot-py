#!/bin/bash
set -e

# Directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PROTO_SRC_DIR="/home/xst/prj/yavot/vot.js/packages/shared/src/protos"
PROTO_OUT_DIR="$PROJECT_ROOT/src/vot/protobuf"

# Create output directory if it doesn't exist
mkdir -p "$PROTO_OUT_DIR"

# Run protoc
protoc --proto_path="$PROTO_SRC_DIR" --python_out="$PROTO_OUT_DIR" "$PROTO_SRC_DIR/yandex.proto"

echo "Successfully generated protobuf Python files in $PROTO_OUT_DIR"
