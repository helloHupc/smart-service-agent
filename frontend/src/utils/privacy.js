import { marked } from 'marked'

marked.setOptions({ breaks: true, gfm: false })

export function maskPhone(phone) {
  if (!phone || phone.length !== 11) return phone
  return phone.slice(0, 3) + '****' + phone.slice(7)
}

export function maskPhoneInText(text) {
  if (!text) return text
  return text.replace(/(1[3-9]\d)\d{4}(\d{4})/g, '$1****$2')
}

export function renderContent(text, role) {
  if (!text) return ''
  let result = maskPhoneInText(text)
  if (role === 'assistant') {
    result = marked.parse(result)
  }
  return result
}
