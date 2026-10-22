#!/bin/bash
# 长椿街执事（nmpa-regulatory-expert）一键安装
# 用法：在仓库目录里 bash install.sh
#   或远程一条命令：
#   curl -fsSL https://codeload.github.com/PotusKing/workbuddy/tar.gz/refs/heads/main | tar xz -C /tmp && bash /tmp/workbuddy-main/install.sh
set -e

HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/plugins/nmpa-regulatory-expert"
WB="${WORKBUDDY_CONFIG_DIR:-$HOME/.workbuddy}"
DEST_DIR="$WB/plugins/marketplaces/my-experts/plugins"
DEST="$DEST_DIR/nmpa-regulatory-expert"
REG="/Applications/WorkBuddy.app/Contents/Resources/app.asar.unpacked/resources/plugins/workbuddy-builtin/skills/expert-manager/scripts/register_expert.py"

[ -d "$SRC" ] || { echo "❌ 未找到 plugins/nmpa-regulatory-expert，请在仓库根目录运行本脚本"; exit 1; }

mkdir -p "$DEST_DIR"
echo "📦 安装专家包 → $DEST"
ditto "$SRC" "$DEST"

if command -v python3 >/dev/null 2>&1 && [ -f "$REG" ]; then
  echo "🔍 校验并注册…"
  python3 "$REG" "$DEST"
  echo ""
  echo "✅ 安装完成。重启 WorkBuddy 后，在专家列表即可看到「长椿街执事」。"
else
  echo ""
  echo "✅ 文件已复制到 $DEST"
  echo "⚠️ 未找到 python3 或 WorkBuddy 内置注册脚本，未完成注册。"
  echo "   重启 WorkBuddy 看专家列表；若未出现，请安装 python3 后重新运行本脚本。"
fi
