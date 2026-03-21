import { ref } from 'vue'

const STORAGE_KEY = 'nb_user_role'
const PRO_CODE = 'nephro2025'

const role = ref(localStorage.getItem(STORAGE_KEY) || 'guest')

export function useUserRole() {
  const isPro = () => role.value === 'pro'
  const isGuest = () => role.value === 'guest'

  function activatePro(code) {
    if (code === PRO_CODE) {
      role.value = 'pro'
      localStorage.setItem(STORAGE_KEY, 'pro')
      return true
    }
    return false
  }

  function logout() {
    role.value = 'guest'
    localStorage.setItem(STORAGE_KEY, 'guest')
  }

  return { role, isPro, isGuest, activatePro, logout }
}
