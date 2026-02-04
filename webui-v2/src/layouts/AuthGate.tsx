import { ReactNode } from 'react'
import { Box, Paper, Typography, Button } from '@mui/material'
import { LockIcon } from '@/ui/icons'

interface AuthGateProps {
  children: ReactNode
}

/**
 * AuthGate - Authentication gate for protected routes
 *
 * Current implementation: Placeholder with minimal admin token check abstraction
 * Future: Will integrate with real authentication system
 *
 * Features:
 * - Checks for minimal auth state (placeholder)
 * - Shows unauthorized prompt if not authenticated
 * - Renders children if authenticated
 */
export default function AuthGate({ children }: AuthGateProps) {
  // Placeholder auth check - always returns true for now
  // Future: Replace with actual auth state from context/store
  const isAuthenticated = checkAuth()

  if (!isAuthenticated) {
    return (
      <Box className="flex items-center justify-center min-h-screen bg-gray-100">
        <Paper elevation={3} className="p-8 max-w-md text-center">
          <LockIcon className="mx-auto mb-4" sx={{ fontSize: 64 }} color="action" />
          <Typography variant="h5" className="mb-2">
            Authentication Required
          </Typography>
          <Typography variant="body2" color="text.secondary" className="mb-6">
            You need to be authenticated to access this resource.
            Please configure your admin token.
          </Typography>
          <Button
            variant="contained"
            onClick={() => {
              // Placeholder: Future auth flow
              console.log('Navigate to auth setup')
            }}
          >
            Configure Access
          </Button>
        </Paper>
      </Box>
    )
  }

  return <>{children}</>
}

/**
 * Placeholder auth check function
 * Future: Replace with real authentication logic
 */
function checkAuth(): boolean {
  // Placeholder: Always return true for demo purposes
  // Real implementation would check:
  // - Local storage for admin token
  // - Session storage for active session
  // - Context/Redux store for auth state
  return true
}
