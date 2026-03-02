#!/usr/bin/env node

/**
 * 构建脚本
 * 用于根据环境配置打包应用
 */

const fs = require('fs')
const path = require('path')

// 解析命令行参数
const args = process.argv.slice(2)
let environment = 'development'
let platform = 'app-plus'

// 解析参数
args.forEach((arg, index) => {
  if (arg === '--env') {
    environment = args[index + 1] || 'development'
  }
  if (arg === '--platform') {
    platform = args[index + 1] || 'app-plus'
  }
})

console.log(`🚀 开始构建应用`)
console.log(`📦 环境: ${environment}`)
console.log(`📱 平台: ${platform}`)

// 读取环境配置
const envFile = path.join(__dirname, '../env', `.env.${environment}`)
if (!fs.existsSync(envFile)) {
  console.error(`❌ 环境配置文件不存在: ${envFile}`)
  process.exit(1)
}

console.log(`📄 读取配置文件: ${envFile}`)

// 解析环境配置
const envConfig = {}
const envContent = fs.readFileSync(envFile, 'utf8')
envContent.split('\n').forEach(line => {
  line = line.trim()
  if (line && !line.startsWith('#') && line.includes('=')) {
    const [key, ...valueParts] = line.split('=')
    const value = valueParts.join('=')
    envConfig[key.trim()] = value.trim()
  }
})

console.log('🔧 环境配置:')
Object.entries(envConfig).forEach(([key, value]) => {
  // 不显示敏感信息的完整值
  const displayValue = key.includes('SECRET') || key.includes('PASSWORD') 
    ? '***' 
    : value
  console.log(`   ${key}: ${displayValue}`)
})

// 读取并更新配置文件
const configFile = path.join(__dirname, '../config/env.js')
if (!fs.existsSync(configFile)) {
  console.error(`❌ 配置文件不存在: ${configFile}`)
  process.exit(1)
}

let configContent = fs.readFileSync(configFile, 'utf8')

// 替换配置占位符
Object.entries(envConfig).forEach(([key, value]) => {
  const placeholder = `__${key}__`
  configContent = configContent.replace(new RegExp(placeholder, 'g'), value)
})

// 写入临时配置文件
const tempConfigFile = path.join(__dirname, '../config/env.temp.js')
fs.writeFileSync(tempConfigFile, configContent)

console.log('✅ 配置文件已更新')

// 备份原始配置文件
const backupFile = `${configFile}.backup`
if (!fs.existsSync(backupFile)) {
  fs.copyFileSync(configFile, backupFile)
}

// 使用临时配置文件替换原始文件
fs.copyFileSync(tempConfigFile, configFile)

console.log('🎯 开始UniApp构建...')

// 调用UniApp CLI构建
const { spawn } = require('child_process')

const projectRoot = path.join(__dirname, '..')
const childEnv = { ...process.env }
let temporarySassLinkCreated = false
// 兼容“源码在项目根目录”的 UniApp 结构，避免 CLI 默认读取 ./src
if (!childEnv.UNI_INPUT_DIR) {
  childEnv.UNI_INPUT_DIR = projectRoot
}
if (!childEnv.UNI_CLI_VUE_BRIDGE) {
  childEnv.UNI_CLI_VUE_BRIDGE = '1'
}
// CLI 构建缺少 sass 时，复用同仓库 web-admin 的依赖，避免中断构建链
const localNodeModules = path.join(projectRoot, 'node_modules')
const localSassDir = path.join(projectRoot, 'node_modules', 'sass')
const webAdminNodeModules = path.resolve(projectRoot, '../web-admin/node_modules')
const webAdminSassDir = path.join(webAdminNodeModules, 'sass')
if (!fs.existsSync(localSassDir) && fs.existsSync(webAdminSassDir)) {
  if (!fs.existsSync(localNodeModules)) {
    fs.mkdirSync(localNodeModules, { recursive: true })
  }
  try {
    fs.symlinkSync(webAdminSassDir, localSassDir, 'junction')
    temporarySassLinkCreated = true
    console.log(`ℹ️ 未检测到本地 sass，已创建临时软链接: ${localSassDir} -> ${webAdminSassDir}`)
  } catch (e) {
    console.warn(`⚠️ 创建临时 sass 软链接失败，将继续尝试 NODE_PATH 方式: ${e?.message || e}`)
  }
  childEnv.NODE_PATH = childEnv.NODE_PATH
    ? `${webAdminNodeModules}${path.delimiter}${childEnv.NODE_PATH}`
    : webAdminNodeModules
  console.log(`ℹ️ 未检测到本地 sass，已临时复用: ${webAdminSassDir}`)
}

const cleanupBuildArtifacts = () => {
  // 恢复原始配置文件
  if (fs.existsSync(backupFile)) {
    fs.copyFileSync(backupFile, configFile)
    fs.unlinkSync(backupFile)
  }

  // 删除临时文件
  if (fs.existsSync(tempConfigFile)) {
    fs.unlinkSync(tempConfigFile)
  }

  // 删除本次构建创建的临时 sass 软链接
  if (temporarySassLinkCreated && fs.existsSync(localSassDir)) {
    fs.rmSync(localSassDir, { recursive: true, force: true })
    temporarySassLinkCreated = false
  }
}

const child = spawn('npm', ['run', 'build', '--', '--platform', platform], {
  cwd: projectRoot,
  env: childEnv,
  stdio: 'inherit',
  shell: true
})

child.on('close', (code) => {
  cleanupBuildArtifacts()
  
  if (code === 0) {
    console.log('🎉 构建完成!')
    console.log(`📱 平台: ${platform}`)
    console.log(`🌍 环境: ${environment}`)
  } else {
    console.error(`❌ 构建失败，退出码: ${code}`)
    process.exit(code)
  }
})

child.on('error', (err) => {
  console.error('❌ 构建过程中出错:', err)
  cleanupBuildArtifacts()
  
  process.exit(1)
})
