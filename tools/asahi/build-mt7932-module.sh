#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
release=${KERNEL_RELEASE:-$(uname -r)}
headers="/usr/lib/modules/$release/build"
driver="$root/drivers/net/wireless/mediatek/mt7932"

if [[ ! -r "$headers/.config" ]]; then
  printf 'Missing configured kernel headers: %s\n' "$headers" >&2
  exit 1
fi

major=$(sed -n 's/^CONFIG_CC_VERSION_TEXT="clang version \([0-9]*\).*/\1/p' "$headers/.config")
if [[ -z "$major" ]]; then
  printf 'This build script expects a Clang-built kernel.\n' >&2
  exit 1
fi
compiler=${CLANG:-}
if [[ -z "$compiler" ]]; then
  for candidate in "clang-$major" "/usr/lib/llvm$major/bin/clang" clang; do
    if command -v "$candidate" >/dev/null 2>&1; then
      compiler=$(command -v "$candidate")
      break
    fi
  done
fi
if [[ -z "$compiler" ]]; then
  printf 'Install clang%s, or set CLANG to its executable path.\n' "$major" >&2
  exit 1
fi
actual=$("$compiler" --version | sed -n '1s/.*clang version \([0-9]*\).*/\1/p')
if [[ "$actual" != "$major" ]]; then
  printf 'Compiler mismatch: kernel Clang %s, selected Clang %s.\n' "$major" "$actual" >&2
  exit 1
fi
printf 'Building development module for %s with %s (no installation).\n' "$release" "$compiler"
make -C "$headers" M="$driver" CONFIG_MT7932_FULLMAC=m \
  CC="$compiler" LD=ld.lld AR=ar NM=nm OBJCOPY=objcopy OBJDUMP=objdump \
  STRIP=strip READELF=readelf -j"${JOBS:-2}" modules
printf '\nBuilt: %s/mt7932-fullmac.ko\nEnterprise authentication remains unimplemented. Nothing was installed.\n' "$driver"
