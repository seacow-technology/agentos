# Minimal Multi-Repo Example

**Simplest possible multi-repository project**

This example demonstrates the bare minimum configuration needed for a multi-repo project.

## Files

- `project.yaml` - Project configuration
- `demo.sh` - One-click demo script

## Quick Start

```bash
# Run the demo
bash demo.sh
```

## What It Does

1. Creates two local test repositories
2. Imports them as a multi-repo project
3. Verifies the import
4. Creates a task spanning both repos
5. Traces task activity

## Configuration

The `project.yaml` defines a minimal project with two repos:

```yaml
name: minimal-demo
description: Minimal multi-repo example

repos:
  - name: repoA
    path: ./repoA
    role: code

  - name: repoB
    path: ./repoB
    role: code
```

## Expected Output

```
=== Multi-Repo Minimal Example ===
1. Creating local test repos...
2. Importing project...
✅ Project imported successfully!
3. Verifying import...
📚 Project: minimal-demo
📦 Repositories: 2
4. Creating cross-repo task...
✅ Task created
5. Tracing task...
Task activity across repos
✓ Demo complete!
```

## Next Steps

- Try Example 02: Frontend + Backend
- See full documentation: `docs/projects/MULTI_REPO_PROJECTS.md`
