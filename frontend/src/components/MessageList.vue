<template>
  <div class="message-list" ref="listRef">
    <div class="messages">
      <div
        v-for="(message, index) in messages"
        :key="index"
        class="message-wrapper"
        :class="message.role"
      >
        <div class="message">
          <div class="message-content" v-html="renderContent(message.content, message.role)"></div>

          <div
            v-if="message.role === 'assistant' && message.metadata?.retrieved_products?.length"
            class="products"
          >
            <ProductCard
              v-for="product in message.metadata.retrieved_products"
              :key="product.product_id || product.id"
              :product="product"
            />
          </div>

          <div class="message-time">
            {{ formatTime(message.timestamp) }}
          </div>
        </div>
      </div>

      <div v-if="loading" class="message-wrapper assistant">
        <div class="message">
          <div class="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <div v-if="loadingHint" class="loading-hint">
            {{ loadingHint }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import ProductCard from './ProductCard.vue'
import { renderContent } from '@/utils/privacy'

const props = defineProps({
  messages: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
  loadingHint: {
    type: String,
    default: '',
  },
})

const listRef = ref(null)

function formatTime(timestamp) {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  if (isNaN(date.getTime())) return ''
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function scrollToBottom() {
  nextTick(() => {
    if (listRef.value) {
      listRef.value.scrollTop = listRef.value.scrollHeight
    }
  })
}

watch(
  () => props.messages.length,
  () => scrollToBottom(),
)

watch(
  () => props.loading,
  () => scrollToBottom(),
)

defineExpose({ scrollToBottom })
</script>

<style scoped>
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: #fff9f9;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 71, 87, 0.2) transparent;
}

.message-list::-webkit-scrollbar {
  width: 6px;
}

.message-list::-webkit-scrollbar-thumb {
  background-color: rgba(255, 71, 87, 0.2);
  border-radius: 10px;
}

.messages {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.message-wrapper {
  display: flex;
  animation: fadeIn 0.3s ease-out;
}

.message-wrapper.user {
  justify-content: flex-end;
}

.message-wrapper.assistant {
  justify-content: flex-start;
}

.message {
  max-width: 85%;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.message-content {
  padding: 10px 16px;
  font-size: 15px;
  word-wrap: break-word;
  line-height: 1.6;
  white-space: pre-wrap;
  position: relative;
}

.user .message-content {
  background: linear-gradient(135deg, #ff6b6b 0%, #ff4757 100%);
  color: white;
  border-radius: 20px 20px 4px 20px;
  box-shadow: 0 4px 12px rgba(255, 71, 87, 0.2);
}

.assistant .message-content {
  background: white;
  color: #2d3436;
  border-radius: 20px 20px 20px 4px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
  border: 1px solid rgba(255, 71, 87, 0.05);
}

.assistant .message-content :deep(strong) {
  color: #ff4757;
  font-weight: 700;
}

.assistant .message-content :deep(ul),
.assistant .message-content :deep(ol) {
  margin: 0;
  padding-left: 20px;
}

.assistant .message-content :deep(li) {
  margin: 0;
  line-height: 1.5;
}

.assistant .message-content :deep(p) {
  margin: 0;
}

.assistant .message-content :deep(p + p) {
  margin-top: 4px;
}

.assistant .message-content :deep(p:empty) {
  display: none;
}

.assistant .message-content :deep(hr) {
  margin: 4px 0;
  border: none;
  border-top: 1px solid rgba(255, 71, 87, 0.1);
}

.assistant .message-content :deep(em) {
  color: #636e72;
}

.assistant .message-content :deep(h1),
.assistant .message-content :deep(h2),
.assistant .message-content :deep(h3),
.assistant .message-content :deep(h4) {
  margin: 10px 0 6px 0;
  font-weight: 700;
  line-height: 1.4;
}

.message-time {
  font-size: 11px;
  color: #999;
  padding: 0 4px;
}

.products {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 4px;
}

.typing-indicator {
  display: flex;
  gap: 6px;
  padding: 14px 18px;
  background: white;
  border-radius: 20px 20px 20px 4px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
  width: fit-content;
}

.loading-hint {
  margin-top: 8px;
  padding: 8px 16px;
  background: rgba(255, 107, 107, 0.08);
  border-radius: 12px;
  font-size: 13px;
  color: #ff6b6b;
  animation: hintPulse 2s ease-in-out infinite;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ff6b6b;
  animation: typing 1.4s infinite;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing {
  0%, 60%, 100% {
    opacity: 0.3;
    transform: scale(1);
  }
  30% {
    opacity: 1;
    transform: scale(1.3);
  }
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes hintPulse {
  0%, 100% { opacity: 0.7; }
  50% { opacity: 1; }
}
</style>
