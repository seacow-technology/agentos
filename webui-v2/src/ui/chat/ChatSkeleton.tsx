/**
 * ChatSkeleton - Loading State Component
 *
 * Displays skeleton placeholders for:
 * - Message bubbles (alternating left/right)
 * - Avatars
 * - Input bar
 */

import { Box, Skeleton, Paper } from '@mui/material'

export function ChatSkeleton() {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: 'calc(100vh - 200px)',
        maxHeight: '800px',
      }}
    >
      {/* Messages Container Skeleton */}
      <Paper sx={{ flex: 1, p: 3, mb: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
        {[1, 2, 3, 4].map((i) => (
          <Box
            key={i}
            sx={{
              display: 'flex',
              justifyContent: i % 2 === 0 ? 'flex-end' : 'flex-start',
              mb: 2,
            }}
          >
            {/* Avatar Skeleton - Left (assistant) */}
            {i % 2 === 1 && (
              <Skeleton variant="circular" width={36} height={36} sx={{ mr: 1 }} />
            )}

            {/* Message Bubble Skeleton */}
            <Skeleton
              variant="rectangular"
              width="60%"
              height={80}
              sx={{ borderRadius: 1 }}
            />

            {/* Avatar Skeleton - Right (user) */}
            {i % 2 === 0 && (
              <Skeleton variant="circular" width={36} height={36} sx={{ ml: 1 }} />
            )}
          </Box>
        ))}
      </Paper>

      {/* Input Bar Skeleton */}
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
        <Skeleton variant="circular" width={48} height={48} />
        <Skeleton variant="rectangular" height={56} sx={{ flex: 1, borderRadius: 1 }} />
        <Skeleton variant="circular" width={48} height={48} />
      </Box>
    </Box>
  )
}
