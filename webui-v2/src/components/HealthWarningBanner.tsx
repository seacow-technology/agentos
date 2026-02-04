/**
 * HealthWarningBanner - Chat Health Warning Display Component
 *
 * P0: Displays health check failures with issues and hints
 */

import { Alert, AlertTitle, IconButton, Collapse, List, ListItem, ListItemText } from '@mui/material'
import CloseIcon from '@mui/icons-material/Close'
import { K, useTextTranslation } from '@/ui/text'

interface HealthWarningBannerProps {
  open: boolean
  issues: string[]
  hints: string[]
  onClose: () => void
}

export function HealthWarningBanner({ open, issues, hints, onClose }: HealthWarningBannerProps) {
  const { t } = useTextTranslation()
  return (
    <Collapse in={open}>
      <Alert
        severity="error"
        action={
          <IconButton
            aria-label={t(K.common.close)}
            color="inherit"
            size="small"
            onClick={onClose}
          >
            <CloseIcon fontSize="inherit" />
          </IconButton>
        }
        sx={{ mb: 2 }}
      >
        <AlertTitle>{t(K.page.chat.healthWarningTitle)}</AlertTitle>

        {issues.length > 0 && (
          <>
            <strong>{t(K.page.chat.healthWarningIssuesLabel)}</strong>
            <List dense>
              {issues.map((issue, idx) => (
                <ListItem key={idx} sx={{ py: 0 }}>
                  <ListItemText primary={`• ${issue}`} />
                </ListItem>
              ))}
            </List>
          </>
        )}

        {hints.length > 0 && (
          <>
            <strong>{t(K.page.chat.healthWarningSuggestionsLabel)}</strong>
            <List dense>
              {hints.map((hint, idx) => (
                <ListItem key={idx} sx={{ py: 0 }}>
                  <ListItemText primary={`• ${hint}`} />
                </ListItem>
              ))}
            </List>
          </>
        )}
      </Alert>
    </Collapse>
  )
}
