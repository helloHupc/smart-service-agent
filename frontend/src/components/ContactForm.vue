<template>
  <div class="contact-form-overlay" @click.self="emit('close')">
    <div class="contact-form">
      <h4>留下您的联系方式</h4>
      <p>我们将为您提供更好的服务</p>

      <div class="form-group">
        <input
          v-model="phone"
          type="tel"
          placeholder="手机号"
          maxlength="11"
        />
      </div>

      <div class="form-divider">或</div>

      <div class="form-group">
        <input
          v-model="email"
          type="email"
          placeholder="邮箱"
        />
      </div>

      <div class="form-actions">
        <button class="btn-cancel" @click="emit('close')">
          稍后再说
        </button>
        <button
          class="btn-submit"
          :disabled="!isValid"
          @click="handleSubmit"
        >
          提交
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const emit = defineEmits(['submit', 'close'])

const phone = ref('')
const email = ref('')

const isValid = computed(() => {
  const phoneValid = /^1[3-9]\d{9}$/.test(phone.value)
  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value)
  return phoneValid || emailValid
})

function handleSubmit() {
  if (!isValid.value) return

  emit('submit', {
    phone: phone.value || null,
    email: email.value || null,
  })
}
</script>

<style scoped>
.contact-form-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}

.contact-form {
  background: white;
  border-radius: 12px;
  padding: 24px;
  width: 90%;
  max-width: 320px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

.contact-form h4 {
  margin: 0 0 8px 0;
  font-size: 18px;
}

.contact-form p {
  margin: 0 0 20px 0;
  font-size: 14px;
  color: #666;
}

.form-group {
  margin-bottom: 12px;
}

.form-group input {
  width: 100%;
  padding: 12px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  font-size: 14px;
  box-sizing: border-box;
}

.form-group input:focus {
  outline: none;
  border-color: #667eea;
}

.form-divider {
  text-align: center;
  color: #999;
  margin: 12px 0;
  font-size: 12px;
}

.form-actions {
  display: flex;
  gap: 12px;
  margin-top: 20px;
}

.form-actions button {
  flex: 1;
  padding: 12px;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  font-size: 14px;
}

.btn-cancel {
  background: #f5f5f5;
  color: #666;
}

.btn-submit {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.btn-submit:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
