# Capability Manifest Examples

This directory contains example capability manifests for the AgentOS Marketplace.

## Directory Structure

```
manifests/
├── valid/              # Valid manifest examples
│   ├── web_scraper.yaml       # Extension example
│   ├── ops_assistant.yaml     # App example
│   └── security_pack.yaml     # Pack example
└── invalid/            # Invalid manifest examples (for testing)
    ├── missing_fields.yaml
    ├── invalid_signature.yaml
    └── malformed_yaml.yaml
```

## Quick Start

### 1. Validate a Manifest

```bash
python3 tools/validate_capability_manifest.py examples/manifests/valid/web_scraper.yaml
```

### 2. Create a New Manifest

```bash
python3 tools/create_capability_manifest.py \
  --id myorg.my_extension.v1.0.0 \
  --type extension \
  --actions read write \
  --sandbox medium \
  --trust-tier MEDIUM \
  --publisher myorg \
  --name "My Extension" \
  --description "My amazing extension" \
  --author "Your Name" \
  --output my_manifest.yaml
```

### 3. Sign a Manifest (requires PyNaCl)

```bash
# First, install PyNaCl
pip3 install pynacl

# Generate a keypair
python3 tools/sign_capability_manifest.py \
  --generate-keypair \
  --output-keys keys/

# Sign the manifest
python3 tools/sign_capability_manifest.py \
  --manifest my_manifest.yaml \
  --private-key keys/private.key \
  --output my_manifest_signed.yaml
```

### 4. Verify Signature

```bash
python3 tools/validate_capability_manifest.py \
  my_manifest_signed.yaml \
  --public-key $(cat keys/public.key)
```

## Valid Examples

### Web Scraper Extension

A read-only extension that scrapes web pages.

- **Type**: extension
- **Actions**: read, external
- **Sandbox**: medium
- **Trust Tier**: MEDIUM

See: `valid/web_scraper.yaml`

### Ops Assistant App

A DevOps automation app with system-level access.

- **Type**: app
- **Actions**: read, write, system
- **Sandbox**: low
- **Trust Tier**: HIGH

See: `valid/ops_assistant.yaml`

### Security Pack

A comprehensive security suite with full permissions.

- **Type**: pack
- **Actions**: read, write, external, system
- **Sandbox**: high
- **Trust Tier**: HIGH

See: `valid/security_pack.yaml`

## Invalid Examples

These examples demonstrate common errors:

1. **missing_fields.yaml** - Missing the `signature` field
2. **invalid_signature.yaml** - Empty signature
3. **malformed_yaml.yaml** - YAML syntax errors

## Manifest Field Reference

### Required Fields

- `capability_id`: Unique identifier (format: `publisher.capability.vX.Y.Z`)
- `capability_type`: Type of capability (`extension`, `app`, or `pack`)
- `declared_actions`: List of actions (`read`, `write`, `external`, `system`)
- `required_sandbox_level`: Isolation level (`none`, `low`, `medium`, `high`)
- `max_trust_tier_allowed`: Maximum trust level (`LOW`, `MEDIUM`, `HIGH`)
- `publisher_id`: Publisher identifier (must match capability_id prefix)
- `signature`: Cryptographic signature (format: `ed25519:<base64>`)
- `version`: Semantic version (format: `X.Y.Z`)
- `created_at`: Creation timestamp (ISO 8601 format)
- `metadata`: Object with:
  - `name`: Display name
  - `description`: Human-readable description
  - `author`: Author name
  - `homepage`: (optional) Website URL

## Full Documentation

For complete specification, see:
- `/docs/marketplace/CAPABILITY_MANIFEST_SPEC.md`

## Testing

Run the test suite:

```bash
python3 -m pytest tests/marketplace/test_capability_manifest.py -v
```

## Need Help?

- Read the spec: `docs/marketplace/CAPABILITY_MANIFEST_SPEC.md`
- Check the examples in this directory
- Run validation to see detailed error messages
