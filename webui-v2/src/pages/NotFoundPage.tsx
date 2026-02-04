/**
 * NotFoundPage - 404 页面
 *
 * Phase 6.1: 完整的多语言支持
 * - 中英文翻译
 * - 友好的错误提示
 * - 导航选项
 */

import { useNavigate } from 'react-router-dom'
import { Box, Typography, Button, Paper } from '@mui/material'
import { HomeIcon, BackIcon, ErrorIcon } from '@/ui/icons'
import { K, useTextTranslation } from '@/ui/text'
import { usePageHeader } from '@/ui/layout'

export default function NotFoundPage() {
  const { t } = useTextTranslation()
  const navigate = useNavigate()

  // Page Header
  usePageHeader({
    title: t(K.page.notFound.title),
    subtitle: t(K.page.notFound.subtitle),
  })

  const handleGoHome = () => {
    navigate('/')
  }

  const handleGoBack = () => {
    navigate(-1)
  }

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '60vh',
        px: 3,
      }}
    >
      <Paper
        elevation={0}
        sx={{
          p: 6,
          maxWidth: 600,
          width: '100%',
          textAlign: 'center',
          border: 1,
          borderColor: 'divider',
          borderRadius: 2,
        }}
      >
        {/* Error Icon */}
        <Box sx={{ mb: 3 }}>
          <ErrorIcon
            sx={{
              fontSize: 120,
              color: 'error.main',
              opacity: 0.8,
            }}
          />
        </Box>

        {/* Error Code */}
        <Typography
          variant="h1"
          sx={{
            fontSize: { xs: 72, md: 96 },
            fontWeight: 700,
            color: 'text.secondary',
            mb: 2,
            lineHeight: 1,
          }}
        >
          404
        </Typography>

        {/* Title */}
        <Typography variant="h4" sx={{ mb: 2, fontWeight: 600 }}>
          {t(K.page.notFound.title)}
        </Typography>

        {/* Subtitle */}
        <Typography
          variant="h6"
          color="text.secondary"
          sx={{ mb: 3, fontWeight: 400 }}
        >
          {t(K.page.notFound.subtitle)}
        </Typography>

        {/* Description */}
        <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
          {t(K.page.notFound.description)}
        </Typography>

        {/* Action Buttons */}
        <Box
          sx={{
            display: 'flex',
            gap: 2,
            justifyContent: 'center',
            flexWrap: 'wrap',
          }}
        >
          <Button
            variant="contained"
            size="large"
            startIcon={<HomeIcon />}
            onClick={handleGoHome}
            sx={{ minWidth: 150 }}
          >
            {t(K.page.notFound.goHome)}
          </Button>
          <Button
            variant="outlined"
            size="large"
            startIcon={<BackIcon />}
            onClick={handleGoBack}
            sx={{ minWidth: 150 }}
          >
            {t(K.page.notFound.goBack)}
          </Button>
        </Box>

        {/* Error Code Label */}
        <Typography
          variant="caption"
          color="text.disabled"
          sx={{ mt: 4, display: 'block' }}
        >
          {t(K.page.notFound.errorCode)}: 404
        </Typography>
      </Paper>
    </Box>
  )
}
