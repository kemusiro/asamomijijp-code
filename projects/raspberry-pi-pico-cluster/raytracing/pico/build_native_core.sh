#!/bin/sh
set -eu

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 /path/to/mpy-cross /path/to/raytracer_core_native.mpy" >&2
    exit 2
fi

mpy_cross=$1
output=$2
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
source_file="$script_dir/raytracer_core.py"

if [ ! -x "$mpy_cross" ]; then
    echo "mpy-cross is not executable: $mpy_cross" >&2
    exit 1
fi

output_dir=$(dirname -- "$output")
if [ ! -d "$output_dir" ]; then
    echo "Output directory does not exist: $output_dir" >&2
    exit 1
fi

"$mpy_cross" \
    -march=armv7emsp \
    -X emit=native \
    -s raytracer_core.py \
    -o "$output" \
    "$source_file"

echo "Built RP2350 native module: $output"
