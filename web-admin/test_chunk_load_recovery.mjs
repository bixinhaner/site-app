import assert from 'node:assert/strict'
import test from 'node:test'

import {
  CHUNK_RECOVERY_STORAGE_KEY,
  createChunkLoadRecovery,
  installChunkLoadRecovery,
  isChunkLoadError,
} from './src/utils/chunkLoadRecovery.js'

const createStorage = () => {
  const values = new Map()
  return {
    getItem: key => values.get(key) ?? null,
    removeItem: key => values.delete(key),
    setItem: (key, value) => values.set(key, value),
  }
}

test('recognizes Vite lazy module and CSS preload failures', () => {
  assert.equal(isChunkLoadError(new TypeError('Failed to fetch dynamically imported module: /assets/Page-old.js')), true)
  assert.equal(isChunkLoadError(new Error('Unable to preload CSS for /assets/Page-old.css')), true)
  assert.equal(isChunkLoadError(new Error('Request failed with status code 500')), false)
})

test('reloads the intended route once and records the recovery attempt', () => {
  const storage = createStorage()
  const reloads = []
  const recovery = createChunkLoadRecovery({
    location: { pathname: '/dashboard', search: '', hash: '' },
    storage,
    now: () => 1_000,
    reload: targetPath => reloads.push(targetPath),
  })

  assert.equal(recovery.handle(
    new TypeError('Failed to fetch dynamically imported module'),
    { targetPath: '/work-orders/review?id=123' },
  ), true)
  assert.deepEqual(reloads, ['/work-orders/review?id=123'])
  assert.deepEqual(JSON.parse(storage.getItem(CHUNK_RECOVERY_STORAGE_KEY)), {
    targetPath: '/work-orders/review?id=123',
    attemptedAt: 1_000,
  })
})

test('shows a retry action instead of entering a reload loop', () => {
  const storage = createStorage()
  const reloads = []
  const fallbacks = []
  storage.setItem(CHUNK_RECOVERY_STORAGE_KEY, JSON.stringify({
    targetPath: '/sites/planning/84',
    attemptedAt: 1_000,
  }))

  const recovery = createChunkLoadRecovery({
    location: { pathname: '/sites/planning/84', search: '', hash: '' },
    storage,
    now: () => 10_000,
    reload: targetPath => reloads.push(targetPath),
    showFallback: payload => fallbacks.push(payload),
  })

  assert.equal(recovery.handle(
    new Error('Importing a module script failed'),
    { targetPath: '/sites/planning/84' },
  ), true)
  assert.equal(reloads.length, 0)
  assert.equal(fallbacks.length, 1)

  fallbacks[0].retry()
  assert.deepEqual(reloads, ['/sites/planning/84'])
  assert.equal(storage.getItem(CHUNK_RECOVERY_STORAGE_KEY), null)
})

test('clears a recovery marker only after the same route loads successfully', () => {
  const storage = createStorage()
  storage.setItem(CHUNK_RECOVERY_STORAGE_KEY, JSON.stringify({
    targetPath: '/inventory/list',
    attemptedAt: 1_000,
  }))
  const recovery = createChunkLoadRecovery({ storage })

  recovery.clear('/dashboard')
  assert.notEqual(storage.getItem(CHUNK_RECOVERY_STORAGE_KEY), null)
  recovery.clear('/inventory/list')
  assert.equal(storage.getItem(CHUNK_RECOVERY_STORAGE_KEY), null)
})

test('keeps the target route across a failed navigation and clears it after success', () => {
  const storage = createStorage()
  const replacedPaths = []
  const hooks = {}
  const originalWindow = globalThis.window
  globalThis.window = {
    location: {
      pathname: '/dashboard',
      search: '',
      hash: '',
      reload: () => replacedPaths.push('/dashboard'),
      replace: targetPath => replacedPaths.push(targetPath),
    },
    sessionStorage: storage,
    addEventListener: (name, callback) => {
      hooks[name] = callback
    },
  }
  const router = {
    beforeEach: callback => { hooks.beforeEach = callback },
    afterEach: callback => { hooks.afterEach = callback },
    onError: callback => { hooks.onError = callback },
  }

  try {
    installChunkLoadRecovery(router)
    hooks.beforeEach({ fullPath: '/work-orders/review?id=123' })
    let prevented = false
    hooks['vite:preloadError']({
      payload: new Error('Failed to fetch dynamically imported module'),
      preventDefault: () => { prevented = true },
    })

    assert.equal(prevented, true)
    assert.deepEqual(replacedPaths, ['/work-orders/review?id=123'])
    assert.notEqual(storage.getItem(CHUNK_RECOVERY_STORAGE_KEY), null)

    hooks.afterEach(
      { fullPath: '/work-orders/review?id=123' },
      { fullPath: '/dashboard' },
      new Error('navigation failed'),
    )
    assert.notEqual(storage.getItem(CHUNK_RECOVERY_STORAGE_KEY), null)

    hooks.afterEach(
      { fullPath: '/work-orders/review?id=123' },
      { fullPath: '/dashboard' },
      undefined,
    )
    assert.equal(storage.getItem(CHUNK_RECOVERY_STORAGE_KEY), null)
  } finally {
    globalThis.window = originalWindow
  }
})
