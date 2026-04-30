const STORAGE_KEYS = {
  SESSION_ID: 'smart-service_session_id',
  USER_ID: 'smart-service_user_id',
}

function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

export function getSessionId() {
  let id = localStorage.getItem(STORAGE_KEYS.SESSION_ID)
  if (!id) {
    id = generateUUID()
    localStorage.setItem(STORAGE_KEYS.SESSION_ID, id)
  }
  return id
}

export function setSessionId(id) {
  localStorage.setItem(STORAGE_KEYS.SESSION_ID, id)
}

export function getUserId() {
  let id = localStorage.getItem(STORAGE_KEYS.USER_ID)
  if (!id) {
    id = generateUUID()
    localStorage.setItem(STORAGE_KEYS.USER_ID, id)
  }
  return id
}

export function setUserId(id) {
  localStorage.setItem(STORAGE_KEYS.USER_ID, id)
}
