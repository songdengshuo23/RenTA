<template>
  <section class="dashboard-page">
    <div class="container" :class="{ 'animate-in': showContent }">
      <header class="page-header">
        <div class="page-header-left">
          <span class="page-issue">Workshop · 工作台</span>
          <h1 class="page-title">
            <span v-if="wbTab === 'activity'">实时调用 <em>监控</em></span>
            <span v-else>智能体 <em>管理</em></span>
          </h1>
          <p class="page-desc" v-if="wbTab === 'activity'">每个智能体代表一台电脑 — 亮屏表示正在被调用,熄屏表示空闲中。点击屏幕模拟一次调用。</p>
          <p class="page-desc" v-else>管理你创建的智能体 — 编辑、下架、查看密钥。</p>
        </div>
        <div class="page-header-right">
          <!-- 顶部 tab 切换 -->
          <div class="wb-tab-switch">
            <button
              class="wb-tab-btn"
              :class="{ active: wbTab === 'activity' }"
              @click="switchTab('activity')"
            >实时监控</button>
            <button
              class="wb-tab-btn"
              :class="{ active: wbTab === 'my-agents' }"
              @click="switchTab('my-agents')"
            >我的智能体</button>
          </div>
          <!-- activity tab 的随机调用按钮 -->
          <button
            v-if="wbTab === 'activity'"
            class="btn-cta"
            @click="simulateCall"
            :disabled="simulating || loading || agents.length === 0"
          >
            <span class="cta-icon">↯</span>
            <span>{{ simulating ? '调用中…' : '随机模拟调用' }}</span>
          </button>
          <!-- my-agents tab 的新建按钮 -->
          <router-link v-if="wbTab === 'my-agents'" to="/agent-apply" class="btn-cta">
            <span class="cta-icon">+</span>
            <span>新建智能体</span>
          </router-link>
        </div>
      </header>

      <!-- ============================================================
           Tab 1: 实时调用监控 (activity)
           ============================================================ -->
      <div v-if="wbTab === 'activity'">
      <!-- 顶部统计条 -->
      <div class="stats-bar" v-if="!loading && agents.length > 0">
        <div class="stat-cell">
          <span class="stat-num">{{ String(agents.length).padStart(2, '0') }}</span>
          <span class="stat-label">总 数</span>
        </div>
        <div class="stat-cell">
          <span class="stat-num text-positive">{{ String(activeCount).padStart(2, '0') }}</span>
          <span class="stat-label">调用中</span>
        </div>
        <div class="stat-cell">
          <span class="stat-num">{{ String(idleCount).padStart(2, '0') }}</span>
          <span class="stat-label">空闲中</span>
        </div>
        <div class="stat-cell">
          <span class="stat-num">{{ String(totalPings).padStart(2, '0') }}</span>
          <span class="stat-label">累计调用</span>
        </div>
        <div class="stat-cell stat-cell-right">
          <button
            class="activity-toggle"
            :class="{ on: polling }"
            @click="polling = !polling"
            type="button"
          >
            <span class="mini-dot"></span>
            {{ polling ? `每 3s 自动刷新` : '已暂停' }}
          </button>
        </div>
      </div>

      <LoadingSpinner v-if="loading" text="加载智能体..." />

      <!-- 空状态 -->
      <div v-else-if="agents.length === 0" class="empty-state-card">
        <div class="empty-icon">
          <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">
            <rect x="2" y="3" width="20" height="14" rx="2"/>
            <line x1="8" y1="21" x2="16" y2="21"/>
            <line x1="12" y1="17" x2="12" y2="21"/>
          </svg>
        </div>
        <span class="empty-tag">// NO AGENT ONLINE</span>
        <h3 class="empty-title">还没有可监控的智能体</h3>
        <p class="empty-desc">已批准并上架的智能体会出现在这里 — 创建一个智能体,审批通过后会自动显示。</p>
        <router-link to="/agent-apply" class="btn-cta">去创建智能体</router-link>
      </div>

      <!-- 显示器网格 + 活动日志 -->
      <div v-else class="dashboard-grid">
        <div class="monitor-grid">
          <article
            v-for="(agent, idx) in agents"
            :key="agent.id"
            class="monitor-unit"
            :class="{ active: agent.active, 'just-pinged': agent.justPinged }"
            :style="{ animationDelay: (idx * 50) + 'ms' }"
            @click="callAgent(agent)"
            title="点击屏幕模拟一次调用"
          >
            <!-- 电脑显示器 -->
            <div class="monitor">
              <div class="screen">
                <div class="screen-glow"></div>
                <div class="screen-grid"></div>
                <div class="screen-content">
                  <template v-if="agent.active">
                    <div class="waveform">
                      <span
                        v-for="i in 9"
                        :key="i"
                        class="wave-bar"
                        :style="{ animationDelay: (i * 0.1) + 's', height: (8 + (i % 3) * 8) + 'px' }"
                      ></span>
                    </div>
                    <div class="screen-text">CALLING…</div>
                  </template>
                  <template v-else>
                    <div class="screen-off-icon">
                      <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" opacity="0.28">
                        <circle cx="12" cy="12" r="10"/>
                        <line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/>
                      </svg>
                    </div>
                  </template>
                </div>
                <div class="screen-shine"></div>
                <div class="screen-tag">// {{ String(idx + 1).padStart(2, '0') }}</div>
              </div>
              <div class="stand-neck"></div>
              <div class="stand-base"></div>
            </div>

            <!-- 信息 -->
            <div class="monitor-info">
              <div class="info-row">
                <span class="monitor-name">{{ agent.name }}</span>
                <span v-if="agent.active" class="status-live">
                  <span class="live-dot"></span> 调用中
                </span>
                <span v-else class="status-idle">
                  <span class="idle-dot"></span> 空闲中
                </span>
              </div>
              <div class="info-meta">
                <span class="meta-owner">@{{ agent.owner_name || 'demo' }}</span>
                <span v-if="agent.ping_count" class="meta-count">{{ agent.ping_count }} 次</span>
              </div>
              <div v-if="agent.tags && agent.tags.length" class="info-tags">
                <span v-for="t in agent.tags.slice(0, 2)" :key="t" class="tag-chip">{{ t }}</span>
              </div>
            </div>
          </article>
        </div>

        <!-- 右侧活动日志 -->
        <aside class="activity-log">
          <div class="log-head">
            <span class="log-tag">// ACTIVITY LOG</span>
            <span class="log-count">{{ recentLogs.length }} 条</span>
          </div>
          <div v-if="recentLogs.length === 0" class="log-empty">
            <span>暂无活动 — 点击任意屏幕模拟一次调用</span>
          </div>
          <ul v-else class="log-list">
            <li
              v-for="(log, idx) in recentLogs.slice(0, 8)"
              :key="log.id + idx"
              class="log-item"
            >
              <span class="log-time">{{ formatLogTime(log.time) }}</span>
              <span class="log-dot"></span>
              <div class="log-body">
                <span class="log-name">{{ log.name }}</span>
                <span class="log-action">被调用 · 屏幕亮起</span>
              </div>
            </li>
          </ul>
          <div class="log-foot">
            <span class="log-meta">数据来源: /api/agents/activity · 每 3 秒刷新</span>
          </div>
        </aside>
      </div>

      <!-- 图例 -->
      <div class="legend-row" v-if="!loading && agents.length > 0">
        <span class="legend-item"><span class="legend-dot active-dot"></span> 调用中</span>
        <span class="legend-item"><span class="legend-dot idle-dot"></span> 空闲中</span>
        <span class="legend-hint">— 点击屏幕模拟一次调用 · 活跃窗口 {{ thresholdSeconds }} 秒</span>
      </div>
      </div>
      <!-- /v-if wbTab==='activity' -->

      <!-- ============================================================
           Tab 2: 我的智能体 (my-agents, 从 AgentManageView 合并)
           ============================================================ -->
      <div v-else>
        <EmptyState v-if="!auth.isLoggedIn" message="请先登录以管理智能体">
          <router-link to="/auth" class="btn btn-primary">登录 / 注册</router-link>
        </EmptyState>

        <EmptyState v-else-if="auth.isAdmin" message="管理员无法管理智能体,只能审批智能体上架">
          <template #icon><svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg></template>
          <router-link to="/agent-apply" class="btn btn-secondary">前往智能体上架</router-link>
        </EmptyState>

        <template v-else>
          <!-- 顶部统计条 -->
          <div class="stats-bar" v-if="!loadingAgents && myAgents.length > 0">
            <div class="stat-cell">
              <span class="stat-num">{{ String(myAgents.length).padStart(2, '0') }}</span>
              <span class="stat-label">总 数</span>
            </div>
            <div class="stat-cell">
              <span class="stat-num text-positive">{{ String(counts.approved).padStart(2, '0') }}</span>
              <span class="stat-label">已批准</span>
            </div>
            <div class="stat-cell">
              <span class="stat-num text-warning">{{ String(counts.pending).padStart(2, '0') }}</span>
              <span class="stat-label">待审批</span>
            </div>
            <div class="stat-cell">
              <span class="stat-num text-negative">{{ String(counts.rejected).padStart(2, '0') }}</span>
              <span class="stat-label">已拒绝</span>
            </div>
            <div class="stat-cell stat-cell-right">
              <button
                class="activity-toggle"
                :class="{ on: activityPolling }"
                @click.stop="activityPolling = !activityPolling"
                type="button"
              >
                <span class="mini-dot"></span>
                {{ activityPolling ? '实时监控中' : '已暂停' }}
              </button>
            </div>
          </div>

          <LoadingSpinner v-if="loadingAgents" />

          <!-- Empty state -->
          <div v-else-if="myAgents.length === 0" class="empty-state-card">
            <div class="empty-icon">
              <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <line x1="9" y1="9" x2="15" y2="9" />
                <line x1="9" y1="13" x2="15" y2="13" />
                <line x1="9" y1="17" x2="13" y2="17" />
              </svg>
            </div>
            <span class="empty-tag">// NO DATA YET</span>
            <h3 class="empty-title">还没有智能体</h3>
            <p class="empty-desc">创建你的第一个智能体 — 提交审批通过后,会在广场上为用户服务。</p>
            <router-link to="/agent-apply" class="btn-cta">立即创建</router-link>
          </div>

          <!-- Table -->
          <div v-else class="agent-table">
            <div class="table-head">
              <div class="th th-num">编号</div>
              <div class="th th-name">智能体</div>
              <div class="th th-status">状态</div>
              <div class="th th-price">定价</div>
              <div class="th th-time">时间</div>
              <div class="th th-actions">操作</div>
            </div>

            <article
              v-for="(agent, idx) in myAgents"
              :key="agent.id"
              class="table-row"
              :class="{ 'is-editing': editingId === agent.id, 'is-active': agent.active }"
            >
              <div class="tr tr-num">
                <span v-if="editingId === agent.id" class="row-num row-num-edit">EDIT</span>
                <span v-else class="row-num">0{{ idx + 1 }}</span>
              </div>

              <div class="tr tr-name">
                <div class="agent-cell">
                  <div class="agent-avatar">
                    <img v-if="agent.image" :src="`/api/uploads/${agent.image}`" alt="" />
                    <svg v-else xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
                      <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/>
                    </svg>
                  </div>
                  <div class="agent-meta">
                    <div class="agent-name-row">
                      <span class="agent-name">{{ agent.name }}</span>
                      <span v-if="agent.key && statusKey(agent.status) === 'approved'" class="key-pill" title="已签发 API Key">
                        <svg xmlns="http://www.w3.org/2000/svg" width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>
                        KEY
                      </span>
                      <span v-if="agent.version" class="version-pill">v{{ agent.version }}</span>
                      <span v-if="agent.versionCount > 1" class="version-pill muted-pill">{{ agent.versionCount }} 个版本</span>
                    </div>
                    <div v-if="agent.tags && agent.tags.length" class="agent-tags">
                      <span v-for="t in agent.tags" :key="t" class="tag-chip">{{ t }}</span>
                    </div>
                    <p v-if="agent.description" class="agent-desc">{{ agent.description }}</p>
                  </div>
                </div>
              </div>

              <div class="tr tr-status">
                <span :class="['status-badge', statusKey(agent.status)]">
                  {{ statusText(agent.status) }}
                </span>
                <span
                  v-if="statusKey(agent.status) === 'approved'"
                  class="live-pulse"
                  :class="{ on: agent.active }"
                  :title="agent.active ? '调用中' : '空闲中'"
                >
                  <span class="live-dot"></span>
                </span>
                <button
                  class="review-btn"
                  :title="'查看审核详情 / Passport'"
                  @click.stop="openReview(agent)"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                </button>
              </div>

              <div class="tr tr-price">
                <span v-if="agent.price" class="price-value">
                  <strong>{{ agent.price }}</strong>
                  <small>积分/次</small>
                </span>
                <span v-else class="muted">—</span>
              </div>

              <div class="tr tr-time">
                <span class="time-value">{{ formatTime(agent.created_at) }}</span>
                <span v-if="agent.approved_at" class="time-sub">→ {{ formatTime(agent.approved_at) }}</span>
              </div>

              <div class="tr tr-actions">
                <button @click="startEdit(agent)" class="icon-btn" title="编辑" aria-label="编辑">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                </button>
                <button @click="deleteAgent(agent)" class="icon-btn icon-btn-danger" title="删除" aria-label="删除">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="3 6 5 6 21 6"/>
                    <path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                  </svg>
                </button>
              </div>

              <!-- 展开的编辑表单 -->
              <div v-if="editingId === agent.id" class="edit-expand">
                <form @submit.prevent="saveAgent(agent.id)" class="edit-form-grid">
                  <div class="form-group">
                    <label>名称</label>
                    <input v-model="editForm.name" placeholder="智能体名称" />
                  </div>
                  <div class="form-group">
                    <label>定价 (积分/次)</label>
                    <input v-model.number="editForm.price" type="number" min="0" placeholder="0" />
                  </div>
                  <div class="form-group form-group-full">
                    <label>描述</label>
                    <textarea v-model="editForm.description" placeholder="智能体描述" rows="2"></textarea>
                  </div>
                  <div class="form-group form-group-full">
                    <label>分类 (可多选)</label>
                    <div class="tag-checkbox-group">
                      <label v-for="tag in tags" :key="tag.value" class="tag-checkbox">
                        <input type="checkbox" :value="tag.value" v-model="editForm.tags" />
                        <span class="tag-checkbox-label">{{ tag.label }}</span>
                      </label>
                    </div>
                  </div>
                  <div class="form-group form-group-full">
                    <label>图标</label>
                    <div class="file-input-wrap">
                      <input id="agent-img" type="file" accept="image/png,image/jpeg,image/gif,image/webp,image/svg+xml" @change="onImageChange" />
                      <label for="agent-img" class="file-input-btn">
                        <span class="file-input-icon">↥</span>
                        <span class="file-input-text">{{ agentImageName || '选择图片文件' }}</span>
                      </label>
                    </div>
                  </div>
                  <div class="form-actions">
                    <button type="button" @click="cancelEdit" class="btn-ghost">取消</button>
                    <button type="submit" class="btn-primary">保存修改</button>
                  </div>
                </form>
              </div>
            </article>
          </div>
        </template>
      </div>
      <!-- /v-else wbTab==='my-agents' -->
    </div>

    <!-- 审核 / Passport 详情弹窗 -->
    <Teleport to="body">
      <Transition name="dialog-fade">
        <div v-if="reviewDialog.open" class="review-backdrop" @click.self="closeReview">
          <div class="review-dialog" role="dialog" aria-labelledby="review-title">
            <header class="review-head">
              <div>
                <h2 id="review-title">{{ reviewDialog.agent?.name }} · 审核详情</h2>
                <span class="review-sub">// {{ reviewDialog.agent?.id }}</span>
              </div>
              <button class="review-close" @click="closeReview">×</button>
            </header>
            <div class="review-body">
              <div v-if="reviewDialog.loading" class="review-loading">
                <span class="spinner-sm"></span> 加载审核与 Passport 中...
              </div>
              <template v-else>
                <!-- Supervisor Review -->
                <section class="review-section">
                  <h3>Supervisor 审核 <span class="review-status" :class="reviewDialog.review?.decision?.toLowerCase()">{{ reviewDialog.review?.decision || '—' }}</span></h3>
                  <div class="kv-grid">
                    <div class="kv"><span class="kv-k">决策</span><span class="kv-v">{{ reviewDialog.review?.decision || '—' }}</span></div>
                    <div class="kv"><span class="kv-k">风险等级</span><span class="kv-v">{{ reviewDialog.review?.risk_level || '—' }}</span></div>
                    <div class="kv"><span class="kv-k">权限层级</span><span class="kv-v">{{ reviewDialog.review?.permission_tier || '—' }}</span></div>
                    <div class="kv"><span class="kv-k">审核模式</span><span class="kv-v">{{ reviewDialog.review?.review_mode || '—' }}</span></div>
                    <div class="kv"><span class="kv-k">状态</span><span class="kv-v">{{ reviewDialog.review?.status || '—' }}</span></div>
                    <div class="kv"><span class="kv-k">错误</span><span class="kv-v">{{ reviewDialog.review?.error_message || '—' }}</span></div>
                  </div>
                  <div v-if="reviewDialog.review?.required_fixes?.length" class="review-fixes">
                    <span class="kv-k">待修复</span>
                    <ul><li v-for="f in reviewDialog.review.required_fixes" :key="f">{{ f }}</li></ul>
                  </div>
                </section>

                <!-- Passport -->
                <section v-if="reviewDialog.passport" class="review-section">
                  <h3>Passport <span class="review-status approved">{{ reviewDialog.passport.status }}</span></h3>
                  <div class="kv-grid">
                    <div class="kv"><span class="kv-k">Passport ID</span><span class="kv-v mono">{{ reviewDialog.passport.passport_id }}</span></div>
                    <div class="kv"><span class="kv-k">Passport 版本</span><span class="kv-v">{{ reviewDialog.passport.passport_version }}</span></div>
                    <div class="kv"><span class="kv-k">ACS Hash</span><span class="kv-v mono ellipsis" :title="reviewDialog.passport.acs_hash">{{ reviewDialog.passport.acs_hash?.slice(0, 16) }}…</span></div>
                    <div class="kv"><span class="kv-k">签发时间</span><span class="kv-v">{{ reviewDialog.passport.issued_at || '—' }}</span></div>
                    <div class="kv"><span class="kv-k">过期时间</span><span class="kv-v">{{ reviewDialog.passport.expires_at || '—' }}</span></div>
                    <div class="kv"><span class="kv-k">复审时间</span><span class="kv-v">{{ reviewDialog.passport.review_after || '—' }}</span></div>
                  </div>
                  <details class="review-payload">
                    <summary>查看完整 passport_payload</summary>
                    <pre>{{ JSON.stringify(reviewDialog.passport.passport_payload, null, 2) }}</pre>
                  </details>
                </section>
                <div v-else class="review-empty">尚无 Passport(未通过审批或未签发)</div>
              </template>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </section>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api'
import { useToastStore } from '@/stores/toast'
import { useAuthStore } from '@/stores/auth'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import EmptyState from '@/components/EmptyState.vue'

const route = useRoute()
const router = useRouter()
const showContent = ref(false)
onMounted(() => { nextTick(() => { showContent.value = true }) })
const toast = useToastStore()
const auth = useAuthStore()

/* ============================================================
 *  Tab 切换
 *  - activity: 实时调用监控 (原 dashboard 内容)
 *  - my-agents: 我的智能体 CRUD (从 AgentManageView 合并)
 * ============================================================ */
const wbTab = ref(route.query.tab === 'my-agents' ? 'my-agents' : 'activity')
watch(() => route.query.tab, (t) => {
  if (t === 'my-agents') wbTab.value = 'my-agents'
  else if (t === 'activity') wbTab.value = 'activity'
})
const switchTab = (tab) => {
  wbTab.value = tab
  router.replace({ query: { ...route.query, tab } })
}

/* ============================================================
 *  Tab 1: activity (实时调用监控)
 * ============================================================ */
const agents = ref([])
const loading = ref(true)
const polling = ref(true)
const simulating = ref(false)
const thresholdSeconds = ref(45)
const recentLogs = ref([])
let activityPollTimer = null

const activeCount = computed(() => agents.value.filter(a => a.active).length)
const idleCount   = computed(() => agents.value.filter(a => !a.active).length)
const totalPings  = computed(() => agents.value.reduce((s, a) => s + (a.ping_count || 0), 0))

const fetchActivity = async () => {
 try {
  const res = await api.get('/agent/client', { params: { page_num: 1, page_size: 200, is_deleted: false } })
  const items = collapseAgentVersions(res?.items || [])
  const prevById = new Map(agents.value.map(a => [a.id, a.justPinged]))
  const prevByName = new Map(agents.value.map(a => [normalizeAgentNameKey(a), a.justPinged]))
  agents.value = items.map(a => ({
    ...a,
    active: !!a.active,
    justPinged: prevById.get(a.id) || prevByName.get(normalizeAgentNameKey(a)) || false,
  }))
  if (typeof res.threshold_seconds === 'number') thresholdSeconds.value = res.threshold_seconds
 } catch (err) {
   toast.error(err.message || '加载活动状态失败')
 } finally {
   loading.value = false
 }
}

const pushLog = (agent) => {
 recentLogs.value.unshift({
   id: agent.id + ':' + Date.now(),
   name: agent.name,
   time: new Date().toISOString(),
 })
 if (recentLogs.value.length > 16) recentLogs.value.length = 16
}

const callAgent = async (agent) => {
 try {
  agent.active = true
  agent.justPinged = true
  agent.ping_count = (agent.ping_count || 0) + 1
  pushLog(agent)
  toast.success(`${agent.name} 调用中`)
  setTimeout(() => { agent.justPinged = false }, 1500)
    setTimeout(() => fetchActivity(), 1500)
 } catch (err) {
   toast.error(err.message || '调用失败')
 }
}

const simulateCall = async () => {
 if (agents.value.length === 0) return
 simulating.value = true
 try {
 const target = agents.value[Math.floor(Math.random() * agents.value.length)]
 target.active = true
 target.justPinged = true
 target.ping_count = (target.ping_count || 0) + 1
 pushLog(target)
 toast.success(`已模拟调用: ${target.name}`)
 setTimeout(() => { target.justPinged = false }, 1500)
    setTimeout(() => fetchActivity(), 1500)
 } catch (err) {
   toast.error(err.message || '模拟失败')
 } finally {
   simulating.value = false
 }
}

const formatLogTime = (iso) => {
 if (!iso) return ''
 const d = new Date(iso)
 const pad = (n) => String(n).padStart(2, '0')
 return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

/* ============================================================
 *  Tab 2: my-agents (从 AgentManageView 合并)
 * ============================================================ */
const myAgents = ref([])
const loadingAgents = ref(false)
const editingId = ref(null)
const editForm = ref({ name: '', description: '', price: 0, tag: '', tags: [] })
const agentImage = ref(null)
const agentImageName = ref('')
const activityPolling = ref(true)
let myAgentsPollTimer = null

const tags = [
  { label: '办公效率', value: '办公效率' }, { label: '休闲娱乐', value: '休闲娱乐' },
  { label: '生活服务', value: '生活服务' }, { label: '内容创作', value: '内容创作' },
  { label: '理财投资', value: '理财投资' }, { label: '学术研究', value: '学术研究' },
]

const statusKey = (s) => {
  if (!s) return 'neutral'
  const lower = String(s).toLowerCase()
  if (['approved', 'pending', 'rejected', 'draft'].includes(lower)) return lower
  return 'neutral'
}
const statusText = (s) => {
  const map = { approved: '已批准', pending: '待审批', rejected: '已拒绝', draft: '草稿' }
  return map[String(s || '').toLowerCase()] || s || '未知'
}
const readAgentStatus = (agent) => agent?.status || agent?.approval_status || agent?.review_status || 'unknown'
const readAgentCallingState = (agent) => {
  const candidates = [
    agent?.is_calling,
    agent?.calling,
    agent?.runtime_active,
    agent?.activity_active,
    agent?.currently_calling,
    agent?.in_call,
  ]
  const value = candidates.find(v => typeof v === 'boolean')
  return value === true
}
const formatTime = (t) => {
  if (!t) return '—'
  return String(t).slice(0, 16).replace('T', ' ')
}

const normalizeAgentNameKey = (agent) => {
  const name = String(agent?.name || '').trim().toLowerCase()
  return name || String(agent?.id || '')
}

const versionParts = (version) => {
  const match = String(version || '').trim().match(/^(\d+)(?:\.(\d+))?(?:\.(\d+))?/)
  return match ? match.slice(1, 4).map(n => Number(n || 0)) : [0, 0, 0]
}

const compareVersions = (left, right) => {
  const a = versionParts(left)
  const b = versionParts(right)
  for (let i = 0; i < 3; i += 1) {
    if (a[i] !== b[i]) return a[i] - b[i]
  }
  return 0
}

const isNewerVersion = (candidate, current) => {
  const byVersion = compareVersions(candidate.version, current.version)
  if (byVersion !== 0) return byVersion > 0
  return new Date(candidate.created_at || 0).getTime() >= new Date(current.created_at || 0).getTime()
}

const normalizeDashboardAgent = (agent) => ({
  id: agent.id,
  name: agent.name,
  version: agent.version,
  description: agent.description || '',
  price: agent.price,
  tag: agent.tag,
  tags: normalizeTags(agent),
  key: agent.key,
  image: agent.image,
  owner_name: agent.owner_name,
  ping_count: agent.ping_count,
  logo_url: agent.logo_url,
  status: readAgentStatus(agent),
  approval_status: agent.approval_status,
  is_active: agent.is_active,
  is_deleted: agent.is_deleted,
  aic: agent.aic,
  created_at: agent.created_at,
  approved_at: agent.approved_at,
  active: readAgentCallingState(agent),
})

const collapseAgentVersions = (items) => {
  const groups = new Map()
  items.filter(a => a.is_deleted !== true && String(a.is_deleted).toLowerCase() !== 'true').forEach(raw => {
    const agent = normalizeDashboardAgent(raw)
    const key = normalizeAgentNameKey(agent)
    const group = groups.get(key)
    if (!group) {
      groups.set(key, { latest: agent, versions: [agent] })
      return
    }
    group.versions.push(agent)
    if (isNewerVersion(agent, group.latest)) group.latest = agent
  })
  return Array.from(groups.values())
    .map(group => ({
      ...group.latest,
      versionCount: group.versions.length,
      versionIds: group.versions.map(a => a.id),
      versions: group.versions.map(a => a.version).filter(Boolean),
    }))
    .sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime())
}

const counts = computed(() => ({
  approved: myAgents.value.filter(a => statusKey(a.status) === 'approved').length,
  pending:  myAgents.value.filter(a => statusKey(a.status) === 'pending').length,
  rejected: myAgents.value.filter(a => statusKey(a.status) === 'rejected').length,
}))

const onImageChange = (e) => { const file = e.target.files?.[0]; if (file) { agentImage.value = file; agentImageName.value = file.name } }

const startEdit = (agent) => { editingId.value = agent.id; editForm.value = { name: agent.name, description: agent.description || '', price: agent.price || 0, tag: agent.tag || '', tags: normalizeTags(agent) } }
const cancelEdit = () => { editingId.value = null; editForm.value = { name: '', description: '', price: 0, tag: '', tags: [] }; agentImage.value = null; agentImageName.value = '' }

const saveAgent = async (agentId) => {
  try {
    const payload = {
      name: editForm.value.name,
      version: '1.0.0',
      description: editForm.value.description,
    }
    const res = await api.put(`/agent/client/${agentId}`, payload)
    if (res.id) { cancelEdit(); fetchMyAgents(); toast.success('智能体已更新') }
  } catch (err) { toast.error(err.message) }
}

const deleteAgent = async (agent) => {
  const ids = Array.isArray(agent?.versionIds) && agent.versionIds.length ? agent.versionIds : [agent?.id].filter(Boolean)
  if (ids.length === 0) return
  const suffix = ids.length > 1 ? `（共 ${ids.length} 个版本）` : ''
  if (!confirm(`确定要删除「${agent.name}」${suffix}吗？`)) return
  try {
    await Promise.all(ids.map(id => api.delete(`/agent/client/${id}`)))
    myAgents.value = myAgents.value.filter(a => a.id !== agent.id)
    await fetchMyAgents()
    toast.success('已删除')
  } catch (err) { toast.error(err.message) }
}

const fetchMyAgents = async () => {
 loadingAgents.value = true
 try {
  const res = await api.get('/agent/client', { params: { page_num: 1, page_size: 200, is_deleted: false } })
  if (res.items) {
    myAgents.value = collapseAgentVersions(res.items)
  }
 } catch (err) { toast.error(err.message) }
 finally { loadingAgents.value = false }
}

const fetchMyActivity = async () => {
  if (myAgents.value.length === 0) return
  myAgents.value.forEach(a => {
    a.active = false
  })
}

/* ============ 审核 / Passport 详情弹窗 ============ */
const reviewDialog = ref({ open: false, loading: false, agent: null, review: null, passport: null })
const openReview = async (agent) => {
  if (!agent?.id) return
  reviewDialog.value = { open: true, loading: true, agent, review: null, passport: null }
  // 并行拉 supervisor-review 和 passport
  const results = await Promise.allSettled([
    api.get(`/agent/client/${agent.id}/supervisor-review/latest`),
    api.get(`/agent/client/${agent.id}/passport/latest`),
  ])
  reviewDialog.value.review = results[0].status === 'fulfilled' ? results[0].value : null
  reviewDialog.value.passport = results[1].status === 'fulfilled' ? results[1].value : null
  reviewDialog.value.loading = false
}
const closeReview = () => { reviewDialog.value.open = false }

const normalizeTags = (agent) => {
  if (Array.isArray(agent.tags)) return agent.tags
  if (agent.tags && typeof agent.tags === 'string') { try { return JSON.parse(agent.tags) } catch {} }
  if (agent.tag) return [agent.tag]
  return []
}

onMounted(() => {
  fetchActivity()
  activityPollTimer = setInterval(() => { if (polling.value) fetchActivity() }, 3000)
  if (auth.isLoggedIn && !auth.isAdmin) {
    fetchMyAgents()
    fetchMyActivity()
    myAgentsPollTimer = setInterval(() => { if (activityPolling.value) fetchMyActivity() }, 4000)
  }
})

onUnmounted(() => {
  if (activityPollTimer) clearInterval(activityPollTimer)
  if (myAgentsPollTimer) clearInterval(myAgentsPollTimer)
})
</script>

<style scoped>
/* ===== 页面框架 ===== */
.dashboard-page { min-height: 100vh; background: var(--bg-page); padding: 48px 0 96px; }
.container { max-width: 1280px; margin: 0 auto; padding: 0 32px; }

.animate-in > * { opacity: 0; transform: translateY(10px); animation: fadeUp 0.5s var(--ease-out) forwards; }
.animate-in > *:nth-child(1) { animation-delay: 0ms; }
.animate-in > *:nth-child(2) { animation-delay: 80ms; }
.animate-in > *:nth-child(3) { animation-delay: 160ms; }
.animate-in > *:nth-child(4) { animation-delay: 240ms; }
@keyframes fadeUp { to { opacity: 1; transform: translateY(0); } }

/* ===== 顶部页头 ===== */
.page-header {
  display: flex; justify-content: space-between; align-items: flex-end;
  gap: 24px;
  margin-bottom: 32px; padding-bottom: 24px;
  border-bottom: 2px solid var(--ink);
  flex-wrap: wrap;
}
.page-header-left { flex: 1; min-width: 0; }
.page-issue {
  display: inline-flex; align-items: center; gap: 8px;
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--accent-blue-d);
  padding-bottom: 8px;
  border-bottom: 1px solid var(--line-blue);
}
.page-title {
  font-family: var(--font-display);
  font-size: clamp(32px, 4vw, 44px);
  font-weight: 600; color: var(--ink);
  letter-spacing: -0.025em;
  line-height: 1.05;
  margin: 12px 0 0;
}
.page-title em {
  font-family: var(--font-editorial);
  font-style: italic; font-weight: 400;
  color: var(--accent-blue);
}
.page-desc { font-size: 14px; color: var(--ink-3); margin: 8px 0 0; max-width: 60ch; line-height: 1.6; }
.page-header-right { flex-shrink: 0; }

.btn-cta {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 12px 20px;
  background: var(--sky-grad-deep); color: var(--ink-inverse); box-shadow: 0 2px 8px rgba(46, 122, 184, 0.22);
  border: 1px solid var(--ink);
  border-radius: var(--r-3);
  font-size: 13px; font-weight: 500;
  text-decoration: none;
  cursor: pointer;
  transition: all var(--t-fast);
  white-space: nowrap;
}
.btn-cta:hover:not(:disabled) { background: var(--accent-blue-d); border-color: var(--accent-blue-d); transform: translateY(-1px); box-shadow: 0 4px 12px rgba(30, 58, 76, 0.2); }
.btn-cta:disabled { opacity: 0.5; cursor: not-allowed; }
.cta-icon { font-size: 16px; line-height: 1; }

/* ===== 统计条 ===== */
.stats-bar {
  display: flex;
  align-items: stretch;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--r-3);
  margin-bottom: 24px;
  overflow: hidden;
}
.stat-cell {
  display: flex; flex-direction: column; align-items: flex-start; justify-content: center;
  padding: 18px 24px;
  flex: 1;
  border-right: 1px solid var(--border-card);
}
.stat-cell:last-child { border-right: 0; }
.stat-cell-right { flex: 0 0 auto; margin-left: auto; }
.stat-num {
  font-family: var(--font-display);
  font-size: 28px; font-weight: 700;
  color: var(--ink);
  line-height: 1;
  letter-spacing: -0.02em;
}
.stat-num.text-positive { color: var(--signal-positive); }
.stat-label {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.18em; text-transform: uppercase;
  color: var(--ink-4);
  margin-top: 6px;
}
.activity-toggle {
  display: inline-flex; align-items: center; gap: 8px;
  background: transparent;
  border: 1px solid transparent;
  padding: 4px 0;
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.18em; text-transform: uppercase;
  color: var(--ink-4);
  cursor: pointer;
  transition: color var(--t-fast);
}
.activity-toggle:hover { color: var(--ink-2); }
.activity-toggle.on { color: var(--signal-positive); }
.mini-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--ink-4); }
.activity-toggle.on .mini-dot {
  background: var(--signal-positive);
  animation: livePulse 1.4s infinite;
}
@keyframes livePulse { 0%,100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.35; transform: scale(0.85); } }

/* ===== 空状态 ===== */
.empty-state-card {
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--r-3);
  padding: 80px 32px;
  text-align: center;
  display: flex; flex-direction: column; align-items: center;
  position: relative;
  overflow: hidden;
}
.empty-state-card::before {
  content: '';
  position: absolute; inset: 0;
  background: radial-gradient(circle at 50% 0%, var(--accent-blue-bg) 0%, transparent 50%);
  pointer-events: none;
}
.empty-icon {
  width: 96px; height: 96px;
  display: flex; align-items: center; justify-content: center;
  background: var(--bg-page);
  border: 1px dashed var(--border-card);
  border-radius: 50%;
  color: var(--ink-3);
  margin-bottom: 20px;
  position: relative;
}
.empty-tag {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--accent-blue-d);
  margin-bottom: 8px;
  position: relative;
}
.empty-title {
  font-family: var(--font-display);
  font-size: 24px; font-weight: 600;
  color: var(--ink);
  margin: 0 0 8px;
  position: relative;
}
.empty-desc {
  font-size: 14px; color: var(--ink-3);
  max-width: 50ch;
  margin: 0 0 24px;
  line-height: 1.6;
  position: relative;
}
.empty-state-card .btn-cta { position: relative; }

/* ===== 仪表盘网格(显示器 + 日志) ===== */
.dashboard-grid {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 24px;
  align-items: flex-start;
}

/* ===== 显示器网格 ===== */
.monitor-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 32px 20px;
  justify-items: center;
}

.monitor-unit {
  display: flex; flex-direction: column; align-items: stretch; gap: 14px;
  cursor: pointer;
  width: 100%;
  max-width: 220px;
  transition: transform var(--t-base);
  opacity: 0; transform: translateY(10px);
  animation: fadeUp 0.4s var(--ease-out) forwards;
}
.monitor-unit:hover { transform: translateY(-4px); }
.monitor-unit.just-pinged .screen { animation: pingFlash 1.4s var(--ease-out); }
@keyframes pingFlash {
  0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.6); }
  60% { box-shadow: 0 0 0 12px rgba(16, 185, 129, 0); }
  100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
}

.monitor {
  display: flex; flex-direction: column; align-items: center;
  position: relative;
}

.screen {
  width: 180px; height: 124px;
  background: var(--sky-grad-deep);
  border-radius: 8px;
  position: relative;
  overflow: hidden;
  border: 5px solid var(--ink-2);
  transition: all 0.5s var(--ease);
}
.monitor-unit.active .screen {
  border-color: var(--signal-positive);
  box-shadow: inset 0 0 32px rgba(16, 185, 129, 0.18), 0 0 0 1px var(--signal-positive);
}

.screen-glow {
  position: absolute; inset: 0;
  background: radial-gradient(ellipse at center, rgba(16, 185, 129, 0.22) 0%, transparent 70%);
  opacity: 0;
  transition: opacity 0.5s var(--ease);
}
.monitor-unit.active .screen-glow { opacity: 1; }

.screen-grid {
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.04) 1px, transparent 1px);
  background-size: 16px 16px;
  opacity: 0;
  transition: opacity 0.5s;
}
.monitor-unit.active .screen-grid { opacity: 1; }

.screen-content {
  position: absolute; inset: 0;
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px;
  z-index: 1;
}
.screen-off-icon { color: rgba(255,255,255,0.25); }

.waveform { display: flex; align-items: flex-end; gap: 3px; height: 36px; }
.wave-bar {
  width: 4px;
  background: linear-gradient(to top, var(--signal-positive), #34d399);
  border-radius: 2px;
  animation: waveBounce 0.8s ease-in-out infinite alternate;
}
@keyframes waveBounce { 0% { opacity: 0.4; } 100% { opacity: 1; } }

.screen-text {
  font-family: var(--font-mono);
  font-size: 10px; font-weight: 700;
  color: var(--signal-positive);
  letter-spacing: 0.22em;
  animation: textBlink 1.2s ease-in-out infinite;
}
@keyframes textBlink { 0%,100% { opacity: 0.6; } 50% { opacity: 1; } }

.screen-shine {
  position: absolute; top: -30%; left: -30%; width: 60%; height: 100%;
  background: linear-gradient(180deg, rgba(255,255,255,0.05) 0%, transparent 100%);
  transform: rotate(-20deg);
  pointer-events: none;
}

.screen-tag {
  position: absolute;
  top: 4px; right: 6px;
  font-family: var(--font-mono);
  font-size: 8px; letter-spacing: 0.12em;
  color: rgba(255, 255, 255, 0.35);
  z-index: 2;
}
.monitor-unit.active .screen-tag { color: var(--signal-positive); opacity: 0.8; }

.stand-neck { width: 22px; height: 16px; background: var(--ink-2); border-radius: 0 0 3px 3px; transition: background 0.5s; }
.monitor-unit.active .stand-neck { background: var(--ink-3); }
.stand-base { width: 64px; height: 5px; background: var(--ink-2); border-radius: 3px; transition: background 0.5s; margin-top: -1px; }
.monitor-unit.active .stand-base { background: var(--ink-3); }

/* 显示器下方信息 */
.monitor-info {
  display: flex; flex-direction: column; gap: 4px;
  padding: 0 4px;
}
.info-row {
  display: flex; align-items: center; justify-content: space-between;
  gap: 8px;
}
.monitor-name {
  font-family: var(--font-display);
  font-size: 14px; font-weight: 600;
  color: var(--ink);
  letter-spacing: -0.01em;
  line-height: 1.2;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.status-live, .status-idle {
  display: inline-flex; align-items: center; gap: 4px;
  font-family: var(--font-mono);
  font-size: 9px; letter-spacing: 0.12em; text-transform: uppercase;
  font-weight: 600;
  flex-shrink: 0;
}
.status-live { color: var(--signal-positive); }
.status-idle { color: var(--ink-4); }
.live-dot, .idle-dot {
  width: 6px; height: 6px; border-radius: 50%;
}
.live-dot { background: var(--signal-positive); animation: liveBurst 1.4s infinite; }
.idle-dot { background: var(--ink-4); }
@keyframes liveBurst {
  0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.5); }
  70% { box-shadow: 0 0 0 5px rgba(16, 185, 129, 0); }
  100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
}

.info-meta {
  display: flex; align-items: center; gap: 8px;
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.05em;
  color: var(--ink-4);
}
.meta-count { color: var(--ink-3); }
.info-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.tag-chip {
  font-size: 10px;
  color: var(--ink-2);
  background: var(--bg-card-soft);
  border: 1px solid var(--border-card);
  padding: 1px 6px;
  border-radius: 2px;
  letter-spacing: 0.02em;
}

/* ===== 右侧活动日志 ===== */
.activity-log {
  position: sticky;
  top: 80px;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--r-3);
  overflow: hidden;
  display: flex; flex-direction: column;
  max-height: calc(100vh - 200px);
}
.log-head {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 16px;
  background: var(--bg-page);
  border-bottom: 1px solid var(--ink);
}
.log-tag {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--ink-2);
  font-weight: 600;
}
.log-count {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.12em;
  color: var(--ink-4);
}
.log-list {
  list-style: none; padding: 0; margin: 0;
  flex: 1;
  overflow-y: auto;
}
.log-empty {
  padding: 40px 16px;
  text-align: center;
  color: var(--ink-4);
  font-size: 12px;
  font-family: var(--font-mono);
  letter-spacing: 0.04em;
  line-height: 1.6;
}
.log-item {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-card);
  transition: background var(--t-fast);
}
.log-item:last-child { border-bottom: 0; }
.log-item:hover { background: var(--accent-blue-bg); }
.log-time {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.04em;
  color: var(--ink-4);
  flex-shrink: 0;
  padding-top: 1px;
}
.log-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--signal-positive);
  margin-top: 6px;
  flex-shrink: 0;
  box-shadow: 0 0 0 2px var(--bg-card), 0 0 0 3px var(--signal-positive);
  animation: liveBurst 1.5s infinite;
}
.log-body { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.log-name {
  font-family: var(--font-display);
  font-size: 13px; font-weight: 600;
  color: var(--ink);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.log-action {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.04em;
  color: var(--ink-3);
}
.log-foot {
  padding: 10px 16px;
  border-top: 1px solid var(--border-card);
  background: var(--bg-page);
}
.log-meta {
  font-family: var(--font-mono);
  font-size: 9px; letter-spacing: 0.04em;
  color: var(--ink-4);
  line-height: 1.5;
  display: block;
}

/* ===== 图例 ===== */
.legend-row {
  display: flex; align-items: center; justify-content: center;
  flex-wrap: wrap;
  gap: 20px;
  margin-top: 48px;
  font-family: var(--font-mono);
  font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--ink-3);
}
.legend-item { display: flex; align-items: center; gap: 6px; }
.legend-dot { width: 8px; height: 8px; border-radius: 2px; }
.active-dot { background: var(--signal-positive); box-shadow: 0 0 6px rgba(16, 185, 129, 0.4); }
.idle-dot { background: var(--ink-3); }
.legend-hint { color: var(--ink-4); font-size: 10px; letter-spacing: 0.08em; text-transform: none; }

/* ============================================================
   顶部 tab 切换按钮
   ============================================================ */
.wb-tab-switch {
  display: inline-flex; gap: 2px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 3px;
  position: relative;
}
.wb-tab-btn {
  position: relative;
  display: inline-flex; align-items: center; gap: 6px;
  padding: 7px 16px;
  background: transparent; border: none;
  border-radius: 6px;
  font-size: 13px; font-weight: 500;
  color: #64748b;
  cursor: pointer;
  transition: color 0.18s ease;
  letter-spacing: 0.01em;
}
.wb-tab-btn:hover { color: #334155 }
.wb-tab-btn.active {
  background: #ffffff;
  color: #0284c7;
  border: 1px solid #e0f2fe;
  box-shadow:
    0 1px 2px rgba(15, 23, 42, 0.04),
    0 1px 0 rgba(15, 23, 42, 0.02);
}
/* 底部 2px 渐变指示条 (浅蓝,克制风) */
.wb-tab-btn.active::after {
  content: '';
  position: absolute;
  left: 14px; right: 14px; bottom: -4px;
  height: 2px;
  background: linear-gradient(90deg, #38bdf8 0%, #0ea5e9 100%);
  border-radius: 2px 2px 0 0;
}

/* ============================================================
   my-agents tab 内的表格 + 编辑表单 (从 AgentManageView 搬过来)
   ============================================================ */
.agent-table {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
}
.table-head {
  display: grid;
  grid-template-columns: 60px 1.6fr 120px 100px 130px 90px;
  gap: 12px;
  padding: 14px 18px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  font-size: 11px; font-weight: 600;
  color: #64748b;
  text-transform: uppercase; letter-spacing: 0.06em;
}
.table-row {
  display: grid;
  grid-template-columns: 60px 1.6fr 120px 100px 130px 90px;
  gap: 12px;
  padding: 16px 18px;
  border-bottom: 1px solid #f1f5f9;
  align-items: start;
  position: relative;
  transition: background 0.15s;
}
.table-row:last-child { border-bottom: none }
.table-row:hover { background: #fafbfc }
.table-row.is-editing { background: #fffbeb }
.table-row.is-active { background: linear-gradient(90deg, rgba(99, 102, 241, 0.03), transparent) }
.tr { min-width: 0 }
.tr-num { font-family: ui-monospace, monospace; }
.row-num {
  display: inline-block;
  background: #f1f5f9; color: #64748b;
  padding: 3px 8px; border-radius: 4px;
  font-size: 11px; font-weight: 600;
}
.row-num-edit { background: #fef3c7; color: #92400e; }
.agent-cell { display: flex; gap: 10px; align-items: flex-start; }
.agent-avatar {
  width: 36px; height: 36px;
  border-radius: 8px;
  background: linear-gradient(135deg, #f1f5f9, #e2e8f0);
  display: flex; align-items: center; justify-content: center;
  color: #94a3b8; flex-shrink: 0;
  overflow: hidden;
}
.agent-avatar img { width: 100%; height: 100%; object-fit: cover }
.agent-meta { min-width: 0; flex: 1 }
.agent-name-row { display: flex; align-items: center; gap: 6px; }
.agent-name { font-weight: 600; color: #1e293b; font-size: 14px; }
.key-pill {
  display: inline-flex; align-items: center; gap: 2px;
  background: #d1fae5; color: #047857;
  padding: 2px 6px; border-radius: 4px;
  font-size: 9px; font-weight: 600;
  letter-spacing: 0.05em;
}
.version-pill {
  display: inline-flex; align-items: center;
  background: #eff6ff; color: #1d4ed8;
  padding: 2px 6px; border-radius: 4px;
  font-size: 9px; font-weight: 600;
  letter-spacing: 0.04em;
  white-space: nowrap;
}
.muted-pill { background: #f1f5f9; color: #64748b; }
.agent-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px }
.tag-chip {
  background: #eff6ff; color: #1e40af;
  padding: 2px 7px; border-radius: 3px;
  font-size: 10px; font-weight: 500;
}
.agent-desc {
  margin: 4px 0 0; font-size: 12px; color: #64748b;
  line-height: 1.4;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}

.status-badge {
  display: inline-flex; align-items: center;
  padding: 3px 8px; border-radius: 4px;
  font-size: 11px; font-weight: 600;
}
.status-badge.approved { background: #d1fae5; color: #047857 }
.status-badge.pending { background: #fef3c7; color: #92400e }
.status-badge.rejected { background: #fee2e2; color: #b91c1c }
.status-badge.draft { background: #f1f5f9; color: #64748b }
.status-badge.neutral { background: #f1f5f9; color: #64748b }

.live-pulse { display: inline-flex; align-items: center; margin-left: 6px }
.live-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: #cbd5e1;
  transition: background 0.2s;
}
.live-pulse.on .live-dot { background: #10b981; box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2);
  animation: liveBlink 1.5s infinite }
@keyframes liveBlink {
  0%, 100% { opacity: 1 }
  50% { opacity: 0.4 }
}

.price-value {
  display: flex; flex-direction: column;
  font-family: ui-monospace, monospace;
}
.price-value strong { font-size: 14px; color: #1e293b }
.price-value small { font-size: 10px; color: #94a3b8 }
.muted { color: #cbd5e1 }

.time-value {
  font-family: ui-monospace, monospace;
  font-size: 11px; color: #475569;
}
.time-sub {
  display: block;
  font-size: 10px; color: #94a3b8;
  font-family: ui-monospace, monospace;
  margin-top: 2px;
}

.tr-actions { display: flex; gap: 4px }
.icon-btn {
  background: transparent; border: 1px solid #e2e8f0;
  border-radius: 5px;
  width: 26px; height: 26px;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; color: #64748b;
  transition: all 0.15s;
}
.icon-btn:hover { background: #f1f5f9; color: #1e293b; border-color: #cbd5e1 }
.icon-btn-danger:hover { background: #fef2f2; color: #b91c1c; border-color: #fecaca }

.edit-expand {
  grid-column: 1 / -1;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px dashed #fde68a;
}
.edit-form-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px 16px;
  background: #fffbeb;
  padding: 16px;
  border-radius: 8px;
  border: 1px solid #fde68a;
}
.form-group { display: flex; flex-direction: column; gap: 4px }
.form-group-full { grid-column: 1 / -1 }
.form-group label { font-size: 11px; font-weight: 600; color: #92400e }
.form-group input, .form-group textarea {
  background: #fff; border: 1px solid #fde68a;
  border-radius: 5px; padding: 6px 10px;
  font-size: 13px; color: #1e293b;
  font-family: inherit;
  transition: border-color 0.15s;
}
.form-group input:focus, .form-group textarea:focus {
  outline: none; border-color: #f59e0b;
}
.tag-checkbox-group { display: flex; flex-wrap: wrap; gap: 8px }
.tag-checkbox {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 10px; border: 1px solid #fde68a;
  border-radius: 6px; cursor: pointer;
  font-size: 12px; color: #92400e; background: #fff;
  transition: all 0.15s;
}
.tag-checkbox:has(input:checked) { background: #f59e0b; color: #fff; border-color: #f59e0b }
.tag-checkbox input { display: none }
.file-input-wrap { position: relative }
.file-input-wrap input[type="file"] { position: absolute; opacity: 0; width: 0; height: 0 }
.file-input-btn {
  display: inline-flex; align-items: center; gap: 8px;
  background: #fff; border: 1px dashed #fde68a;
  border-radius: 6px; padding: 8px 14px;
  font-size: 12px; color: #92400e;
  cursor: pointer;
  transition: all 0.15s;
}
.file-input-btn:hover { background: #fef3c7; border-style: solid }
.file-input-icon { font-size: 14px }
.form-actions {
  grid-column: 1 / -1;
  display: flex; justify-content: flex-end; gap: 8px;
  margin-top: 4px;
}
.btn-ghost {
  background: transparent; border: 1px solid #cbd5e1;
  color: #64748b; padding: 6px 14px;
  border-radius: 6px; font-size: 12px; cursor: pointer;
}
.btn-ghost:hover { background: #f8fafc }
.btn-primary {
  background: #f59e0b; color: #fff; border: none;
  padding: 6px 14px; border-radius: 6px;
  font-size: 12px; font-weight: 500; cursor: pointer;
}
.btn-primary:hover { background: #d97706 }

@media (max-width: 768px) {
  .table-head, .table-row { grid-template-columns: 50px 1fr 100px 80px; }
  .th-price, .th-time, .tr-price, .tr-time { display: none }
  .edit-form-grid { grid-template-columns: 1fr }
  .wb-tab-switch { flex: 1 }
  .wb-tab-btn { flex: 1; padding: 6px 8px; font-size: 12px }
}

/* ===== 响应式 ===== */
@media (max-width: 1024px) {
  .dashboard-grid { grid-template-columns: 1fr; }
  .activity-log { position: static; max-height: 400px; }
}
@media (max-width: 720px) {
  .container { padding: 0 16px; }
  .page-header { flex-direction: column; align-items: flex-start; }
  .stats-bar { flex-wrap: wrap; }
  .stat-cell { min-width: 110px; flex: 1 1 40%; }
  .stat-cell-right { width: 100%; border-top: 1px solid var(--border-card); border-right: 0; }
  .monitor-grid { grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 28px 12px; }
  .screen { width: 140px; height: 96px; }
  .stand-base { width: 50px; }
  .monitor-unit { max-width: 160px; }
}

/* ===== 审核 / Passport 详情 ===== */
.review-btn {
  display: inline-flex; align-items: center; justify-content: center;
  width: 24px; height: 24px;
  background: transparent;
  border: 1px solid var(--border-card);
  border-radius: 50%;
  color: var(--ink-3);
  cursor: pointer;
  margin-left: 8px;
  transition: all var(--t-fast);
}
.review-btn:hover { background: var(--bg-page-blue); border-color: var(--accent-blue-d); color: var(--accent-blue-d); }

.review-backdrop {
  position: fixed; inset: 0; z-index: 9999;
  background: rgba(15, 23, 42, 0.55);
  display: flex; align-items: center; justify-content: center;
  padding: 20px;
}
.review-dialog {
  width: 100%;
  max-width: 720px;
  max-height: 86vh;
  background: var(--bg-card);
  border-radius: var(--r-3);
  border: 1px solid var(--border-card);
  display: flex; flex-direction: column;
  overflow: hidden;
  box-shadow: 0 30px 80px -20px rgba(15, 23, 42, 0.4);
}
.review-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 18px 24px;
  border-bottom: 1px solid var(--border-divider);
}
.review-head h2 { font-family: var(--font-display); font-size: 16px; font-weight: 600; color: var(--ink); margin: 0 0 4px; }
.review-sub { font-family: var(--font-mono); font-size: 10px; color: var(--ink-3); letter-spacing: 0.06em; }
.review-close { background: transparent; border: none; font-size: 24px; line-height: 1; color: var(--ink-3); cursor: pointer; padding: 0 4px; }
.review-close:hover { color: var(--ink); }
.review-body { padding: 20px 24px; overflow: auto; flex: 1; }

.review-section { margin-bottom: 24px; }
.review-section h3 {
  font-family: var(--font-display);
  font-size: 14px; font-weight: 600;
  color: var(--ink);
  margin: 0 0 14px;
  display: flex; align-items: center; gap: 10px;
}
.review-status {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.08em;
  padding: 2px 8px;
  border-radius: var(--r-1);
  background: var(--bg-card-soft);
  color: var(--ink-2);
  font-weight: 500;
}
.review-status.approved { background: #d1fae5; color: #047857; }
.review-status.rejected, .review-status.failed { background: #fee2e2; color: #b91c1c; }
.review-status.pending, .review-status.manual_review { background: #fef3c7; color: #92400e; }

.kv-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px 24px;
  margin-bottom: 12px;
}
.kv { display: flex; flex-direction: column; gap: 2px; padding: 8px 12px; background: var(--bg-page); border-radius: var(--r-1); }
.kv-k { font-family: var(--font-mono); font-size: 9px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--ink-3); }
.kv-v { font-size: 13px; color: var(--ink); font-weight: 500; }
.kv-v.mono { font-family: var(--font-mono); font-size: 12px; }
.kv-v.ellipsis { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.review-fixes { background: #fef3c7; border: 1px solid #fde68a; border-radius: var(--r-2); padding: 12px 16px; margin-top: 12px; }
.review-fixes ul { margin: 6px 0 0; padding-left: 20px; font-size: 13px; color: #92400e; }
.review-fixes li { margin-bottom: 4px; }

.review-payload { margin-top: 12px; }
.review-payload summary {
  cursor: pointer; font-size: 12px; color: var(--accent-blue-d);
  font-family: var(--font-mono); letter-spacing: 0.06em;
  padding: 4px 0;
}
.review-payload pre {
  margin: 8px 0 0;
  background: var(--bg-page);
  padding: 12px;
  border-radius: var(--r-1);
  font-family: var(--font-mono);
  font-size: 11px; line-height: 1.6;
  color: var(--ink-2);
  max-height: 280px;
  overflow: auto;
  white-space: pre-wrap; word-break: break-word;
}

.review-empty { padding: 20px; text-align: center; color: var(--ink-3); font-size: 13px; }
.review-loading { padding: 40px; text-align: center; color: var(--ink-3); font-size: 13px; }

.dialog-fade-enter-active, .dialog-fade-leave-active { transition: opacity 0.2s; }
.dialog-fade-enter-from, .dialog-fade-leave-to { opacity: 0; }
</style>
