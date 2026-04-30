<template>
  <div class="chat-widget" :class="{ 'is-open': isOpen }">
    <Transition name="widget-switch" mode="out-in">
      <button
        v-if="!isOpen"
        key="trigger"
        class="chat-trigger"
        @click="toggleChat"
        aria-label="打开客服聊天"
      >
        <div class="trigger-content">
          <div class="trigger-icon-wrapper">
            <svg class="icon" viewBox="0 0 24 24">
              <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
            </svg>
          </div>
          <span class="trigger-text">客服咨询</span>
        </div>
        <span class="badge" v-if="unreadCount > 0">{{ unreadCount }}</span>
      </button>

      <div v-else key="window" class="chat-window">
        <div class="chat-header">
          <div class="header-content">
            <div class="avatar-wrapper">
              <div class="avatar">🎁</div>
              <span class="status-dot" :class="{ online: isConnected }"></span>
            </div>
            <div class="header-info">
              <h3>保军礼品助手</h3>
              <span class="status-text">
                {{ isConnected ? '为您服务中' : '正在连接...' }}
              </span>
            </div>
          </div>
          <button class="close-btn" @click="toggleChat" aria-label="关闭聊天">
            <svg viewBox="0 0 24 24">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
            </svg>
          </button>
        </div>

        <MessageList
          :messages="messages"
          :loading="isLoading"
          :loading-hint="loadingHint"
        />

        <ContactForm
          v-if="shouldShowContactForm"
          @submit="handleContactSubmit"
          @close="shouldShowContactForm = false"
        />

        <MessageInput
          ref="messageInputRef"
          :disabled="!isConnected || isLoading"
          @send="handleSendMessage"
        />
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useChatStore } from '@/stores/chat'
import MessageList from './MessageList.vue'
import MessageInput from './MessageInput.vue'
import ContactForm from './ContactForm.vue'
import { socketService } from '@/api/socket'

const chatStore = useChatStore()

const isOpen = ref(false)
const isLoading = ref(false)
const loadingHint = ref('')
const shouldShowContactForm = ref(false)
const messageInputRef = ref(null)

const messages = computed(() => chatStore.messages)
const isConnected = computed(() => chatStore.isConnected)
const unreadCount = computed(() => chatStore.unreadCount)

function toggleChat() {
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    chatStore.markAsRead()
  }
}

function handleSendMessage(content) {
  if (!content.trim()) return

  chatStore.addMessage({
    role: 'user',
    content: content.trim(),
  })

  isLoading.value = true
  loadingHint.value = '正在处理您的请求...'

  socketService.sendMessage({
    message: content.trim(),
    session_id: chatStore.sessionId,
    user_id: chatStore.userId,
  })
}

function handleContactSubmit(contactInfo) {
  chatStore.setContactInfo(contactInfo)
  shouldShowContactForm.value = false

  socketService.sendMessage({
    message: `我的联系方式：${contactInfo.phone || contactInfo.email}`,
    session_id: chatStore.sessionId,
    user_id: chatStore.userId,
  })
}

onMounted(() => {
  socketService.connect()

  socketService.on('message', (data) => {
    isLoading.value = false
    loadingHint.value = ''

    chatStore.addMessage({
      role: 'assistant',
      content: data.message,
      intent: data.intent,
      metadata: data.metadata,
    })

    if (data.should_collect_contact && !chatStore.hasContactInfo) {
      shouldShowContactForm.value = true
    }

    if (!isOpen.value) {
      chatStore.incrementUnread()
    }

    nextTick(() => {
      messageInputRef.value?.focus()
    })
  })

  socketService.on('status', (data) => {
    if (data && data.text) {
      loadingHint.value = data.text
    }
  })

  socketService.on('contact_collected', (contactInfo) => {
    chatStore.setContactInfo(contactInfo)
  })

  socketService.on('error', (error) => {
    isLoading.value = false
    loadingHint.value = ''
    console.error('Socket error:', error)
  })
})

onUnmounted(() => {
  socketService.disconnect()
})
</script>

<style scoped>
.chat-widget {
  position: fixed;
  bottom: 30px;
  right: 30px;
  z-index: 9999;
  font-family: 'PingFang SC', 'Microsoft YaHei', -apple-system, sans-serif;
}

.chat-trigger {
  height: 56px;
  padding: 0 24px;
  border-radius: 28px;
  background: linear-gradient(135deg, #ff6b6b 0%, #ff4757 100%);
  border: none;
  cursor: pointer;
  box-shadow: 0 8px 24px rgba(255, 71, 87, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

.chat-trigger:hover {
  transform: translateY(-5px) scale(1.02);
  box-shadow: 0 12px 28px rgba(255, 71, 87, 0.4);
}

.trigger-content {
  display: flex;
  align-items: center;
  gap: 10px;
}

.trigger-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  animation: bounce 2s infinite;
}

.chat-trigger .icon {
  width: 24px;
  height: 24px;
  fill: white;
}

.trigger-text {
  color: white;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 1px;
  white-space: nowrap;
}

.badge {
  position: absolute;
  top: -8px;
  right: -8px;
  background: #ffd93d;
  color: #333;
  border-radius: 12px;
  padding: 2px 8px;
  font-size: 12px;
  font-weight: 800;
  min-width: 24px;
  text-align: center;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  border: 2px solid white;
}

.chat-window {
  width: 400px;
  height: 640px;
  background: #fff9f9;
  border-radius: 24px;
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid rgba(255, 71, 87, 0.1);
}

.chat-header {
  padding: 20px;
  background: linear-gradient(135deg, #ff6b6b 0%, #ff4757 100%);
  color: white;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
  position: relative;
}

.chat-header::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 10px;
  background: radial-gradient(circle at 10px -5px, transparent 12px, rgba(255,255,255,0.1) 13px);
  background-size: 20px 20px;
}

.header-content {
  display: flex;
  align-items: center;
  gap: 12px;
}

.avatar-wrapper {
  position: relative;
  width: 44px;
  height: 44px;
}

.avatar {
  width: 100%;
  height: 100%;
  background: white;
  border-radius: 15px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

.status-dot {
  position: absolute;
  bottom: -2px;
  right: -2px;
  width: 12px;
  height: 12px;
  background: #95a5a6;
  border: 2px solid #ff4757;
  border-radius: 50%;
}

.status-dot.online {
  background: #2ecc71;
  box-shadow: 0 0 8px #2ecc71;
}

.header-info h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.status-text {
  font-size: 12px;
  opacity: 0.9;
  display: block;
  margin-top: 2px;
}

.close-btn {
  background: rgba(255, 255, 255, 0.2);
  border: none;
  cursor: pointer;
  padding: 6px;
  border-radius: 10px;
  transition: all 0.2s;
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.3);
  transform: rotate(90deg);
}

.close-btn svg {
  width: 20px;
  height: 20px;
  fill: white;
}

/* Transition: out-in mode 避免两个元素同时渲染导致闪现 */
.widget-switch-leave-active,
.widget-switch-enter-active {
  transition: all 0.3s ease;
}

.widget-switch-leave-to {
  opacity: 0;
  transform: scale(0.8);
}

.widget-switch-enter-active {
  transition: all 0.4s cubic-bezier(0.165, 0.84, 0.44, 1);
}

.widget-switch-enter-from {
  opacity: 0;
  transform: translateY(30px) scale(0.95);
}

@keyframes bounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-5px); }
}

@media (max-width: 768px) {
  .chat-widget {
    bottom: 0;
    right: 0;
  }
  .chat-window {
    width: 100vw;
    height: 100vh;
    border-radius: 0;
    position: fixed;
    top: 0;
    left: 0;
  }
}
</style>
