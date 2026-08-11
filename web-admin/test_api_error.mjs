import assert from 'node:assert/strict'
import test from 'node:test'

import { getApiErrorMessage, getApiErrorStatus } from './src/utils/apiError.js'

test('reads an Axios conflict response', () => {
  const error = {
    response: {
      status: 409,
      data: { detail: '该工单仍绑定 2 台设备' },
    },
  }

  assert.equal(getApiErrorStatus(error), 409)
  assert.equal(getApiErrorMessage(error, '作废失败'), '该工单仍绑定 2 台设备')
})

test('supports normalized errors and fallback messages', () => {
  assert.equal(getApiErrorStatus({ status: '409' }), 409)
  assert.equal(
    getApiErrorMessage({ data: { detail: '请先解绑设备' } }, '作废失败'),
    '请先解绑设备'
  )
  assert.equal(getApiErrorMessage({}, '作废失败'), '作废失败')
})

test('formats validation detail arrays without leaking objects', () => {
  const error = {
    response: {
      data: {
        detail: [{ msg: '字段缺失' }, { message: '格式错误' }],
      },
    },
  }

  assert.equal(getApiErrorMessage(error, '请求失败'), '字段缺失；格式错误')
})
