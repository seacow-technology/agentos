# Frontend + Backend Example

**Realistic full-stack application with separate repositories**

This example demonstrates a typical microservices architecture with separate frontend and backend repositories.

## Architecture

```
my-fullstack-app/
  ├── backend/       (Python FastAPI)
  │   ├── api/
  │   ├── models/
  │   └── tests/
  └── frontend/      (React TypeScript)
      ├── src/
      ├── public/
      └── tests/
```

## What This Example Shows

1. **Cross-Repo Task Execution**: Task modifies both backend API and frontend consumer
2. **Dependency Tracking**: Frontend depends on backend API contract
3. **Artifact References**: Commits are linked across repos
4. **Audit Trail**: Full lineage across both repositories

## Files

- `project.yaml` - Project configuration with 2 repos
- `demo.sh` - Automated demo script
- `cleanup.sh` - Remove demo artifacts

## Quick Start

```bash
bash demo.sh
```

## Manual Steps

### 1. Setup

```bash
# Create demo workspace
mkdir -p /tmp/fullstack-demo
cd /tmp/fullstack-demo
```

### 2. Create Backend Repo

```bash
mkdir backend
cd backend
git init

# Create FastAPI structure
cat > api.py << 'PYTHON'
from fastapi import FastAPI

app = FastAPI()

@app.get("/users")
def get_users():
    return [{"id": 1, "name": "Alice"}]
PYTHON

cat > requirements.txt << 'TXT'
fastapi==0.104.1
uvicorn==0.24.0
TXT

git add .
git commit -m "Initial backend API"
cd ..
```

### 3. Create Frontend Repo

```bash
mkdir frontend
cd frontend
git init

# Create React structure
mkdir -p src
cat > src/App.tsx << 'TS'
import { useState, useEffect } from 'react';

function App() {
  const [users, setUsers] = useState([]);

  useEffect(() => {
    fetch('http://localhost:8000/users')
      .then(res => res.json())
      .then(data => setUsers(data));
  }, []);

  return <div>Users: {JSON.stringify(users)}</div>;
}
TS

git add .
git commit -m "Initial frontend app"
cd ..
```

### 4. Import Project

```bash
cat > project.yaml << 'YAML'
name: my-fullstack-app
description: Full-stack app with FastAPI backend and React frontend

repos:
  - name: backend
    path: ./backend
    role: code
    writable: true

  - name: frontend
    path: ./frontend
    role: code
    writable: true
YAML

agentos project import --from project.yaml --workspace-root /tmp/fullstack-demo --yes
```

### 5. Verify Import

```bash
agentos project repos list my-fullstack-app
```

Expected output:
```
📚 Project: my-fullstack-app
📦 Repositories: 2

┌────────────────────────────────────────────┐
│  Repositories in 'my-fullstack-app'        │
├──────────┬───────────┬──────┬──────────┤
│ Name     │ Path      │ Role │ Writable │
├──────────┼───────────┼──────┼──────────┤
│ backend  │ ./backend │ code │ ✓        │
│ frontend │ ./frontend│ code │ ✓        │
└──────────┴───────────┴──────┴──────────┘
```

### 6. Create Cross-Repo Task

```bash
# Simulate a task that modifies both repos
cd /tmp/fullstack-demo

# Update backend API
cd backend
cat >> api.py << 'PYTHON'

@app.get("/users/{user_id}")
def get_user(user_id: int):
    return {"id": user_id, "name": f"User {user_id}"}
PYTHON
git add api.py
git commit -m "Add user detail endpoint"

# Update frontend to use new endpoint
cd ../frontend
cat > src/UserDetail.tsx << 'TS'
import { useEffect, useState } from 'react';

export function UserDetail({ userId }: { userId: number }) {
  const [user, setUser] = useState(null);

  useEffect(() => {
    fetch(`http://localhost:8000/users/${userId}`)
      .then(res => res.json())
      .then(data => setUser(data));
  }, [userId]);

  return user ? <div>{user.name}</div> : <div>Loading...</div>;
}
TS
git add src/UserDetail.tsx
git commit -m "Add user detail component"

cd ..
```

### 7. Trace Activity

```bash
agentos project trace my-fullstack-app
```

## Expected Outcomes

1. **Project imported** with 2 repositories
2. **Both repos accessible** in workspace
3. **Cross-repo changes tracked** in audit trail
4. **Dependency detected** between frontend and backend

## Cleanup

```bash
# Remove demo workspace
rm -rf /tmp/fullstack-demo

# Remove project from AgentOS
sqlite3 ~/.agentos/db.sqlite "DELETE FROM projects WHERE id='my-fullstack-app';"
```

Or run:
```bash
bash cleanup.sh
```

## Key Learnings

1. **Repository Isolation**: Each repo has independent git history
2. **Unified Management**: Single project view across repos
3. **Cross-Repo Tasks**: Tasks can modify multiple repos atomically
4. **Dependency Tracking**: AgentOS detects cross-repo dependencies

## Next Steps

- Try modifying only one repo (scoped changes)
- Add path filters to limit access
- Add a third repo (e.g., shared library)
- Explore dependency visualization

## See Also

- [Multi-Repo Architecture](../../../docs/projects/MULTI_REPO_PROJECTS.md)
- [CLI Usage Guide](../../../docs/cli/PROJECT_IMPORT.md)
