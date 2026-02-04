/**
 * Draft Service - Auto-save and Crash Protection
 *
 * 🎯 产品级功能：
 * - ✅ 自动保存用户输入（300ms debounce）
 * - ✅ 页面关闭时强制保存
 * - ✅ 崩溃后自动恢复
 * - ✅ 24小时过期自动清理
 *
 * 架构：
 * - localStorage 存储（简单可靠）
 * - 按 sessionId 隔离
 * - 支持元数据扩展（光标位置、附件等）
 */

export interface DraftData {
  content: string
  timestamp: number
  sessionId: string
  metadata?: {
    cursorPosition?: number
    attachments?: string[]
  }
}

class DraftService {
  private readonly STORAGE_KEY = 'agentos_chat_draft'
  private readonly DEBOUNCE_MS = 300
  private readonly MAX_AGE_MS = 24 * 60 * 60 * 1000 // 24 hours
  private saveTimer: number | null = null

  /**
   * 保存草稿（debounced）
   * 自动延迟 300ms 保存，避免频繁写入
   */
  saveDraft(data: DraftData): void {
    if (this.saveTimer) {
      clearTimeout(this.saveTimer)
    }

    this.saveTimer = window.setTimeout(() => {
      this.flushDraft(data)
    }, this.DEBOUNCE_MS)
  }

  /**
   * 强制立即保存（用于 beforeunload）
   */
  flushDraft(data: DraftData): void {
    if (this.saveTimer) {
      clearTimeout(this.saveTimer)
      this.saveTimer = null
    }

    try {
      const json = JSON.stringify(data)
      localStorage.setItem(this.STORAGE_KEY, json)

      if (import.meta.env.DEV) {
        console.debug('[DraftService] 💾 Draft saved:', {
          length: data.content.length,
          sessionId: data.sessionId.substring(0, 8),
        })
      }
    } catch (e) {
      console.error('[DraftService] Failed to save draft:', e)
    }
  }

  /**
   * 读取草稿
   */
  loadDraft(): DraftData | null {
    try {
      const raw = localStorage.getItem(this.STORAGE_KEY)
      if (!raw) return null

      const draft = JSON.parse(raw) as DraftData

      // 验证草稿有效性（不超过 24 小时）
      const age = Date.now() - draft.timestamp
      if (age > this.MAX_AGE_MS) {
        console.debug('[DraftService] ⏰ Draft expired, clearing')
        this.clearDraft()
        return null
      }

      return draft
    } catch (e) {
      console.error('[DraftService] Failed to load draft:', e)
      return null
    }
  }

  /**
   * 清除草稿
   */
  clearDraft(): void {
    localStorage.removeItem(this.STORAGE_KEY)
    if (import.meta.env.DEV) {
      console.debug('[DraftService] 🗑️ Draft cleared')
    }
  }

  /**
   * 检查是否有有效的待恢复草稿
   */
  hasPendingDraft(currentSessionId: string): boolean {
    const draft = this.loadDraft()
    if (!draft) return false

    // 只在同一 session 且内容不为空时才算有效草稿
    const trimmedContent = draft.content.trim()
    return draft.sessionId === currentSessionId && trimmedContent.length > 0
  }

  /**
   * 取消pending的保存操作
   */
  cancelPendingSave(): void {
    if (this.saveTimer) {
      clearTimeout(this.saveTimer)
      this.saveTimer = null
    }
  }
}

// Singleton instance
export const draftService = new DraftService()
