import assert from 'node:assert/strict'
import { mkdir, mkdtemp, readFile, rm, stat, utimes, writeFile } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

import { publishBuild } from './publish-web-admin.mjs'

const writeBuild = async (directory, assetName) => {
  await mkdir(path.join(directory, 'assets'), { recursive: true })
  await writeFile(path.join(directory, 'index.html'), `<script type="module" src="/assets/${assetName}"></script>`)
  await writeFile(path.join(directory, 'assets', assetName), `console.log('${assetName}')`)
}

test('publishes assets before the new index and retains recent previous hashes', async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'siteapp-publish-test-'))
  const dist = path.join(root, 'dist')
  const firstBuild = path.join(root, 'build-1')
  const secondBuild = path.join(root, 'build-2')
  const now = Date.UTC(2026, 7, 11)

  try {
    await writeBuild(firstBuild, 'page-v1.js')
    await mkdir(path.join(dist, 'assets'), { recursive: true })
    await writeFile(path.join(dist, 'assets', 'recent-old.js'), 'recent')
    await writeFile(path.join(dist, 'assets', 'expired-old.js'), 'expired')
    await utimes(path.join(dist, 'assets', 'recent-old.js'), new Date(now - 5 * 86_400_000), new Date(now - 5 * 86_400_000))
    await utimes(path.join(dist, 'assets', 'expired-old.js'), new Date(now - 31 * 86_400_000), new Date(now - 31 * 86_400_000))

    const firstResult = await publishBuild({
      sourceBuildDirectory: firstBuild,
      distDirectory: dist,
      retentionDays: 30,
      now,
    })

    assert.equal(firstResult.removedAssets, 1)
    assert.equal((await stat(path.join(dist, 'assets', 'page-v1.js'))).isFile(), true)
    assert.equal((await stat(path.join(dist, 'assets', 'recent-old.js'))).isFile(), true)
    await assert.rejects(stat(path.join(dist, 'assets', 'expired-old.js')))

    await writeBuild(secondBuild, 'page-v2.js')
    const secondResult = await publishBuild({
      sourceBuildDirectory: secondBuild,
      distDirectory: dist,
      retentionDays: 30,
      now: now + 86_400_000,
    })

    assert.equal(secondResult.removedAssets, 0)
    assert.equal((await stat(path.join(dist, 'assets', 'page-v1.js'))).isFile(), true)
    assert.equal((await stat(path.join(dist, 'assets', 'page-v2.js'))).isFile(), true)
    assert.match(await readFile(path.join(dist, 'index.html'), 'utf8'), /page-v2\.js/)
  } finally {
    await rm(root, { recursive: true, force: true })
  }
})
