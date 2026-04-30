<template>
  <div class="product-card" @click="openProductPage" title="查看产品详情">
    <div class="product-header">
      <img
        v-if="product.images?.[0]"
        :src="product.images[0]"
        :alt="product.name"
        class="product-image"
        @error="handleImageError"
      />
      <div class="product-info">
        <h5 class="product-name">{{ product.name }}</h5>
        <span v-if="product.price != null" class="product-price">
          ¥{{ product.price }}
        </span>
      </div>
    </div>
    <p v-if="product.description" class="product-desc">
      {{ product.description }}
    </p>
  </div>
</template>

<script setup>
defineProps({
  product: {
    type: Object,
    required: true,
  },
})

function handleImageError(e) {
  e.target.style.display = 'none'
}

function openProductPage() {
  window.open('https://home.smart-service.cn/products.html', '_blank')
}
</script>

<style scoped>
.product-card {
  background: white;
  border-radius: 16px;
  padding: 12px;
  border: 1px solid rgba(255, 71, 87, 0.1);
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.165, 0.84, 0.44, 1);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
  margin: 4px 0;
}

.product-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(255, 71, 87, 0.12);
  border-color: rgba(255, 71, 87, 0.3);
}

.product-header {
  display: flex;
  gap: 12px;
  align-items: center;
}

.product-image {
  width: 64px;
  height: 64px;
  border-radius: 12px;
  object-fit: cover;
  background: #f8f9fa;
  flex-shrink: 0;
  border: 1px solid #f1f2f6;
}

.product-info {
  flex: 1;
  min-width: 0;
}

.product-name {
  margin: 0 0 4px 0;
  font-size: 15px;
  font-weight: 700;
  color: #2d3436;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.product-price {
  font-size: 16px;
  font-weight: 800;
  color: #ff4757;
  display: block;
}

.product-desc {
  margin: 10px 0 0 0;
  font-size: 12px;
  color: #636e72;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  background: #fff9f9;
  padding: 8px;
  border-radius: 8px;
}
</style>
