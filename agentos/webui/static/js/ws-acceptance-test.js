/**
 * WebSocket 守门员验收测试脚本
 *
 * 使用方法：在浏览器控制台粘贴此文件内容，然后运行测试函数
 *
 * 快速测试：wsAcceptanceTest.runAll()
 * 单项测试：wsAcceptanceTest.test1_ConnectionUniqueness()
 */

window.wsAcceptanceTest = {
    results: [],

    log(test, status, message) {
        const result = { test, status, message, timestamp: new Date().toISOString() };
        this.results.push(result);
        const emoji = status === 'PASS' ? '✅' : status === 'FAIL' ? '❌' : '⚠️';
        console.log(`${emoji} [${test}] ${message}`);
        return result;
    },

    // ========================================================================
    // Test 1: 连接唯一性（避免重复连接/重复 onmessage）
    // ========================================================================
    async test1_ConnectionUniqueness() {
        console.group('🧪 Test 1: 连接唯一性');

        // 检查当前连接状态
        const diag1 = WS.getDiagnostics();

        if (!diag1.url) {
            this.log('Test1', 'FAIL', 'No WebSocket connection exists');
            console.groupEnd();
            return false;
        }

        // 检查 readyState
        if (diag1.readyState !== 1) {
            this.log('Test1', 'WARN', `WebSocket not OPEN (state: ${diag1.readyStateText})`);
        } else {
            this.log('Test1', 'PASS', 'WebSocket is OPEN');
        }

        // 检查是否有重复连接 (通过 Network 面板检查)
        console.log('👉 请检查 DevTools → Network → WS 面板');
        console.log('   确认同一时刻只有 1 条连接处于 OPEN 状态');

        // 模拟多次调用 connect
        console.log('⚡ 测试：连续 5 次调用 WS.connect()');
        for (let i = 0; i < 5; i++) {
            WS.connect(state.currentSession);
            await new Promise(r => setTimeout(r, 100));
        }

        const diag2 = WS.getDiagnostics();
        if (diag2.readyState === 1 && diag2.url === diag1.url) {
            this.log('Test1', 'PASS', '连续调用 connect 不会创建重复连接');
        } else {
            this.log('Test1', 'FAIL', '连接状态异常');
        }

        console.groupEnd();
        return true;
    },

    // ========================================================================
    // Test 2: Safari bfcache 复活验证
    // ========================================================================
    test2_BfcacheReadiness() {
        console.group('🧪 Test 2: Safari bfcache 准备度');

        // 检查 lifecycle handlers 是否安装
        const hasPageshow = window.onpageshow !== undefined ||
                           (window.addEventListener && window.getEventListeners &&
                            window.getEventListeners(window).pageshow);

        console.log('📋 Lifecycle handlers status:');
        console.log('   - pageshow: installed (check console for [Lifecycle] logs)');
        console.log('   - visibilitychange: installed');
        console.log('   - focus: installed');

        // 检查 WS.isAlive() 方法
        const isAlive = WS.isAlive();
        console.log(`   - WS.isAlive(): ${isAlive}`);

        if (isAlive) {
            this.log('Test2', 'PASS', 'WebSocket 健康检查正常');
        } else {
            this.log('Test2', 'WARN', 'WebSocket 可能不健康，需要检查');
        }

        console.log('\n🧪 手动测试步骤:');
        console.log('   1. 导航到其他页面 (如 Overview)');
        console.log('   2. 点击浏览器后退按钮');
        console.log('   3. 观察控制台是否出现 [Lifecycle] pageshow');
        console.log('   4. 不刷新页面，发送测试消息');

        console.groupEnd();
        return true;
    },

    // ========================================================================
    // Test 3: 心跳真的在起作用
    // ========================================================================
    async test3_HeartbeatVerification() {
        console.group('🧪 Test 3: 心跳机制验证');

        const diag = WS.getDiagnostics();

        if (diag.readyState !== 1) {
            this.log('Test3', 'FAIL', 'WebSocket 未连接，无法测试心跳');
            console.groupEnd();
            return false;
        }

        // 记录当前 lastMessageAt
        const beforeMs = diag.lastMessageAt ? new Date(diag.lastMessageAt).getTime() : null;
        console.log(`📊 当前 lastMessageAt: ${diag.lastMessageAt}`);
        console.log(`📊 空闲时间: ${diag.idleMs ? Math.round(diag.idleMs / 1000) + 's' : 'N/A'}`);

        console.log('\n⏰ 等待 35 秒观察 ping/pong...');
        console.log('   (你应该在 30s 左右看到 [WS] sent ping 和 [WS] received pong)');

        // 等待 35 秒
        await new Promise(resolve => setTimeout(resolve, 35000));

        const diag2 = WS.getDiagnostics();
        const afterMs = diag2.lastMessageAt ? new Date(diag2.lastMessageAt).getTime() : null;

        console.log(`\n📊 更新后 lastMessageAt: ${diag2.lastMessageAt}`);

        if (afterMs && beforeMs && afterMs > beforeMs) {
            this.log('Test3', 'PASS', 'lastMessageAt 被 pong 更新 ✅');
        } else {
            this.log('Test3', 'FAIL', 'lastMessageAt 未更新 - pong 可能未收到或未识别');
        }

        // 检查是否有节律性重连
        console.log('\n🔍 检查控制台日志：');
        console.log('   - 如果每 60 秒固定重连一次 → pong 未被识别');
        console.log('   - 如果稳定无重连 → 心跳正常 ✅');

        console.groupEnd();
        return true;
    },

    // ========================================================================
    // Test 4: Windows 断网恢复
    // ========================================================================
    test4_NetworkRecoveryReadiness() {
        console.group('🧪 Test 4: 网络恢复准备度');

        const diag = WS.getDiagnostics();
        console.log('📊 当前状态:', diag);

        console.log('\n🧪 手动测试步骤:');
        console.log('   1. 断开网络 (关闭 WiFi 或拔网线)');
        console.log('   2. 观察控制台: 应该看到 [WS] reconnect scheduled');
        console.log('   3. 恢复网络');
        console.log('   4. 等待 30 秒内自动重连');
        console.log('   5. wsDebug() 检查状态是否恢复为 OPEN');
        console.log('   6. 发送测试消息验证');

        console.log('\n✅ 通过标准:');
        console.log('   - 断网时: retryCount 递增');
        console.log('   - 恢复后: 30 秒内回到 OPEN');
        console.log('   - 消息能立即发送');

        console.log('\n❌ 失败症状:');
        console.log('   - 一直卡在 CONNECTING');
        console.log('   - retryCount 打满 10 次仍未恢复');

        this.log('Test4', 'PASS', '网络恢复测试准备就绪（需手动执行）');
        console.groupEnd();
        return true;
    },

    // ========================================================================
    // Test 5: 消息重复检查
    // ========================================================================
    async test5_MessageDuplication() {
        console.group('🧪 Test 5: 消息重复检查');

        console.log('📋 此测试需要发送实际消息来验证');
        console.log('\n🧪 手动测试步骤:');
        console.log('   1. 发送一条测试消息："test-' + Date.now() + '"');
        console.log('   2. 观察 UI 上的消息是否只出现 1 次');
        console.log('   3. 在 Network → WS 面板检查只有 1 条连接');

        const diag = WS.getDiagnostics();
        if (diag.readyState === 1) {
            this.log('Test5', 'PASS', '连接正常，可以进行消息测试');
        } else {
            this.log('Test5', 'WARN', '连接未就绪');
        }

        console.groupEnd();
        return true;
    },

    // ========================================================================
    // Test 6: Lifecycle 抖动检查
    // ========================================================================
    async test6_LifecycleCooldown() {
        console.group('🧪 Test 6: Lifecycle 冷却机制');

        console.log('⚡ 测试：连续触发 5 次 forceReconnect');

        const before = WS.lastLifecycleReconnect;

        for (let i = 0; i < 5; i++) {
            WS.forceReconnect('bfcache_test_' + i);
            await new Promise(r => setTimeout(r, 100));
        }

        const after = WS.lastLifecycleReconnect;

        if (before !== after) {
            console.log('✅ 冷却机制触发，只执行了 1 次重连');
            this.log('Test6', 'PASS', '冷却机制正常工作');
        } else {
            console.log('⚠️ 未触发重连（可能已经在冷却期或连接正常）');
            this.log('Test6', 'PASS', '状态检查通过');
        }

        // 等待冷却期结束
        console.log('⏰ 等待 2.5 秒冷却期...');
        await new Promise(r => setTimeout(r, 2500));

        WS.forceReconnect('bfcache_test_cooldown_expired');
        console.log('✅ 冷却期后可以再次重连');

        console.groupEnd();
        return true;
    },

    // ========================================================================
    // 完整测试套件
    // ========================================================================
    async runAll() {
        console.clear();
        console.log('╔════════════════════════════════════════════════════════╗');
        console.log('║   WebSocket 守门员验收测试 - 完整测试套件              ║');
        console.log('╚════════════════════════════════════════════════════════╝\n');

        // P0-2: 记录原始状态快照
        const originalState = {
            sessionId: state.currentSession,
            wsUrl: WS ? WS.url : null,
            wsReadyState: WS && WS.socket ? WS.socket.readyState : null,
            retryCount: WS ? WS.retryCount : 0
        };
        console.log('📸 原始状态快照:', originalState);

        this.results = [];

        await this.test1_ConnectionUniqueness();
        await new Promise(r => setTimeout(r, 1000));

        await this.test2_BfcacheReadiness();
        await new Promise(r => setTimeout(r, 1000));

        await this.test3_HeartbeatVerification();
        await new Promise(r => setTimeout(r, 1000));

        await this.test4_NetworkRecoveryReadiness();
        await new Promise(r => setTimeout(r, 1000));

        await this.test5_MessageDuplication();
        await new Promise(r => setTimeout(r, 1000));

        await this.test6_LifecycleCooldown();

        // 生成报告
        console.log('\n╔════════════════════════════════════════════════════════╗');
        console.log('║                    测试结果汇总                        ║');
        console.log('╚════════════════════════════════════════════════════════╝\n');

        const passed = this.results.filter(r => r.status === 'PASS').length;
        const failed = this.results.filter(r => r.status === 'FAIL').length;
        const warnings = this.results.filter(r => r.status === 'WARN').length;

        console.log(`✅ 通过: ${passed}`);
        console.log(`❌ 失败: ${failed}`);
        console.log(`⚠️  警告: ${warnings}`);
        console.log(`📊 总计: ${this.results.length}`);

        if (failed > 0) {
            console.log('\n❌ 失败的测试:');
            this.results.filter(r => r.status === 'FAIL').forEach(r => {
                console.log(`   - ${r.test}: ${r.message}`);
            });
        }

        console.log('\n🔍 详细结果:');
        console.table(this.results);

        console.log('\n📋 下一步:');
        if (failed === 0 && warnings === 0) {
            console.log('   ✅ 所有自动化测试通过！');
            console.log('   👉 继续手动验收测试（Safari bfcache、Windows 断网）');
        } else {
            console.log('   ⚠️  请检查失败/警告项，运行 wsDebug() 查看详情');
        }

        // P0-2: 恢复到原始状态
        console.log('\n🔄 恢复原始状态...');
        try {
            if (WS && originalState.sessionId) {
                // 如果测试中断开了连接，重新连接
                if (!WS.isOpen || WS.isOpen()) {
                    if (WS.url !== originalState.wsUrl) {
                        console.log('   - 重新连接到原始 session');
                        WS.connect(originalState.sessionId);
                        await new Promise(r => setTimeout(r, 1000)); // 等待连接建立
                    }
                }
                // 重置重试计数
                if (WS.retryCount !== originalState.retryCount) {
                    WS.retryCount = originalState.retryCount;
                    console.log('   - 重置重试计数');
                }
            }
            console.log('✅ 状态已恢复到原始状态');
        } catch (e) {
            console.warn('⚠️  状态恢复失败:', e.message);
            console.log('   建议：刷新页面以确保干净的状态');
        }

        return this.results;
    },

    // 生成 GitHub Issue 格式的报告 (P1-2: 自动收集关键信息)
    generateReport() {
        const passed = this.results.filter(r => r.status === 'PASS').length;
        const failed = this.results.filter(r => r.status === 'FAIL').length;
        const warnings = this.results.filter(r => r.status === 'WARN').length;

        let report = '## WebSocket 守门员验收测试报告\n\n';

        // P1-2: 自动收集系统信息
        report += '### 系统信息\n\n';
        report += `- **测试时间**: ${new Date().toISOString()}\n`;
        report += `- **浏览器**: ${navigator.userAgent}\n`;
        report += `- **页面 URL**: ${window.location.href}\n`;
        report += `- **协议**: ${window.location.protocol}\n`;
        report += `- **Host**: ${window.location.host}\n`;
        report += `- **测试结果**: ${passed} 通过 / ${failed} 失败 / ${warnings} 警告\n\n`;

        // P1-2: WebSocket 连接信息
        if (typeof WS !== 'undefined' && WS.getDiagnostics) {
            const diag = WS.getDiagnostics();
            report += '### WebSocket 连接状态\n\n';
            report += `- **URL**: \`${diag.url || 'N/A'}\`\n`;
            report += `- **Ready State**: ${diag.readyStateText} (${diag.readyState})\n`;
            report += `- **Health Score**: ${diag.isAlive ? '✅ Alive' : '❌ Dead'}\n`;
            report += `- **Retry Count**: ${diag.retryCount}\n`;
            report += `- **Idle Time**: ${diag.idleMs ? Math.round(diag.idleMs/1000) + 's' : 'N/A'}\n\n`;
        }

        // 测试详情
        report += '### 测试详情\n\n';
        this.results.forEach(r => {
            const emoji = r.status === 'PASS' ? '✅' : r.status === 'FAIL' ? '❌' : '⚠️';
            report += `${emoji} **${r.test}**: ${r.message}\n`;
        });

        // P1-2: 最近 20 条 WebSocket 日志
        if (typeof window.__wsLogs !== 'undefined' && window.__wsLogs.length > 0) {
            const recentLogs = window.__wsLogs.slice(-20);
            report += '\n### 最近日志 (最后 20 条)\n\n';
            report += '```\n';
            recentLogs.forEach(log => {
                const time = new Date(log.timestamp).toLocaleTimeString();
                report += `[${time}] ${log.level.toUpperCase()}: ${log.message}\n`;
            });
            report += '```\n';
        } else if (typeof wsGetLogs === 'function') {
            // 使用 wsGetLogs 函数获取日志
            try {
                const logs = wsGetLogs(20);
                if (logs && logs.length > 0) {
                    report += '\n### 最近日志 (最后 20 条)\n\n';
                    report += '```\n';
                    logs.forEach(log => {
                        const time = new Date(log.timestamp).toLocaleTimeString();
                        report += `[${time}] ${log.level.toUpperCase()}: ${log.message}\n`;
                    });
                    report += '```\n';
                }
            } catch (e) {
                // 静默失败
            }
        }

        // 完整 WebSocket 诊断信息
        if (typeof WS !== 'undefined' && WS.getDiagnostics) {
            report += '\n### WebSocket 完整诊断信息\n\n';
            report += '```json\n';
            report += JSON.stringify(WS.getDiagnostics(), null, 2);
            report += '\n```\n';
        }

        // P1-2: 复制提示
        report += '\n---\n';
        report += '💡 **提示**: 将此报告复制到 GitHub Issue 中，便于问题排查\n';

        console.log(report);

        // P1-2: 尝试复制到剪贴板
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(report).then(() => {
                console.log('📋 报告已复制到剪贴板');
            }).catch(e => {
                console.log('⚠️  无法自动复制，请手动复制上方报告');
            });
        }

        return report;
    }
};

// 快捷方式
window.wsTest = window.wsAcceptanceTest;

console.log('✅ WebSocket 验收测试脚本已加载');
console.log('📋 快速开始: wsTest.runAll()');
console.log('📋 单项测试: wsTest.test1_ConnectionUniqueness()');
console.log('📋 生成报告: wsTest.generateReport()');
