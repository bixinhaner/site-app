#!/bin/bash

# 构建脚本 - Shell版本
# 用于在不同环境和平台下构建应用

set -e

# 默认值
ENVIRONMENT="development"
PLATFORM="app-plus"

# 解析命令行参数
while [[ $# -gt 0 ]]; do
  case $1 in
    --env)
      ENVIRONMENT="$2"
      shift 2
      ;;
    --platform)
      PLATFORM="$2"
      shift 2
      ;;
    --help)
      echo "用法: $0 [选项]"
      echo ""
      echo "选项:"
      echo "  --env ENVIRONMENT      设置环境 (development|production) [默认: development]"
      echo "  --platform PLATFORM    设置平台 (app-plus|h5|mp-weixin) [默认: app-plus]"
      echo "  --help                 显示帮助信息"
      echo ""
      echo "示例:"
      echo "  $0 --env production --platform app-plus    # 生产环境Android/iOS应用"
      echo "  $0 --env development --platform h5         # 开发环境H5应用"
      echo "  $0 --env production --platform mp-weixin   # 生产环境微信小程序"
      exit 0
      ;;
    *)
      echo "未知选项: $1"
      echo "使用 --help 查看帮助信息"
      exit 1
      ;;
  esac
done

echo "🚀 开始构建应用"
echo "📦 环境: $ENVIRONMENT"
echo "📱 平台: $PLATFORM"

# 检查环境配置文件
ENV_FILE="env/.env.$ENVIRONMENT"
if [[ ! -f "$ENV_FILE" ]]; then
    echo "❌ 环境配置文件不存在: $ENV_FILE"
    echo "请创建配置文件或使用现有环境配置"
    echo "可用环境:"
    ls env/.env.* 2>/dev/null | sed 's/env\/.env\./  - /' || echo "  无可用环境配置"
    exit 1
fi

echo "📄 使用配置文件: $ENV_FILE"

# 调用Node.js构建脚本
node scripts/build.js --env "$ENVIRONMENT" --platform "$PLATFORM"