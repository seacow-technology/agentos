/**
 * useDraftProtection - React Hook for Draft Auto-save & Crash Recovery
 *
 * 🎯 产品级功能：
 * - ✅ 自动保存用户输入（无感体验）
 * - ✅ 页面关闭前提示 + 强制保存
 * - ✅ 崩溃后友好恢复提示
 *
 * 使用方式：
 * ```tsx
 * const { clearDraft } = useDraftProtection(
 *   sessionId,
 *   inputValue,
 *   (restoredContent) => setInputValue(restoredContent)
 * )
 *
 * // 发送消息后清除草稿
 * handleSend().then(() => clearDraft())
 * ```
 */

import { useEffect, useRef, useCallback } from 'react'
import { draftService } from '@/services/draftService'

export function useDraftProtection(
  sessionId: string,
  content: string,
  onRestore: (content: string) => void
) {
  const hasShownRestorePrompt = useRef(false)
  const isRestoringRef = useRef(false)

  // ===================================
  // 1. 页面加载时检查未发送的草稿
  // ===================================
  useEffect(() => {
    if (!sessionId || hasShownRestorePrompt.current || isRestoringRef.current) {
      return
    }

    const draft = draftService.loadDraft()
    if (!draft || draft.sessionId !== sessionId) {
      return
    }

    const trimmedContent = draft.content.trim()
    if (trimmedContent.length === 0) {
      draftService.clearDraft()
      return
    }

    hasShownRestorePrompt.current = true

    // 延迟显示提示，避免阻塞页面渲染
    const timer = setTimeout(() => {
      const preview =
        trimmedContent.length > 100
          ? trimmedContent.substring(0, 100) + '...'
          : trimmedContent

      const shouldRestore = window.confirm(
        `💾 检测到未发送的内容（${trimmedContent.length} 字）：\n\n` +
          `"${preview}"\n\n` +
          `是否恢复？`
      )

      if (shouldRestore) {
        isRestoringRef.current = true
        onRestore(draft.content)
        console.log('[DraftProtection] ✅ Draft restored')

        // 恢复完成后重置标志
        setTimeout(() => {
          isRestoringRef.current = false
        }, 100)
      } else {
        draftService.clearDraft()
        console.log('[DraftProtection] ❌ Draft discarded by user')
      }
    }, 500)

    return () => clearTimeout(timer)
  }, [sessionId, onRestore])

  // ===================================
  // 2. 监听内容变化，自动保存（debounced）
  // ===================================
  useEffect(() => {
    if (!sessionId || isRestoringRef.current) {
      return
    }

    const trimmedContent = content.trim()

    if (trimmedContent.length === 0) {
      // 内容为空时，清除草稿
      draftService.clearDraft()
      return
    }

    // 自动保存（debounced）
    draftService.saveDraft({
      content,
      timestamp: Date.now(),
      sessionId,
    })

    // Cleanup: 取消pending的保存
    return () => {
      draftService.cancelPendingSave()
    }
  }, [content, sessionId])

  // ===================================
  // 3. 页面卸载前强制保存 + 提示
  // ===================================
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      const trimmedContent = content.trim()

      if (trimmedContent.length === 0) {
        return // 内容为空，不需要提示
      }

      // 强制立即保存
      draftService.flushDraft({
        content,
        timestamp: Date.now(),
        sessionId,
      })

      // 浏览器标准提示（阻止用户意外关闭）
      e.preventDefault()
      e.returnValue = '' // Chrome 需要
      return '' // 其他浏览器
    }

    window.addEventListener('beforeunload', handleBeforeUnload)

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload)
    }
  }, [content, sessionId])

  // ===================================
  // 4. 提供手动清除方法（发送消息后调用）
  // ===================================
  const clearDraft = useCallback(() => {
    draftService.clearDraft()
  }, [])

  return { clearDraft }
}
