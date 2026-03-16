import { initializeApp } from 'firebase/app'
import { getFirestore } from 'firebase/firestore'
import { getStorage } from 'firebase/storage'

const firebaseConfig = {
  apiKey: 'AIzaSyCupjdOfp3P0vtBgd1tNq8vLEHiaGW0Tg8',
  authDomain: 'nephro-brain.firebaseapp.com',
  projectId: 'nephro-brain',
  storageBucket: 'nephro-brain.firebasestorage.app',
  messagingSenderId: '761804517300',
  appId: '1:761804517300:web:d51bcd26893223498f8ce1',
}

const app = initializeApp(firebaseConfig)
export const db = getFirestore(app)
export const storage = getStorage(app)
