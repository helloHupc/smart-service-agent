import { io } from 'socket.io-client'
import { useChatStore } from '@/stores/chat'

const WS_URL = import.meta.env.VITE_WS_URL || 'https://chat.smart-service.cn'

class SocketService {
  constructor() {
    this.socket = null
    this._listeners = {}
  }

  connect() {
    if (this.socket?.connected) return

    this.socket = io(WS_URL, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 10000,
      reconnectionAttempts: 10,
    })

    const chatStore = useChatStore()

    this.socket.on('connect', () => {
      chatStore.setConnected(true)
    })

    this.socket.on('disconnect', () => {
      chatStore.setConnected(false)
    })

    this.socket.on('connect_error', (err) => {
      console.error('Socket connection error:', err.message)
      chatStore.setConnected(false)
    })
  }

  disconnect() {
    if (this.socket) {
      this.socket.removeAllListeners()
      this.socket.disconnect()
      this.socket = null
    }
    this._listeners = {}
  }

  sendMessage(data) {
    if (this.socket?.connected) {
      this.socket.emit('message', data)
    }
  }

  on(event, callback) {
    if (this.socket) {
      this.socket.on(event, callback)
    }
    if (!this._listeners[event]) {
      this._listeners[event] = []
    }
    this._listeners[event].push(callback)
  }

  off(event, callback) {
    if (this.socket) {
      this.socket.off(event, callback)
    }
    if (this._listeners[event]) {
      this._listeners[event] = this._listeners[event].filter((cb) => cb !== callback)
    }
  }
}

export const socketService = new SocketService()
