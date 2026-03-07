const EMPTY_FIELD_VALUES = [undefined, null, '']

export const buildFieldValueMap = (dataValue) => {
  const out = {}
  if (!Array.isArray(dataValue)) return out
  dataValue.forEach((item) => {
    if (!item || typeof item !== 'object') return
    const key = String(item.field_name || item.field_id || item.key || item.name || '').trim()
    if (!key) return
    out[key] = item.value
  })
  return out
}

const evaluateDependencyCondition = (value, condition = {}) => {
  const operator = String(condition?.operator || 'eq').trim()
  const expected = condition?.value

  if (operator === 'eq') return value === expected
  if (operator === 'neq') return value !== expected
  if (operator === 'in') return Array.isArray(expected) ? expected.includes(value) : false
  if (operator === 'not_in') return Array.isArray(expected) ? !expected.includes(value) : true
  if (operator === 'contains') {
    if (Array.isArray(value)) return value.includes(expected)
    return String(value ?? '').includes(String(expected ?? ''))
  }
  if (operator === 'not_contains') {
    if (Array.isArray(value)) return !value.includes(expected)
    return !String(value ?? '').includes(String(expected ?? ''))
  }
  if (operator === 'empty') {
    return value == null || value === '' || (Array.isArray(value) && value.length === 0)
  }
  if (operator === 'not_empty') {
    return !(value == null || value === '' || (Array.isArray(value) && value.length === 0))
  }
  if (operator === 'true') return value === true || value === 'true'
  if (operator === 'false') return value === false || value === 'false'
  return false
}

export const isFieldVisible = (field = {}, fieldValues = {}) => {
  let hidden = Boolean(field?.hidden)
  const dependencies = Array.isArray(field?.dependencies) ? field.dependencies : []

  dependencies.forEach((dependency) => {
    if (!dependency || String(dependency.type || '').toLowerCase() !== 'visibility') return
    const sourceField = String(dependency.source_field || '').trim()
    const sourceValue = fieldValues[sourceField]
    const matched = evaluateDependencyCondition(sourceValue, dependency.condition || {})
    if (matched) {
      hidden = !Boolean(dependency.effect?.visible ?? true)
    } else {
      hidden = false
    }
  })

  return !hidden
}

export const serializeDataValue = (fields = [], fieldValues = {}) => {
  const fieldIds = Array.isArray(fields)
    ? fields
      .map(field => String(field?.field_id || '').trim())
      .filter(Boolean)
    : []

  const unionKeys = [...new Set([...fieldIds, ...Object.keys(fieldValues || {})])]
  return unionKeys.map((fieldId) => ({
    field_name: fieldId,
    value: fieldValues[fieldId],
  }))
}

export const isEmptyFieldValue = (value) => {
  if (EMPTY_FIELD_VALUES.includes(value)) return true
  if (Array.isArray(value)) return value.length === 0
  return false
}

export const getPhotoFieldSections = (item, fieldValues = {}) => {
  const fields = Array.isArray(item?.fields) ? item.fields : []
  const photoFields = fields.filter(field => field?.allow_photo)
  const visiblePhotoFields = photoFields.filter(field => isFieldVisible(field, fieldValues))

  if (item?.required_type === 'photo' || visiblePhotoFields.length === 0) {
    return [{
      key: '__general__',
      label: '检查照片',
      fieldId: '',
      required: item?.required_type === 'photo',
    }]
  }

  return visiblePhotoFields.map((field) => ({
    key: String(field.field_id || ''),
    label: String(field.label || field.field_id || '字段照片'),
    fieldId: String(field.field_id || ''),
    required: Boolean(field.photo_required),
  }))
}

export const isPhotoRequirementSatisfied = (item, fieldValues = {}) => {
  const photos = Array.isArray(item?.photos) ? item.photos : []
  const sections = getPhotoFieldSections(item, fieldValues)
  if (!sections.length) return true

  return sections.every((section) => {
    if (!section.required) return true
    if (!section.fieldId) return photos.length > 0
    return photos.some(photo => String(photo.field_id || '') === section.fieldId)
  })
}

export const isDeviceSlotItem = (item) => {
  const sectorId = String(item?.sector_id || '').trim()
  const band = String(item?.band || '').trim()
  return Boolean(sectorId && band)
}

const arrayBufferToHex = (buffer) => {
  const bytes = new Uint8Array(buffer)
  return Array.from(bytes).map(byte => byte.toString(16).padStart(2, '0')).join('')
}

export const computeFileSha256 = async (file) => {
  const buffer = await file.arrayBuffer()
  const digest = await window.crypto.subtle.digest('SHA-256', buffer)
  return arrayBufferToHex(digest)
}

const loadImage = (source) => new Promise((resolve, reject) => {
  const image = new Image()
  image.onload = () => resolve(image)
  image.onerror = reject
  image.src = source
})

export const buildLocalUploadWatermarkFile = async (file, lines = []) => {
  const objectUrl = URL.createObjectURL(file)

  try {
    const image = await loadImage(objectUrl)
    const canvas = document.createElement('canvas')
    canvas.width = image.naturalWidth || image.width
    canvas.height = image.naturalHeight || image.height
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('无法创建图片画布')

    ctx.drawImage(image, 0, 0, canvas.width, canvas.height)

    const textLines = lines.filter(Boolean)
    const fontSize = Math.max(20, Math.round(canvas.width / 45))
    const padding = Math.max(16, Math.round(fontSize * 0.6))
    const lineHeight = Math.round(fontSize * 1.4)
    ctx.font = `${fontSize}px sans-serif`

    const maxWidth = textLines.reduce((max, line) => Math.max(max, ctx.measureText(line).width), 0)
    const boxWidth = Math.min(canvas.width - padding * 2, Math.ceil(maxWidth + padding * 2))
    const boxHeight = textLines.length * lineHeight + padding * 2
    const x = padding
    const y = Math.max(padding, canvas.height - boxHeight - padding)

    ctx.fillStyle = 'rgba(0, 0, 0, 0.68)'
    ctx.fillRect(x, y, boxWidth, boxHeight)

    ctx.fillStyle = '#ff8f1f'
    ctx.font = `${fontSize}px sans-serif`
    textLines.forEach((line, index) => {
      ctx.fillText(line, x + padding, y + padding + fontSize + index * lineHeight)
    })

    const blob = await new Promise((resolve, reject) => {
      canvas.toBlob((result) => {
        if (result) resolve(result)
        else reject(new Error('生成本地水印图片失败'))
      }, file.type || 'image/jpeg', 0.92)
    })

    return new File([blob], file.name, {
      type: blob.type || file.type || 'image/jpeg',
      lastModified: Date.now(),
    })
  } finally {
    URL.revokeObjectURL(objectUrl)
  }
}

export const formatFileSize = (size) => {
  const value = Number(size || 0)
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}
