import { ref } from 'vue'
import { defineStore } from 'pinia'

let nextId = 0

export const useToastStore = defineStore('toast', () => {
  const toasts = ref([])

  function add(message, type = 'info', duration = 3000) {
    const id = ++nextId
    toasts.value.push({ id, message, type, leaving: false })
    setTimeout(() => remove(id), duration)
    return id
  }

  function remove(id) {
    const toast = toasts.value.find((item) => item.id === id)
    if (toast) toast.leaving = true
    setTimeout(() => {
      toasts.value = toasts.value.filter((item) => item.id !== id)
    }, 300)
  }

  const success = (message) => add(message, 'success')
  const error = (message) => add(message, 'error')
  const warning = (message) => add(message, 'warning')
  const info = (message) => add(message, 'info')

  return { toasts, add, remove, success, error, warning, info }
})
