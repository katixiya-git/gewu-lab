import http from './request'

/**
 * 与实验室助手对话。
 * @param {{ message: string, history?: Array<{role: 'user'|'assistant', content: string}> }} payload
 */
export function chatWithAi(payload) {
  return http.post('/ai/chat', payload)
}
