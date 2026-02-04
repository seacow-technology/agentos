/**
 * Phase 5 Feature Template
 *
 * 此文件展示Phase 5功能必须满足的所有Gate要求
 * 复制此模板作为新功能的起点
 *
 * Gates Checklist:
 * - [ ] G1: Dry-Run支持
 * - [ ] G2: Blast Radius声明
 * - [ ] G3: Idempotency声明
 * - [ ] G4: Kill-Switch集成
 * - [ ] G5: Audit & Rollback
 */

// ============================================
// G2: Blast Radius声明 (必须)
// ============================================
export const BLAST_RADIUS = {
  scope: 'user' as const, // 'user' | 'project' | 'tenant' | 'global'
  max_records: 1,
  description: 'Only affects the specified user - cannot impact other users',
}

// ============================================
// G3: Idempotency声明 (必须)
// ============================================
export const IDEMPOTENT = true
export const IDEMPOTENCY_KEY = 'request_id' // 或 'operation_id' 或 'business_key'

// ============================================
// G5: Rollback声明 (可选，但强烈建议)
// ============================================
export const ROLLBACK_AVAILABLE = true

// ============================================
// Types
// ============================================
interface ExampleFeatureParams {
  userId: string
  data: {
    name: string
    value: number
  }
  requestId: string // G3要求：用于幂等性
}

interface ExampleFeatureResult {
  success: boolean
  operationId: string
  mode: 'dry-run' | 'live'
  affectedRecords: number
}

// ============================================
// G4: Feature Flag检查
// ============================================
import { featureFlags } from '@/lib/feature-flags'

function checkFeatureEnabled() {
  if (!featureFlags.isEnabled('example-feature')) {
    throw new FeatureDisabledError('example-feature is disabled', {
      code: 'FEATURE_DISABLED',
      statusCode: 503,
    })
  }
}

// ============================================
// G5: Audit Log集成
// ============================================
import { auditLog } from '@/lib/audit-log'
import { sha256 } from '@/lib/crypto'

async function writeAuditLog(
  operationId: string,
  actor: string,
  action: string,
  scope: Record<string, any>,
  payload: any
) {
  await auditLog.write({
    operation_id: operationId,
    actor,
    action,
    scope,
    payload_hash: sha256(JSON.stringify(payload)),
    timestamp: new Date(),
    rollback_available: ROLLBACK_AVAILABLE,
  })
}

// ============================================
// 主功能函数 (G1: 支持dry-run)
// ============================================
export async function exampleFeature(
  params: ExampleFeatureParams,
  mode: 'dry-run' | 'live' = 'dry-run' // G1: 默认dry-run，确保安全
): Promise<ExampleFeatureResult> {
  const { userId, data, requestId } = params

  // G4: Kill-Switch检查
  checkFeatureEnabled()

  // G3: 幂等性检查
  const existingOperation = await checkRequestId(requestId)
  if (existingOperation) {
    console.log('[IDEMPOTENT] Returning existing result for:', requestId)
    return existingOperation
  }

  // G1: Dry-run模式
  if (mode === 'dry-run') {
    console.log('[DRY-RUN] Would execute example-feature with:', params)
    console.log('[DRY-RUN] Blast Radius:', BLAST_RADIUS)
    console.log('[DRY-RUN] Would write audit log')

    return {
      success: true,
      operationId: requestId,
      mode: 'dry-run',
      affectedRecords: 0, // 无实际影响
    }
  }

  // Live模式：执行真实操作
  try {
    // 1. 备份数据（用于rollback）
    const backup = await db.queryOne(
      'SELECT * FROM users WHERE id = ? LIMIT 1', // G2: 限定scope
      [userId]
    )

    // 2. 执行操作（在事务中）
    await db.transaction(async (tx) => {
      // G2: 所有写操作必须有WHERE子句限定scope
      await tx.execute(
        'UPDATE users SET name = ?, value = ? WHERE id = ? LIMIT 1',
        [data.name, data.value, userId]
      )

      // G5: 写audit log
      await writeAuditLog(
        requestId,
        userId,
        'update_user_data',
        { userId },
        data
      )

      // G5: 保存backup用于rollback
      if (ROLLBACK_AVAILABLE) {
        await tx.execute(
          'INSERT INTO rollback_data (operation_id, table_name, record_id, data) VALUES (?, ?, ?, ?)',
          [requestId, 'users', userId, JSON.stringify(backup)]
        )
      }

      // G3: 记录requestId（防止重复执行）
      await tx.execute(
        'INSERT INTO request_log (request_id, completed_at) VALUES (?, NOW())',
        [requestId]
      )
    })

    return {
      success: true,
      operationId: requestId,
      mode: 'live',
      affectedRecords: 1,
    }
  } catch (error) {
    // 错误处理 + audit log
    await auditLog.write({
      operation_id: requestId,
      actor: userId,
      action: 'update_user_data_failed',
      scope: { userId },
      error: String(error),
      timestamp: new Date(),
    })

    throw error
  }
}

// ============================================
// G3: 幂等性辅助函数
// ============================================
async function checkRequestId(requestId: string): Promise<ExampleFeatureResult | null> {
  const existing = await db.queryOne(
    'SELECT * FROM request_log WHERE request_id = ?',
    [requestId]
  )

  if (existing) {
    return {
      success: true,
      operationId: requestId,
      mode: 'live',
      affectedRecords: 0, // 已执行过
    }
  }

  return null
}

// ============================================
// G5: Rollback Handler (可选但强烈建议)
// ============================================
export const ROLLBACK_HANDLER = async (operationId: string): Promise<void> => {
  console.log('[ROLLBACK] Starting rollback for:', operationId)

  // 1. 查找backup数据
  const backup = await db.queryOne(
    'SELECT * FROM rollback_data WHERE operation_id = ?',
    [operationId]
  )

  if (!backup) {
    throw new Error(`No backup found for operation: ${operationId}`)
  }

  // 2. 恢复数据
  const originalData = JSON.parse(backup.data)
  await db.execute(
    'UPDATE users SET name = ?, value = ? WHERE id = ?',
    [originalData.name, originalData.value, originalData.id]
  )

  // 3. 记录rollback
  await auditLog.write({
    operation_id: `rollback-${operationId}`,
    actor: 'system',
    action: 'rollback_user_data',
    scope: { userId: originalData.id },
    original_operation_id: operationId,
    timestamp: new Date(),
  })

  console.log('[ROLLBACK] Successfully rolled back:', operationId)
}

// ============================================
// Mock Database (仅用于示例)
// ============================================
class FeatureDisabledError extends Error {
  code: string
  statusCode: number

  constructor(message: string, { code, statusCode }: { code: string; statusCode: number }) {
    super(message)
    this.code = code
    this.statusCode = statusCode
    this.name = 'FeatureDisabledError'
  }
}

const db = {
  queryOne: async (sql: string, params: any[]) => {
    console.log('[DB] Query:', sql, params)
    return null
  },
  execute: async (sql: string, params: any[]) => {
    console.log('[DB] Execute:', sql, params)
  },
  transaction: async (callback: (tx: any) => Promise<void>) => {
    console.log('[DB] Starting transaction')
    await callback(db)
    console.log('[DB] Committing transaction')
  },
}

// ============================================
// 导出清单（用于Gate检查）
// ============================================
export const PHASE5_FEATURE_METADATA = {
  name: 'example-feature',
  gates: {
    g1_dry_run: true,
    g2_blast_radius: BLAST_RADIUS,
    g3_idempotent: IDEMPOTENT,
    g4_kill_switch: true,
    g5_audit: true,
    g5_rollback: ROLLBACK_AVAILABLE,
  },
  production_ready: false, // 设置为true后才能上线
}
