import { nextTick, onBeforeUnmount, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { containsCJK, isEnglishLocale, translateLegacyText } from './translator'

const ATTR_NAMES = ['placeholder', 'title', 'aria-label', 'alt']
const TEXT_BLACKLIST = new Set(['SCRIPT', 'STYLE'])

const toDatasetKey = (attr) => `i18nOrig${attr.replace(/-([a-z])/g, (_, c) => c.toUpperCase()).replace(/^([a-z])/, (_, c) => c.toUpperCase())}`

const translateElementAttributes = (element, english) => {
  if (!(element instanceof HTMLElement)) return

  for (const attr of ATTR_NAMES) {
    const datasetKey = toDatasetKey(attr)
    const currentValue = element.getAttribute(attr)
    const storedOriginal = element.dataset[datasetKey] || ''
    const originalValue = storedOriginal || currentValue || ''

    if (!originalValue || !containsCJK(originalValue)) continue

    if (!english) {
      if (currentValue && containsCJK(currentValue)) {
        element.dataset[datasetKey] = currentValue
        continue
      }

      if (storedOriginal && storedOriginal !== currentValue) {
        element.setAttribute(attr, storedOriginal)
      }
      continue
    }

    if (currentValue && containsCJK(currentValue)) {
      element.dataset[datasetKey] = currentValue
    } else if (!element.dataset[datasetKey]) {
      element.dataset[datasetKey] = originalValue
    }

    let nextValue = element.dataset[datasetKey]
    const translated = translateLegacyText(element.dataset[datasetKey])
    // If a component has already rendered an English value via i18n,
    // avoid forcing it back to the original Chinese text.
    if (translated === element.dataset[datasetKey] && currentValue && !containsCJK(currentValue)) {
      continue
    }
    nextValue = translated

    if (nextValue !== currentValue) {
      element.setAttribute(attr, nextValue)
    }
  }
}

const translateTextNode = (node, english) => {
  const parentTag = node.parentElement?.tagName
  if (parentTag && TEXT_BLACKLIST.has(parentTag)) return

  const currentText = node.nodeValue || ''
  const storedOriginal = node.__i18nOriginalText || ''
  const originalText = storedOriginal || currentText || ''
  const currentHasCJK = containsCJK(currentText)
  const originalHasCJK = containsCJK(originalText)
  if (!currentHasCJK && !originalHasCJK) return

  if (!english) {
    if (currentHasCJK) {
      node.__i18nOriginalText = currentText
      return
    }

    if (storedOriginal && storedOriginal !== currentText) {
      node.nodeValue = storedOriginal
    }
    return
  }

  if (currentHasCJK || !storedOriginal) {
    node.__i18nOriginalText = currentText
  }

  let targetText = node.__i18nOriginalText
  const translated = translateLegacyText(node.__i18nOriginalText)
  // If Vue i18n already produced an English text node, keep it.
  if (translated === node.__i18nOriginalText && node.nodeValue && !containsCJK(node.nodeValue)) {
    return
  }
  targetText = translated

  if (targetText !== node.nodeValue) {
    node.nodeValue = targetText
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
