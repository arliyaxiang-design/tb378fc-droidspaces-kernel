#!/usr/bin/env bash
set -euo pipefail
ROOT="$(pwd)"
mkdir -p "$ROOT/dist" "$ROOT/build"
DIST="$ROOT/dist"
exec > >(tee "$DIST/build.log") 2>&1
KERNEL_COMMIT=076ac12bde16ea0405a4ffd30404085b96b74eb5
CLANG_COMMIT=42d100b025eb5f4a41781348016c148e9e912cf9
RELEASE=6.6.82-android15-8-g076ac12bde16-ab13715361-4k
export ARCH=arm64 LLVM=1 LLVM_IAS=1
export KBUILD_BUILD_USER=kleaf KBUILD_BUILD_HOST=build-host
export KBUILD_BUILD_TIMESTAMP='Mon Jun 30 15:06:58 UTC 2025'
export KBUILD_BUILD_VERSION=1
export KCFLAGS=-D__ANDROID_COMMON_KERNEL__
export LOCALVERSION=-android15-8-g076ac12bde16-ab13715361-4k
unset BUILD_NUMBER || true

git init "$ROOT/build/common"
git -C "$ROOT/build/common" remote add origin https://github.com/aosp-mirror/kernel_common.git
git -C "$ROOT/build/common" fetch --depth=1 origin "$KERNEL_COMMIT"
git -C "$ROOT/build/common" checkout --detach FETCH_HEAD
test "$(git -C "$ROOT/build/common" rev-parse HEAD)" = "$KERNEL_COMMIT"

git init "$ROOT/build/clang"
git -C "$ROOT/build/clang" remote add origin https://android.googlesource.com/platform/prebuilts/clang/host/linux-x86
git -C "$ROOT/build/clang" config core.sparseCheckout true
printf '/clang-r510928/\n' > "$ROOT/build/clang/.git/info/sparse-checkout"
git -C "$ROOT/build/clang" fetch --depth=1 --filter=blob:none origin "$CLANG_COMMIT"
git -C "$ROOT/build/clang" checkout --detach FETCH_HEAD
test "$(git -C "$ROOT/build/clang" rev-parse HEAD)" = "$CLANG_COMMIT"
export PATH="$ROOT/build/clang/clang-r510928/bin:$PATH"
clang --version | tee "$DIST/clang-version.txt"
grep -q '11368308' "$DIST/clang-version.txt"
grep -q 'clang version 18.0.0' "$DIST/clang-version.txt"

SRC="$ROOT/build/common"
OUT="$ROOT/build/out"
mkdir -p "$OUT"
cp "$ROOT/config/stock.config" "$OUT/.config"
cp "$ROOT/config/stock-module-certs.pem" "$SRC/certs/stock-module-certs.pem"
"$SRC/scripts/config" --file "$OUT/.config" -d TRIM_UNUSED_KSYMS -d LOCALVERSION_AUTO
"$SRC/scripts/config" --file "$OUT/.config" --set-str LOCALVERSION ''
"$SRC/scripts/config" --file "$OUT/.config" --set-str SYSTEM_TRUSTED_KEYS 'certs/stock-module-certs.pem'
make -C "$SRC" O="$OUT" olddefconfig
cp "$OUT/.config" "$DIST/baseline.config"

capture_build() {
    local phase="$1"
    make -C "$SRC" O="$OUT" -j"${BUILD_JOBS:-2}" Image modules
    cp "$OUT/Module.symvers" "$DIST/$phase.Module.symvers"
    cp "$OUT/arch/arm64/boot/Image" "$DIST/$phase.Image"
    cp "$OUT/include/config/kernel.release" "$DIST/$phase.kernel.release"
    test "$(cat "$DIST/$phase.kernel.release")" = "$RELEASE"
    llvm-objcopy --dump-section ".BTF=$DIST/$phase.btf" "$OUT/vmlinux"
    pahole -C task_struct "$OUT/vmlinux" > "$DIST/$phase.task_struct.txt"
    python3 "$ROOT/scripts/verify-build.py" "$phase"
}
capture_build baseline

git -C "$SRC" apply --check "$ROOT/patches/droidspaces-sysvipc.patch"
git -C "$SRC" apply "$ROOT/patches/droidspaces-sysvipc.patch"
for feature in SYSVIPC POSIX_MQUEUE PID_NS IPC_NS USER_NS DEVTMPFS; do
    "$SRC/scripts/config" --file "$OUT/.config" -e "$feature"
done
make -C "$SRC" O="$OUT" olddefconfig
cp "$OUT/.config" "$DIST/droidspaces.config"
capture_build droidspaces
cp "$DIST/droidspaces.Image" "$DIST/Image-UNTESTED"
git -C "$SRC" diff > "$DIST/applied.patch"
printf '%s\n' "$KERNEL_COMMIT" > "$DIST/kernel-commit.txt"
printf '%s\n' "$CLANG_COMMIT" > "$DIST/clang-commit.txt"
printf '%s\n' 'NOT FLASH READY. No boot image is produced. Hardware boot testing and recovery preparation remain required.' > "$DIST/NOT-FLASH-READY.txt"
(cd "$DIST" && sha256sum Image-UNTESTED *.Image *.btf *.Module.symvers > SHA256SUMS)
echo 'Build and static compatibility checks passed. Candidate remains UNTESTED.'
