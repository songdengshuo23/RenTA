<template>
  <Teleport to="body">
    <div class="toast-container">
      <div
        v-for="t in toasts"
        :key="t.id"
        :class="['toast', t.type, { 'toast-leaving': t.leaving }]"
      >{{ t.message }}</div>
    </div>
  </Teleport>
</template>

<script setup>
import { storeToRefs } from 'pinia'
import { useToastStore } from '@/stores/toast'
const toastStore = useToastStore()
const { toasts } = storeToRefs(toastStore)
</script>
