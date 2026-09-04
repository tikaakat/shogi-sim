#!/bin/bash
set -e

# やねうら王をMATERIAL版（駒得評価、評価関数ファイル不要）でビルドする
# YANEURAOU_EDITION はフルネームで指定する必要がある（省略形だと "no engine entry point" エラーになる）

WORK_DIR="${1:-/tmp/YaneuraOu}"

if [ ! -d "$WORK_DIR" ]; then
  git clone --depth 1 https://github.com/yaneurao/YaneuraOu.git "$WORK_DIR"
fi

sudo apt-get update -qq
sudo apt-get -y install clang lld

cd "$WORK_DIR/source"
make clean YANEURAOU_EDITION=YANEURAOU_ENGINE_MATERIAL || true
make -j"$(nproc)" tournament COMPILER=clang++ YANEURAOU_EDITION=YANEURAOU_ENGINE_MATERIAL TARGET_CPU=AVX2

echo "ビルド完了: $WORK_DIR/source/YaneuraOu-by-gcc"
