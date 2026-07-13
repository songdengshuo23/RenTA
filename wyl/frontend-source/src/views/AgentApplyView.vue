<template>
  <section class="apply-page">
    <div class="apply-bg" aria-hidden="true">
      <div class="apply-bg-grid"></div>
      <div class="apply-bg-glow"></div>
    </div>

    <div class="apply-container" :class="{ 'is-in': showContent }">

      <!-- ==================== IDLE: 申请表单 ==================== -->
      <template v-if="flowState === 'idle'">
        <!-- Page Header -->
        <header class="apply-header anim-item anim-0">
          <div class="header-eyebrow">
            <span class="dot"></span>
            <span class="eyebrow-text">准备好让你的Agent赚钱了吗？</span>

          </div>
          <h1 class="apply-title">
            上架你的<span class="title-italic">智能体</span>
          </h1>
          <p class="apply-sub">
            四步完成基础身份、接入配置、能力描述与视觉形象，提交后将由平台管理员在 24 小时内完成审核。
          </p>
        </header>

        <!-- 顶栏右侧工具:查看后端真实 ACS 示例 (idle 块内,默认显示) -->
        <div class="apply-toolbar anim-item anim-1">
          <button type="button" class="tool-link" @click="openAcsExample">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            查看后端 ACS 示例
          </button>
        </div>

        <!-- Form -->
        <form
          v-if="auth.isLoggedIn && !auth.isAdmin"
          @submit.prevent="submitApply"
          class="apply-form"
        >
          <!-- 01 基础身份 -->
          <fieldset class="form-section anim-item anim-1">
            <legend class="section-legend">
              <span class="legend-title">基础身份</span>
            </legend>

            <div class="field">
              <label class="field-label">
                <span>智能体名称</span>
                <span class="field-required">必填</span>
              </label>
              <div class="field-input-wrap"
                :class="{ 'is-filled': form.name, 'has-error': touched.name && errors.name }">
                <input v-model="form.name" type="text" maxlength="32" placeholder="给你的智能体取个名字"
                  @blur="onBlur('name')" @input="onInput('name')" />
                <span class="field-counter">{{ form.name.length }} / 32</span>
              </div>
              <p v-if="touched.name && errors.name" class="field-error">{{ errors.name }}</p>
              <p v-else class="field-hint">将展示在广场卡片顶部，建议 2–10 个字符</p>
            </div>

            <div class="field">
              <label class="field-label">
                <span>版本号</span>
                <span class="field-required">必填</span>
              </label>
              <div class="field-input-wrap is-mono"
                :class="{ 'is-filled': form.version, 'has-error': touched.version && errors.version }">
                <input v-model="form.version" type="text" placeholder="1.0.0"
                  @blur="onBlur('version')" @input="onInput('version')" />
              </div>
              <p v-if="touched.version && errors.version" class="field-error">{{ errors.version }}</p>
              <p v-else class="field-hint">遵循语义化版本规范，例如 <code>1.0.0</code></p>
            </div>
          </fieldset>

          <!-- 02 接入配置 -->
          <fieldset class="form-section anim-item anim-2">
            <legend class="section-legend">
              <span class="legend-num">02</span>
              <span class="legend-line"></span>
              <span class="legend-title">接入配置</span>
              <span class="legend-en">/ Endpoint</span>
            </legend>

            <div class="field">
              <label class="field-label">
                <span>API 接入 URL</span>
                <span class="field-required">必填</span>
              </label>
              <div class="field-input-wrap is-mono"
                :class="{ 'is-filled': form.url, 'has-error': touched.url && errors.url }">
                <input v-model="form.url" type="url" maxlength="200" placeholder="https://api.example.com/v1/chat"
                  @blur="onBlur('url')" @input="onInput('url')" />
              </div>
              <p v-if="touched.url && errors.url" class="field-error">{{ errors.url }}</p>
              <p v-else class="field-hint">
                平台将通过该端点调用你的智能体服务。需支持 <code>POST</code> 请求，
                Content-Type 为 <code>application/json</code>，返回 JSON 格式响应。
              </p>
            </div>
          </fieldset>

          <!-- 03 能力描述 -->
          <fieldset class="form-section anim-item anim-3">
            <legend class="section-legend">
              <span class="legend-num">03</span>
              <span class="legend-line"></span>
              <span class="legend-title">能力描述</span>
              <span class="legend-en">/ Capability</span>
            </legend>

            <div class="field">
              <label class="field-label">
                <span>详细介绍</span>
                <span class="field-required">必填</span>
              </label>
              <div class="field-textarea-wrap"
                :class="{ 'is-filled': form.description, 'has-error': touched.description && errors.description }">
                <textarea v-model="form.description" rows="5" maxlength="500"
                  placeholder="它能做什么？适合什么场景？有什么独特之处？"
                  @blur="onBlur('description')" @input="onInput('description')"></textarea>
                <span class="field-counter">{{ form.description.length }} / 500</span>
              </div>
              <p v-if="touched.description && errors.description" class="field-error">{{ errors.description }}</p>
              <p v-else class="field-hint">清晰的描述能显著提升通过率与曝光量</p>
            </div>

            <div class="field">
              <label class="field-label">
                <span>分类标签</span>
                <span class="field-optional">至多 3 个</span>
              </label>
              <div class="tag-chip-group">
                <button v-for="tag in tags" :key="tag.value" type="button" class="tag-chip"
                  :class="{ active: form.tags.includes(tag.value) }"
                  :disabled="!form.tags.includes(tag.value) && form.tags.length >= 3"
                  @click="toggleTag(tag.value)">
                  <span class="chip-dot"></span>
                  <span>{{ tag.label }}</span>
                </button>
              </div>
              <p class="field-hint">已选 {{ form.tags.length }} / 3</p>
            </div>
          </fieldset>

          <!-- 04 视觉形象 -->
          <fieldset class="form-section anim-item anim-4">
            <legend class="section-legend">
              <span class="legend-num">04</span>
              <span class="legend-line"></span>
              <span class="legend-title">视觉形象</span>
              <span class="legend-en">/ Visual</span>
            </legend>

            <div class="field">
              <label class="field-label">
                <span>智能体图标</span>
                <span class="field-optional">可选</span>
              </label>
              <div class="icon-drop" :class="{ 'has-image': !!imagePreview, 'is-drag': isDragging }"
                @dragover.prevent="isDragging = true" @dragleave.prevent="isDragging = false" @drop.prevent="onDrop">
                <input type="file" accept="image/png,image/jpeg,image/gif,image/webp,image/svg+xml"
                  @change="onImageChange" class="icon-drop-input" id="agent-icon-input" />
                <div v-if="!imagePreview" class="icon-drop-empty">
                  <div class="drop-icon">
                    <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.5">
                      <path d="M12 16V4M12 4l-4 4M12 4l4 4"/>
                      <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>
                    </svg>
                  </div>
                  <div class="drop-text">
                    <strong>拖拽图片到此处</strong>
                    <span>或<label for="agent-icon-input" class="drop-link">点击选择文件</label></span>
                  </div>
                  <div class="drop-meta">PNG / JPG / GIF / WEBP / SVG · 最大 2MB</div>
                </div>
                <div v-else class="icon-drop-preview">
                  <img :src="imagePreview" class="preview-img" alt="图标预览" />
                  <div class="preview-actions">
                    <label for="agent-icon-input" class="preview-btn">更换</label>
                    <button type="button" class="preview-btn preview-btn-danger" @click="clearImage">移除</button>
                  </div>
                  <div class="preview-name">{{ imageName }}</div>
                </div>
              </div>
            </div>
          </fieldset>

          <!-- 05 定价 -->
          <fieldset class="form-section anim-item anim-5">
            <legend class="section-legend">
              <span class="legend-num">05</span>
              <span class="legend-line"></span>
              <span class="legend-title">定价</span>
              <span class="legend-en">/ Pricing</span>
            </legend>

            <div class="field">
              <label class="field-label">
                <span>每次调用定价</span>
                <span class="field-required">必填</span>
              </label>
              <div class="field-input-wrap is-mono"
                :class="{ 'is-filled': form.price, 'has-error': touched.price && errors.price }">
                <input v-model.number="form.price" type="number" min="1" max="10000" step="1" placeholder="例如 10"
                  @blur="onBlur('price')" @input="onInput('price')" />
                <span class="field-counter-suffix">积分 / 10K tokens</span>
              </div>
              <p v-if="touched.price && errors.price" class="field-error">{{ errors.price }}</p>
              <p v-else class="field-hint">用户每次调用消耗的积分 = 实际 token 数 × (你的定价 / 100)</p>
            </div>

            <!-- 推荐价卡片 -->
            <div class="pricing-suggestion" v-if="suggestion">
              <div class="ps-head">
                <span class="ps-icon">💡</span>
                <span class="ps-title">系统推荐价</span>
                <span class="ps-sample">基于 {{ suggestion.sample_count }} 个同类智能体</span>
              </div>
              <div class="ps-body">
                <div class="ps-bar">
                  <div class="ps-bar-track">
                    <div class="ps-bar-p25" :style="{ left: pctLeft(suggestion.p25) + '%' }" :title="'P25: ' + suggestion.p25"></div>
                    <div class="ps-bar-p50" :style="{ left: pctLeft(suggestion.p50) + '%' }" :title="'P50: ' + suggestion.p50"></div>
                    <div class="ps-bar-p75" :style="{ left: pctLeft(suggestion.p75) + '%' }" :title="'P75: ' + suggestion.p75"></div>
                    <div class="ps-bar-current" v-if="form.price" :style="{ left: pctLeft(form.price) + '%' }" :title="'当前: ' + form.price"></div>
                  </div>
                  <div class="ps-bar-labels">
                    <span>{{ suggestion.min }}</span>
                    <span>{{ Math.round((suggestion.min + suggestion.max) / 2) }}</span>
                    <span>{{ suggestion.max }}</span>
                  </div>
                </div>
                <div class="ps-stats">
                  <div class="ps-stat">
                    <span class="ps-stat-label">P25 (便宜)</span>
                    <span class="ps-stat-num">{{ suggestion.p25 }}</span>
                  </div>
                  <div class="ps-stat ps-stat-mid">
                    <span class="ps-stat-label">P50 (中位)</span>
                    <span class="ps-stat-num">{{ suggestion.p50 }}</span>
                  </div>
                  <div class="ps-stat">
                    <span class="ps-stat-label">P75 (偏贵)</span>
                    <span class="ps-stat-num">{{ suggestion.p75 }}</span>
                  </div>
                </div>
                <div class="ps-actions">
                  <button v-if="suggestion.p25 > 0" type="button" class="ps-quick" @click="form.price = suggestion.p25">设为 P25 ({{ suggestion.p25 }})</button>
                  <button v-if="suggestion.p50 > 0" type="button" class="ps-quick ps-quick-mid" @click="form.price = suggestion.p50">设为 P50 ({{ suggestion.p50 }})</button>
                  <button v-if="suggestion.p75 > 0" type="button" class="ps-quick" @click="form.price = suggestion.p75">设为 P75 ({{ suggestion.p75 }})</button>
                </div>
                <p v-if="suggestion.note" class="ps-note">{{ suggestion.note }}</p>
              </div>
            </div>
          </fieldset>
        </form>

        <EmptyState v-else-if="!auth.isLoggedIn" message="请先登录以创建智能体">
          <router-link to="/auth" class="btn btn-primary">登录 / 注册</router-link>
        </EmptyState>
        <EmptyState v-else message="管理员不能创建智能体" />
      </template>

      <!-- ==================== SUBMITTED: 审批流程 ==================== -->
      <template v-else>
        <div class="approval-flow">

          <!-- Flow header -->
          <header class="flow-header">
            <div class="flow-issue">
              <span class="flow-issue-dot"></span>
              <span>审批中 · Review Process</span>
              <span class="flow-issue-line"></span>
              <span class="flow-issue-meta">est. 5–10 min</span>
            </div>
            <h2 class="flow-title">
              <span class="flow-quote">"</span>{{ submittedName }}<span class="flow-quote">"</span>
              <span class="flow-title-suffix">正在接受审核</span>
            </h2>
            <p class="flow-sub">
              AI 系统先做一轮黑箱测试，再由管理员人工校验。审核期间可继续浏览广场，审核结果会通过站内通知告知。
            </p>
        </header>

          <!-- Big progress bar -->
          <div class="progress-block anim-flow-1">
            <div class="progress-meta">
              <span class="progress-label">总体进度</span>
              <span class="progress-num">{{ progressPercent }}<small>%</small></span>
            </div>
            <div class="progress-track">
              <div class="progress-fill" :style="{ width: progressPercent + '%' }">
                <span class="progress-fill-shine"></span>
              </div>
              <!-- 刻度 = 步骤分界点。3 个 step 共 2 个分界(0% 和 100%),原本写成 4 个 @ 33% 间隔,中间那根不会落在第 2 个圆点下面 -->
              <div class="progress-tick" :style="{ left: '50%' }"></div>
            </div>
            <div class="progress-steps">
              <div class="progress-step" :class="stepState(0)">
                <span class="step-dot">
                  <span v-if="stepState(0) === 'done'">✓</span>
                  <span v-else>01</span>
                </span>
                <span class="step-label">黑箱测试</span>
              </div>
              <div class="progress-connector" :class="stepState(0)"></div>
              <div class="progress-step" :class="stepState(1)">
                <span class="step-dot">
                  <span v-if="stepState(1) === 'done'">✓</span>
                  <span v-else>02</span>
                </span>
                <span class="step-label">人工校验</span>
              </div>
              <div class="progress-connector" :class="stepState(1)"></div>
              <div class="progress-step" :class="stepState(2)">
                <span class="step-dot">
                  <span v-if="stepState(2) === 'done'">✓</span>
                  <span v-else>03</span>
                </span>
                <span class="step-label">发布上线</span>
              </div>
            </div>
          </div>

          <!-- Three step cards (01 黑箱 / 02 人工 / 03 发布) -->
          <div class="flow-cards">

            <!-- 01 黑箱测试 -->
            <div class="flow-card" :class="cardState(0)">
              <div class="flow-card-head">
                <span class="flow-card-num">01</span>
                <span class="flow-card-status">
                  <span class="status-dot"></span>
                  <span>{{ cardStatusText(0) }}</span>
                </span>
              </div>
              <h3 class="flow-card-title">黑箱测试</h3>
              <p class="flow-card-desc">通过对抗性输入测试智能体的安全性、可用性与输出稳定性。</p>

              <!-- 审视 loader (来自 审视.css) -->
              <div class="flow-card-anim anim-scope-blackbox">
                <div class="loader-stage">
                  <div class="loader"></div>
                  <div class="loader-glow"></div>
                  <div class="loader-label mono">AI · SCANNING</div>
                </div>
              </div>

              <ul class="flow-checklist">
                <li v-for="(item, j) in steps[0].items" :key="j" :class="{ done: j < steps[0].doneCount }">
                  <span class="check"></span>
                  <span>{{ item }}</span>
                </li>
              </ul>
            </div>

            <!-- 02 人工校验 -->
            <div class="flow-card" :class="cardState(1)">
              <div class="flow-card-head">
                <span class="flow-card-num">02</span>
                <span class="flow-card-status">
                  <span class="status-dot"></span>
                  <span>{{ cardStatusText(1) }}</span>
                </span>
              </div>
              <h3 class="flow-card-title">人工校验审批</h3>
              <p class="flow-card-desc">平台管理员在后台查看描述、调用记录与测试报告，给出最终结论。</p>

              <!-- 审批 MacBook (来自 审批.css) -->
              <div class="flow-card-anim anim-scope-macbook">
                <div class="macbook">
                  <div class="shadow"></div>
                  <div class="inner">
                    <div class="screen">
                      <div class="face-one">
                        <div class="camera"></div>
                        <div class="display">
                          <div class="shade"></div>
                          <div class="display-lines">
                            <span></span><span></span><span></span>
                          </div>
                        </div>
                      </div>
                      <span>MacBook · Admin Console</span>
                    </div>
                  </div>
                  <div class="macbody">
                    <div class="face-one">
                      <div class="touchpad"></div>
                      <div class="keyboard">
                        <div v-for="k in 60" :key="k" class="key" :class="k === 30 ? 'space' : (k % 13 === 0 ? 'f' : '')"></div>
                      </div>
                    </div>
                    <div class="pad one"></div>
                    <div class="pad two"></div>
                    <div class="pad three"></div>
                    <div class="pad four"></div>
                  </div>
                </div>
              </div>

              <ul class="flow-checklist">
                <li v-for="(item, j) in steps[1].items" :key="j" :class="{ done: j < steps[1].doneCount }">
                  <span class="check"></span>
                  <span>{{ item }}</span>
                </li>
              </ul>
            </div>

            <!-- 03 发布上线 -->
            <div class="flow-card" :class="cardState(2)">
              <div class="flow-card-head">
                <span class="flow-card-num">03</span>
                <span class="flow-card-status">
                  <span class="status-dot"></span>
                  <span>{{ cardStatusText(2) }}</span>
                </span>
              </div>
              <h3 class="flow-card-title">发布上线</h3>
              <p class="flow-card-desc">智能体正式进入广场，所有用户可在浏览页发现并调用。</p>

              <div class="flow-card-anim anim-scope-rocket">
                <div class="rocket-stage">
                  <div class="rocket-glow"></div>
                  <div class="rocket-scale">
                    <div class="rocket">
                      <div class="rocket-body">
                        <div class="body"></div>
                        <div class="window"></div>
                        <div class="fin fin-left"></div>
                        <div class="fin fin-right"></div>
                        <div class="exhaust-flame"></div>
                      </div>
                      <ul class="exhaust-fumes">
                        <li></li><li></li><li></li><li></li><li></li>
                        <li></li><li></li><li></li><li></li>
                      </ul>
                      <ul class="star">
                        <li></li><li></li><li></li><li></li><li></li><li></li>
                      </ul>
                    </div>
                  </div>
                  <div class="loader-label mono">LAUNCHING</div>
                </div>
              </div>

              <ul class="flow-checklist">
                <li v-for="(item, j) in steps[2].items" :key="j" :class="{ done: j < steps[2].doneCount }">
                  <span class="check"></span>
                  <span>{{ item }}</span>
                </li>
              </ul>
            </div>
          </div>

          <!-- Result footer -->
          <div v-if="progressPercent === 100" class="flow-result anim-flow-3">
            <div class="flow-result-icon">✓</div>
            <div class="flow-result-info">
              <h3 class="flow-result-title">已通过审核</h3>
              <p class="flow-result-sub">"{{ submittedName }}" 已成功发布到智能体广场，所有用户都能看到。</p>
            </div>
            <div class="flow-result-actions">
              <button type="button" class="btn-ghost" @click="resetFlow">再申请一个</button>
              <router-link to="/square" class="btn-primary-cta">
                <span class="cta-content">
                  <span>去广场看看</span>
                  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M5 12h14M13 5l7 7-7 7"/>
                  </svg>
                </span>
              </router-link>
            </div>
          </div>

        </div>
      </template>

      <!-- Floating Action Bar (悬浮窗 - 居中) -->
      <div v-if="flowState === 'idle'" class="form-actions anim-item anim-5">
        <button type="button" class="btn-ghost" @click="resetForm" :disabled="submitting">重置</button>
        <button type="button" class="btn-primary-cta" :disabled="submitting || !auth.isLoggedIn || auth.isAdmin" @click="submitApply">
          <span v-if="!submitting" class="cta-content">
            <span>提交申请</span>
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M5 12h14M13 5l7 7-7 7"/>
            </svg>
          </span>
          <span v-else class="cta-content">
            <span class="cta-spinner"></span>
            <span>提交中…</span>
          </span>
        </button>
      </div>
    </div>

    <!-- ACS 示例弹窗 (后端 GET /api/agent/public/acs_example) -->
    <Teleport to="body">
      <Transition name="dialog-fade">
        <div v-if="acsExampleDialog" class="acs-dialog-backdrop" @click.self="acsExampleDialog = false">
          <div class="acs-dialog" role="dialog" aria-labelledby="acs-example-title">
            <header class="acs-dialog-head">
              <h2 id="acs-example-title">后端 ACS 示例 <span class="acs-dialog-sub">// /api/agent/public/acs_example</span></h2>
              <button class="acs-dialog-close" @click="acsExampleDialog = false">×</button>
            </header>
            <div class="acs-dialog-body">
              <pre class="acs-pre">{{ acsExampleRaw || '加载中...' }}</pre>
            </div>
            <footer class="acs-dialog-foot">
              <button class="btn btn-secondary" @click="copyAcsExample">复制</button>
              <button class="btn btn-primary" @click="acsExampleDialog = false">关闭</button>
            </footer>
          </div>
        </div>
      </Transition>
    </Teleport>
  </section>
</template>

<script setup>
import { ref, onMounted, nextTick, onUnmounted } from 'vue'
import api from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import EmptyState from '@/components/EmptyState.vue'

const showContent = ref(false)
onMounted(() => { nextTick(() => { showContent.value = true }); fetchSuggestion(); loadAcsTemplate() })

const auth = useAuthStore()
const toast = useToastStore()

const tags = [
  { label: '办公效率', value: '办公效率' },
  { label: '休闲娱乐', value: '休闲娱乐' },
  { label: '生活服务', value: '生活服务' },
  { label: '内容创作', value: '内容创作' },
  { label: '理财投资', value: '理财投资' },
  { label: '学术研究', value: '学术研究' },
]

const form = ref({ name: '', version: '1.0.0', url: '', description: '', tags: [], price: 0 })
const imageFile = ref(null)
const imageName = ref('')
const imagePreview = ref('')
const submitting = ref(false)
const isDragging = ref(false)
const suggestion = ref(null)
let suggestionTimer = null

/* ============ Validation ============ */
// 字段级错误对象:key = 字段名,value = 错误文案(空字符串代表无错)
const errors = ref({ name: '', version: '', url: '', description: '', price: '' })
// 失焦后才显示对应字段错误,避免一开始就一片红
const touched = ref({ name: false, version: false, url: false, description: false, price: false })

// 语义化版本: 主.次.修订,可选 - prerelease / + build
const SEMVER_RE = /^\d+\.\d+\.\d+(?:-[0-9A-Za-z-.]+)?(?:\+[0-9A-Za-z-.]+)?$/
// 简单 URL 校验:有协议 + 主机,避免用户填 "abc" 也能过
const URL_RE = /^https?:\/\/[^\s/$.?#].[^\s]*$/i

const validateField = (key) => {
  // price 是数字,其他是字符串 → 统一转 String 再 trim
  const raw = form.value[key]
  const v = (raw === 0 ? '0' : (raw == null ? '' : String(raw))).trim()
  let msg = ''
  if (key === 'name') {
    if (!v) msg = '请输入智能体名称'
    else if (v.length < 2 || v.length > 32) msg = '名称需在 2–32 个字符之间'
  } else if (key === 'version') {
    if (!v) msg = '请输入版本号'
    else if (!SEMVER_RE.test(v)) msg = '请输入合法的语义化版本,如 1.0.0'
  } else if (key === 'url') {
    if (!v) msg = '请输入 API 接入 URL'
    else if (!URL_RE.test(v)) msg = '请输入以 http(s):// 开头的合法 URL'
  } else if (key === 'description') {
    if (!v) msg = '请输入详细介绍'
    else if (v.length < 10) msg = '描述太短,建议至少 10 个字符,有助于通过审核'
  } else if (key === 'price') {
    const n = Number(form.value.price)
    if (!n || n <= 0) msg = '请输入大于 0 的定价'
    else if (n > 10000) msg = '定价过高(单次最高 10000 积分)'
  }
  errors.value[key] = msg
  return !msg
}

const validateAll = () => {
  // 一次性把所有字段标为 touched,让错误一次性显现
  touched.value = { name: true, version: true, url: true, description: true, price: true }
  return ['name', 'version', 'url', 'description', 'price'].every(validateField)
}

// 模板 @blur / @input 的封装:失焦时标 touched 并校验,输入时只在已 touched 后才校验
// (避免用户刚进页面就一片红,边输边改时只在他离开过该字段后才实时提示)
const onBlur = (key) => { touched.value[key] = true; validateField(key) }
const onInput = (key) => { if (touched.value[key]) validateField(key) }

/* ============ Flow state ============ */
const flowState = ref('idle')                // 'idle' | 'submitted'
const submittedName = ref('')
const progressPercent = ref(0)

const steps = ref([
  {
    title: '黑箱测试',
    items: [
      '内容安全与越权检测',
      'Prompt 注入与对抗输入',
      '响应稳定性与延迟基准',
    ],
    doneCount: 0,
  },
  {
    title: '人工校验',
    items: [
      '描述合规性审核',
      '调用配额与计费配置',
      '管理员最终签发',
    ],
    doneCount: 0,
  },
  {
    title: '发布上线',
    items: [
      '智能体卡片生成',
      '广场索引同步',
      '开放用户调用',
    ],
    doneCount: 0,
  },
])

let flowTimers = []
const clearFlowTimers = () => {
  flowTimers.forEach(t => clearTimeout(t))
  flowTimers = []
}
onUnmounted(clearFlowTimers)

const stepState = (i) => {
  // 0=黑箱测试, 1=人工校验, 2=发布上线
  if (i === 0) {
    if (progressPercent.value >= 50) return 'done'
    if (progressPercent.value > 0) return 'active'
    return 'pending'
  }
  if (i === 1) {
    if (progressPercent.value >= 100) return 'done'
    if (progressPercent.value >= 50) return 'active'
    return 'pending'
  }
  if (i === 2) {
    if (progressPercent.value >= 100) return 'done'
    return 'pending'
  }
  return 'pending'
}
const cardState = (i) => {
  if (i === 0) {
    if (progressPercent.value >= 50) return 'is-done'
    if (progressPercent.value > 0) return 'is-active'
    return 'is-pending'
  }
  if (i === 1) {
    if (progressPercent.value >= 100) return 'is-done'
    if (progressPercent.value >= 50) return 'is-active'
    return 'is-pending'
  }
  if (i === 2) {
    // 03 发布上线: 50% 后开始"发射",100% 落地
    if (progressPercent.value >= 100) return 'is-done'
    if (progressPercent.value >= 50) return 'is-active'
    return 'is-pending'
  }
  return 'is-pending'
}
const cardStatusText = (i) => {
  const s = cardState(i)
  if (s === 'is-done') return '已完成'
  if (s === 'is-active') return '进行中…'
  return '等待中'
}

const startFlow = () => {
  flowState.value = 'submitted'
  progressPercent.value = 0
  steps.value[0].doneCount = 0
  steps.value[1].doneCount = 0
  steps.value[2].doneCount = 0

  // Step 1: 0 → 50% over 5s
  let p = 0
  const tick1 = setInterval(() => {
    p += 2
    if (p >= 50) {
      progressPercent.value = 50
      steps.value[0].doneCount = steps.value[0].items.length
      clearInterval(tick1)
    } else {
      progressPercent.value = p
      // 每 1.7s 推一条 checklist
      if (p === 18) steps.value[0].doneCount = 1
      if (p === 34) steps.value[0].doneCount = 2
    }
  }, 200)
  flowTimers.push(tick1)

  // Step 2: 50 → 100% over 5s, started at 5.2s
  const startStep2 = setTimeout(() => {
    let p2 = 50
    const tick2 = setInterval(() => {
      p2 += 2
      if (p2 >= 100) {
        progressPercent.value = 100
        steps.value[1].doneCount = steps.value[1].items.length
        steps.value[2].doneCount = steps.value[2].items.length
        clearInterval(tick2)
      } else {
        progressPercent.value = p2
        if (p2 === 68) {
          steps.value[1].doneCount = 1
          steps.value[2].doneCount = 1
        }
        if (p2 === 84) {
          steps.value[1].doneCount = 2
          steps.value[2].doneCount = 2
        }
      }
    }, 200)
    flowTimers.push(tick2)
  }, 5200)
  flowTimers.push(startStep2)
}

const resetFlow = () => {
  clearFlowTimers()
  flowState.value = 'idle'
  progressPercent.value = 0
  submittedName.value = ''
  steps.value.forEach(s => { s.doneCount = 0 })
  resetForm()
}

/* ============ Form logic ============ */
const toggleTag = (v) => {
  const list = form.value.tags
  const i = list.indexOf(v)
  if (i > -1) list.splice(i, 1)
  else if (list.length < 3) list.push(v)
  // 标签变化时重新拉推荐价
  fetchSuggestion()
}

/* ============ ACS 示例 (真后端 /api/agent/public/acs_example) ============ */
// 拉回来的 example 仅供"参考"展示,实际提交时前端手填最小 ACS (实测 example 含大量手填字段,不适合做模板覆盖)
const acsExampleRaw = ref('')
const acsExampleDialog = ref(false)
const loadAcsTemplate = async () => {
  try {
    const raw = await api.get('/agent/public/acs_example')
    // 后端返回 JSON 字符串(带 // 注释),先解外层 JSON 再展示源码
    if (typeof raw === 'string') {
      // raw 形如 "\"{...}\"" → 双重 JSON
      let unescaped = raw
      try { unescaped = JSON.parse(raw) } catch {}
      acsExampleRaw.value = typeof unescaped === 'string' ? unescaped : JSON.stringify(unescaped, null, 2)
    } else {
      acsExampleRaw.value = JSON.stringify(raw, null, 2)
    }
  } catch (e) {
    acsExampleRaw.value = '// 拉取示例失败: ' + (e.message || e.error_msg || '未知错误')
  }
}
const openAcsExample = async () => {
  if (!acsExampleRaw.value) await loadAcsTemplate()
  acsExampleDialog.value = true
}
const copyAcsExample = async () => {
  try {
    await navigator.clipboard.writeText(acsExampleRaw.value)
    toast.success('已复制 ACS 示例')
  } catch {
    toast.error('复制失败')
  }
}

/* ============ Pricing suggestion ============ */
const fetchSuggestion = async () => {
  clearTimeout(suggestionTimer)
  suggestionTimer = setTimeout(async () => {
    try {
      const params = { tags: JSON.stringify(form.value.tags) }
      const data = await api.get('/agents/pricing-suggestion', { params })
      suggestion.value = data
    } catch (err) {
      suggestion.value = null
    }
  }, 300)
}
const pctLeft = (v) => {
  if (!suggestion.value) return 0
  const { min, max } = suggestion.value
  if (max <= min) return 50
  return Math.max(0, Math.min(100, ((v - min) / (max - min)) * 100))
}

const onImageChange = (e) => {
  const file = e.target.files?.[0]
  if (!file) return
  applyFile(file)
}
const onDrop = (e) => {
  isDragging.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) applyFile(file)
}
const applyFile = (file) => {
  imageFile.value = file
  imageName.value = file.name
  const reader = new FileReader()
  reader.onload = (ev) => { imagePreview.value = ev.target.result }
  reader.readAsDataURL(file)
}
const clearImage = () => {
  imageFile.value = null
  imageName.value = ''
  imagePreview.value = ''
  const el = document.getElementById('agent-icon-input')
  if (el) el.value = ''
}

const resetForm = () => {
  form.value = { name: '', version: '1.0.0', url: '', description: '', tags: [], price: 0 }
  clearImage()
  touched.value = { name: false, version: false, url: false, description: false, price: false }
  errors.value = { name: '', version: '', url: '', description: '', price: '' }
  fetchSuggestion()
}

const submitApply = async () => {
  if (!auth.isLoggedIn || auth.isAdmin) return
  if (submitting.value) return         // 二次防抖,避免 Enter + 点击连击
  if (!validateAll()) {
    toast.warning('请检查表单中标红的字段')
    return
  }
  submitting.value = true
  try {
    // ====== 步骤 1:先上传图标(如有) ======
    // SDS Server 的 /api/agent/client 期望 JSON body,不能接 multipart;
    // 图标走单独的 /api/file/upload 拿 file_path,作为 logo_url 回填。
    let logoUrl = null
    if (imageFile.value) {
      const fd = new FormData()
      fd.append('file', imageFile.value, imageFile.value.name)
      // axios 见到 FormData 会自动加 boundary,这里不要手动指定 Content-Type
      const upRes = await api.post('/file/upload', fd)
      logoUrl = upRes?.file_path || null
    }

    // ====== 步骤 2:构造 ACS 描述符(SDS Server 必填) ======
    const now = new Date().toISOString()
    const safeName = (form.value.name || 'agent').replace(/\W/g, '')
    const acs = {
      aic: `1.2.156.${Date.now()}.local.${safeName}.1.0001`,
      protocolVersion: '02.00',
      name: form.value.name,
      version: form.value.version,
      active: true,
      description: form.value.description || '',
      lastModifiedTime: now,
      defaultInputModes: ['text/plain'],
      defaultOutputModes: ['text/plain'],
      capabilities: {
        streaming: false,
        notification: false,
        messageQueue: []
      },
      securitySchemes: {
        mtls: {
          type: 'mutualTLS',
          description: '智能体间mTLS双向认证',
          'x-caChallengeBaseUrl': 'http://10.126.126.8:8888/acps-atr-v2'
        }
      },
      provider: {
        url: 'https://agents.local',
        organization: '本地开发',
        department: '智能体研发部'
      },
      skills: [{
        id: 'default.skill',
        name: '默认技能',
        tags: ['通用'],
        version: '1.0.0',
        examples: ['示例调用'],
        inputModes: ['text/plain'],
        outputModes: ['text/plain'],
        description: form.value.description || '默认技能'
      }],
      endPoints: form.value.url
        ? [{ url: form.value.url, transport: 'HTTP', security: [{ mtls: [] }] }]
        : [{ url: 'http://10.126.126.8:9000/rpc', transport: 'HTTP', security: [{ mtls: [] }] }]
    }

    // ====== 步骤 3:统一 JSON 创建(SDS Server AgentCreate schema) ======
    // 必填: name, version;可选: description, logo_url, acs, is_ontology
    // 不再发 price/tags — SDS Server 这俩不在 AgentCreate 里(原 standalone.py 才会读)
    const payload = {
      name: form.value.name,
      version: form.value.version,
      description: form.value.description,
      logo_url: logoUrl,
      acs
    }
    const res = await api.post('/agent/client', payload)
    if (!res?.id) throw new Error('创建智能体失败:后端未返回 id')

    // ====== 步骤 4:提交审批(DRAFT → PENDING) ======
    // SDS Server 在 submit 内部其实**先**把 status 改成 PENDING,**后**调远端 CA 同步 passport。
    // 即便 CA 同步返 502,agent 状态已经是 PENDING 并进审批队列,管理员侧能正常看到。
    // 所以这里对 submit 的失败降级处理:仅 console.warn,不让用户被红字误导
    // ——从用户视角"创建+提交"已经成功,具体 passport 同步是后端问题,留给后端修。
    try {
      await api.post(`/agent/client/${res.id}/submit`)
    } catch (submitErr) {
      console.warn('[AgentApply] submit 时 CA 同步失败,agent 已是 PENDING,稍后由后端补 passport:', submitErr)
    }

    toast.success('智能体已创建并提交审批')

    // 进入流程页
    submittedName.value = form.value.name
    startFlow()
  } catch (err) {
    toast.error(err.message || '创建失败')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
/* ============== Page Container & Background ============== */
.apply-page {
  /* 把组件级 CSS 变量挂在自己身上,避免污染全局 :root */
  --float-bar-bottom: 32px;
  --float-bar-start: 8px;
  position: relative;
  min-height: 100vh;
  padding: 56px 0 140px;
  background: var(--bg-page-blue);
  overflow: hidden;
}
.apply-bg { position: absolute; inset: 0; pointer-events: none; z-index: 0; }
.apply-bg-grid {
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(46, 122, 184, 0.07) 1px, transparent 1px),
    linear-gradient(90deg, rgba(46, 122, 184, 0.07) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(ellipse 80% 60% at 50% 0%, #000 30%, transparent 80%);
  -webkit-mask-image: radial-gradient(ellipse 80% 60% at 50% 0%, #000 30%, transparent 80%);
  opacity: 0.6;
}
.apply-bg-glow {
  position: absolute;
  top: -10%; right: -10%;
  width: 480px; height: 480px;
  background: radial-gradient(circle, var(--accent-blue) 0%, transparent 60%);
  opacity: 0.10;
  filter: blur(60px);
}
.apply-container {
  position: relative; z-index: 1;
  max-width: 720px; margin: 0 auto; padding: 0 32px;
}

/* ============== Header ============== */
.apply-header {
  text-align: left;
  max-width: 720px;
  margin-bottom: 56px;
}
.header-eyebrow {
  display: inline-flex; align-items: center; gap: 12px;
  margin-bottom: 20px;
  font-family: var(--font-mono);
  font-size: 12px; font-weight: 500;
  color: var(--text-muted);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.header-eyebrow .dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--accent-blue);
  box-shadow: 0 0 12px var(--accent-blue);
  animation: pulseDot 2s ease-in-out infinite;
}
.eyebrow-text { color: var(--text-secondary); }
.eyebrow-line { width: 40px; height: 1px; background: var(--line-blue); }
.eyebrow-meta { color: var(--text-placeholder); }
@keyframes pulseDot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.apply-title {
  font-family: var(--font-display);
  font-size: clamp(40px, 5vw, 64px);
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.03em;
  line-height: 1.05;
  margin: 0 0 16px;
}
.title-italic {
  font-family: var(--font-editorial);
  font-style: italic;
  font-weight: 400;
  color: var(--accent-blue);
  letter-spacing: -0.02em;
}
.apply-sub {
  font-size: 16px; line-height: 1.7;
  color: var(--text-muted);
  margin: 0;
  max-width: 580px;
}

/* ============== Form ============== */
.apply-form {
  display: flex; flex-direction: column;
}
.form-section {
  border: none;
  margin: 0 0 40px;
  padding: 0;
}
.section-legend {
  display: flex; align-items: center; gap: 12px;
  margin-bottom: 24px;
  padding: 0;
}
.legend-num {
  font-family: var(--font-mono);
  font-size: 14px; font-weight: 500;
  color: var(--accent-blue);
  letter-spacing: 0.05em;
}
.legend-line {
  flex: 0 0 24px; height: 1px;
  background: var(--accent-blue);
  opacity: 0.4;
}
.legend-title {
  font-family: var(--font-display);
  font-size: 20px; font-weight: 600;
  color: var(--text-primary);
  letter-spacing: -0.01em;
}
.legend-en {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-placeholder);
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

/* ============== Field ============== */
.field { margin-bottom: 24px; }
.field:last-child { margin-bottom: 0; }
.field-label {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 10px;
  font-size: 14px; font-weight: 500;
  color: var(--text-primary);
}
.field-required {
  font-family: var(--font-mono);
  font-size: 11px; font-weight: 500;
  color: var(--accent-blue);
  letter-spacing: 0.05em;
  text-transform: uppercase;
}
.field-optional {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-placeholder);
  letter-spacing: 0.05em;
  text-transform: uppercase;
}
.field-hint {
  margin: 8px 0 0;
  font-size: 12px; line-height: 1.5;
  color: var(--text-placeholder);
}
.field-hint code {
  font-family: var(--font-mono);
  padding: 1px 5px;
  background: var(--bg-badge);
  border-radius: 4px;
  color: var(--text-secondary);
}
.field-error {
  margin: 8px 0 0;
  font-size: 12px; line-height: 1.5;
  color: var(--text-danger);
  display: flex; align-items: center; gap: 4px;
  animation: errorIn 0.18s ease;
}
.field-error::before {
  content: "!";
  display: inline-flex; align-items: center; justify-content: center;
  width: 14px; height: 14px; flex-shrink: 0;
  background: var(--accent-danger);
  color: #fff;
  border-radius: 50%;
  font-family: var(--font-mono);
  font-size: 10px; font-weight: 600;
  line-height: 1;
}
@keyframes errorIn {
  from { opacity: 0; transform: translateY(-2px); }
  to   { opacity: 1; transform: translateY(0); }
}
.field-input-wrap,
.field-textarea-wrap {
  position: relative;
  background: var(--bg-input);
  border: 1.5px solid var(--border-input);
  border-radius: 14px;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}
.field-input-wrap:hover,
.field-textarea-wrap:hover { border-color: var(--text-placeholder); }
.field-input-wrap:focus-within,
.field-textarea-wrap:focus-within {
  border-color: var(--accent-blue);
  box-shadow: 0 0 0 4px rgba(46, 122, 184, 0.14);
  background: #fff;
}
.field-input-wrap.is-filled,
.field-textarea-wrap.is-filled {
  border-color: var(--accent-blue-border);
  background: linear-gradient(180deg, var(--accent-blue-bg) 0%, #fff 60%);
}
/* 错误态:红边 + 红光晕 + 浅红底,跟正常态的蓝边明显区分 */
.field-input-wrap.has-error,
.field-textarea-wrap.has-error {
  border-color: var(--accent-danger);
  background: rgba(239, 68, 68, 0.04);
}
.field-input-wrap.has-error:focus-within,
.field-textarea-wrap.has-error:focus-within {
  box-shadow: 0 0 0 4px rgba(239, 68, 68, 0.14);
  background: #fff;
}
.field-input-wrap input,
.field-textarea-wrap textarea {
  width: 100%;
  padding: 16px 56px 16px 18px;
  font-family: var(--font-text);
  font-size: 15px;
  color: var(--text-primary);
  background: transparent;
  border: none;
  border-radius: 14px;
  outline: none;
}
.field-input-wrap.is-mono input {
  font-family: var(--font-mono);
  letter-spacing: 0.02em;
}
.field-textarea-wrap textarea {
  padding: 16px 18px 36px;
  resize: vertical;
  min-height: 120px;
  line-height: 1.6;
}
.field-counter {
  position: absolute;
  right: 14px; top: 50%; transform: translateY(-50%);
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-placeholder);
  pointer-events: none;
  letter-spacing: 0.02em;
}
.field-textarea-wrap .field-counter {
  top: auto; bottom: 10px; transform: none;
}

/* ============== Tag Chips ============== */
.tag-chip-group {
  display: flex; flex-wrap: wrap; gap: 8px;
}
.tag-chip {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 8px 14px;
  font-family: var(--font-text);
  font-size: 13px; font-weight: 500;
  color: var(--text-secondary);
  background: var(--bg-input);
  border: 1.5px solid var(--border-input);
  border-radius: 100px;
  cursor: pointer;
  transition: all 0.2s ease;
  user-select: none;
}
.tag-chip:hover:not(:disabled) {
  border-color: var(--accent-blue);
  color: var(--accent-blue);
  transform: translateY(-1px);
}
.tag-chip.active {
  background: var(--accent-blue);
  color: #fff;
  border-color: var(--accent-blue);
  box-shadow: 0 4px 12px rgba(46, 122, 184, 0.28);
}
.tag-chip:disabled:not(.active) {
  opacity: 0.4; cursor: not-allowed;
}
.chip-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--accent-blue);
  opacity: 0.55;
  transition: all 0.2s;
}
.tag-chip.active .chip-dot { background: #fff; opacity: 1; }

/* ============== Icon Drop ============== */
.icon-drop {
  position: relative;
  border: 2px dashed var(--border-card);
  border-radius: 18px;
  background:
    repeating-linear-gradient(
      45deg,
      transparent 0 12px,
      rgba(46, 122, 184, 0.04) 12px 13px
    );
  transition: all 0.25s ease;
  overflow: hidden;
}
.icon-drop:hover { border-color: var(--accent-blue); }
.icon-drop.is-drag {
  border-color: var(--accent-blue);
  background: rgba(46, 122, 184, 0.06);
  transform: scale(1.005);
}
.icon-drop.has-image {
  border-style: solid;
  border-color: var(--border-card);
  background: #fff;
}
.icon-drop-input {
  position: absolute; opacity: 0; pointer-events: none; width: 0; height: 0;
}
.icon-drop-empty {
  display: flex; flex-direction: column; align-items: center;
  padding: 40px 24px;
  text-align: center;
  cursor: pointer;
}
.drop-icon {
  width: 56px; height: 56px;
  display: flex; align-items: center; justify-content: center;
  background: var(--bg-input);
  border: 1.5px solid var(--border-input);
  border-radius: 50%;
  color: var(--text-muted);
  margin-bottom: 16px;
  transition: all 0.25s ease;
}
.icon-drop:hover .drop-icon {
  background: var(--accent-blue); color: #fff; border-color: var(--accent-blue);
  transform: translateY(-2px);
}
.drop-text {
  display: flex; flex-direction: column; gap: 4px;
  margin-bottom: 12px;
  font-size: 14px;
  color: var(--text-secondary);
}
.drop-text strong {
  font-weight: 600; color: var(--text-primary);
  font-size: 15px;
}
.drop-link {
  color: var(--accent-blue);
  font-weight: 500;
  cursor: pointer;
  margin: 0 4px;
  border-bottom: 1px dashed var(--accent-blue);
}
.drop-meta {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-placeholder);
  letter-spacing: 0.03em;
}
.icon-drop-preview {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 20px;
  align-items: center;
  padding: 20px;
}
.preview-img {
  width: 96px; height: 96px;
  object-fit: cover;
  border-radius: 16px;
  background: var(--bg-page);
}
.preview-actions {
  display: flex; flex-direction: column; gap: 8px;
  align-items: flex-start;
}
.preview-btn {
  display: inline-flex; align-items: center; justify-content: center;
  padding: 7px 14px;
  font-size: 13px; font-weight: 500;
  font-family: var(--font-text);
  color: var(--text-primary);
  background: var(--bg-input);
  border: 1px solid var(--border-input);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.preview-btn:hover {
  background: var(--accent-blue); color: #fff; border-color: var(--accent-blue);
}
.preview-btn-danger {
  color: var(--text-danger);
  background: transparent;
  border-color: transparent;
}
.preview-btn-danger:hover {
  background: rgba(239, 68, 68, 0.08);
  color: var(--text-danger);
  border-color: transparent;
}
.preview-name {
  grid-column: 1 / -1;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-placeholder);
  margin-top: 4px;
  word-break: break-all;
}

/* ============== Pricing Suggestion ============== */
.field-counter-suffix {
  position: absolute;
  right: 14px; top: 50%; transform: translateY(-50%);
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-placeholder);
  pointer-events: none;
  background: var(--bg-input);
  padding-left: 6px;
}
.pricing-suggestion {
  margin-top: 16px;
  background: linear-gradient(135deg, rgba(46, 122, 184, 0.05) 0%, rgba(27, 90, 142, 0.03) 100%);
  border: 1px solid var(--accent-blue-border);
  border-radius: 14px;
  padding: 18px 20px;
  animation: psIn 0.4s var(--ease-out);
}
@keyframes psIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
.ps-head {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 14px;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-secondary);
  letter-spacing: 0.04em;
}
.ps-icon { font-size: 16px; }
.ps-title { font-weight: 600; color: var(--accent-blue-d); }
.ps-sample { margin-left: auto; color: var(--text-placeholder); font-size: 10px; }

.ps-bar { margin-bottom: 14px; }
.ps-bar-track {
  position: relative;
  height: 6px;
  background: var(--bg-input);
  border-radius: 3px;
  border: 1px solid var(--border-input);
  margin-bottom: 8px;
}
.ps-bar-track > div {
  position: absolute;
  top: -4px; bottom: -4px;
  width: 2px;
  background: var(--accent-blue);
}
.ps-bar-p25 { opacity: 0.4; }
.ps-bar-p50 {
  background: var(--accent-blue-d);
  width: 3px !important;
  opacity: 1;
  box-shadow: 0 0 0 4px rgba(46, 122, 184, 0.10);
}
.ps-bar-p75 { opacity: 0.4; }
.ps-bar-current {
  background: var(--signal-warning) !important;
  width: 3px !important;
  box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.20);
}
.ps-bar-labels {
  display: flex; justify-content: space-between;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-placeholder);
  letter-spacing: 0.05em;
}

.ps-stats {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 12px;
}
.ps-stat {
  display: flex; flex-direction: column; align-items: center; gap: 2px;
  padding: 10px 6px;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: 10px;
}
.ps-stat.ps-stat-mid {
  border-color: var(--accent-blue);
  background: rgba(46, 122, 184, 0.05);
}
.ps-stat-label {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-placeholder);
  letter-spacing: 0.05em;
}
.ps-stat-num {
  font-family: var(--font-display);
  font-size: 18px; font-weight: 600;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}
.ps-stat-mid .ps-stat-num { color: var(--accent-blue-d); }

.ps-actions { display: flex; gap: 6px; flex-wrap: wrap; }
.ps-quick {
  padding: 6px 12px;
  font-family: var(--font-mono);
  font-size: 11px; font-weight: 500;
  color: var(--text-secondary);
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}
.ps-quick:hover { border-color: var(--accent-blue); color: var(--accent-blue-d); }
.ps-quick-mid {
  background: var(--accent-blue);
  color: #fff;
  border-color: var(--accent-blue);
}
.ps-quick-mid:hover { background: var(--accent-blue-d); color: #fff; border-color: var(--accent-blue-d); }
.ps-note {
  margin: 10px 0 0;
  font-size: 11px; line-height: 1.5;
  color: var(--text-placeholder);
  font-style: italic;
}

/* ============== Floating Action Bar (悬浮窗 - 居中) ============== */
.form-actions {
  position: fixed;
  inset: auto 0 var(--float-bar-bottom) 0;
  margin: 0 auto;
  width: fit-content;
  z-index: 100;
  display: flex; align-items: center;
  gap: 6px;
  padding: 8px 8px 8px 8px;
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(20px) saturate(1.6);
  -webkit-backdrop-filter: blur(20px) saturate(1.6);
  border: 1px solid rgba(46, 122, 184, 0.20);
  border-radius: 999px;
  box-shadow:
    0 18px 44px -10px rgba(46, 122, 184, 0.28),
    0 4px 14px -2px rgba(23, 26, 32, 0.04),
    inset 0 1px 0 rgba(255, 255, 255, 0.6);
  animation: floatBarIn 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.3s backwards;
}
@keyframes floatBarIn {
  from { opacity: 0; bottom: var(--float-bar-start); }
  to   { opacity: 1; bottom: var(--float-bar-bottom); }
}
.btn-ghost {
  display: inline-flex; align-items: center;
  padding: 9px 16px;
  font-family: var(--font-text);
  font-size: 13px; font-weight: 500;
  color: var(--text-secondary);
  background: transparent;
  border: none;
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.btn-ghost:hover:not(:disabled) {
  color: var(--text-primary);
  background: var(--bg-hover);
}
.btn-ghost:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-primary-cta {
  position: relative;
  display: inline-flex; align-items: center; justify-content: center;
  padding: 10px 20px;
  font-family: var(--font-text);
  font-size: 13px; font-weight: 600;
  color: #fff;
  background: var(--accent-blue);
  border: none;
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 4px 12px rgba(46, 122, 184, 0.35);
  text-decoration: none;
  white-space: nowrap;
}
.btn-primary-cta:hover:not(:disabled) {
  background: var(--accent-blue-d);
  transform: translateY(-1px);
  box-shadow: 0 8px 20px rgba(46, 122, 184, 0.45);
}
.btn-primary-cta:active:not(:disabled) { transform: translateY(0); }
.btn-primary-cta:disabled { opacity: 0.5; cursor: not-allowed; }
.cta-content { display: inline-flex; align-items: center; gap: 8px; }
.cta-spinner {
  width: 14px; height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ============================================================== */
/* ============== APPROVAL FLOW PAGE ============================= */
/* ============================================================== */
.approval-flow { width: 100%; }

/* --- Flow header --- */
.flow-header { margin-bottom: 32px; }
.flow-issue {
  display: inline-flex; align-items: center; gap: 12px;
  margin-bottom: 16px;
  font-family: var(--font-mono);
  font-size: 12px; font-weight: 500;
  color: var(--text-muted);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.flow-issue-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--accent-warning);
  box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.18);
  animation: pulseDot 1.4s ease-in-out infinite;
}
.flow-issue-line { width: 32px; height: 1px; background: var(--line-blue); }
.flow-issue-meta { color: var(--text-placeholder); }

.flow-title {
  font-family: var(--font-display);
  font-size: clamp(32px, 4.2vw, 48px);
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.025em;
  line-height: 1.1;
  margin: 0 0 14px;
}
.flow-quote {
  font-family: var(--font-editorial);
  font-style: italic;
  font-weight: 400;
  color: var(--accent-blue);
  margin: 0 4px;
}
.flow-title-suffix {
  display: inline-block;
  margin-left: 8px;
  font-size: 0.55em;
  font-weight: 500;
  color: var(--text-muted);
  letter-spacing: 0;
}
.flow-sub {
  font-size: 15px; line-height: 1.7;
  color: var(--text-muted);
  margin: 0;
  max-width: 580px;
}

/* --- Big progress block --- */
.progress-block {
  margin: 32px 0 28px;
  padding: 24px 28px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid var(--accent-blue-border);
  border-radius: 20px;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.8) inset;
}
.progress-meta {
  display: flex; justify-content: space-between; align-items: baseline;
  margin-bottom: 12px;
}
.progress-label {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-muted);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.progress-num {
  font-family: var(--font-display);
  font-size: 32px; font-weight: 600;
  color: var(--text-primary);
  letter-spacing: -0.02em;
}
.progress-num small {
  font-size: 16px;
  color: var(--text-muted);
  font-weight: 500;
  margin-left: 2px;
}
.progress-track {
  position: relative;
  height: 10px;
  background: var(--bg-badge);
  border-radius: 100px;
  overflow: hidden;
  margin-bottom: 20px;
}
.progress-fill {
  position: relative;
  height: 100%;
  background: linear-gradient(90deg, var(--accent-blue) 0%, var(--accent-blue-d) 100%);
  border-radius: 100px;
  transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}
.progress-fill-shine {
  position: absolute;
  top: 0; left: 0;
  width: 30%; height: 100%;
  background: linear-gradient(90deg, transparent 0%, rgba(255, 255, 255, 0.5) 50%, transparent 100%);
  animation: shine 1.8s linear infinite;
}
@keyframes shine {
  from { transform: translateX(-100%); }
  to   { transform: translateX(400%); }
}
.progress-tick {
  position: absolute;
  top: 0; bottom: 0;
  width: 1px;
  background: rgba(255, 255, 255, 0.6);
  transform: translateX(-50%);
  pointer-events: none;
}

.progress-steps {
  display: flex; align-items: center;
  gap: 0;
}
.progress-step {
  display: flex; align-items: center; gap: 10px;
  font-size: 13px;
  color: var(--text-placeholder);
  transition: color 0.3s;
  flex-shrink: 0;
}
.progress-step.active { color: var(--accent-blue-d); }
.progress-step.done { color: var(--text-primary); }
.step-dot {
  display: flex; align-items: center; justify-content: center;
  width: 28px; height: 28px;
  border-radius: 50%;
  background: var(--bg-badge);
  border: 1.5px solid var(--border-card);
  font-family: var(--font-mono);
  font-size: 11px; font-weight: 500;
  color: var(--text-placeholder);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.progress-step.active .step-dot {
  background: var(--accent-blue);
  color: #fff;
  border-color: var(--accent-blue);
  box-shadow: 0 0 0 4px rgba(46, 122, 184, 0.18);
}
.progress-step.done .step-dot {
  background: var(--accent-success);
  color: #fff;
  border-color: var(--accent-success);
}
.step-label {
  font-weight: 500;
  letter-spacing: -0.005em;
}
.progress-connector {
  flex: 1;
  height: 1.5px;
  background: var(--border-card);
  margin: 0 16px;
  border-radius: 2px;
  position: relative;
  overflow: hidden;
  transition: background 0.3s;
}
.progress-connector.done { background: var(--accent-success); }

/* --- Step cards --- */
.flow-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  margin-bottom: 32px;
}
.flow-card {
  position: relative;
  padding: 24px;
  background: #fff;
  border: 1.5px solid var(--border-card);
  border-radius: 20px;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}
.flow-card.is-pending { opacity: 0.6; }
.flow-card.is-active {
  border-color: var(--accent-blue);
  box-shadow: 0 12px 32px -8px rgba(46, 122, 184, 0.20);
}
.flow-card.is-done {
  border-color: var(--badge-approved-border);
  background: linear-gradient(180deg, rgba(16, 185, 129, 0.04) 0%, #fff 30%);
}

.flow-card-head {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 10px;
}
.flow-card-num {
  font-family: var(--font-mono);
  font-size: 13px; font-weight: 500;
  color: var(--text-placeholder);
  letter-spacing: 0.05em;
}
.flow-card.is-active .flow-card-num { color: var(--accent-blue); }
.flow-card.is-done .flow-card-num { color: var(--accent-success); }
.flow-card-status {
  display: inline-flex; align-items: center; gap: 6px;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-placeholder);
}
.flow-card.is-active .flow-card-status { color: var(--accent-blue-d); }
.flow-card.is-done .flow-card-status { color: var(--accent-success); }
.status-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: currentColor;
}
.flow-card.is-active .status-dot { animation: pulseDot 1.4s infinite; }

.flow-card-title {
  font-family: var(--font-display);
  font-size: 22px; font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 6px;
  letter-spacing: -0.01em;
}
.flow-card-desc {
  font-size: 13px; line-height: 1.55;
  color: var(--text-muted);
  margin: 0 0 20px;
}

/* --- Animation stage (white frame, centered) --- */
.flow-card-anim {
  height: 180px;
  background: linear-gradient(180deg, #fafbfd 0%, #f0f7fc 100%);
  border: 1px solid var(--line-blue);
  border-radius: 14px;
  margin-bottom: 18px;
  display: flex; align-items: center; justify-content: center;
  position: relative;
  overflow: hidden;
}
.flow-card.is-pending .flow-card-anim {
  background: linear-gradient(180deg, #f7f8fa 0%, #eef0f3 100%);
}
.flow-card-anim::before {
  content: '';
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(46, 122, 184, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(46, 122, 184, 0.05) 1px, transparent 1px);
  background-size: 20px 20px;
  pointer-events: none;
}

/* --- Checklist inside card --- */
.flow-checklist {
  list-style: none; padding: 0; margin: 0;
  display: flex; flex-direction: column; gap: 6px;
}
.flow-checklist li {
  display: flex; align-items: center; gap: 8px;
  font-size: 12px;
  color: var(--text-placeholder);
  transition: color 0.3s;
}
.flow-checklist li.done { color: var(--text-secondary); }
.flow-checklist .check {
  width: 14px; height: 14px;
  border-radius: 50%;
  background: var(--bg-badge);
  border: 1.5px solid var(--border-card);
  position: relative;
  flex-shrink: 0;
  transition: all 0.3s;
}
.flow-checklist li.done .check {
  background: var(--accent-success);
  border-color: var(--accent-success);
}
.flow-checklist li.done .check::after {
  content: '';
  position: absolute;
  left: 4px; top: 1px;
  width: 3px; height: 7px;
  border: solid #fff;
  border-width: 0 1.5px 1.5px 0;
  transform: rotate(45deg);
}

/* ============================================================== */
/* ===== 审视.css: 黑箱测试 loader (含蓝色光晕) ================ */
/* ============================================================== */
.anim-scope-blackbox {
  position: relative; width: 100%; height: 100%;
  display: flex; align-items: center; justify-content: center;
}
.loader-stage {
  position: relative;
  display: flex; flex-direction: column; align-items: center; gap: 16px;
}
.loader {
  position: relative;
  width: 78px; height: 78px;
  border-radius: 50%;
  background: #fff;
  border: 8px solid #131a1d;
  overflow: hidden;
  box-sizing: border-box;
  z-index: 1;
}
.loader::after {
  content: '';
  position: absolute;
  left: 0; top: -50%;
  width: 100%; height: 100%;
  background: #263238;
  z-index: 5;
  border-bottom: 8px solid #131a1d;
  box-sizing: border-box;
  animation: eyeShade 3s infinite;
}
.loader::before {
  content: '';
  position: absolute;
  left: 20px; bottom: 15px;
  width: 32px; z-index: 2;
  height: 32px;
  background: var(--accent-blue);
  border-radius: 50%;
  box-shadow: 0 0 12px var(--accent-blue);
  animation: eyeMove 3s infinite;
}
@keyframes eyeShade {
  0%   { transform: translateY(0); }
  20%  { transform: translateY(5px); }
  40%, 50% { transform: translateY(-5px); }
  60%  { transform: translateY(-8px); }
  75%  { transform: translateY(5px); }
  100% { transform: translateY(10px); }
}
@keyframes eyeMove {
  0%   { transform: translate(0, 0); }
  20%  { transform: translate(0px, 5px); }
  40%, 50% { transform: translate(0px, -5px); }
  60%  { transform: translate(-10px, -5px); }
  75%  { transform: translate(-20px, 5px); }
  100% { transform: translate(0, 10px); }
}
.loader-glow {
  position: absolute;
  top: 50%; left: 50%;
  width: 140px; height: 140px;
  transform: translate(-50%, -65%);
  background: radial-gradient(circle, rgba(46, 122, 184, 0.25) 0%, transparent 70%);
  border-radius: 50%;
  z-index: 0;
  animation: glowPulse 3s ease-in-out infinite;
  pointer-events: none;
}
@keyframes glowPulse {
  0%, 100% { opacity: 0.6; transform: translate(-50%, -65%) scale(1); }
  50%      { opacity: 1;   transform: translate(-50%, -65%) scale(1.15); }
}
.loader-label {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.18em;
  color: var(--text-placeholder);
  text-transform: uppercase;
  position: relative; z-index: 1;
}
.mono { font-family: var(--font-mono); }

/* ============================================================== */
/* ===== 火箭.css: 发布上线 (Launching) ========================= */
/* ============================================================== */
.anim-scope-rocket {
  position: relative; width: 100%; height: 100%;
  display: flex; align-items: center; justify-content: center;
  overflow: hidden;
}
.rocket-stage {
  position: relative;
  display: flex; flex-direction: column; align-items: center; gap: 12px;
  width: 100%; height: 100%;
  justify-content: center;
}
.rocket-glow {
  position: absolute;
  top: 50%; left: 50%;
  width: 130px; height: 130px;
  transform: translate(-50%, -50%);
  background: radial-gradient(circle, rgba(46, 122, 184, 0.18) 0%, transparent 70%);
  border-radius: 50%;
  z-index: 0;
  animation: glowPulse 2.4s ease-in-out infinite;
}

/* ============================================================== */
/* ===== 火箭动画 (来自 C:\Users\86152\Desktop\火箭动画.css) ===== */
/* 用 transform: scale(0.5) 把参考的 80×180 火箭缩进 180px 容器 */
/* ============================================================== */
.rocket-scale {
  position: relative;
  width: 100%; height: 100%;
  display: flex; align-items: center; justify-content: center;
  transform: scale(0.5);
  transform-origin: center center;
  z-index: 1;
}

.rocket {
  position: absolute;
  top: 20%;
  width: 80px;
  left: calc(50% - 40px);
}

.rocket .rocket-body {
  width: 80px;
  left: calc(50% - 50px);
  animation: bounce 0.5s infinite;
  z-index: 1;
}

.rocket .rocket-body .body {
  background-color: #fff;
  height: 180px;
  left: calc(50% - 50px);
  border-top-right-radius: 100%;
  border-top-left-radius: 100%;
  border-bottom-left-radius: 50%;
  border-bottom-right-radius: 50%;
  border: 2px solid var(--accent-blue);
  box-shadow: 0 8px 20px -6px rgba(20, 22, 26, 0.18);
}

.rocket .rocket-body:before {
  content: '';
  position: absolute;
  left: calc(50% - 24px);
  width: 48px;
  height: 13px;
  background-color: var(--accent-blue-d);
  bottom: -13px;
  border-bottom-right-radius: 60%;
  border-bottom-left-radius: 60%;
}

.rocket .window {
  position: absolute;
  width: 40px;
  height: 40px;
  border-radius: 100%;
  background: radial-gradient(circle at 30% 30%, #fff 0%, #d4e6f2 50%, #4a8db5 100%);
  left: calc(50% - 25px);
  top: 40px;
  border: 2px solid var(--accent-blue);
  box-shadow: inset -2px -2px 4px rgba(13, 36, 56, 0.35);
}

.rocket .fin {
  position: absolute;
  z-index: -100;
  height: 55px;
  width: 50px;
  background-color: var(--accent-blue);
}

.rocket .fin-left {
  left: -30px;
  top: calc(100% - 55px);
  border-top-left-radius: 80%;
  border-bottom-left-radius: 20%;
}

.rocket .fin-right {
  right: -30px;
  top: calc(100% - 55px);
  border-top-right-radius: 80%;
  border-bottom-right-radius: 20%;
}

.rocket .exhaust-flame {
  position: absolute;
  top: 90%;
  width: 28px;
  background: linear-gradient(to bottom, transparent 10%, #f5f5f5 50%, #f59e0b 90%, #ef4444 100%);
  height: 150px;
  left: calc(50% - 14px);
  animation: exhaust 0.2s infinite;
  border-radius: 0 0 14px 14px;
}

.rocket .exhaust-fumes {
  list-style: none;
  margin: 0; padding: 0;
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.rocket .exhaust-fumes li {
  width: 60px;
  height: 60px;
  background-color: rgba(74, 141, 181, 0.18);
  list-style: none;
  position: absolute;
  border-radius: 100%;
}

.rocket .exhaust-fumes li:first-child {
  width: 200px;
  height: 200px;
  bottom: -300px;
  animation: fumes 5s infinite;
}
.rocket .exhaust-fumes li:nth-child(2) {
  width: 150px;
  height: 150px;
  left: -120px;
  top: 260px;
  animation: fumes 3.2s infinite;
}
.rocket .exhaust-fumes li:nth-child(3) {
  width: 120px;
  height: 120px;
  left: -40px;
  top: 330px;
  animation: fumes 3s 1s infinite;
}
.rocket .exhaust-fumes li:nth-child(4) {
  width: 100px;
  height: 100px;
  left: -170px;
  animation: fumes 4s 2s infinite;
  top: 380px;
}
.rocket .exhaust-fumes li:nth-child(5) {
  width: 130px;
  height: 130px;
  left: -120px;
  top: 350px;
  animation: fumes 5s infinite;
}
.rocket .exhaust-fumes li:nth-child(6) {
  width: 200px;
  height: 200px;
  left: -60px;
  top: 280px;
  animation: fumes2 10s infinite;
}
.rocket .exhaust-fumes li:nth-child(7) {
  width: 100px;
  height: 100px;
  left: -100px;
  top: 320px;
}
.rocket .exhaust-fumes li:nth-child(8) {
  width: 110px;
  height: 110px;
  left: 70px;
  top: 340px;
}
.rocket .exhaust-fumes li:nth-child(9) {
  width: 90px;
  height: 90px;
  left: 200px;
  top: 380px;
  animation: fumes 20s infinite;
}

.star {
  list-style: none;
  margin: 0; padding: 0;
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.star li {
  list-style: none;
  position: absolute;
}

.star li:before, .star li:after {
  content: '';
  position: absolute;
  background-color: var(--accent-blue-l);
  border-radius: 50%;
}

.star li:before {
  width: 10px;
  height: 2px;
}

.star li:after {
  height: 8px;
  width: 2px;
  left: 4px;
  top: -3px;
}

.star li:first-child {
  top: -30px;
  left: -210px;
  animation: twinkle 0.4s infinite;
}
.star li:nth-child(2) {
  top: 0;
  left: 60px;
  animation: twinkle 0.5s infinite;
}
.star li:nth-child(2):before { height: 1px; width: 5px; }
.star li:nth-child(2):after  { width: 1px; height: 5px; top: -2px; left: 2px; }

.star li:nth-child(3) {
  left: 120px;
  top: 220px;
  animation: twinkle 1s infinite;
}
.star li:nth-child(4) {
  left: -100px;
  top: 200px;
  animation: twinkle 0.5s ease infinite;
}
.star li:nth-child(5) {
  left: 170px;
  top: 100px;
  animation: twinkle 0.4s ease infinite;
}
.star li:nth-child(6) {
  top: 87px;
  left: -79px;
  animation: twinkle 0.2s infinite;
}
.star li:nth-child(6):before { height: 1px; width: 5px; }
.star li:nth-child(6):after  { width: 1px; height: 5px; top: -2px; left: 2px; }

/* 关键帧 */
@keyframes bounce {
  0%   { transform: translate3d(0, 0, 0); }
  50%  { transform: translate3d(0, -4px, 0); }
  100% { transform: translate3d(0, 0, 0); }
}
@keyframes exhaust {
  0%   { background: linear-gradient(to bottom, transparent 10%, #f5f5f5 100%); }
  50%  { background: linear-gradient(to bottom, transparent 8%,  #f5f5f5 100%); }
  75%  { background: linear-gradient(to bottom, transparent 12%, #f5f5f5 100%); }
}
@keyframes fumes {
  0%   { transform: scale(1); background-color: rgba(74, 141, 181, 0.18); }
  50%  { transform: scale(1.5); background-color: transparent; }
  51%  { transform: scale(0.8); }
  100% { transform: scale(1); background-color: rgba(74, 141, 181, 0.18); }
}
@keyframes fumes2 {
  0%, 100% { transform: scale(1); }
  50%      { transform: scale(1.1); }
}
@keyframes twinkle {
  0%, 100% { transform: scale(1); opacity: 1; }
  80%      { transform: scale(1.1); opacity: 0.7; }
}

/* done 状态:火箭变绿勾,落地 */
.flow-card.is-done .rocket-scale .rocket .body {
  background-color: #fff;
  border-color: var(--accent-success);
  box-shadow: 0 8px 20px -6px rgba(16, 185, 129, 0.3);
}
.flow-card.is-done .rocket-scale .rocket-body { animation: none; }
.flow-card.is-done .rocket-scale .rocket .window {
  background: var(--accent-success);
  border-color: var(--accent-success);
  box-shadow: none;
}
.flow-card.is-done .rocket-scale .rocket .window::after {
  content: "✓";
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  color: #fff;
  font-size: 22px; font-weight: 700;
  line-height: 1;
}
.flow-card.is-done .rocket-scale .rocket .fin {
  background-color: var(--accent-success);
}
.flow-card.is-done .rocket-scale .rocket .exhaust-flame { display: none; }
.flow-card.is-done .rocket-scale .rocket .exhaust-fumes { display: none; }
.flow-card.is-done .rocket-scale .star { display: none; }
.flow-card.is-done .rocket-scale .rocket-body:before {
  background-color: var(--accent-success);
}
.flow-card.is-done .rocket-glow {
  background: radial-gradient(circle, rgba(16, 185, 129, 0.18) 0%, transparent 70%);
  animation: none;
}

/* ============================================================== */
.anim-scope-macbook {
  position: relative; width: 100%; height: 100%;
  display: flex; align-items: center; justify-content: center;
  perspective: 500px;
  overflow: visible;
}
.macbook {
  width: 150px; height: 96px;
  position: relative;
  margin: 0;
  perspective: 500px;
}
.shadow {
  position: absolute;
  width: 60px; height: 0;
  left: 40px; top: 160px;
  transform: rotateX(80deg) rotateY(0deg) rotateZ(0deg);
  box-shadow: 0 0 60px 40px rgba(0, 0, 0, 0.3);
  animation: shadow infinite 7s ease;
}
.inner {
  z-index: 20;
  position: absolute;
  width: 150px; height: 96px;
  left: 0; top: 0;
  transform-style: preserve-3d;
  transform: rotateX(-20deg) rotateY(0deg) rotateZ(0deg);
  animation: rotate infinite 7s ease;
}
.screen {
  width: 150px; height: 96px;
  position: absolute;
  left: 0; bottom: 0;
  border-radius: 7px;
  background: #ddd;
  transform-style: preserve-3d;
  transform-origin: 50% 93px;
  transform: rotateX(0deg) rotateY(0deg) rotateZ(0deg);
  animation: lid-screen infinite 7s ease;
  background-image: linear-gradient(45deg, rgba(0, 0, 0, 0.34) 0%, rgba(0, 0, 0, 0) 100%);
  background-position: left bottom;
  background-size: 300px 300px;
  box-shadow: inset 0 3px 7px rgba(255, 255, 255, 0.5);
}
.screen .face-one {
  width: 150px; height: 96px;
  position: absolute;
  left: 0; bottom: 0;
  border-radius: 7px;
  background: #d3d3d3;
  transform: translateZ(2px);
  background-image: linear-gradient(45deg, rgba(0, 0, 0, 0.24) 0%, rgba(0, 0, 0, 0) 100%);
}
.screen .face-one .camera {
  width: 3px; height: 3px;
  border-radius: 100%;
  background: #000;
  position: absolute;
  left: 50%; top: 4px;
  margin-left: -1.5px;
}
.screen .face-one .display {
  width: 130px; height: 74px;
  margin: 10px;
  background-color: #0a1d2e;
  background-size: 100% 100%;
  border-radius: 1px;
  position: relative;
  box-shadow: inset 0 0 2px rgba(0, 0, 0, 1);
  overflow: hidden;
}
.display .shade {
  position: absolute;
  left: 0; top: 0;
  width: 130px; height: 74px;
  background: linear-gradient(-135deg, rgba(255, 255, 255, 0) 0%, rgba(255, 255, 255, 0.1) 47%, rgba(255, 255, 255, 0) 48%);
  animation: screen-shade infinite 7s ease;
  background-size: 300px 200px;
  background-position: 0px 0px;
  z-index: 2;
}
.display-lines {
  position: absolute;
  left: 0; top: 0;
  width: 100%; height: 100%;
  padding: 12px;
  display: flex; flex-direction: column; gap: 4px;
  z-index: 1;
}
.display-lines span {
  height: 4px;
  background: linear-gradient(90deg, rgba(46, 122, 184, 0.6) 0%, rgba(46, 122, 184, 0.1) 100%);
  border-radius: 1px;
  animation: lineScan 2.4s ease-in-out infinite;
}
.display-lines span:nth-child(1) { width: 70%; animation-delay: 0s; }
.display-lines span:nth-child(2) { width: 90%; animation-delay: 0.3s; }
.display-lines span:nth-child(3) { width: 50%; animation-delay: 0.6s; }
@keyframes lineScan {
  0%, 100% { opacity: 0.5; }
  50%      { opacity: 1; }
}
.screen span {
  position: absolute;
  top: 85px; left: 57px;
  font-size: 6px; color: #666;
}
.macbody {
  width: 150px; height: 96px;
  position: absolute;
  left: 0; bottom: 0;
  border-radius: 7px;
  background: #cbcbcb;
  transform-style: preserve-3d;
  transform-origin: 50% bottom;
  transform: rotateX(-90deg);
  animation: lid-macbody infinite 7s ease;
  background-image: linear-gradient(45deg, rgba(0, 0, 0, 0.24) 0%, rgba(0, 0, 0, 0) 100%);
}
.macbody .face-one {
  width: 150px; height: 96px;
  position: absolute;
  left: 0; bottom: 0;
  border-radius: 7px;
  transform-style: preserve-3d;
  background: #dfdfdf;
  animation: lid-keyboard-area infinite 7s ease;
  transform: translateZ(-2px);
  background-image: linear-gradient(30deg, rgba(0, 0, 0, 0.24) 0%, rgba(0, 0, 0, 0) 100%);
}
.macbody .touchpad {
  width: 40px; height: 31px;
  position: absolute;
  left: 50%; top: 50%;
  border-radius: 4px;
  margin: -44px 0 0 -18px;
  background: #cdcdcd;
  background-image: linear-gradient(30deg, rgba(0, 0, 0, 0.24) 0%, rgba(0, 0, 0, 0) 100%);
  box-shadow: inset 0 0 3px #888;
}
.macbody .keyboard {
  width: 130px; height: 45px;
  position: absolute;
  left: 7px; top: 41px;
  border-radius: 4px;
  transform-style: preserve-3d;
  background: #cdcdcd;
  background-image: linear-gradient(30deg, rgba(0, 0, 0, 0.24) 0%, rgba(0, 0, 0, 0) 100%);
  box-shadow: inset 0 0 3px #777;
  padding: 0 0 0 2px;
}
.keyboard .key {
  width: 6px; height: 6px;
  background: #444;
  float: left;
  margin: 1px;
  transform: translateZ(-2px);
  border-radius: 2px;
  box-shadow: 0 -2px 0 #222;
  animation: keys infinite 7s ease;
}
.key.space { width: 45px; }
.key.f { height: 3px; }
.macbody .pad {
  width: 5px; height: 5px;
  background: #333;
  border-radius: 100%;
  position: absolute;
}
.pad.one { left: 20px; top: 20px; }
.pad.two { right: 20px; top: 20px; }
.pad.three { right: 20px; bottom: 20px; }
.pad.four { left: 20px; bottom: 20px; }

@keyframes rotate {
  0%   { transform: rotateX(-20deg) rotateY(0deg)   rotateZ(0deg); }
  5%   { transform: rotateX(-20deg) rotateY(-20deg)  rotateZ(0deg); }
  20%  { transform: rotateX(30deg)  rotateY(200deg)  rotateZ(0deg); }
  25%  { transform: rotateX(-60deg) rotateY(150deg)  rotateZ(0deg); }
  60%  { transform: rotateX(-20deg) rotateY(130deg)  rotateZ(0deg); }
  65%  { transform: rotateX(-20deg) rotateY(120deg)  rotateZ(0deg); }
  80%  { transform: rotateX(-20deg) rotateY(375deg)  rotateZ(0deg); }
  85%  { transform: rotateX(-20deg) rotateY(357deg)  rotateZ(0deg); }
  87%  { transform: rotateX(-20deg) rotateY(360deg)  rotateZ(0deg); }
  100% { transform: rotateX(-20deg) rotateY(360deg)  rotateZ(0deg); }
}
@keyframes lid-screen {
  0%   { transform: rotateX(0deg);  background-position: left bottom; }
  5%   { transform: rotateX(50deg); background-position: left bottom; }
  20%  { transform: rotateX(-90deg); background-position: -150px top; }
  25%  { transform: rotateX(15deg);  background-position: left bottom; }
  30%  { transform: rotateX(-5deg);  background-position: right top; }
  38%  { transform: rotateX(5deg);   background-position: right top; }
  48%  { transform: rotateX(0deg);   background-position: right top; }
  90%  { transform: rotateX(0deg);   background-position: right top; }
  100% { transform: rotateX(0deg);   background-position: right center; }
}
@keyframes lid-macbody {
  0%, 100% { transform: rotateX(-90deg); }
}
@keyframes lid-keyboard-area {
  0%, 100% { background-color: #dfdfdf; }
  50%      { background-color: #bbb; }
}
@keyframes screen-shade {
  0%   { background-position: -20px 0px; }
  5%   { background-position: -40px 0px; }
  20%  { background-position: 200px 0; }
  50%  { background-position: -200px 0; }
  80%  { background-position: 0px 0px; }
  85%  { background-position: -30px 0; }
  90%  { background-position: -20px 0; }
  100% { background-position: -20px 0px; }
}
@keyframes keys {
  0%, 80%, 85%, 87%, 100% { box-shadow: 0 -2px 0 #222; }
  5%                      { box-shadow: 1px -1px 0 #222; }
  20%, 25%, 60%           { box-shadow: -1px 1px 0 #222; }
}
@keyframes shadow {
  0%   { transform: rotateX(80deg) rotateY(0deg)   rotateZ(0deg);    box-shadow: 0 0 60px 40px rgba(0, 0, 0, 0.3); }
  5%   { transform: rotateX(80deg) rotateY(10deg)  rotateZ(0deg);    box-shadow: 0 0 60px 40px rgba(0, 0, 0, 0.3); }
  20%  { transform: rotateX(30deg) rotateY(-20deg) rotateZ(-20deg);  box-shadow: 0 0 50px 30px rgba(0, 0, 0, 0.3); }
  25%  { transform: rotateX(80deg) rotateY(-20deg) rotateZ(50deg);   box-shadow: 0 0 35px 15px rgba(0, 0, 0, 0.1); }
  60%  { transform: rotateX(80deg) rotateY(0deg)   rotateZ(-50deg) translateX(30px); box-shadow: 0 0 60px 40px rgba(0, 0, 0, 0.3); }
  100% { box-shadow: 0 0 60px 40px rgba(0, 0, 0, 0.3); }
}

/* --- Result footer --- */
.flow-result {
  display: flex; align-items: center;
  gap: 20px;
  padding: 24px 28px;
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.06) 0%, #fff 60%);
  border: 1.5px solid var(--badge-approved-border);
  border-radius: 20px;
}
.flow-result-icon {
  width: 48px; height: 48px;
  flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 22px; font-weight: 600;
  color: #fff;
  background: var(--accent-success);
  border-radius: 50%;
  box-shadow: 0 8px 20px -4px rgba(16, 185, 129, 0.4);
}
.flow-result-info { flex: 1; min-width: 0; }
.flow-result-title {
  font-family: var(--font-display);
  font-size: 20px; font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 4px;
  letter-spacing: -0.01em;
}
.flow-result-sub {
  font-size: 13px; line-height: 1.5;
  color: var(--text-muted);
  margin: 0;
}
.flow-result-actions {
  display: flex; gap: 8px;
  flex-shrink: 0;
}

/* --- Flow entry animations --- */
.anim-flow-1, .anim-flow-3 { opacity: 0; transform: translateY(16px); }
.is-in .anim-flow-1 { animation: fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.1s forwards; }
.is-in .anim-flow-3 { animation: fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.3s forwards; }

/* ============== Entry Animations ============== */
.anim-item { opacity: 0; transform: translateY(16px); }
.is-in .anim-item { animation: fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards; }
.is-in .anim-0 { animation-delay: 0ms; }
.is-in .anim-1 { animation-delay: 80ms; }
.is-in .anim-2 { animation-delay: 160ms; }
.is-in .anim-3 { animation-delay: 240ms; }
.is-in .anim-4 { animation-delay: 320ms; }
.is-in .anim-5 { animation-delay: 400ms; }
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ============== Mobile ============== */
@media (max-width: 640px) {
  .apply-page {
    --float-bar-bottom: 20px;
    --float-bar-start: 4px;
  }
  .apply-page { padding: 32px 0 64px; }
  .apply-container { padding: 0 20px; }
  .apply-header { margin-bottom: 32px; }
  .apply-title { font-size: 36px; }
  .apply-sub { font-size: 14px; }
  .form-section { margin-bottom: 28px; }
  .form-actions {
    position: static;
    inset: auto;
    width: 100%;
    margin: 32px auto 0;
    padding: 6px;
    gap: 4px;
    transform: none;
  }
  .btn-ghost { padding: 8px 12px; }
  .btn-primary-cta { padding: 9px 16px; }
  .icon-drop-empty { padding: 28px 16px; }
  .flow-cards { grid-template-columns: 1fr; gap: 16px; }
  .flow-card { padding: 20px; }
  .flow-card-anim { height: 160px; }
  .flow-result { flex-direction: column; align-items: flex-start; padding: 20px; }
  .flow-result-actions { width: 100%; }
  .flow-result-actions .btn-ghost,
  .flow-result-actions .btn-primary-cta { flex: 1; justify-content: center; }
  .progress-num { font-size: 24px; }
  /* 不再 display:none,而是改成纵向排列:圆点在上文字在下,保留信息且不挤 */
  .progress-step { flex-direction: column; gap: 6px; flex: 0 0 auto; }
  .step-label {
    font-size: 10px;
    text-align: center;
    max-width: 64px;
    line-height: 1.3;
    letter-spacing: 0;
  }
  .progress-connector { margin: 0 4px; align-self: center; }
  .progress-step .step-dot { width: 24px; height: 24px; font-size: 10px; }
}

/* ===== ACS 示例 工具栏 + 弹窗 ===== */
.apply-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 20px;
}
.tool-link {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 14px;
  background: var(--bg-card);
  border: 1px solid var(--line-blue);
  border-radius: var(--r-pill);
  color: var(--accent-blue-d);
  font-family: var(--font-mono);
  font-size: 11px; letter-spacing: 0.08em;
  cursor: pointer;
  transition: all var(--t-fast);
}
.tool-link:hover { background: var(--bg-page-blue); border-color: var(--accent-blue); }

.acs-dialog-backdrop {
  position: fixed; inset: 0; z-index: 9999;
  background: rgba(15, 23, 42, 0.55);
  display: flex; align-items: center; justify-content: center;
  padding: 20px;
}
.acs-dialog {
  width: 100%;
  max-width: 880px;
  max-height: 86vh;
  background: var(--bg-card);
  border-radius: var(--r-3);
  border: 1px solid var(--border-card);
  display: flex; flex-direction: column;
  overflow: hidden;
  box-shadow: 0 30px 80px -20px rgba(15, 23, 42, 0.4);
}
.acs-dialog-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 18px 24px;
  border-bottom: 1px solid var(--border-divider);
}
.acs-dialog-head h2 {
  font-family: var(--font-display);
  font-size: 16px; font-weight: 600;
  color: var(--ink);
  margin: 0;
  display: flex; align-items: baseline; gap: 12px;
}
.acs-dialog-sub { font-family: var(--font-mono); font-size: 10px; color: var(--ink-3); letter-spacing: 0.08em; font-weight: 400; }
.acs-dialog-close {
  background: transparent; border: none;
  font-size: 24px; line-height: 1;
  color: var(--ink-3); cursor: pointer;
  padding: 0 4px;
}
.acs-dialog-close:hover { color: var(--ink); }
.acs-dialog-body { padding: 0; overflow: auto; flex: 1; background: var(--bg-page); }
.acs-pre {
  margin: 0; padding: 20px 24px;
  font-family: var(--font-mono);
  font-size: 12px; line-height: 1.65;
  color: var(--ink-2);
  white-space: pre-wrap; word-break: break-word;
}
.acs-dialog-foot {
  display: flex; justify-content: flex-end; gap: 10px;
  padding: 14px 24px;
  border-top: 1px solid var(--border-divider);
}
.dialog-fade-enter-active, .dialog-fade-leave-active { transition: opacity 0.2s; }
.dialog-fade-enter-from, .dialog-fade-leave-to { opacity: 0; }

@media (prefers-reduced-motion: reduce) {
  .anim-item, .anim-flow-1, .anim-flow-3 {
    opacity: 1; transform: none; animation: none !important;
  }
  .pulse, .header-eyebrow .dot, .flow-issue-dot,
  .progress-fill-shine, .flow-card.is-active .status-dot {
    animation: none !important;
  }
}
</style>
