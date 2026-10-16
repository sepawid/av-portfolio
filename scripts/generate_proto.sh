#!/bin/bash
set -e

echo "🔧 Regenerating Protobuf Python bindings from traffic_signs.proto..."
uv run python -m grpc_tools.protoc -I. --python_out=src/av_portfolio/proto traffic_signs.proto
echo "✨ Bindings regenerated in src/av_portfolio/proto/"
