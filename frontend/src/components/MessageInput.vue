<template>
  <div class="message-input">
    <textarea
      v-model="inputText"
      :disabled="disabled"
      placeholder="输入您的问题..."
      @keydown.enter.exact.prevent="handleSend"
      rows="1"
      ref="textareaRef"
    />
    <button
      class="send-btn"
      :disabled="disabled || !inputText.trim()"
      @click="handleSend"
      aria-label="发送消息"
    >
      <svg viewBox="0 0 24 24">
        <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
      </svg>
    </button>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  disabled: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['send'])

const inputText = ref('')
const textareaRef = ref(null)

function handleSend() {
  if (!inputText.value.trim() || props.disabled) return

  emit('send', inputText.value)
  inputText.value = ''

  nextTick(() => {
    adjustHeight()
  })
}

function adjustHeight() {
  const el = textareaRef.value
  if (!el) return

  // 重置高度以获取真实的内容高度
  el.style.height = 'auto'
  
  // scrollHeight 包含内容和上下 padding (10px + 10px = 20px)
  // 当 line-height 为 20px 时，单行内容的 scrollHeight 理论上是 40px
  const scrollHeight = el.scrollHeight
  
  // 基础高度为 44px (包含 4px 边框)
  // 我们使用 42px 作为阈值，留出 2px 的容差，确保单行输入时不会增加高度
  if (scrollHeight > 42) {
    const newHeight = scrollHeight + 4 // 加上 4px 的边框高度 (border: 2px * 2)
    el.style.height = Math.min(newHeight, 120) + 'px'
    // 当达到最大高度 120px 时显示滚动条
    el.style.overflowY = newHeight >= 120 ? 'auto' : 'hidden'
  } else {
    el.style.height = '44px'
    el.style.overflowY = 'hidden'
  }
}

watch(inputText, () => {
  nextTick(adjustHeight)
})

defineExpose({
  focus() {
    nextTick(() => {
      textareaRef.value?.focus()
    })
  },
})
</script>

<style scoped>
.message-input {
  padding: 16px 20px;
  background: white;
  border-top: 1px solid rgba(255, 71, 87, 0.1);
  display: flex;
  gap: 12px;
  align-items: flex-end;
  flex-shrink: 0;
  box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.02);
}

textarea {
  flex: 1;
  border: 2px solid #f1f2f6;
  border-radius: 18px;
  padding: 10px 16px;
  font-size: 14px;
  resize: none;
  max-height: 120px;
  font-family: inherit;
  line-height: 20px; /* 固定行高 */
  /* 必须移除 height 的 transition，否则高度计算会因为动画延迟而不准确 */
  transition: border-color 0.2s, background-color 0.2s, box-shadow 0.2s;
  background: #f8f9fa;
  min-height: 44px;
  height: 44px;
  box-sizing: border-box;
  overflow-y: hidden;
  display: block;
}

textarea:focus {
  outline: none;
  border-color: #ff6b6b;
  background: white;
  box-shadow: 0 0 0 4px rgba(255, 107, 107, 0.1);
}

textarea:disabled {
  background: #f1f2f6;
  cursor: not-allowed;
  border-color: #f1f2f6;
}

.send-btn {
  width: 44px;
  height: 44px;
  border-radius: 15px;
  background: linear-gradient(135deg, #ff6b6b 0%, #ff4757 100%);
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  box-shadow: 0 4px 12px rgba(255, 71, 87, 0.2);
}

.send-btn:hover:not(:disabled) {
  transform: scale(1.05) translateY(-2px);
  box-shadow: 0 6px 16px rgba(255, 71, 87, 0.3);
}

.send-btn:active:not(:disabled) {
  transform: scale(0.95);
}

.send-btn:disabled {
  background: #dfe6e9;
  box-shadow: none;
  cursor: not-allowed;
}

.send-btn svg {
  width: 22px;
  height: 22px;
  fill: white;
  transform: rotate(-10deg);
}
</style>
