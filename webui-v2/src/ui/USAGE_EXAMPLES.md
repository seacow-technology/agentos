# Theme Usage Examples

This document provides practical examples of how to use the MD3 theme system in your components.

## Table of Contents

1. [Basic Component Usage](#basic-component-usage)
2. [Using Design Tokens](#using-design-tokens)
3. [DataGrid Styling](#datagrid-styling)
4. [Form Components](#form-components)
5. [Cards and Layouts](#cards-and-layouts)
6. [Typography](#typography)
7. [Dark Mode Toggle](#dark-mode-toggle)

---

## Basic Component Usage

### Buttons

All button variants automatically use theme styles:

```typescript
import { Button } from '@mui/material'
import { Add as AddIcon } from '@mui/icons-material'

// Contained button (primary action)
<Button variant="contained">
  Save Changes
</Button>

// Outlined button (secondary action)
<Button variant="outlined" startIcon={<AddIcon />}>
  Add Item
</Button>

// Text button (tertiary action)
<Button variant="text">
  Cancel
</Button>

// Different sizes
<Button variant="contained" size="small">Small</Button>
<Button variant="contained" size="medium">Medium</Button>
<Button variant="contained" size="large">Large</Button>
```

---

## Using Design Tokens

### Importing Tokens

```typescript
import { tokens } from '@/ui'
```

### Using Tokens in Styled Components

```typescript
import { styled } from '@mui/material/styles'
import { tokens } from '@/ui'

const CustomContainer = styled('div')({
  borderRadius: tokens.radius.lg,
  padding: tokens.spacing.xl,
  boxShadow: `0 ${tokens.elevation.sm}px 8px rgba(0,0,0,0.1)`,
  transition: `all ${tokens.duration.normal}ms ${tokens.easing.standard}`,
})
```

### Using Tokens in React Components

```typescript
import { tokens } from '@/ui'

function MyComponent() {
  const styles = {
    container: {
      borderRadius: tokens.radius.md,
      padding: tokens.spacing.lg,
      marginTop: tokens.spacing.xl,
    }
  }

  return <div style={styles.container}>Content</div>
}
```

---

## DataGrid Styling

DataGrid requires explicit sx prop since it's not part of MUI core:

```typescript
import { DataGrid } from '@mui/x-data-grid'
import { dataGridStyles } from '@/ui'

function MyTable() {
  return (
    <DataGrid
      rows={rows}
      columns={columns}
      sx={dataGridStyles}
      // OR merge with custom styles:
      sx={{
        ...dataGridStyles,
        height: 600,
      }}
    />
  )
}
```

---

## Form Components

### Text Fields

```typescript
import { TextField } from '@mui/material'

// Standard text field
<TextField
  label="Email"
  fullWidth
  required
  helperText="Enter your email address"
/>

// Multiline text area
<TextField
  label="Description"
  multiline
  rows={4}
  fullWidth
/>

// Small size for compact forms
<TextField
  label="Search"
  size="small"
  placeholder="Search items..."
/>
```

### Select Dropdowns

```typescript
import { FormControl, InputLabel, Select, MenuItem } from '@mui/material'

<FormControl fullWidth>
  <InputLabel>Priority</InputLabel>
  <Select value={priority} label="Priority">
    <MenuItem value="low">Low</MenuItem>
    <MenuItem value="medium">Medium</MenuItem>
    <MenuItem value="high">High</MenuItem>
  </Select>
</FormControl>
```

### Chips

```typescript
import { Chip } from '@mui/material'

// Status chip
<Chip label="Active" color="success" />

// Tag chip
<Chip label="Design" variant="outlined" />

// Small chip
<Chip label="New" size="small" color="primary" />
```

---

## Cards and Layouts

### Basic Card

```typescript
import { Card, CardContent, CardActions, Button, Typography } from '@mui/material'

<Card>
  <CardContent>
    <Typography variant="h5" gutterBottom>
      Card Title
    </Typography>
    <Typography variant="body2" color="text.secondary">
      Card description with automatic theme spacing and colors.
    </Typography>
  </CardContent>
  <CardActions>
    <Button size="small">Learn More</Button>
  </CardActions>
</Card>
```

### Card with Custom Elevation

```typescript
import { Card, CardContent } from '@mui/material'
import { tokens } from '@/ui'

<Card elevation={tokens.elevation.md}>
  <CardContent>
    Elevated card with higher shadow
  </CardContent>
</Card>
```

---

## Typography

### Using Typography Variants

```typescript
import { Typography } from '@mui/material'

// Page title
<Typography variant="h4" gutterBottom>
  Dashboard
</Typography>

// Section title
<Typography variant="h6" gutterBottom>
  Recent Activity
</Typography>

// Body text
<Typography variant="body1" paragraph>
  This is the main content paragraph with standard body text styling.
</Typography>

// Secondary text
<Typography variant="body2" color="text.secondary">
  Last updated 2 hours ago
</Typography>

// Caption
<Typography variant="caption" display="block">
  Additional information
</Typography>
```

### Typography with Custom Colors

```typescript
<Typography variant="body1" color="primary">
  Primary colored text
</Typography>

<Typography variant="body1" color="error">
  Error message
</Typography>

<Typography variant="body1" color="text.secondary">
  Secondary text
</Typography>
```

---

## Dark Mode Toggle

### Setting Up Theme Toggle

```typescript
import { useState } from 'react'
import { ThemeProvider, CssBaseline, IconButton } from '@mui/material'
import { Brightness4, Brightness7 } from '@mui/icons-material'
import { lightTheme, darkTheme } from '@/ui'

function App() {
  const [mode, setMode] = useState<'light' | 'dark'>('light')
  const theme = mode === 'light' ? lightTheme : darkTheme

  const toggleTheme = () => {
    setMode((prev) => (prev === 'light' ? 'dark' : 'light'))
  }

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <IconButton onClick={toggleTheme} color="inherit">
        {mode === 'light' ? <Brightness4 /> : <Brightness7 />}
      </IconButton>
      {/* Rest of your app */}
    </ThemeProvider>
  )
}
```

---

## Complete Page Example

Here's a complete example of a well-styled page using the theme:

```typescript
import {
  Box,
  Button,
  Card,
  CardContent,
  TextField,
  Typography,
  Chip,
} from '@mui/material'
import { Save as SaveIcon, Cancel as CancelIcon } from '@mui/icons-material'

export default function CreateTaskPage() {
  return (
    <Box sx={{ maxWidth: 800, mx: 'auto' }}>
      {/* Page Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" gutterBottom>
          Create New Task
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Fill in the details below to create a new task
        </Typography>
      </Box>

      {/* Form Card */}
      <Card>
        <CardContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* Task Name */}
            <TextField
              label="Task Name"
              fullWidth
              required
              placeholder="Enter task name"
            />

            {/* Description */}
            <TextField
              label="Description"
              fullWidth
              multiline
              rows={4}
              placeholder="Describe the task"
            />

            {/* Priority */}
            <Box>
              <Typography variant="body2" gutterBottom>
                Priority
              </Typography>
              <Box sx={{ display: 'flex', gap: 1 }}>
                <Chip label="Low" color="success" variant="outlined" />
                <Chip label="Medium" color="warning" />
                <Chip label="High" color="error" variant="outlined" />
              </Box>
            </Box>

            {/* Actions */}
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2, pt: 2 }}>
              <Button
                variant="outlined"
                startIcon={<CancelIcon />}
              >
                Cancel
              </Button>
              <Button
                variant="contained"
                startIcon={<SaveIcon />}
              >
                Create Task
              </Button>
            </Box>
          </Box>
        </CardContent>
      </Card>
    </Box>
  )
}
```

---

## Best Practices Summary

1. **Let the theme do the work** - Don't override styles unless necessary
2. **Use semantic variants** - `variant="contained"` instead of custom colors
3. **Use theme spacing** - `sx={{ p: 3 }}` instead of `padding: '24px'`
4. **Use color roles** - `color="primary"` instead of hex codes
5. **Use Typography variants** - `variant="h4"` instead of custom font sizes
6. **Reference tokens** - Import tokens for non-MUI elements
7. **Keep pages clean** - No inline styles or magic numbers

---

## Getting Help

- Check `UI_THEME_SPEC.md` for complete token reference
- Review `src/ui/tokens/tokens.ts` for available values
- Check `src/ui/theme/components.ts` for component defaults
- Look at existing demo pages in `src/pages/_lab/` for examples
