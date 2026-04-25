#!/bin/bash
# 拖拽 txt 文件到此图标 → 自动多角色有声书转换
NOVEL_DIR="$HOME/Documents/novel"

if [ -z "$1" ]; then
    echo "═══════════════════════════════════════"
    echo "  NovelEasyVoice — 拖拽转换"
    echo "═══════════════════════════════════════"
    echo ""
    echo "使用方式: 将 .txt 文件拖拽到此图标上"
    echo ""
    read -p "按回车退出..."
    exit 0
fi

INPUT="$1"
BASENAME=$(basename "$INPUT")
NAME="${BASENAME%.*}"

echo "═══════════════════════════════════════"
echo "  开始转换: $NAME"
echo "═══════════════════════════════════════"
echo ""

# 先复制到 txt 目录
mkdir -p "$NOVEL_DIR/txt"
cp "$INPUT" "$NOVEL_DIR/txt/$BASENAME"

cd "$NOVEL_DIR"
exec ./easyvoice.sh start "$BASENAME"
