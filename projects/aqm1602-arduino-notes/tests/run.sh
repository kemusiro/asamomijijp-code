#!/bin/sh
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
output_dir=$(mktemp -d "${TMPDIR:-/tmp}/aqm1602-tests.XXXXXX")
trap 'rm -rf "$output_dir"' EXIT HUP INT TERM
"${CXX:-c++}" -std=c++11 -Wall -Wextra -Werror -pedantic \
  -fsanitize=address,undefined -fno-omit-frame-pointer \
  -I"$project_dir/tests/fakes" -I"$project_dir/src" \
  "$project_dir/src/Aqm1602.cpp" "$project_dir/tests/test.cpp" -o "$output_dir/test"
"$output_dir/test"
