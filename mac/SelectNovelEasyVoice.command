#!/bin/bash
# 双击 → 弹出文件选择框 → 选 txt → 自动转换
NOVEL_DIR="$HOME/Documents/novel"

echo "═══════════════════════════════════════"
echo "  请在弹出的窗口中选择 txt 文件..."
echo "═══════════════════════════════════════"

FILE=$(osascript -e 'POSIX path of (choose file with prompt "选择要转换的小说 txt 文件" of type {"txt","text"})')

if [ -z "$FILE" ]; then
    echo "未选择文件"
    read -p "按回车退出..."
    exit 0
fi

BASENAME=$(basename "$FILE")
NAME="${BASENAME%.*}"

echo ""
echo "  选中: $NAME"
echo ""

# 复制到 txt 目录
mkdir -p "$NOVEL_DIR/txt"
cp "$FILE" "$NOVEL_DIR/txt/$BASENAME"

cd "$NOVEL_DIR"
./easyvoice.sh start "$BASENAME"

echo ""
read -p "按回车退出..."
