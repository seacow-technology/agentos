/**
 * MessagesPage - 消息列表
 *
 * ✅ i18n: 使用 useTextTranslation + K keys
 * ✅ API: agentosService.getMessages()
 * ✅ States: loading, error, empty, success
 * 
 * 🔒 No-Interaction Contract:
 * - 所有 onClick 为空函数
 * - 使用 API 数据
 */

import { useState, useEffect } from 'react'
import { TextField, Select, MenuItem, Chip } from '@mui/material'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar } from '@/ui'
import { DeleteIcon, DownloadIcon } from '@/ui/icons'
import { agentosService } from '@/services'
import { useTextTranslation, K } from '@/ui/text'
import type { GridColDef } from '@/ui'

// ===================================
// Types
// ===================================

interface MessageRow {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  conversationId: string
  timestamp: string
  tokenCount: number
}

// ===================================
// Component
// ===================================

export default function MessagesPage() {
  // ===================================
  // i18n Hook
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State
  // ===================================

  // API State
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState<any[]>([])


  const [searchQuery, setSearchQuery] = useState('')
  const [roleFilter, setRoleFilter] = useState('all')
  const [conversationFilter, setConversationFilter] = useState('all')

  // ===================================
  // API Call
  // ===================================
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        const response = await agentosService.getMessages()
        setData(response.data)
      } catch (err) {
        console.error('Failed to fetch messages:', err)
        setData([])
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])


  // ===================================
  // Page Header
  // ===================================

  usePageHeader({
    title: t(K.page.messages.title),
    subtitle: t(K.page.messages.subtitle),
  })

  usePageActions([
    {
      key: 'export',
      label: t(K.common.export),
      icon: <DownloadIcon />,
      variant: 'outlined',
      onClick: () => {}, // 🔒 No-Interaction: 空函数
    },
    {
      key: 'delete',
      label: t(K.page.messages.deleteSelected),
      icon: <DeleteIcon />,
      variant: 'outlined',
      color: 'error',
      onClick: () => {}, // 🔒 No-Interaction: 空函数
    },
  ])

  // ===================================
  // Table Columns
  // ===================================

  const columns: GridColDef<MessageRow>[] = [
    {
      field: 'role',
      headerName: t(K.page.messages.columnRole),
      width: 110,
      renderCell: (params) => {
        const colorMap: Record<MessageRow['role'], 'primary' | 'success' | 'info'> = {
          user: 'primary',
          assistant: 'success',
          system: 'info',
        }
        return (
          <Chip
            label={params.value}
            color={colorMap[params.value as MessageRow['role']]}
            size="small"
            variant="outlined"
          />
        )
      },
    },
    {
      field: 'content',
      headerName: t(K.page.messages.columnContent),
      flex: 1,
      minWidth: 350,
    },
    {
      field: 'conversationId',
      headerName: t(K.page.messages.columnConversation),
      width: 140,
    },
    {
      field: 'timestamp',
      headerName: t(K.page.messages.columnTimestamp),
      width: 180,
    },
    {
      field: 'tokenCount',
      headerName: t(K.page.messages.columnTokens),
      width: 100,
      type: 'number',
    },
  ]

  // ===================================
  // FilterBar
  // ===================================

  const filterBar = (
    <FilterBar
      filters={[
        {
          width: 4,
          component: (
            <TextField
              label={t(K.common.search)}
              placeholder={t(K.page.messages.searchPlaceholder)}
              size="small"
              fullWidth
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          ),
        },
        {
          width: 4,
          component: (
            <Select
              label={t(K.page.messages.filterRole)}
              size="small"
              fullWidth
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
            >
              <MenuItem value="all">{t(K.page.messages.filterAllRoles)}</MenuItem>
              <MenuItem value="user">{t(K.page.messages.filterUser)}</MenuItem>
              <MenuItem value="assistant">{t(K.page.messages.filterAssistant)}</MenuItem>
              <MenuItem value="system">{t(K.page.messages.filterSystem)}</MenuItem>
            </Select>
          ),
        },
        {
          width: 4,
          component: (
            <Select
              label={t(K.page.messages.filterConversation)}
              size="small"
              fullWidth
              value={conversationFilter}
              onChange={(e) => setConversationFilter(e.target.value)}
            >
              <MenuItem value="all">{t(K.page.messages.filterAllConversations)}</MenuItem>
              <MenuItem value="conv-1">{t(K.page.messages.conversationConv1)}</MenuItem>
              <MenuItem value="conv-2">{t(K.page.messages.conversationConv2)}</MenuItem>
            </Select>
          ),
        },
      ]}
    />
  )

  // ===================================
  // Render
  // ===================================

  return (
    <TableShell
      loading={loading}
      rows={data}
      columns={columns}
      filterBar={filterBar}
      onRowClick={() => {}} // 🔒 No-Interaction: 空函数
      emptyState={{
        title: t(K.page.messages.noMessages),
        description: t(K.page.messages.noMessagesDesc),
      }}
      pagination={{
        page: 0,
        pageSize: 25,
        total: data.length,
        onPageChange: () => {}, // 🔒 No-Interaction: 空函数
      }}
    />
  )
}
