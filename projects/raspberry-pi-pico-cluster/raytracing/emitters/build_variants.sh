#!/bin/sh
set -eu

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    echo "Usage: $0 /path/to/mpy-cross [output-directory]" >&2
    exit 2
fi

mpy_cross=$1
output_dir=${2:-build}
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

if [ ! -x "$mpy_cross" ]; then
    echo "mpy-cross is not executable: $mpy_cross" >&2
    exit 1
fi

mkdir -p "$output_dir"

compile() {
    source_file=$1
    output_file=$2
    shift 2
    "$mpy_cross" \
        -march=armv7emsp \
        "$@" \
        -s raytracer_core.py \
        -o "$output_dir/$output_file" \
        "$script_dir/$source_file"
}

compile raytracer_core_original.py raytracer_core_original.mpy
compile raytracer_core_original.py raytracer_core_native.mpy -X emit=native
compile raytracer_core_viper.py raytracer_core_viper.mpy
compile raytracer_core_inline_asm.py raytracer_core_inline_asm.mpy -X emit=native

echo "Built emitter variants in: $output_dir"
echo "Rename one selected file to raytracer_core.mpy when deploying it."
