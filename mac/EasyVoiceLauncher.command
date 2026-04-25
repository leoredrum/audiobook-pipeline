#!/bin/bash
# EasyVoice 总控入口
NOVEL_DIR="$HOME/Documents/novel"
cd "$NOVEL_DIR"

while true; do
    echo ""
    echo "═══════════════════════════════════════"
    echo "  EasyVoice 有声书工具"
    echo "═══════════════════════════════════════"
    echo ""
    echo "  1) 选择 txt 文件转换"
    echo "  2) 查看当前进度"
    echo "  3) 批量转换 txt/ 下所有小说"
    echo "  4) 停止当前任务"
    echo "  5) 打开输出目录"
    echo "  6) 启动/重启 easyVoice 服务"
    echo "  7) 退出"
    echo ""
    read -p "  请选择 [1-7]: " choice

    case "$choice" in
        1)
            echo ""
            echo "  请在弹出窗口选择文件..."
            FILE=$(osascript -e 'POSIX path of (choose file with prompt "选择要转换的小说 txt 文件" of type {"txt","text"})' 2>/dev/null)
            if [ -n "$FILE" ]; then
                BASENAME=$(basename "$FILE")
                mkdir -p "$NOVEL_DIR/txt"
                cp "$FILE" "$NOVEL_DIR/txt/$BASENAME"
                echo "  开始转换: $BASENAME"
                ./easyvoice.sh start "$BASENAME"
            else
                echo "  未选择文件"
            fi
            ;;
        2)
            echo ""
            ./easyvoice.sh status
            ;;
        3)
            echo ""
            echo "  启动批量转换..."
            ./easyvoice.sh start
            ;;
        4)
            echo ""
            ./easyvoice.sh stop
            ;;
        5)
            open "$NOVEL_DIR/output_easyvoice" 2>/dev/null || echo "  输出目录不存在"
            ;;
        6)
            echo ""
            ./easyvoice.sh server
            ;;
        7)
            echo "  再见"
            exit 0
            ;;
        *)
            echo "  无效选择"
            ;;
    esac
done
