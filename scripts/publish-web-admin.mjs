#!/usr/bin/env node

import { spawnSync } from 'node:child_process'
import { access, cp, mkdir, mkdtemp, readFile, readdir, rename, rm, stat, writeFile } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const DEFAULT_RETENTION_DAYS = 30
const scriptDirectory = path.dirname(fileURLToPath(import.meta.url))
const repositoryRoot = path.dirname(scriptDirectory)

const pathExists = async (targetPath) => {
  try {
    await access(targetPath)
    return true
  } catch {
    return false
  }
}

const listFiles = async (directory, root = directory) => {
  if (!await pathExists(directory)) return []
  const entries = await readdir(directory, { withFileTypes: true })
  const nested = await Promise.all(entries.map(async (entry) => {
    const absolutePath = path.join(directory, entry.name)
    if (entry.isDirectory()) return listFiles(absolutePath, root)
    if (!entry.isFile()) return []
    return [{
      absolutePath,
      relativePath: path.relative(root, absolutePath),
    }]
  }))
  return nested.flat()
}

const removeEmptyDirectories = async (directory, root = directory) => {
  if (!await pathExists(directory)) return
  const entries = await readdir(directory, { withFileTypes: true })
  for (const entry of entries) {
    if (!entry.isDirectory()) continue
    await removeEmptyDirectories(path.join(directory, entry.name), root)
  }
  if (directory === root) return
  if ((await readdir(directory)).length === 0) await rm(directory, { recursive: true, force: true })
}

const verifyPublishedIndex = async (distDirectory) => {
  const indexPath = path.join(distDirectory, 'index.html')
  const html = await readFile(indexPath, 'utf8')
  const references = [...html.matchAll(/(?:src|href)=["']\/assets\/([^"'?#]+)["']/g)]
    .map(match => match[1])

  for (const relativePath of references) {
    const assetPath = path.join(distDirectory, 'assets', relativePath)
    if (!await pathExists(assetPath)) {
      throw new Error(`发布校验失败，index.html 引用的资源不存在：${relativePath}`)
    }
  }
  return references.length
}

export const publishBuild = async ({
  sourceBuildDirectory,
  distDirectory,
  retentionDays = DEFAULT_RETENTION_DAYS,
  now = Date.now(),
}) => {
  if (!Number.isInteger(retentionDays) || retentionDays < 1) {
    throw new Error('资源保留天数必须是大于 0 的整数')
  }

  const sourceIndex = path.join(sourceBuildDirectory, 'index.html')
  const sourceAssets = path.join(sourceBuildDirectory, 'assets')
  if (!await pathExists(sourceIndex) || !await pathExists(sourceAssets)) {
    throw new Error(`构建产物不完整：${sourceBuildDirectory}`)
  }

  const distAssets = path.join(distDirectory, 'assets')
  await mkdir(distAssets, { recursive: true })

  const currentAssets = await listFiles(sourceAssets)
  const currentAssetPaths = new Set(currentAssets.map(file => file.relativePath))

  // 先发布全部带哈希资源，确保新入口生效时依赖已经就位。
  await cp(sourceAssets, distAssets, {
    recursive: true,
    force: true,
    preserveTimestamps: true,
  })

  const rootEntries = await readdir(sourceBuildDirectory, { withFileTypes: true })
  for (const entry of rootEntries) {
    if (entry.name === 'assets' || entry.name === 'index.html') continue
    await cp(
      path.join(sourceBuildDirectory, entry.name),
      path.join(distDirectory, entry.name),
      { recursive: true, force: true, preserveTimestamps: true },
    )
  }

  // 最后原子替换入口，避免入口先引用到尚未复制完成的新资源。
  const nextIndex = path.join(distDirectory, `.index.html.${process.pid}.next`)
  await writeFile(nextIndex, await readFile(sourceIndex))
  await rename(nextIndex, path.join(distDirectory, 'index.html'))

  const cutoff = now - retentionDays * 24 * 60 * 60 * 1000
  let removedAssets = 0
  const publishedAssets = await listFiles(distAssets)
  for (const file of publishedAssets) {
    if (currentAssetPaths.has(file.relativePath)) continue
    const fileStat = await stat(file.absolutePath)
    if (fileStat.mtimeMs >= cutoff) continue
    await rm(file.absolutePath, { force: true })
    removedAssets += 1
  }
  await removeEmptyDirectories(distAssets)

  for (const relativePath of currentAssetPaths) {
    if (!await pathExists(path.join(distAssets, relativePath))) {
      throw new Error(`发布校验失败，当前构建资源不存在：${relativePath}`)
    }
  }

  const indexAssetReferences = await verifyPublishedIndex(distDirectory)
  return {
    currentAssets: currentAssetPaths.size,
    indexAssetReferences,
    removedAssets,
    retainedAssets: (await listFiles(distAssets)).length - currentAssetPaths.size,
  }
}

const printUsage = () => {
  console.log(`用法：node scripts/publish-web-admin.mjs [选项]

选项：
  --web-admin <目录>     WebAdmin 源码目录，默认 web-admin
  --dist <目录>          发布目录，默认 <web-admin>/dist
  --source-build <目录>  使用已有构建产物，省略时自动执行 npm run build
  --retain-days <天数>   旧哈希资源保留天数，默认 30
  --help                 显示帮助`)
}

const parseArguments = (argumentsList) => {
  const options = {
    webAdminDirectory: path.join(repositoryRoot, 'web-admin'),
    distDirectory: '',
    sourceBuildDirectory: '',
    retentionDays: DEFAULT_RETENTION_DAYS,
  }

  for (let index = 0; index < argumentsList.length; index += 1) {
    const argument = argumentsList[index]
    const value = argumentsList[index + 1]
    if (argument === '--help') return { help: true }
    if (!value) throw new Error(`缺少参数值：${argument}`)

    if (argument === '--web-admin') options.webAdminDirectory = path.resolve(value)
    else if (argument === '--dist') options.distDirectory = path.resolve(value)
    else if (argument === '--source-build') options.sourceBuildDirectory = path.resolve(value)
    else if (argument === '--retain-days') options.retentionDays = Number(value)
    else throw new Error(`未知参数：${argument}`)
    index += 1
  }

  if (!options.distDirectory) options.distDirectory = path.join(options.webAdminDirectory, 'dist')
  return options
}

const run = async () => {
  const options = parseArguments(process.argv.slice(2))
  if (options.help) {
    printUsage()
    return
  }

  let temporaryDirectory = ''
  try {
    if (!options.sourceBuildDirectory) {
      temporaryDirectory = await mkdtemp(path.join(os.tmpdir(), 'siteapp-web-build-'))
      options.sourceBuildDirectory = path.join(temporaryDirectory, 'dist')
      const buildResult = spawnSync(
        process.platform === 'win32' ? 'npm.cmd' : 'npm',
        ['run', 'build', '--', '--outDir', options.sourceBuildDirectory, '--emptyOutDir'],
        { cwd: options.webAdminDirectory, stdio: 'inherit' },
      )
      if (buildResult.status !== 0) throw new Error(`WebAdmin 构建失败，退出码：${buildResult.status}`)
    }

    const result = await publishBuild(options)
    console.log([
      'WebAdmin 发布完成',
      `当前版本资源 ${result.currentAssets} 个`,
      `保留旧资源 ${result.retainedAssets} 个`,
      `清理过期资源 ${result.removedAssets} 个`,
      `入口引用校验 ${result.indexAssetReferences} 个`,
    ].join('；'))
  } finally {
    if (temporaryDirectory) await rm(temporaryDirectory, { recursive: true, force: true })
  }
}

const isDirectExecution = process.argv[1]
  && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)

if (isDirectExecution) {
  run().catch((error) => {
    console.error(error.message || error)
    process.exitCode = 1
  })
}
