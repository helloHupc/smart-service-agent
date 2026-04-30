import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getSessionId, getUserId } from '@/utils/storage'

export const useChatStore = defineStore('chat', () => {
  const messages = ref([])
  const sessionId = ref(getSessionId())
  const userId = ref(getUserId())
  const isConnected = ref(false)
  const unreadCount = ref(0)
  const contactInfo = ref(null)
  const isLoading = ref(false)

  const hasContactInfo = computed(() => {
    return !!(contactInfo.value?.phone || contactInfo.value?.email)
  })

  function addMessage(message) {
    messages.value.push({
      ...message,
      timestamp: message.timestamp || new Date().toISOString(),
    })
  }

  function setConnected(status) {
    isConnected.value = status
  }

  function incrementUnread() {
    unreadCount.value++
  }

  function markAsRead() {
    unreadCount.value = 0
  }

  function setContactInfo(info) {
    contactInfo.value = info
  }

  function setLoading(loading) {
    isLoading.value = loading
  }

  function clearMessages() {
    messages.value = []
  }

  return {
    messages,
    sessionId,
    userId,
    isConnected,
    unreadCount,
    contactInfo,
    isLoading,
    hasContactInfo,
    addMessage,
    setConnected,
    incrementUnread,
    markAsRead,
    setContactInfo,
    setLoading,
    clearMessages,
  }
})
