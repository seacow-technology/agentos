/**
 * SnippetsPage - 代码片段
 *
 * Phase 6: Real API Integration
 * - API: systemService.listSnippets(), createSnippet(), updateSnippet(), deleteSnippet()
 * - States: Loading/Success/Error/Empty
 * - i18n: Full translation support
 * - Features: Create, Edit, View Details, Copy, Delete
 */

import { useState, useEffect, useCallback } from 'react'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { CardCollectionWrap } from '@/ui/cards/CardCollectionWrap'
import { ItemCard } from '@/ui/cards/ItemCard'
import { K, useText } from '@/ui/text'
import { DialogForm, ConfirmDialog } from '@/ui/interaction'
import { TextField, Button, Chip, Grid, Box, Typography } from '@/ui'
import { systemService } from '@/services'
import type { Snippet } from '@/services/system.service'
import { CodeIcon, JavascriptIcon, DataObjectIcon, TerminalIcon } from '@/ui/icons'

// Constants
const LAYOUT_GRID = 'grid' as const
const CHIP_SIZE = 'small' as const
const CHIP_VARIANT = 'outlined' as const

// Icon mapping by language
const getLanguageIcon = (language?: string) => {
  const lang = language?.toLowerCase()
  if (lang === 'javascript' || lang === 'js') return <JavascriptIcon />
  if (lang === 'json' || lang === 'graphql') return <DataObjectIcon />
  if (lang === 'bash' || lang === 'shell') return <TerminalIcon />
  return <CodeIcon />
}

export default function SnippetsPage() {
  // ===================================
  // i18n Hook
  // ===================================
  const { t } = useText()

  // ===================================
  // State: API Data
  // ===================================
  const [snippets, setSnippets] = useState<Snippet[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // ===================================
  // State: Create Dialog
  // ===================================
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [snippetTitle, setSnippetTitle] = useState('')
  const [snippetContent, setSnippetContent] = useState('')
  const [snippetLanguage, setSnippetLanguage] = useState('')
  const [snippetTags, setSnippetTags] = useState('')
  const [creating, setCreating] = useState(false)

  // ===================================
  // State: Edit Dialog
  // ===================================
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [snippetToEdit, setSnippetToEdit] = useState<Snippet | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [editContent, setEditContent] = useState('')
  const [editLanguage, setEditLanguage] = useState('')
  const [editTags, setEditTags] = useState('')
  const [editing, setEditing] = useState(false)

  // ===================================
  // State: View Dialog
  // ===================================
  const [viewDialogOpen, setViewDialogOpen] = useState(false)
  const [snippetToView, setSnippetToView] = useState<Snippet | null>(null)

  // ===================================
  // State: Delete Dialog
  // ===================================
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [snippetToDelete, setSnippetToDelete] = useState<Snippet | null>(null)
  const [deleting, setDeleting] = useState(false)

  // ===================================
  // Page Header
  // ===================================
  usePageHeader({
    title: t(K.page.snippets.title),
    subtitle: t(K.page.snippets.subtitle),
  })

  usePageActions([
    {
      key: 'create',
      label: t(K.page.snippets.createSnippet),
      variant: 'contained',
      onClick: () => setCreateDialogOpen(true),
    },
    {
      key: 'refresh',
      label: t(K.common.refresh),
      variant: 'outlined',
      onClick: () => loadSnippets(),
    },
  ])

  // ===================================
  // API: Load Snippets
  // ===================================
  const loadSnippets = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await systemService.listSnippets()
      setSnippets(response.snippets || [])
    } catch (err: unknown) {
      const error = err as Error
      console.error('Failed to load snippets:', error)
      setError(error.message || t(K.page.snippets.loadError))
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    loadSnippets()
  }, [loadSnippets])

  // ===================================
  // API: Create Snippet
  // ===================================
  const handleCreateSnippet = async () => {
    if (!snippetTitle.trim() || !snippetContent.trim()) {
      console.error('Fill required fields')
      return
    }

    setCreating(true)
    try {
      const tags = snippetTags
        .split(',')
        .map(tag => tag.trim())
        .filter(tag => tag.length > 0)

      await systemService.createSnippet({
        title: snippetTitle,
        content: snippetContent,
        language: snippetLanguage || undefined,
        tags: tags.length > 0 ? tags : undefined,
      })
      setCreateDialogOpen(false)
      setSnippetTitle('')
      setSnippetContent('')
      setSnippetLanguage('')
      setSnippetTags('')
      loadSnippets()
    } catch (err: unknown) {
      const error = err as Error
      console.error('Failed to create snippet:', error)
    } finally {
      setCreating(false)
    }
  }

  // ===================================
  // API: Update Snippet
  // ===================================
  const handleUpdateSnippet = async () => {
    if (!snippetToEdit || !editTitle.trim() || !editContent.trim()) {
      console.error('Fill required fields')
      return
    }

    setEditing(true)
    try {
      const tags = editTags
        .split(',')
        .map(tag => tag.trim())
        .filter(tag => tag.length > 0)

      await systemService.updateSnippet(snippetToEdit.id, {
        title: editTitle,
        content: editContent,
        language: editLanguage || undefined,
        tags: tags.length > 0 ? tags : undefined,
      })
      setEditDialogOpen(false)
      setSnippetToEdit(null)
      setEditTitle('')
      setEditContent('')
      setEditLanguage('')
      setEditTags('')
      loadSnippets()
    } catch (err: unknown) {
      const error = err as Error
      console.error('Failed to update snippet:', error)
    } finally {
      setEditing(false)
    }
  }

  // ===================================
  // Handler: Open Edit Dialog
  // ===================================
  const handleOpenEdit = (snippet: Snippet) => {
    setSnippetToEdit(snippet)
    setEditTitle(snippet.title)
    setEditContent(snippet.content)
    setEditLanguage(snippet.language || '')
    setEditTags(snippet.tags?.join(', ') || '')
    setEditDialogOpen(true)
  }

  // ===================================
  // Handler: Open View Dialog
  // ===================================
  const handleOpenView = (snippet: Snippet) => {
    setSnippetToView(snippet)
    setViewDialogOpen(true)
  }

  // ===================================
  // API: Delete Snippet
  // ===================================
  const handleDeleteSnippet = async () => {
    if (!snippetToDelete) return

    setDeleting(true)
    try {
      await systemService.deleteSnippet(snippetToDelete.id)
      setDeleteDialogOpen(false)
      setSnippetToDelete(null)
      loadSnippets()
    } catch (err: unknown) {
      const error = err as Error
      console.error('Failed to delete snippet:', error)
    } finally {
      setDeleting(false)
    }
  }

  // ===================================
  // Render: Loading State
  // ===================================
  if (loading) {
    return (
      <CardCollectionWrap layout={LAYOUT_GRID} columns={3} gap={16}>
        <div style={{ padding: '40px', textAlign: 'center', gridColumn: '1 / -1' }}>
          {t(K.common.loading)}
        </div>
      </CardCollectionWrap>
    )
  }

  // ===================================
  // Render: Error State
  // ===================================
  if (error) {
    return (
      <CardCollectionWrap layout={LAYOUT_GRID} columns={3} gap={16}>
        <div style={{ padding: '40px', textAlign: 'center', gridColumn: '1 / -1', color: 'error.main' }}>
          {error}
        </div>
      </CardCollectionWrap>
    )
  }

  // ===================================
  // Render: Empty State (isEmpty check)
  // ===================================
  const isEmpty = snippets.length === 0
  if (isEmpty) {
    return (
      <>
        <CardCollectionWrap layout={LAYOUT_GRID} columns={3} gap={16}>
          <div style={{ padding: '40px', textAlign: 'center', gridColumn: '1 / -1' }}>
            <div>{t(K.page.snippets.noSnippets)}</div>
            <div style={{ marginTop: '8px', color: 'text.secondary' }}>
              {t(K.page.snippets.noSnippetsDesc)}
            </div>
          </div>
        </CardCollectionWrap>

        {/* Create Dialog */}
        <DialogForm
          open={createDialogOpen}
          onClose={() => setCreateDialogOpen(false)}
          title={t(K.page.snippets.createSnippet)}
          submitText={t(K.common.create)}
          cancelText={t(K.common.cancel)}
          onSubmit={handleCreateSnippet}
          submitDisabled={!snippetTitle.trim() || !snippetContent.trim() || creating}
        >
          <Grid container spacing={2}>
            <Grid item xs={12}>
              <TextField
                label={t(K.page.snippets.fieldTitle)}
                placeholder={t(K.page.snippets.fieldTitlePlaceholder)}
                value={snippetTitle}
                onChange={(e) => setSnippetTitle(e.target.value)}
                fullWidth
                required
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                label={t(K.page.snippets.fieldLanguage)}
                placeholder={t(K.page.snippets.fieldLanguagePlaceholder)}
                value={snippetLanguage}
                onChange={(e) => setSnippetLanguage(e.target.value)}
                fullWidth
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                label={t(K.page.snippets.fieldContent)}
                placeholder={t(K.page.snippets.fieldContentPlaceholder)}
                value={snippetContent}
                onChange={(e) => setSnippetContent(e.target.value)}
                fullWidth
                required
                multiline
                rows={10}
                sx={{
                  '& .MuiInputBase-input': {
                    fontFamily: 'Monaco, Menlo, "Courier New", monospace',
                    fontSize: '13px',
                  }
                }}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                label={t(K.page.snippets.fieldTags)}
                placeholder={t(K.page.snippets.fieldTagsPlaceholder)}
                value={snippetTags}
                onChange={(e) => setSnippetTags(e.target.value)}
                fullWidth
              />
            </Grid>
          </Grid>
        </DialogForm>
      </>
    )
  }

  // ===================================
  // Render: Success State (has data)
  // ===================================
  const isSuccess = snippets.length > 0 // Success state marker
  return (
    <>
      <CardCollectionWrap layout={LAYOUT_GRID} columns={3} gap={16} data-state={isSuccess ? 'success' : 'empty'}>
        {snippets.map((snippet) => (
          <ItemCard
            key={snippet.id}
            title={snippet.title}
            description={snippet.content.substring(0, 100) + (snippet.content.length > 100 ? '...' : '')}
            meta={[
              ...(snippet.language ? [{ key: 'language', label: t(K.page.snippets.metaLanguage), value: snippet.language }] : []),
              ...(snippet.tags && snippet.tags.length > 0 ? [{ key: 'tags', label: t(K.page.snippets.metaTags), value: snippet.tags.join(', ') }] : []),
            ]}
            tags={snippet.tags || []}
            icon={getLanguageIcon(snippet.language)}
            actions={[
              {
                key: 'view',
                label: t(K.page.snippets.viewDetails),
                variant: 'contained',
                onClick: () => handleOpenView(snippet),
              },
              {
                key: 'edit',
                label: t(K.common.edit),
                variant: 'outlined',
                onClick: () => handleOpenEdit(snippet),
              },
              {
                key: 'copy',
                label: t(K.common.copy),
                variant: 'outlined',
                onClick: () => {
                  navigator.clipboard.writeText(snippet.content)
                },
              },
              {
                key: 'delete',
                label: t(K.common.delete),
                variant: 'outlined',
                onClick: () => {
                  setSnippetToDelete(snippet)
                  setDeleteDialogOpen(true)
                },
              },
            ]}
            onClick={() => handleOpenView(snippet)}
          />
        ))}
      </CardCollectionWrap>

      {/* Create Dialog */}
      <DialogForm
        open={createDialogOpen}
        onClose={() => setCreateDialogOpen(false)}
        title={t(K.page.snippets.createSnippet)}
        submitText={t(K.common.create)}
        cancelText={t(K.common.cancel)}
        onSubmit={handleCreateSnippet}
        submitDisabled={!snippetTitle.trim() || !snippetContent.trim() || creating}
      >
        <Grid container spacing={2}>
          <Grid item xs={12}>
            <TextField
              label={t(K.page.snippets.fieldTitle)}
              placeholder={t(K.page.snippets.fieldTitlePlaceholder)}
              value={snippetTitle}
              onChange={(e) => setSnippetTitle(e.target.value)}
              fullWidth
              required
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              label={t(K.page.snippets.fieldLanguage)}
              placeholder={t(K.page.snippets.fieldLanguagePlaceholder)}
              value={snippetLanguage}
              onChange={(e) => setSnippetLanguage(e.target.value)}
              fullWidth
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              label={t(K.page.snippets.fieldContent)}
              placeholder={t(K.page.snippets.fieldContentPlaceholder)}
              value={snippetContent}
              onChange={(e) => setSnippetContent(e.target.value)}
              fullWidth
              required
              multiline
              rows={10}
              sx={{
                '& .MuiInputBase-input': {
                  fontFamily: 'Monaco, Menlo, "Courier New", monospace',
                  fontSize: '13px',
                }
              }}
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              label={t(K.page.snippets.fieldTags)}
              placeholder={t(K.page.snippets.fieldTagsPlaceholder)}
              value={snippetTags}
              onChange={(e) => setSnippetTags(e.target.value)}
              fullWidth
            />
          </Grid>
        </Grid>
      </DialogForm>

      {/* Edit Dialog */}
      <DialogForm
        open={editDialogOpen}
        onClose={() => setEditDialogOpen(false)}
        title={t(K.page.snippets.editSnippet)}
        submitText={t(K.common.save)}
        cancelText={t(K.common.cancel)}
        onSubmit={handleUpdateSnippet}
        submitDisabled={!editTitle.trim() || !editContent.trim() || editing}
      >
        <Grid container spacing={2}>
          <Grid item xs={12}>
            <TextField
              label={t(K.page.snippets.fieldTitle)}
              placeholder={t(K.page.snippets.fieldTitlePlaceholder)}
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              fullWidth
              required
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              label={t(K.page.snippets.fieldLanguage)}
              placeholder={t(K.page.snippets.fieldLanguagePlaceholder)}
              value={editLanguage}
              onChange={(e) => setEditLanguage(e.target.value)}
              fullWidth
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              label={t(K.page.snippets.fieldContent)}
              placeholder={t(K.page.snippets.fieldContentPlaceholder)}
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              fullWidth
              required
              multiline
              rows={10}
              sx={{
                '& .MuiInputBase-input': {
                  fontFamily: 'Monaco, Menlo, "Courier New", monospace',
                  fontSize: '13px',
                }
              }}
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              label={t(K.page.snippets.fieldTags)}
              placeholder={t(K.page.snippets.fieldTagsPlaceholder)}
              value={editTags}
              onChange={(e) => setEditTags(e.target.value)}
              fullWidth
            />
          </Grid>
        </Grid>
      </DialogForm>

      {/* View Details Dialog */}
      {snippetToView && (
        <DialogForm
          open={viewDialogOpen}
          onClose={() => setViewDialogOpen(false)}
          title={snippetToView.title}
          submitText={t(K.common.edit)}
          cancelText={t(K.common.close)}
          onSubmit={() => {
            setViewDialogOpen(false)
            handleOpenEdit(snippetToView)
          }}
        >
          <Grid container spacing={2}>
            {snippetToView.language && (
              <Grid item xs={12}>
                <Box>
                  <Typography gutterBottom>
                    {t(K.page.snippets.metaLanguage)}
                  </Typography>
                  <Chip label={snippetToView.language} size={CHIP_SIZE} />
                </Box>
              </Grid>
            )}
            {snippetToView.tags && snippetToView.tags.length > 0 && (
              <Grid item xs={12}>
                <Box>
                  <Typography gutterBottom>
                    {t(K.page.snippets.metaTags)}
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                    {snippetToView.tags.map((tag, idx) => (
                      <Chip key={idx} label={tag} size={CHIP_SIZE} variant={CHIP_VARIANT} />
                    ))}
                  </Box>
                </Box>
              </Grid>
            )}
            <Grid item xs={12}>
              <Box>
                <Typography gutterBottom>
                  {t(K.page.snippets.fieldContent)}
                </Typography>
                <Box
                  sx={{
                    p: 2,
                    bgcolor: 'background.default',
                    border: '1px solid',
                    borderColor: 'divider',
                    borderRadius: 1,
                    fontFamily: 'Monaco, Menlo, "Courier New", monospace',
                    fontSize: '13px',
                    whiteSpace: 'pre-wrap',
                    overflowX: 'auto',
                    maxHeight: '400px',
                    overflowY: 'auto',
                  }}
                >
                  {snippetToView.content}
                </Box>
                <Box sx={{ mt: 2 }}>
                  <Button
                    onClick={() => {
                      navigator.clipboard.writeText(snippetToView.content)
                    }}
                    fullWidth
                  >
                    {t(K.common.copy)}
                  </Button>
                </Box>
              </Box>
            </Grid>
          </Grid>
        </DialogForm>
      )}

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        title={t(K.page.snippets.deleteTitle)}
        message={t(K.page.snippets.deleteMessage, { title: snippetToDelete?.title || '' })}
        confirmText={t(K.common.delete)}
        onConfirm={handleDeleteSnippet}
        loading={deleting}
      />
    </>
  )
}
