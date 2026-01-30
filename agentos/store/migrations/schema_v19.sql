-- Migration v0.19: Auth Profiles for Git Credential Management
-- Adds support for secure credential storage and management
-- Migration from v0.18 -> v0.19

-- ============================================
-- Auth Profiles: Git 认证配置
-- ============================================

CREATE TABLE IF NOT EXISTS auth_profiles (
    profile_id TEXT PRIMARY KEY,                     -- Profile ID (ULID)
    profile_name TEXT NOT NULL UNIQUE,               -- User-friendly name (e.g., "github-personal", "work-gitlab")
    profile_type TEXT NOT NULL,                      -- Auth type: ssh_key | pat_token | netrc

    -- SSH Key authentication
    ssh_key_path TEXT,                               -- Path to SSH private key (e.g., ~/.ssh/id_rsa)
    ssh_passphrase_encrypted TEXT,                   -- Encrypted SSH passphrase (optional)

    -- PAT Token authentication
    token_encrypted TEXT,                            -- Encrypted Personal Access Token
    token_provider TEXT,                             -- Provider: github | gitlab | bitbucket | gitea | other
    token_scopes TEXT,                               -- JSON array: token scopes (e.g., ["repo", "workflow"])

    -- Netrc authentication
    netrc_machine TEXT,                              -- Machine name for .netrc (e.g., github.com)
    netrc_login TEXT,                                -- Login username for .netrc
    netrc_password_encrypted TEXT,                   -- Encrypted password for .netrc

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_validated_at TIMESTAMP,                     -- Last time credentials were validated
    validation_status TEXT DEFAULT 'unknown',        -- Validation status: unknown | valid | invalid | expired
    validation_message TEXT,                         -- Validation message (error details if invalid)
    metadata TEXT,                                   -- JSON: additional metadata (encryption details, etc.)

    -- Constraints
    CHECK (profile_type IN ('ssh_key', 'pat_token', 'netrc')),
    CHECK (token_provider IS NULL OR token_provider IN ('github', 'gitlab', 'bitbucket', 'gitea', 'other')),
    CHECK (validation_status IN ('unknown', 'valid', 'invalid', 'expired'))
);

-- Indexes for auth_profiles
CREATE INDEX IF NOT EXISTS idx_auth_profiles_type
ON auth_profiles(profile_type);

CREATE INDEX IF NOT EXISTS idx_auth_profiles_provider
ON auth_profiles(token_provider)
WHERE token_provider IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_auth_profiles_status
ON auth_profiles(validation_status);

-- ============================================
-- Auth Profile Usage Log: 凭证使用审计
-- ============================================

CREATE TABLE IF NOT EXISTS auth_profile_usage (
    usage_id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL,                        -- Profile ID
    repo_id TEXT,                                    -- Associated repo ID (nullable for standalone validation)
    operation TEXT NOT NULL,                         -- Operation: clone | pull | push | validate
    status TEXT NOT NULL,                            -- Status: success | failure
    error_message TEXT,                              -- Error message if failed
    used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT,                                   -- JSON: additional context (command, duration, etc.)

    FOREIGN KEY (profile_id) REFERENCES auth_profiles(profile_id) ON DELETE CASCADE,

    CHECK (operation IN ('clone', 'pull', 'push', 'validate')),
    CHECK (status IN ('success', 'failure'))
);

-- Indexes for auth_profile_usage
CREATE INDEX IF NOT EXISTS idx_auth_profile_usage_profile
ON auth_profile_usage(profile_id, used_at DESC);

CREATE INDEX IF NOT EXISTS idx_auth_profile_usage_repo
ON auth_profile_usage(repo_id, used_at DESC)
WHERE repo_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_auth_profile_usage_status
ON auth_profile_usage(status, used_at DESC);

-- ============================================
-- Encryption Key Storage: 加密密钥管理
-- ============================================

CREATE TABLE IF NOT EXISTS encryption_keys (
    key_id TEXT PRIMARY KEY,                         -- Key ID (ULID)
    key_type TEXT NOT NULL,                          -- Key type: master | derived
    key_encrypted BLOB NOT NULL,                     -- Encrypted key material
    salt BLOB,                                       -- Salt for key derivation
    algorithm TEXT NOT NULL DEFAULT 'AES-256-GCM',   -- Encryption algorithm
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rotated_at TIMESTAMP,                            -- Last key rotation timestamp
    metadata TEXT,                                   -- JSON: additional metadata

    CHECK (key_type IN ('master', 'derived'))
);

-- Index for encryption_keys
CREATE INDEX IF NOT EXISTS idx_encryption_keys_type
ON encryption_keys(key_type);

-- ============================================
-- 设计原则和安全考虑
-- ============================================

-- Auth Profile 设计原则：
-- 1. 凭证分离：凭证存储与项目/仓库解耦，通过 profile_name 关联
-- 2. 多种认证方式：支持 SSH Key、PAT Token、Netrc（可扩展 OAuth）
-- 3. 安全存储：敏感信息（密码、Token、Passphrase）加密存储
-- 4. 审计追踪：所有凭证使用操作记录到 auth_profile_usage
-- 5. 验证机制：定期验证凭证有效性，记录验证状态
-- 6. 环境变量回退：代码层支持从环境变量读取（如 GITHUB_TOKEN）

-- 安全实现策略：
-- 1. 加密存储：使用 AES-256-GCM 加密敏感字段
-- 2. 密钥派生：从系统密钥派生加密密钥（PBKDF2 或 Argon2）
-- 3. 盐值存储：每个凭证使用独立盐值
-- 4. 密钥轮换：支持定期密钥轮换，旧密钥保留用于解密历史数据
-- 5. 权限控制：数据库文件权限限制为用户只读（chmod 600）

-- Profile Type 定义：
-- ssh_key: SSH 私钥认证（需要 ssh_key_path，可选 ssh_passphrase_encrypted）
-- pat_token: Personal Access Token（需要 token_encrypted 和 token_provider）
-- netrc: .netrc 文件认证（需要 netrc_machine、netrc_login、netrc_password_encrypted）

-- Token Provider 定义：
-- github: GitHub PAT (https://github.com/settings/tokens)
-- gitlab: GitLab PAT (https://gitlab.com/-/profile/personal_access_tokens)
-- bitbucket: Bitbucket App Password (https://bitbucket.org/account/settings/app-passwords/)
-- gitea: Gitea Token (self-hosted)
-- other: 其他 Git 服务商

-- Validation Status 定义：
-- unknown: 未验证（新建凭证）
-- valid: 验证通过（Available）
-- invalid: 验证失败（凭证无效或权限不足）
-- expired: 凭证已过期（需要更新）

-- Operation 定义：
-- clone: 克隆仓库
-- pull: 拉取更新
-- push: 推送变更
-- validate: 验证凭证（测试连接）

-- ============================================
-- 使用示例
-- ============================================

-- 示例 1: 创建 GitHub PAT Profile
-- INSERT INTO auth_profiles (
--     profile_id, profile_name, profile_type,
--     token_encrypted, token_provider, token_scopes,
--     validation_status, metadata
-- ) VALUES (
--     '01H8X...',                                    -- ULID
--     'github-personal',                             -- 用户友好名称
--     'pat_token',                                   -- PAT 认证
--     '<encrypted_token>',                           -- 加密后的 Token
--     'github',                                      -- GitHub Provider
--     '["repo", "workflow"]',                        -- Token 权限范围
--     'unknown',                                     -- 待验证
--     json_object('comment', 'Personal GitHub token for private repos')
-- );

-- 示例 2: 创建 SSH Key Profile
-- INSERT INTO auth_profiles (
--     profile_id, profile_name, profile_type,
--     ssh_key_path, ssh_passphrase_encrypted,
--     validation_status, metadata
-- ) VALUES (
--     '01H8Y...',                                    -- ULID
--     'work-ssh',                                    -- 用户友好名称
--     'ssh_key',                                     -- SSH Key 认证
--     '~/.ssh/id_rsa_work',                          -- SSH 私钥路径
--     '<encrypted_passphrase>',                      -- 加密后的 Passphrase（可选）
--     'unknown',                                     -- 待验证
--     json_object('comment', 'Work SSH key for company repos')
-- );

-- 示例 3: 关联 Profile 到仓库
-- UPDATE project_repos
-- SET auth_profile = 'github-personal'
-- WHERE repo_id = '01H8Z...';

-- 示例 4: 记录使用审计
-- INSERT INTO auth_profile_usage (
--     profile_id, repo_id, operation, status, metadata
-- ) VALUES (
--     '01H8X...',                                    -- Profile ID
--     '01H8Z...',                                    -- Repo ID
--     'clone',                                       -- 克隆操作
--     'success',                                     -- 成功
--     json_object('duration_ms', 1234, 'size_mb', 56)
-- );

-- Update schema version
INSERT OR REPLACE INTO schema_version (version) VALUES ('0.19.0');
