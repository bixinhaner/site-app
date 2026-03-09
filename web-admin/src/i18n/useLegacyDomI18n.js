import { nextTick, onBeforeUnmount, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { containsCJK, isEnglishLocale, translateLegacyText } from './translator'

const ATTR_NAMES = ['placeholder', 'title', 'aria-label', 'alt']
const TEXT_BLACKLIST = new Set(['SCRIPT', 'STYLE'])

const toDatasetKey = (attr, prefix = 'i18nOrig') => `${prefix}${attr.replace(/-([a-z])/g, (_, c) => c.toUpperCase()).replace(/^([a-z])/, (_, c) => c.toUpperCase())}`
const toOriginalDatasetKey = (attr) => toDatasetKey(attr, 'i18nOrig')
const toTranslatedDatasetKey = (attr) => toDatasetKey(attr, 'i18nTranslated')

const translateElementAttributes = (element, english) => {
  if (!(element instanceof HTMLElement)) return

  for (const attr of ATTR_NAMES) {
    const originalKey = toOriginalDatasetKey(attr)
    const translatedKey = toTranslatedDatasetKey(attr)
    const hasAttr = element.hasAttribute(attr)
    const currentValue = hasAttr ? (element.getAttribute(attr) || '') : ''
    const storedOriginal = element.dataset[originalKey] || ''
    const storedTranslated = element.dataset[translatedKey] || ''
    const currentHasCJK = containsCJK(currentValue)

    if (!hasAttr) {
      delete element.dataset[originalKey]
      delete element.dataset[translatedKey]
      continue
    }

    if (!english) {
      if (currentHasCJK) {
        element.dataset[originalKey] = currentValue
        delete element.dataset[translatedKey]
        continue
      }

      if (storedOriginal && storedTranslated && currentValue === storedTranslated && containsCJK(storedOriginal)) {
        element.setAttribute(attr, storedOriginal)
        element.dataset[originalKey] = storedOriginal
        delete element.dataset[translatedKey]
        continue
      }

      if (currentValue) {
        element.dataset[originalKey] = currentValue
      } else {
        delete element.dataset[originalKey]
      }
      delete element.dataset[translatedKey]
      continue
    }

    if (currentHasCJK) {
      element.dataset[originalKey] = currentValue
    } else if (storedTranslated && currentValue !== storedTranslated) {
      // A component just rendered a fresh non-CJK value, so drop stale bridge cache.
      if (currentValue) {
        element.dataset[originalKey] = currentValue
      } else {
        delete element.dataset[originalKey]
      }
      delete element.dataset[translatedKey]
      continue
    } else if (!storedOriginal && currentValue) {
      element.dataset[originalKey] = currentValue
    }

    const sourceValue = element.dataset[originalKey] || currentValue || ''
    if (!sourceValue || !containsCJK(sourceValue)) {
      delete element.dataset[translatedKey]
      continue
    }

    let nextValue = sourceValue
    const translated = translateLegacyText(sourceValue)
    // If a component has already rendered an English value via i18n,
    // avoid forcing it back to the original Chinese text.
    if (translated === sourceValue && currentValue && !containsCJK(currentValue)) {
      delete element.dataset[translatedKey]
      continue
    }
    nextValue = translated

    if (nextValue !== currentValue) {
      element.setAttribute(attr, nextValue)
    }

    if (nextValue !== sourceValue) {
      element.dataset[translatedKey] = nextValue
    } else {
      delete element.dataset[translatedKey]
    }
  }
}

const translateTextNode = (node, english) => {
  const parentTag = node.parentElement?.tagName
  if (parentTag && TEXT_BLACKLIST.has(parentTag)) return

  const currentText = node.nodeValue || ''
  const storedOriginal = node.__i18nOriginalText || ''
  const storedTranslated = node.__i18nTranslatedText || ''
  const originalText = storedOriginal || currentText || ''
  const currentHasCJK = containsCJK(currentText)
  const originalHasCJK = containsCJK(originalText)
  if (!currentHasCJK && !originalHasCJK) return

  if (!english) {
    if (currentHasCJK) {
      node.__i18nOriginalText = currentText
      node.__i18nTranslatedText = ''
      return
    }

    if (storedOriginal && storedTranslated && currentText === storedTranslated && containsCJK(storedOriginal)) {
      node.nodeValue = storedOriginal
      node.__i18nOriginalText = storedOriginal
      node.__i18nTranslatedText = ''
      return
    }

    node.__i18nOriginalText = currentText
    node.__i18nTranslatedText = ''
    return
  }

  if (currentHasCJK) {
    node.__i18nOriginalText = currentText
  } else if (storedTranslated && currentText !== storedTranslated) {
    // A component produced a fresh non-CJK value while in EN mode.
    // Sync it to avoid stale Chinese source text overriding new UI.
    node.__i18nOriginalText = currentText
    node.__i18nTranslatedText = ''
  } else if (!storedOriginal) {
    node.__i18nOriginalText = currentText
  }

  const sourceText = node.__i18nOriginalText || currentText || ''
  if (!sourceText || !containsCJK(sourceText)) {
    node.__i18nTranslatedText = ''
    return
  }

  let targetText = sourceText
  const translated = translateLegacyText(sourceText)
  // If Vue i18n already produced an English text node, keep it.
  if (translated === sourceText && node.nodeValue && !containsCJK(node.nodeValue)) {
    node.__i18nTranslatedText = ''
    return
  }
  targetText = translated

  if (targetText !== node.nodeValue) {
    node.nodeValue = targetText
  }

  if (targetText !== sourceText) {
    node.__i18nTranslatedText = targetText
  } else {
    node.__i18nTranslatedText = ''
  }
}
const applyTranslation = (root, english) => {
  if (!root) return

  if (root instanceof HTMLElement) {
    translateElementAttributes(root, english)
    const elements = root.querySelectorAll('*')
    for (const element of elements) {
      translateElementAttributes(element, english)
    }
  }

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
  let textNode = walker.nextNode()
  while (textNode) {
    translateTextNode(textNode, english)
    textNode = walker.nextNode()
  }
}

export const useLegacyDomI18n = (getRoot = () => document.body) => {
  const { locale } = useI18n()
  let observer = null
  let rafId = 0
  const mapLoadedHandler = () => schedule()

  const run = () => {
    const root = getRoot()
    if (!root) return
    applyTranslation(root, isEnglishLocale())
  }

  const schedule = () => {
    if (typeof window === 'undefined') return
    window.cancelAnimationFrame(rafId)
    rafId = window.requestAnimationFrame(run)
  }

  onMounted(() => {
    nextTick(() => schedule())

    const root = getRoot()
    if (!root || typeof MutationObserver === 'undefined') return

    observer = new MutationObserver(() => {
      schedule()
    })

    observer.observe(root, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
      attributeFilter: ATTR_NAMES,
    })

    if (typeof window !== 'undefined') {
      window.addEventListener('legacy-i18n-map-loaded', mapLoadedHandler)
    }
  })

  watch(locale, () => {
    nextTick(() => schedule())
  })

  onBeforeUnmount(() => {
    if (observer) {
      observer.disconnect()
      observer = null
    }
    if (typeof window !== 'undefined') {
      window.cancelAnimationFrame(rafId)
      window.removeEventListener('legacy-i18n-map-loaded', mapLoadedHandler)
    }
  })
}
