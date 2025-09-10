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

const buildCommand = platform === 'h5' ? 'build:h5' : `build:${platform}`
const child = spawn('npm', ['run', buildCommand], {
  cwd: path.join(__dirname, '..'),
  stdio: 'inherit',
  shell: true
})

child.on('close', (code) => {
  // 恢复原始配置文件
  if (fs.existsSync(backupFile)) {
    fs.copyFileSync(backupFile, configFile)
    fs.unlinkSync(backupFile)
  }
  
  // 删除临时文件
  if (fs.existsSync(tempConfigFile)) {
    fs.unlinkSync(tempConfigFile)
  }
  
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
  
  // 恢复原始配置文件
  if (fs.existsSync(backupFile)) {
    fs.copyFileSync(backupFile, configFile)
    fs.unlinkSync(backupFile)
  }
  
  // 删除临时文件
  if (fs.existsSync(tempConfigFile)) {
    fs.unlinkSync(tempConfigFile)
  }
  
  process.exit(1)
})