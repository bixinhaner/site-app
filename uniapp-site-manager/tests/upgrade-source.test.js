import assert from 'node:assert/strict'
import test from 'node:test'

import { bindVersionInfoToSource, isSameUpgradeSource } from '../utils/upgradeSource.js'

test('binds a relative APK path to the server that returned the version', () => {
  const result = bindVersionInfoToSource(
    { version_code: 10049, download_url: '/uploads/apk/app_20260606_170131.apk' },
    'https://siteapp.savannafibre.com/',
  )

  assert.equal(
    result.download_url,
    'https://siteapp.savannafibre.com/uploads/apk/app_20260606_170131.apk',
  )
  assert.equal(result.download_source_base_url, 'https://siteapp.savannafibre.com')
})

test('keeps an absolute APK URL unchanged', () => {
  const result = bindVersionInfoToSource(
    {
      version_code: 10049,
      download_url: 'https://cdn.example.com/releases/site-app.apk',
    },
    'https://siteapp.indonesiacentral.cloudapp.azure.com',
  )

  assert.equal(result.download_url, 'https://cdn.example.com/releases/site-app.apk')
})

test('detects a server switch before download', () => {
  assert.equal(
    isSameUpgradeSource(
      'https://siteapp.savannafibre.com/',
      'https://siteapp.savannafibre.com',
    ),
    true,
  )
  assert.equal(
    isSameUpgradeSource(
      'https://siteapp.savannafibre.com',
      'https://siteapp.indonesiacentral.cloudapp.azure.com',
    ),
    false,
  )
})
