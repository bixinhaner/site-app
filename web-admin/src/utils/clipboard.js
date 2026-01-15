export const copyTextToClipboard = async (text) => {
  const value = String(text ?? '').trim()
  if (!value) return false

  const clipboard = navigator?.clipboard
  if (clipboard?.writeText && window?.isSecureContext) {
    try {
      await clipboard.writeText(value)
      return true
    } catch {
      // 继续走降级方案
    }
  }

  try {
    const textArea = document.createElement('textarea')
    textArea.value = value
    textArea.setAttribute('readonly', '')
    textArea.style.position = 'fixed'
    textArea.style.top = '0'
    textArea.style.left = '0'
    textArea.style.opacity = '0'
    textArea.style.pointerEvents = 'none'
    document.body.appendChild(textArea)
    textArea.focus()
    textArea.select()
    textArea.setSelectionRange(0, textArea.value.length)

    const ok = document.execCommand('copy')
    document.body.removeChild(textArea)
    return ok
  } catch {
    return false
  }
}

