import { normalizeLocale } from '@/i18n/locale'

const ARCHIVE_LABELS = {
  survey: {
    'zh-CN': '勘察档案',
    'en-US': 'Survey_Archive',
    'id-ID': 'Arsip_Survei',
  },
  opening: {
    'zh-CN': '开站档案',
    'en-US': 'Opening_Archive',
    'id-ID': 'Arsip_Pembukaan',
  },
  ssv: {
    'zh-CN': 'SSV档案',
    'en-US': 'SSV_Archive',
    'id-ID': 'Arsip_SSV',
  },
}

const pad2 = (value) => String(value).padStart(2, '0')

const normalizeTimestamp = (input) => {
  const date = input ? new Date(input) : new Date()
  const target = Number.isNaN(date.getTime()) ? new Date() : date
  return `${target.getFullYear()}${pad2(target.getMonth() + 1)}${pad2(target.getDate())}_${pad2(target.getHours())}${pad2(target.getMinutes())}`
}

const sanitizePart = (value, fallback = 'NA') => {
  const text = String(value || '').trim() || fallback
  return text.replace(/[\\/:*?"<>|]/g, '-').replace(/\s+/g, '_')
}

const resolveArchiveLabel = (archiveType, locale) => {
  const type = ARCHIVE_LABELS[archiveType] || ARCHIVE_LABELS.survey
  const normalizedLocale = normalizeLocale(locale)
  return type[normalizedLocale] || type['zh-CN']
}

export const buildArchiveExportName = ({
  archiveType,
  locale,
  siteCode,
  siteName,
  version,
  updatedAt,
  ext,
}) => {
  const label = resolveArchiveLabel(archiveType, locale)
  const code = sanitizePart(siteCode, 'NA')
  const name = sanitizePart(siteName, 'NA')
  const ver = Number.isFinite(Number(version)) && Number(version) > 0 ? Number(version) : 1
  const ts = normalizeTimestamp(updatedAt)
  const fileExt = sanitizePart(ext || 'pdf', 'pdf')
  const raw = `${label}_${code}_${name}_v${ver}_${ts}.${fileExt}`
  return raw.replace(/[\\/:*?"<>|]/g, '-').replace(/\s+/g, '_')
}

