<template>
  <div class="home" @wheel="onWheel">
    <!-- 背景层 -->
    <div class="home-bg" aria-hidden="true"></div>
    <div class="home-mesh" aria-hidden="true"></div>
    <div class="home-grain" aria-hidden="true"></div>

    <div
      class="pages-track"
      :class="{ animating: isAnimating }"
      :style="{ transform: `translateY(-${currentPage * 100}%)` }"
    >

      <!-- ============================================
           Page 1 — HERO / 封面 (优化版)
      ============================================= -->
      <section class="page page-hero">
        <div class="hero">
          <div class="hero-left">
            <!-- 刊头:品牌 + 期号 -->
            <header class="masthead">
              <div class="mast-left">
                <div class="renta-card" role="img" aria-label="RenTA — Agent Marketplace">
                  <img class="renta-logo" src="/renta-logo-mark.png" alt="RenTA — Agent Marketplace" />
                </div>
              </div>
            </header>

            <!-- 大标题:方案 D · 描边空心(wireframe 风格) -->
            <div class="title-frame">
              <h1 class="hero-title">
                <span class="title-fragment">IoA<em class="cn">原生智能体</em></span>
                <span class="title-ai">交易平台</span>
              </h1>
            </div>
            <p class="title-caption">
              <span class="caption-mark"></span>
              新一代智能体互联网产业界的<em>「闲鱼」</em>
            </p>

            <p class="hero-deck">
              你的Agent闲置了？<br>
              一键赚点零花钱
            </p>

            <div class="hero-actions">
              <router-link to="/square" class="hero-cta">
                <span>进入广场</span>
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
              </router-link>
              <router-link to="/chat" class="hero-cta-ghost">
                开始对话 <span class="ghost-arrow">→</span>
              </router-link>
              <router-link to="/agent-apply" class="hero-cta-ghost">
                上传智能体 <span class="ghost-arrow">→</span>
              </router-link>
            </div>

            <div class="mobile-home-only mobile-signal-board" aria-label="实时智能体信号">
              <div class="mobile-signal-head">
                <span class="mobile-signal-live"><i></i> Live network</span>
                <span class="mobile-signal-count">128 nodes</span>
              </div>
              <div class="mobile-signal-list">
                <div v-for="agent in squareAgents.slice(0, 3)" :key="`mobile-signal-${agent.id}`" class="mobile-signal-row">
                  <span class="mobile-signal-avatar" :style="{ background: agent.gradient }">{{ agent.name.slice(0, 1) }}</span>
                  <span class="mobile-signal-meta">
                    <strong>{{ agent.name }}</strong>
                    <small>{{ agent.status === 'calling' ? '正在响应请求' : '等待调用' }}</small>
                  </span>
                  <span class="mobile-signal-ping">{{ agent.status === 'calling' ? 'LIVE' : 'READY' }}</span>
                </div>
              </div>
              <span class="mobile-signal-beam" aria-hidden="true"></span>
            </div>



            <div class="hero-strip">
              <div class="strip-pill">
                <span class="strip-pulse"></span>
                <span class="strip-pill-k">128 智能体正在运行</span>
              </div>
              <div class="strip-stat">
                <span class="strip-v">2,847</span>
                <span class="strip-k">今日调用</span>
              </div>
              <div class="strip-stat">
                <span class="strip-v">98%</span>
                <span class="strip-k">可用率</span>
              </div>
              <div class="strip-stat">
                <span class="strip-v">24h</span>
                <span class="strip-k">在线服务</span>
              </div>
            </div>
          </div>

          <!-- 右侧:chat 预览 + 浮动卡 -->
          <div class="hero-right">
            <div class="chat-preview">
              <div class="cp-head">
                <div class="cp-avatar">
                  <span class="cp-mark">A</span>
                  <span class="cp-pulse"></span>
                </div>
                <div class="cp-meta">
                  <div class="cp-name">My Agent</div>
                  <div class="cp-row">
                    <span class="cp-status"><span class="cp-dot"></span>已出租</span>
                  </div>
                </div>
                <span class="cp-badge">你的智能体正在工作...</span>
              </div>

              <div class="cp-body">


                <div class="cp-msg cp-msg-bot">
                  <div class="cp-bubble">
                    <p>帮我写一段产品介绍文案,要有画面感。</p>
                  </div>
                </div>
                <div class="cp-msg cp-msg-user">
                  <div class="cp-bubble">
                    <p>好的,我先勾勒一个开场镜头 —</p>
                    <p>晨光透过百叶窗,落在那本翻开的笔记本上,墨迹尚未干透。</p>
                    <p>这便是你的故事开始的地方。</p>
                    <span class="cp-typing"><span></span><span></span><span></span></span>
                  </div>
                </div>
              </div>

              <div class="cp-foot">
                <div class="cp-input-mock">
                  <span class="cp-placeholder">输入消息…</span>
                  <div class="cp-tools">
                    <span class="cp-tool">联网</span>
                    <span class="cp-tool">模型</span>
                    <span class="cp-send">⏎</span>
                  </div>
                </div>
              </div>

              <div
                v-for="(card, idx) in floatCards"
                :key="card.name + idx"
                class="float-card"
                :class="card.pos"
                :style="{ '--d': card.delay }"
              >
                <div class="fc-icon" :style="{ background: card.gradient }" v-html="FLOAT_ICONS[card.icon]" />
                <div class="fc-text">
                  <span class="fc-title">{{ card.name }}</span>
                  <span class="fc-status">
                    <span v-if="card.live" class="fc-dot"></span>{{ card.status }}
                  </span>
                </div>
              </div>
            </div>

            <div class="hero-right-deco">
              <span class="deco-tag">A working journal of RenTA</span>
            </div>
          </div>
        </div>

        <div class="scroll-hint" aria-hidden="true">
          <span>向下滚动</span>
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
        </div>
      </section>

      <!-- ============================================
           Page 2 — Quick Start (等距立体)
           ⚠️ 此区块完全照搬参考文件,流程图不动
      ============================================= -->
      <section class="page page-quickstart">
        <div class="quickstart-iso">
          <div class="section-header iso-header">
            <span class="page-issue">运转逻辑 · How It Works</span>
            <h2 class="section-title">平台<em>如何运转</em></h2>
            <p class="section-desc">注册、上架、调用、分润 — 五步贯穿智能体的完整旅程。</p>
          </div>

          <div class="quickstart-body desktop-story">
            <div class="quickstart-chart-col">
              <div class="iso-viewport">
                <div class="iso-stage">
                  <div class="iso-grid" aria-hidden="true"></div>

                  <svg class="iso-arrows" viewBox="0 0 960 520" fill="none" aria-hidden="true">
                    <defs>
                      <marker
                        id="arrowHead"
                        :markerWidth="ARROW_HEAD_LEN + 2"
                        :markerHeight="ARROW_HEAD_LEN + 4"
                        refX="0"
                        :refY="(ARROW_HEAD_LEN + 4) / 2"
                        orient="auto"
                        markerUnits="userSpaceOnUse"
                      >
                        <path :d="`M0,0 L${ARROW_HEAD_LEN},${(ARROW_HEAD_LEN + 4) / 2} L0,${ARROW_HEAD_LEN + 4} Z`" fill="#3b82f6" />
                      </marker>
                    </defs>
                    <g v-for="(arrow, i) in isoArrows" :key="i">
                      <path
                        class="iso-path-shadow"
                        :d="arrow.shadow"
                        :stroke-width="ARROW_STROKE - 2"
                        stroke-linecap="butt"
                      />
                      <path
                        class="iso-path"
                        :d="arrow.main"
                        :stroke-width="ARROW_STROKE"
                        stroke-linecap="butt"
                        marker-end="url(#arrowHead)"
                      />
                    </g>
                  </svg>

                  <div
                    v-for="(s, i) in steps"
                    :key="i"
                    class="iso-node"
                    :class="'iso-node-' + (i + 1)"
                    :style="{ left: s.x + '%', top: s.y + '%' }"
                  >
                    <div class="iso-pedestal">
                      <span class="iso-pedestal-num">0{{ i + 1 }}</span>
                      <div class="iso-platform" :class="{ 'is-image': s.image }">
                        <div v-if="s.image" class="iso-icon-billboard">
                          <img
                            :src="s.image"
                            :alt="s.title"
                            class="iso-icon-img"
                            :style="getIconTiltStyle(s.iconTilt)"
                          />
                        </div>
                      </div>
                    </div>
                    <div class="iso-label">
                      <!---- <span class="iso-step-mark">// STEP 0{{ i + 1 }} / 05</span> -->
                      <h4 class="iso-label-title">{{ s.title }}</h4>
                      <p class="iso-label-desc">{{ s.desc }}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <aside class="quickstart-side" aria-label="平台流程介绍">
              <h3 class="side-title"><em>流程速览</em></h3>
              <p class="side-lead">
                从创建到获益，RenTA 将每个环节串联为清晰可感的协作链路。
              </p>
              <ul class="side-list">
                <li>注册账号，进入 Agent 广场</li>
                <li>上传 Agent，等待平台审核</li>
                <li>审核通过，上架供用户租用</li>
                <li>按需调用，积分实时结算</li>
                <li>创作者按调用量获得回报</li>
              </ul>
              <p class="side-foot">
                无论使用还是创作，都能在这套流程中找到入口。
              </p>
            </aside>
          </div>

          <div class="mobile-home-only mobile-process-story">
            <div class="mobile-step-list">
              <article v-for="(step, index) in visibleMobileSteps" :key="`mobile-step-${step.title}`" class="mobile-step-row">
                <span class="mobile-step-num">0{{ index + 1 }}</span>
                <span class="mobile-step-icon"><img :src="step.image" :alt="step.title" /></span>
                <span class="mobile-step-copy">
                  <strong>{{ step.title }}</strong>
                  <small>{{ step.desc }}</small>
                </span>
                <span class="mobile-step-state">{{ index === 0 ? 'START' : 'NEXT' }}</span>
              </article>
            </div>
            <button class="mobile-expand-control" type="button" :aria-expanded="mobileStepsExpanded" @click="mobileStepsExpanded = !mobileStepsExpanded">
              <span>{{ mobileStepsExpanded ? '收起完整流程' : '展开后续 2 步' }}</span>
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" :class="{ rotated: mobileStepsExpanded }"><polyline points="6 9 12 15 18 9" /></svg>
            </button>
          </div>
        </div>
      </section>

      <!-- ============================================
           Page 3 — 实时广场
      ============================================= -->
      <section class="page page-square">
        <div class="quickstart-iso">
          <div class="section-header iso-header">
            <span class="page-issue">Agent 广场 · Live Square</span>
            <h2 class="section-title">智能体<em>实时广场</em></h2>
            <p class="section-desc">热门 Agent 实时在线 — 浏览、租用、即刻调用。</p>
          </div>

          <div class="quickstart-body desktop-story">
            <div class="quickstart-chart-col square-agents-col">
              <div class="sq-waterfall">
                <div
                  v-for="(col, colIdx) in waterfallColumns"
                  :key="colIdx"
                  class="sq-waterfall-col"
                  :class="colIdx === 1 ? 'is-up' : 'is-down'"
                >
                  <div class="sq-waterfall-track" :style="{ animationDuration: `${32 + colIdx * 4}s` }">
                    <div
                      v-for="setIdx in 2"
                      :key="setIdx"
                      class="sq-waterfall-set"
                      :aria-hidden="setIdx === 2 ? 'true' : undefined"
                    >
                      <article
                        v-for="a in col"
                        :key="`${setIdx}-${a.id}`"
                        class="sq-card sq-card--flow"
                        :class="{ 'is-calling': a.status === 'calling' }"
                      >
                        <header class="sq-card-head">
                          <div class="sq-card-id">
                            <div class="sq-card-avatar" :style="{ background: a.gradient }">
                              <span class="sq-card-initial">{{ a.name.slice(0, 1) }}</span>
                            </div>
                            <div class="sq-card-meta">
                              <div class="sq-card-name">{{ a.name }}</div>
                              <div class="sq-card-owner">by {{ a.owner }}</div>
                            </div>
                          </div>
                          <span class="sq-card-status" :class="a.status">
                            <span class="scs-dot"></span>
                            {{ a.status === 'calling' ? '调用中' : '在线' }}
                          </span>
                        </header>
                        <div class="sq-card-snippet"><code>{{ a.snippet }}</code></div>
                        <footer class="sq-card-foot">
                          <div class="sq-card-tags"><span class="sq-tag">{{ a.category }}</span></div>
                          <div class="sq-card-rating">
                            <span class="sq-star">★</span>
                            <span class="sq-rating num">{{ a.rating }}</span>
                            <span class="sq-calls num">{{ a.calls }} 次</span>
                          </div>
                        </footer>
                      </article>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <aside class="quickstart-side" aria-label="广场介绍">
              <h3 class="side-title"><em>广场速览</em></h3>
              <p class="side-lead">
                Agent 广场是 RenTA 的核心枢纽 — 所有通过审核的智能体在此汇聚，等待被发现与调用。
              </p>
              <ul class="side-list">
                <li>按类别浏览，快速找到所需能力</li>
                <li>查看实时状态与调用热度</li>
                <li>一键租用，即刻开始对话</li>
                <li>创作者可在此展示与推广 Agent</li>
              </ul>
              <p class="side-foot">
                左侧为当前热门智能体预览，完整列表请进入广场。
              </p>
              <router-link to="/square" class="square-enter-btn">
                <span>进入完整广场</span>
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
              </router-link>
            </aside>
          </div>

          <div class="mobile-home-only mobile-agent-story">
            <div class="mobile-agent-list">
              <article v-for="agent in visibleMobileAgents" :key="`mobile-agent-${agent.id}`" class="mobile-agent-card">
                <header>
                  <span class="mobile-agent-avatar" :style="{ background: agent.gradient }">{{ agent.name.slice(0, 1) }}</span>
                  <span class="mobile-agent-id">
                    <strong>{{ agent.name }}</strong>
                    <small>{{ agent.owner }}</small>
                  </span>
                  <span class="mobile-agent-status" :class="agent.status">{{ agent.status === 'calling' ? '调用中' : '在线' }}</span>
                </header>
                <code>{{ agent.snippet }}</code>
                <footer><span>{{ agent.category }}</span><span>★ {{ agent.rating }} · {{ agent.calls }} 次</span></footer>
              </article>
            </div>
            <div class="mobile-story-actions">
              <button class="mobile-expand-control" type="button" :aria-expanded="mobileAgentsExpanded" @click="mobileAgentsExpanded = !mobileAgentsExpanded">
                <span>{{ mobileAgentsExpanded ? '收起精选' : '再看 3 个' }}</span>
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" :class="{ rotated: mobileAgentsExpanded }"><polyline points="6 9 12 15 18 9" /></svg>
              </button>
              <router-link to="/square" class="mobile-primary-link">进入完整广场 <span>→</span></router-link>
            </div>
          </div>
        </div>
      </section>

      <!-- ============================================
           Page 4 — 上传智能体（框架）
      ============================================= -->
      <section class="page page-upload">
        <div class="quickstart-iso">
          <div class="section-header iso-header">
            <span class="page-issue">创作者 · Creator Hub</span>
            <h2 class="section-title">上传你的<em> Agent</em></h2>
            <p class="section-desc">配置能力、提交审核、上架广场 — 五步发布属于你的智能体。</p>
          </div>

          <div class="quickstart-body desktop-story">
            <div class="quickstart-chart-col upload-visual-col">
              <div
                class="upload-assembly"
                :class="{ 'is-active': currentPage === 3 }"
                :key="uploadAnimCycle"
                aria-label="智能体分层组装动画"
              >
                <div class="asm-orbit-stage">
                  <div class="asm-star-ring" aria-hidden="true">
                    <div class="asm-ring asm-ring--outer"></div>
                    <div class="asm-ring asm-ring--mid"></div>
                    <div class="asm-ring asm-ring--inner"></div>
                    <div class="asm-ring-sweep"></div>
                    <div class="asm-ring-sweep asm-ring-sweep--reverse"></div>
                    <span
                      v-for="n in 12"
                      :key="n"
                      class="asm-spark"
                      :style="{
                        '--spark-angle': `${(n - 1) * 30}deg`,
                        '--spark-delay': `${((n - 1) * 0.22).toFixed(2)}s`
                      }"
                    ></span>
                  </div>

                  <div class="asm-center">
                    <div class="asm-card-shell">
                      <div class="asm-glow" aria-hidden="true"></div>

                      <div class="asm-layer asm-layer--icon">
                        <div class="asm-layer-inner">
                          <span class="asm-layer-tag">ICON</span>
                          <div class="asm-layer-body asm-layer-body--head">
                            <div class="asm-avatar" :style="{ background: uploadPreviewAgent.gradient }">
                              <span>{{ uploadPreviewAgent.name.slice(0, 1) }}</span>
                            </div>
                            <div class="asm-head-meta">
                              <strong>{{ uploadPreviewAgent.name }}</strong>
                              <span>{{ uploadPreviewAgent.owner }}</span>
                            </div>
                          </div>
                        </div>
                        <div class="asm-layer-legend">
                          <span class="asm-legend-idx">05</span>
                          <span class="asm-legend-text">图标与名称标识</span>
                        </div>
                      </div>

                      <div class="asm-layer asm-layer--prompt">
                        <div class="asm-layer-inner">
                          <span class="asm-layer-tag">PROMPT</span>
                          <div class="asm-layer-body">
                            <p class="asm-prompt-text">{{ uploadPreviewAgent.prompt }}</p>
                          </div>
                        </div>
                        <div class="asm-layer-legend">
                          <span class="asm-legend-idx">01</span>
                          <span class="asm-legend-text">Prompt 能力描述</span>
                        </div>
                      </div>

                      <div class="asm-layer asm-layer--skill">
                        <div class="asm-layer-inner">
                          <span class="asm-layer-tag">SKILL</span>
                          <div class="asm-layer-body">
                            <div class="asm-skill-tags">
                              <span v-for="s in uploadPreviewAgent.skills" :key="s" class="asm-skill-chip">{{ s }}</span>
                            </div>
                          </div>
                        </div>
                        <div class="asm-layer-legend">
                          <span class="asm-legend-idx">02</span>
                          <span class="asm-legend-text">挂载 Skill 能力包</span>
                        </div>
                      </div>

                      <div class="asm-layer asm-layer--api">
                        <div class="asm-layer-inner">
                          <span class="asm-layer-tag">API</span>
                          <div class="asm-layer-body">
                            <code class="asm-api-line">{{ uploadPreviewAgent.api }}</code>
                          </div>
                        </div>
                        <div class="asm-layer-legend">
                          <span class="asm-legend-idx">03</span>
                          <span class="asm-legend-text">API 端点配置</span>
                        </div>
                      </div>

                      <div class="asm-layer asm-layer--pricing">
                        <div class="asm-layer-inner">
                          <span class="asm-layer-tag">PRICING</span>
                          <div class="asm-layer-body asm-layer-body--foot">
                            <span class="asm-price">{{ uploadPreviewAgent.price }}</span>
                            <span class="asm-trial">{{ uploadPreviewAgent.trial }}</span>
                          </div>
                        </div>
                        <div class="asm-layer-legend">
                          <span class="asm-legend-idx">04</span>
                          <span class="asm-legend-text">定价与试用策略</span>
                        </div>
                      </div>
                    </div>

                    <div class="asm-ready-badge" aria-hidden="true">
                      <span class="asm-ready-dot"></span>
                      已就绪
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <aside class="quickstart-side" aria-label="上传智能体介绍">
              <h3 class="side-title"><em>发布指南</em></h3>
              <p class="side-lead">
                任何人都可以将自研 Agent 发布到 RenTA。填写能力说明与接口配置，通过审核后即可在广场被用户发现与租用。
              </p>
              <ul class="side-list">
                <li>描述 Agent 能力与适用场景</li>
                <li>挂载 Skill 扩展能力包</li>
                <li>配置 API 端点与调用参数</li>
                <li>设定定价与积分策略</li>
                <li>提交审核，通过后自动上架</li>
              </ul>
              <router-link to="/agent-apply" class="square-enter-btn">
                <span>开始上传智能体</span>
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
              </router-link>
            </aside>
          </div>

          <div class="mobile-home-only mobile-builder-story">
            <div class="mobile-builder-stage" aria-label="智能体发布结构预览">
              <div class="mobile-builder-head">
                <span><i></i> Agent blueprint</span>
                <strong>READY</strong>
              </div>
              <div class="mobile-builder-layers">
                <div v-for="(layer, index) in mobileUploadLayers" :key="layer.label" class="mobile-builder-layer" :style="{ '--layer-index': index }">
                  <span class="mobile-builder-index">0{{ index + 1 }}</span>
                  <span class="mobile-builder-label">{{ layer.label }}</span>
                  <strong>{{ layer.value }}</strong>
                </div>
              </div>
            </div>
            <p class="mobile-builder-copy">把能力说明、Skill、API 与定价组合成可验证、可租用的 Agent 服务。</p>
            <router-link to="/agent-apply" class="mobile-primary-link mobile-builder-link">开始上传智能体 <span>→</span></router-link>
          </div>
        </div>
      </section>
    </div>

    <nav class="page-dots" aria-label="页面导航">
      <button
        v-for="(p, i) in pageLabels"
        :key="i"
        type="button"
        class="dot"
        :class="{ active: currentPage === i }"
        :aria-label="p.label"
        @click="goToPage(i)"
      >
        <span class="dot-num">0{{ i + 1 }}</span>
        <span class="dot-name">{{ p.label }}</span>
      </button>
    </nav>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

/* ===== 等距立体图标倾角(参考文件原样) ===== */
const ICON_TILT_DEFAULT = {
  size: 76,
  rotate: 0,
  skewX: 0,
  skewY: 0,
  scaleX: 1,
  scaleY: 1,
  translateX: 0,
  translateY: 0
}

function getIconTiltStyle(overrides = {}) {
  const t = { ...ICON_TILT_DEFAULT, ...overrides }
  return {
    width: `${t.size}px`,
    height: `${t.size}px`,
    transform: [
      `translate(${t.translateX}px, ${t.translateY}px)`,
      `rotate(${t.rotate}deg)`,
      `skewX(${t.skewX}deg)`,
      `skewY(${t.skewY}deg)`,
      `scale(${t.scaleX}, ${t.scaleY})`
    ].join(' ')
  }
}

/* ===== 流程图 5 步(参考文件原样) ===== */
const steps = [
  { title: '注册账号',         desc: '创建平台个人账户',       x: 15, y: 15, image: '/icons/1.png', iconTilt: {} },
  { title: 'Agent上传审批',    desc: '提交 Agent 等待审核',     x: 40, y: 15, image: '/icons/2.png', iconTilt: { scaleX: 1.5, scaleY: 1.5 } },
  { title: 'Agent上架',         desc: '审核通过后上架广场',     x: 65, y: 15, image: '/icons/3.png', iconTilt: { scaleX: 1.3, scaleY: 1.3 } },
  { title: '用户租用',         desc: '按需调用Agent获得服务',   x: 90, y: 15, image: '/icons/4.png', iconTilt: { scaleX: 1.5, scaleY: 1.5 } },
  { title: '上传者获利',       desc: '按找Agent调用情况获得积分', x: 65, y: 75, image: '/icons/5.png', iconTilt: {} }
]

const ISO_SVG_W = 960
const ISO_SVG_H = 520
const ARROW_INSET = 72
const ARROW_STROKE = 20
const ARROW_HEAD_LEN = 40

function pctToSvg(x, y) {
  return { x: (x / 100) * ISO_SVG_W, y: (y / 100) * ISO_SVG_H }
}

function buildArrowSegment(fromIdx, toIdx, options = {}) {
  const from = pctToSvg(steps[fromIdx].x, steps[fromIdx].y)
  const to = pctToSvg(steps[toIdx].x, steps[toIdx].y)
  const dx = to.x - from.x
  const dy = to.y - from.y
  const len = Math.hypot(dx, dy) || 1
  const ux = dx / len
  const uy = dy / len

  let sx, sy, ex, ey
  if (options.range) {
    const [tStart, tEnd] = options.range
    sx = from.x + dx * tStart
    sy = from.y + dy * tStart
    ex = from.x + dx * tEnd
    ey = from.y + dy * tEnd
  } else {
    const inset = Math.min(ARROW_INSET, len * 0.44)
    sx = from.x + ux * inset
    sy = from.y + uy * inset
    ex = to.x - ux * inset
    ey = to.y - uy * inset
  }

  const lx = ex - ux * ARROW_HEAD_LEN
  const ly = ey - uy * ARROW_HEAD_LEN
  const shadowDy = 6
  const fmt = (n) => Math.round(n * 10) / 10
  return {
    main: `M ${fmt(sx)} ${fmt(sy)} L ${fmt(lx)} ${fmt(ly)}`,
    shadow: `M ${fmt(sx)} ${fmt(sy + shadowDy)} L ${fmt(lx)} ${fmt(ly + shadowDy)}`
  }
}

// 1→2, 2→3, 3→4, 3→5(3→5 落在 3-5 线段的 60%~80% 区间,靠近 5 为节点 3 文字留空)
const isoArrows = [
  buildArrowSegment(0, 1),
  buildArrowSegment(1, 2),
  buildArrowSegment(2, 3),
  buildArrowSegment(2, 4, { range: [0.6, 0.8] })
]

/* ===== 实时广场 Mock ===== */
const squareAgents = [
  { id: 1, name: '代码Agent', owner: '@ren_dev',     category: '编程开发', status: 'calling', rating: 4.9, calls: 1284,
    snippet: 'def optimize_query(sql):\n    return query.plan()',
    gradient: 'linear-gradient(135deg, #3b82f6, #1d4ed8)' },
  { id: 2, name: '文案Agent', owner: '@copy_studio',  category: '内容创作', status: 'online',  rating: 4.8, calls: 892,
    snippet: '"让每一次文案,都成为读者心中的画面。"',
    gradient: 'linear-gradient(135deg, #d4906a, #b4761e)' },
  { id: 3, name: '数据Agent', owner: '@data_co',      category: '学术研究', status: 'online',  rating: 4.7, calls: 567,
    snippet: 'Q3 销售环比 ↑23.4% / 转化率 4.8% / ROI 3.2x',
    gradient: 'linear-gradient(135deg, #10b981, #047857)' },
  { id: 4, name: '翻译Agent', owner: '@lingo',        category: '办公效率', status: 'calling', rating: 4.9, calls: 2103,
    snippet: '"AI is reshaping the way we work."',
    gradient: 'linear-gradient(135deg, #8b5cf6, #6d28d9)' },
  { id: 5, name: '视觉Agent', owner: '@vision_lab',   category: '创意设计', status: 'online',  rating: 4.6, calls: 423,
    snippet: 'detect(人, 0.94) → region(12, 48, 240, 360)',
    gradient: 'linear-gradient(135deg, #ec4899, #be185d)' },
  { id: 6, name: '语音Agent', owner: '@voice_ai',     category: '休闲娱乐', status: 'online',  rating: 4.8, calls: 789,
    snippet: '00:02:14 / 普通话 / 准确率 98.2%',
    gradient: 'linear-gradient(135deg, #f59e0b, #d97706)' },
  { id: 7, name: '法律顾问', owner: '@legal_ai',     category: '办公效率', status: 'online',  rating: 4.7, calls: 356,
    snippet: 'contract.review(clause="责任限制") → risk: low',
    gradient: 'linear-gradient(135deg, #6366f1, #4338ca)' },
  { id: 8, name: '简历优化', owner: '@hr_lab',       category: '内容创作', status: 'calling', rating: 4.8, calls: 1120,
    snippet: 'STAR 法则重构项目经历 · 匹配度 92%',
    gradient: 'linear-gradient(135deg, #14b8a6, #0f766e)' },
  { id: 9, name: '数学解题', owner: '@math_co',      category: '学术研究', status: 'online',  rating: 4.9, calls: 2041,
    snippet: '∫ x²e^x dx = x²e^x - 2xe^x + 2e^x + C',
    gradient: 'linear-gradient(135deg, #0ea5e9, #0369a1)' },
  { id: 10, name: 'API 测试', owner: '@devops',      category: '编程开发', status: 'online',  rating: 4.6, calls: 445,
    snippet: 'POST /api/v1/agents → 200 OK (42ms)',
    gradient: 'linear-gradient(135deg, #64748b, #334155)' },
  { id: 11, name: '情感陪伴', owner: '@care_bot',    category: '休闲娱乐', status: 'calling', rating: 4.5, calls: 1678,
    snippet: '「今天过得怎么样？我在这里听你说。」',
    gradient: 'linear-gradient(135deg, #f472b6, #db2777)' },
  { id: 12, name: 'SEO 优化', owner: '@growth',      category: '内容创作', status: 'online',  rating: 4.7, calls: 623,
    snippet: 'keywords: 智能体, 转化率, 长尾词覆盖 87%',
    gradient: 'linear-gradient(135deg, #a855f7, #7e22ce)' },
  { id: 13, name: '绘本创作', owner: '@story_maker', category: '创意设计', status: 'online',  rating: 4.8, calls: 312,
    snippet: '从前有一只小狐狸,住在蓝色森林的边缘…',
    gradient: 'linear-gradient(135deg, #fb923c, #ea580c)' },
  { id: 14, name: '代码审查', owner: '@reviewer',    category: '编程开发', status: 'online',  rating: 4.9, calls: 956,
    snippet: '⚠ L42: 潜在空指针 · 建议 optional chaining',
    gradient: 'linear-gradient(135deg, #22c55e, #15803d)' },
  { id: 15, name: '会议纪要', owner: '@meet_ai',     category: '办公效率', status: 'calling', rating: 4.7, calls: 1388,
    snippet: 'Action: Q2 上线 · Owner: @pm · Due: 6/15',
    gradient: 'linear-gradient(135deg, #78716c, #44403c)' }
]

/* 瀑布流三列：按索引取模分配，每列 5 张 */
const waterfallColumns = computed(() => {
  const cols = [[], [], []]
  squareAgents.forEach((agent, i) => {
    cols[i % 3].push(agent)
  })
  return cols
})

/* ===== 浮动卡 ===== */
const FLOAT_ICONS = {
  code:  '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>',
  star:  '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>',
  chart: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
  globe: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
  eye:   '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>'
}
const floatCards = [
  { name: '代码Agent', status: '正在重构',   gradient: 'linear-gradient(135deg, #3b82f6, #1d4ed8)', icon: 'code',  live: true, pos: 'fc-1', delay: '0s'   },
  { name: '文案Agent', status: '正在创作',   gradient: 'linear-gradient(135deg, #d4906a, #b4761e)', icon: 'star',  live: true, pos: 'fc-2', delay: '0.6s' },
  { name: '数据Agent', status: '实时分析中', gradient: 'linear-gradient(135deg, #10b981, #047857)', icon: 'chart', live: true, pos: 'fc-3', delay: '1.2s' },
  { name: '翻译Agent', status: '实时翻译中', gradient: 'linear-gradient(135deg, #8b5cf6, #6d28d9)', icon: 'globe', live: true, pos: 'fc-4', delay: '1.8s' },
  { name: '视觉Agent', status: '图像识别中', gradient: 'linear-gradient(135deg, #ec4899, #be185d)', icon: 'eye',   live: true, pos: 'fc-5', delay: '0.3s' }
]

/* ===== 上传页 · 分层组装预览 ===== */
const uploadPreviewAgent = {
  name: '我的写作助手',
  owner: '@creator',
  gradient: 'linear-gradient(135deg, #4a8db5, #2c6688)',
  prompt: 'System: 你是专业文案助手，擅长品牌叙事与短文案创作，语气简洁有力。',
  skills: ['品牌叙事', '短文案', 'SEO 优化'],
  api: 'POST /v1/agents/chat · Bearer sk-••••8f2a',
  price: '10 积分 / 次',
  trial: '免费试用 3 次'
}

const mobileUploadLayers = [
  { label: 'Identity', value: '名称与能力边界' },
  { label: 'Skill', value: '能力包与输入输出' },
  { label: 'Endpoint', value: 'API 与协议配置' },
  { label: 'Pricing', value: '定价与试用策略' }
]

const mobileStepsExpanded = ref(false)
const mobileAgentsExpanded = ref(false)
const visibleMobileSteps = computed(() => mobileStepsExpanded.value ? steps : steps.slice(0, 3))
const visibleMobileAgents = computed(() => mobileAgentsExpanded.value ? squareAgents.slice(0, 6) : squareAgents.slice(0, 3))

/* ===== 翻页 ===== */
const pageLabels = [{ label: '封面' }, { label: '流程' }, { label: '广场' }, { label: '上传' }]
const totalPages = 4
const currentPage = ref(0)
const isAnimating = ref(false)
const uploadAnimCycle = ref(0)

watch(currentPage, (p) => {
  if (p === 3) uploadAnimCycle.value++
})

const goToPage = (index) => {
  if (index < 0 || index >= totalPages || isAnimating.value || index === currentPage.value) return
  isAnimating.value = true
  currentPage.value = index
  setTimeout(() => { isAnimating.value = false }, 700)
}
const onWheel = (e) => {
  if (window.matchMedia('(max-width: 768px)').matches) return
  e.preventDefault()
  if (isAnimating.value) return
  if (e.deltaY > 40) goToPage(currentPage.value + 1)
  else if (e.deltaY < -40) goToPage(currentPage.value - 1)
}
const onKey = (e) => {
  if (window.matchMedia('(max-width: 768px)').matches) return
  if (e.key === 'ArrowDown' || e.key === 'PageDown') { e.preventDefault(); goToPage(currentPage.value + 1) }
  if (e.key === 'ArrowUp' || e.key === 'PageUp')     { e.preventDefault(); goToPage(currentPage.value - 1) }
}
onMounted(() => { window.addEventListener('keydown', onKey) })
onUnmounted(() => { window.removeEventListener('keydown', onKey) })
</script>

<style scoped>
/* ============================================
   背景
============================================ */
.home { position: relative; height: 100vh; overflow: hidden; }
.home-bg {
  position: fixed; inset: 0; z-index: 0;
  background: url('/background.png') center / cover no-repeat;
}
.home-mesh {
  position: fixed; inset: 0; z-index: 1;
  background:
    radial-gradient(ellipse 700px 500px at 20% 30%, rgba(74, 141, 181, 0.10) 0%, transparent 60%),
    radial-gradient(ellipse 600px 500px at 80% 70%, rgba(30, 58, 76, 0.06) 0%, transparent 60%);
  animation: meshDrift 24s ease-in-out infinite alternate;
  pointer-events: none;
}
@keyframes meshDrift {
  0%   { transform: translate(0, 0) scale(1); }
  100% { transform: translate(-3%, 2%) scale(1.05); }
}
.home-grain {
  position: fixed; inset: 0; z-index: 2;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.5'/%3E%3C/svg%3E");
  opacity: 0.04;
  pointer-events: none;
  mix-blend-mode: multiply;
}

.pages-track {
  position: relative; z-index: 3;
  height: 100%;
  transition: transform 0.7s cubic-bezier(0.4, 0, 0.2, 1);
}
.pages-track.animating { pointer-events: none; }

.page {
  height: 100vh;
  display: flex; align-items: flex-start;
  position: relative;
  padding: 0 48px;
  padding-top: 60px;
}

/* ============================================
   HERO (优化版)
============================================ */
.hero {
  display: grid;
  grid-template-columns: 1.3fr 0.7fr;
  gap: 60px;
  align-items: center;
  width: 100%;
  max-width: 1340px;
  padding: 0px ;
  margin-left: 120px;
}

.hero-left { max-width: 680px; }

/* 刊头 */
.masthead {
  display: flex; justify-content: space-between; align-items: center;
  padding-bottom: 20px;
  margin-bottom: 32px;
  border-bottom: 1px solid var(--ink);
  gap: 20px;
}
.mast-left { display: flex; align-items: center; gap: 16px; }

/* RenTA —— 纯文字刊头
   用 <img> 引用 renta-logo.png（白底深蓝 RenTA 字 + 一道弧线）
   mix-blend-mode: multiply 把白底抠掉，让 logo 直接落在页面 #EAF3FB 上
   蓝色 logo 主色 multiply 后会略深，但页面背景本身很浅，整体观感仍然统一 */
.renta-card {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 0;
  background: transparent;
  border: none;
  border-radius: 0;
  opacity: 0;
  animation: rentaIn 0.6s var(--ease-out) 0.1s forwards;
  transition: opacity var(--t-fast) var(--ease-out);
}
.renta-logo {
  /* 关键：multiply —— 白色像素 (#FFFFFF) × 任何色 = 该色 → 白底变透明
     蓝色像素 × 浅蓝背景 → 略深一点的蓝，跟页面自然融合 */
  display: block;
  height: 88px;                                 /* 主视觉锚点，跟 .title-fragment 字号接近 */
  width: auto;
  mix-blend-mode: normal;
  /* multiply 会让 logo 整体略变暗，luminosity 反向提亮一点，找回原色感 */
  /* 但 luminosity 在浅背景上对深色 logo 反而会洗白，先关掉，单 multiply 已够用 */
}
.renta-tagline {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 500;
  color: var(--accent-blue);                    /* 天空蓝主色，跟 .italic-emph 同款 */
  letter-spacing: 0.18em;
  text-transform: uppercase;
  margin: 0;
}

@keyframes rentaIn {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0);   }
}

@media (prefers-reduced-motion: reduce) {
  .renta-card { animation: none !important; opacity: 1; }
}
.mast-right {
  display: flex; align-items: center; gap: 10px;
  font-family: var(--font-mono);
  font-size: 12px; letter-spacing: 0.18em; text-transform: uppercase;
  color: var(--ink-3);
}
.mast-issue { color: var(--ink-2); font-weight: 500; }
.mast-dot { color: var(--ink-4); }
.mast-edition { color: var(--ink-3); }

/* 标题:Logo-Mark 风格 — AI 作为深色色块,前后中文退到平等位置 */
.hero-title {
  margin: 0 0 40px;
  display: flex; align-items: center;
  flex-wrap: wrap;
  gap: 20px;
  line-height: 1;
}

.title-fragment {
  font-family: var(--font-display);               /* Plus Jakarta Sans */
  font-size: clamp(56px, 7vw, 92px);
  font-weight: 800;                              /* Plus Jakarta Sans 极粗 */
  font-style: italic;                            /* Plus Jakarta Sans 支持 italic */
  color: var(--ink);                            /* 深海军 #0E2A47 */
  letter-spacing: -0.03em;                       /* sans italic 字距收紧 */
  line-height: 1;
  display: inline-flex;
  align-items: baseline;
}

/* 中文"原生智能体"也用 Plus Jakarta Sans，中文回退到 Noto Sans SC 黑体
   风格统一：无衬线斜体 */
.title-fragment .cn {
  font-family: var(--font-display);               /* Plus Jakarta Sans，中文 → Noto Sans SC */
  font-weight: 800;                              /* 跟 IoA 同字重，保持视觉重量 */
  font-style: normal;                            /* 不斜，正体 */
  color: var(--ink);                            /* 跟 IoA 同色深海军 */
  letter-spacing: 0.01em;
  margin-left: 0.28em;
  font-size: 0.82em;
  align-self: baseline;
}

.title-ai {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.08em 0.22em 0.12em;
  background: var(--ink);
  color: var(--ink-inverse);
  font-family: var(--font-display);
  font-size: clamp(36px, 4.6vw, 56px);          /* 比 .title-fragment 整体小一档，让"IoA 原生智能体"当主角 */
  font-weight: 800;
  letter-spacing: -0.04em;
  line-height: 1;
  border-radius: 8px;
}

.title-caption {
  display: flex;
  align-items: center;
  gap: 12px;
  font-family: var(--font-editorial);             /* 衬线 italic —— 杂志导读引文语气，跟 .italic-emph 同款 */
  font-style: italic;
  font-size: 19px;
  font-weight: 400;
  letter-spacing: 0.01em;                        /* italic 衬线不需要大字距 */
  color: var(--ink-2);
  margin: -20px 0 32px;
}

.title-caption em {
  font-family: var(--font-editorial);
  font-style: italic;
  font-weight: 400;
  color: var(--accent-blue);                     /* 蓝色 italic —— 项目最强装饰语言 .italic-emph */
  text-transform: none;
  letter-spacing: 0;
  font-size: 1.05em;                            /* 微大一点，呼应"重点词"地位 */
}

.caption-mark {
  width: 32px;
  height: 2px;
  background: var(--ink-3);
  flex-shrink: 0;
}

/* 副标题 */
.hero-deck {
  font-size: 19px; line-height: 1.6;
  color: var(--ink-2);                           /* #1E3F60，提亮后跟主标题同色系，不再灰掉 */
  margin: 0 0 32px;
  max-width: 48ch;
}

/* 行动 */
.hero-actions { display: flex; align-items: center; gap: 18px; flex-wrap: wrap; margin-bottom: 16px; }
.hero-cta {
  display: inline-flex; align-items: center; gap: 12px;
  padding: 16px 28px;
  background: var(--ink);
  color: var(--ink-inverse);
  border: 1px solid var(--ink);
  border-radius: var(--r-3);
  font-size: 16px; font-weight: 500;
  text-decoration: none;
  transition: all var(--t-fast);
  box-shadow: 0 1px 0 rgba(20,22,26,0.06);
}
.hero-cta:hover {
  background: var(--ink-2);
  transform: translateY(-1px);
  box-shadow: 0 6px 18px -4px rgba(20,22,26,0.25);
}
.hero-cta-ghost {
  display: inline-flex; align-items: center; gap: 10px;
  padding: 16px 28px;
  background: var(--accent-blue-bg);             /* 浅蓝软底，跟 .cp-badge 同款 rgba(46,122,184,0.10) */
  color: var(--accent-blue-d);                  /* 深空蓝文字，跟底色同色系 */
  font-size: 16px; font-weight: 500;
  text-decoration: none;
  border: 1px solid var(--accent-blue-border);  /* 浅蓝软边，跟底色呼应 */
  border-radius: var(--r-3);                    /* 跟主 CTA 一样的 12px 圆角 */
  transition:
    background var(--t-fast),
    color var(--t-fast),
    border-color var(--t-fast),
    box-shadow var(--t-fast),
    transform var(--t-fast);
}
.ghost-arrow { display: inline-block; transition: transform var(--t-fast); }
.hero-cta-ghost:hover {
  background: var(--accent-blue-border);        /* hover 加深底色 */
  color: var(--accent-blue-d);
  border-color: var(--accent-blue-d);
  transform: translateY(-1px);
  box-shadow: 0 6px 18px -4px rgba(46, 122, 184, 0.25);
}
.hero-cta-ghost:hover .ghost-arrow { transform: translateX(3px); }

/* 行动注脚 */
.hero-footnote {
  display: flex; align-items: center; gap: 10px;
  font-family: var(--font-mono);
  font-size: 12px; letter-spacing: 0.06em;
  color: var(--ink-3);
  margin-bottom: 42px;
}
.fn-dot {
  width: 6px; height: 6px;
  background: var(--signal-positive);
  border-radius: 50%;
}

/* 实时数据条 */
.hero-strip {
  display: flex; align-items: center;
  gap: 20px;
  padding-top: 20px;
  border-top: 1px solid var(--line-blue);
  flex-wrap: wrap;
}
.strip-pill {
  display: inline-flex; align-items: center; gap: 10px;
  padding: 6px 12px;
  background: var(--bg-card-soft);
  border: 1px solid var(--line-blue);
  border-radius: var(--r-pill);
  font-family: var(--font-mono);
  font-size: 12px; letter-spacing: 0.06em;
  color: var(--ink-2);
  white-space: nowrap;
}
.strip-pulse {
  position: relative;
  width: 8px; height: 8px;
  flex-shrink: 0;
}
.strip-pulse::before, .strip-pulse::after {
  content: ''; position: absolute; inset: 0;
  background: var(--signal-positive);
  border-radius: 50%;
}
.strip-pulse::after { animation: pulseRing 1.8s ease-out infinite; }
@keyframes pulseRing {
  0%   { transform: scale(1); opacity: 0.6; }
  100% { transform: scale(2.4); opacity: 0; }
}
.strip-pill-k { color: var(--ink-2); }
.strip-stat { display: flex; flex-direction: column; gap: 1px; }
.strip-v {
  font-family: var(--font-editorial);
  font-size: 22px; font-style: italic; font-weight: 400;
  color: var(--ink);
  line-height: 1;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
}
.strip-k {
  font-family: var(--font-mono);
  font-size: 11px; font-weight: 500;
  letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--ink-3);
  margin-top: 3px;
  white-space: nowrap;
}

/* 右侧:chat 预览 */
.hero-right {
  position: relative;
  display: flex; flex-direction: column;
  align-items: flex-end;
  gap: 14px;
  margin-top: 200px;     /* 向下移动，越大越靠下 */
  margin-left: -60px;    /* 向左移动 */
}
.hero-right-deco {
  font-family: var(--font-editorial);
  font-style: italic;
  font-size: 14px;
  color: var(--ink-3);
}
.deco-tag { position: relative; padding-left: 32px; }
.deco-tag::before {
  content: '';
  position: absolute; left: 0; top: 50%;
  width: 24px; height: 1px;
  background: var(--ink-3);
}

.chat-preview {
  position: relative;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--r-3);
  padding: 22px;
  box-shadow:
    0 24px 80px -20px rgba(30, 58, 76, 0.28),
    0 4px 12px rgba(0,0,0,0.04);
  width: 100%;
  max-width: 500px;
  animation: chatEnter 0.8s 0.4s var(--ease-out) backwards;
}
@keyframes chatEnter {
  from { opacity: 0; transform: translateY(20px) scale(0.97); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}
.cp-head {
  display: flex; align-items: center; gap: 12px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-divider);
  margin-bottom: 16px;
}
.cp-avatar {
  position: relative;
  width: 40px; height: 40px;
  background: var(--ink);
  color: var(--ink-inverse);
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-family: var(--font-editorial);
  font-size: 20px; font-style: italic; font-weight: 400;
  flex-shrink: 0;
}
.cp-pulse {
  position: absolute; right: -2px; bottom: -2px;
  width: 12px; height: 12px;
  background: var(--signal-positive);
  border-radius: 50%;
  border: 2px solid var(--bg-card);
  animation: pulseDot 1.5s ease-in-out infinite;
}
@keyframes pulseDot { 0%,100% { transform: scale(1); opacity: 1; } 50% { transform: scale(0.7); opacity: 0.5; } }
.cp-meta { flex: 1; min-width: 0; }
.cp-name { font-family: var(--font-display); font-size: 15px; font-weight: 600; color: var(--ink); letter-spacing: -0.01em; }
.cp-row {
  display: flex; align-items: center; gap: 6px;
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--ink-3);
  margin-top: 2px;
}
.cp-status { display: flex; align-items: center; gap: 4px; }
.cp-dot { width: 5px; height: 5px; background: var(--signal-positive); border-radius: 50%; }
.cp-sep { color: var(--ink-4); }
.cp-model { color: var(--ink-2); }
.cp-badge {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.12em; text-transform: uppercase;
  padding: 3px 8px;
  background: var(--accent-blue-bg);
  color: var(--accent-blue-d);
  border-radius: var(--r-1);
  border: 1px solid var(--accent-blue-border);
}

.cp-body { display: flex; flex-direction: column; gap: 10px; margin-bottom: 16px; min-height: 160px; }
.cp-msg { display: flex; max-width: 90%; }
.cp-msg-user { align-self: flex-end; }
.cp-msg-bot { align-self: flex-start; }
.cp-bubble { padding: 10px 14px; font-size: 13px; line-height: 1.6; border-radius: 14px; }
/* 样式对调：位置不变（bot 在左、user 在右），但气泡颜色/字体样式互换
   bot 走原 user 的深色实心底白字，user 走原 bot 的浅蓝软底 italic 衬线 */
.cp-msg-user .cp-bubble {
  background: var(--bg-page-blue);
  color: var(--ink-2);
  border: 1px solid var(--line-blue);
  border-bottom-right-radius: 4px;
  font-family: var(--font-editorial);
  font-size: 14px;
  font-style: italic;
  line-height: 1.55;
}
.cp-msg-bot .cp-bubble {
  background: var(--ink);
  color: var(--ink-inverse);
  border-bottom-left-radius: 4px;
}
.cp-msg-user .cp-bubble p { margin: 0 0 4px; }
.cp-msg-user .cp-bubble p:last-child { margin-bottom: 0; }

.cp-typing { display: inline-flex; align-items: center; gap: 3px; margin-left: 6px; vertical-align: -2px; }
.cp-typing span {
  width: 4px; height: 4px;
  background: var(--accent-blue);
  border-radius: 50%;
  animation: typingBounce 1.2s infinite ease-in-out both;
}
.cp-typing span:nth-child(1) { animation-delay: -0.32s; }
.cp-typing span:nth-child(2) { animation-delay: -0.16s; }
@keyframes typingBounce { 0%,80%,100% { transform: scale(0); opacity: 0.4; } 40% { transform: scale(1); opacity: 1; } }

.cp-foot { padding-top: 12px; border-top: 1px solid var(--border-divider); }
.cp-input-mock {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px;
  background: var(--bg-card-soft);
  border: 1px solid var(--border-card);
  border-radius: var(--r-2);
}
.cp-placeholder { flex: 1; font-size: 12px; color: var(--ink-4); }
.cp-tools { display: flex; align-items: center; gap: 8px; }
.cp-tool {
  font-family: var(--font-mono);
  font-size: 10px;
  padding: 2px 6px;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--r-1);
  color: var(--ink-3);
  letter-spacing: 0.06em;
}
.cp-send {
  width: 24px; height: 24px;
  display: flex; align-items: center; justify-content: center;
  background: var(--ink);
  color: var(--ink-inverse);
  border-radius: var(--r-1);
  font-size: 11px; font-weight: 600;
}

/* 浮动卡 */
.float-card {
  position: absolute;
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px 8px 8px;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--r-pill);
  box-shadow: 0 10px 24px -6px rgba(0,0,0,0.12);
  animation: floatCard 5s ease-in-out infinite;
  animation-delay: var(--d, 0s);
  z-index: 4;
  white-space: nowrap;
}
@keyframes floatCard {
  0%, 100% { transform: translateY(0); }
  50%      { transform: translateY(-8px); }
}
.fc-icon { width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; border-radius: 50%; flex-shrink: 0; }
.fc-text { display: flex; flex-direction: column; gap: 0; line-height: 1.1; }
.fc-title { font-family: var(--font-display); font-size: 12px; font-weight: 600; color: var(--ink); }
.fc-status {
  font-family: var(--font-mono);
  font-size: 9px; letter-spacing: 0.08em;
  color: var(--ink-3);
  display: flex; align-items: center; gap: 4px;
}
.fc-dot { width: 5px; height: 5px; background: var(--signal-positive); border-radius: 50%; animation: pulseDot 1.4s ease-in-out infinite; }
.fc-1 { top: -12px;  left: -28px; }
.fc-2 { top: 32%;    right: -52px; }
.fc-3 { bottom: -8px; left: 24%; }
.fc-4 { top: 62%;    left: -56px; }
.fc-5 { top: -20px;  right: 18%; }

/* 滚动提示 */
.scroll-hint {
  position: absolute;
  bottom: 80px;
  left: 50%; transform: translateX(-50%);
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.18em; text-transform: uppercase;
  color: var(--ink-3);
  animation: hintBounce 2s ease-in-out infinite;
  z-index: 10;
}
@keyframes hintBounce { 0%,100% { transform: translateX(-50%) translateY(0); } 50% { transform: translateX(-50%) translateY(6px); } }

/* ============================================
   Page 2 — Quick Start (等距立体)
   ⚠️ 此区块完全照搬参考文件,不要改
============================================ */
.section-header { text-align: center; margin-bottom: 48px; margin-left: 80px;}
.section-title { font-size: 34px; font-weight: 600; color: var(--text-primary); margin: 0 0 14px; letter-spacing: -0.02em; }
.section-desc { font-size: 16px; color: var(--text-muted); margin: 0; }

/* Page 2 - Isometric Quick Start */
.page-quickstart {
  align-items: stretch;
  padding: 0;
}

.quickstart-iso {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 40px 24px 56px;
  margin-top: 40px;
  /* margin-left: 56px; */
}

.iso-header {
  margin-bottom: 18px;
  flex-shrink: 0;
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.iso-header .page-issue {
  align-self: flex-start;
}
.iso-header .section-title {
  font-family: var(--font-display);
  font-size: clamp(32px, 4.4vw, 52px);
  font-weight: 600;
  color: var(--ink);
  letter-spacing: -0.025em;
  line-height: 1.05;
  margin: 0;
}
.iso-header .section-title em {
  font-family: var(--font-editorial);
  font-style: italic;
  font-weight: 400;
  color: var(--accent-blue);
}
.iso-header .section-desc {
  font-size: 14px;
  color: var(--ink-3);
  margin: 0;
  max-width: 60ch;
  line-height: 1.6;
}

.quickstart-body {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(0, 6fr) minmax(0, 4fr);
  gap: 0;
  align-items: center;
  min-height: 0;
}

.quickstart-chart-col {
  min-width: 0;
  min-height: 0;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: -100px;
}

.quickstart-chart-col .iso-viewport {
  flex: 1;
  width: 100%;
}

.quickstart-chart-col .iso-stage {
  width: min(960px, 100%);
  height: min(600px, 54vh);
}

.quickstart-side {
  min-width: 0;
  height: 80%;
  align-self: stretch;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 0 0 0 16px;
  border-left: 1px solid rgba(20, 22, 26, 0.14);
  text-align: left;
  margin-right: 170px;
}

.side-title {
  font-family: var(--font-display);
  font-size: clamp(26px, 2.4vw, 34px);
  font-weight: 600;
  font-style: normal;
  color: var(--ink);
  margin: 0 0 22px;
  line-height: 1.2;
  letter-spacing: -0.02em;
}

.side-title em {
  font-family: var(--font-editorial);
  font-style: italic;
  font-weight: 400;
  color: var(--accent-blue);
}

.side-lead {
  font-family: var(--font-display);
  font-size: 17px;
  line-height: 1.75;
  color: var(--ink-2);
  margin: 0 0 28px;
  letter-spacing: 0.01em;
}

.side-list {
  margin: 0 0 28px;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.side-list li {
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 500;
  line-height: 1.55;
  color: var(--ink-3);
}

.side-list li::before {
  content: '— ';
  font-family: var(--font-editorial);
  font-style: italic;
  font-weight: 400;
  color: var(--ink-4);
}

.side-foot {
  font-family: var(--font-editorial);
  font-size: 16px;
  font-style: italic;
  line-height: 1.65;
  color: var(--ink-3);
  margin: 0;
}

.iso-viewport {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  perspective: 1400px;
  perspective-origin: 50% 42%;
  transform-style: preserve-3d;
  min-height: 0;
  overflow: visible;
  margin-top: -20px;
}

/* 核心:3D 旋转制造斜向俯视(影响整块场景:格子/箭头/台座/文字一起转) */
.iso-stage {
  position: relative;
  width: min(960px, 58vw);
  height: min(600px, 58vh);
  --iso-rotate-x: 50deg;
  --iso-rotate-z: -45deg;
  --iso-rotate-x-inv: -50deg;
  --iso-rotate-z-inv: 45deg;
  transform: rotateX(var(--iso-rotate-x)) rotateZ(var(--iso-rotate-z));
  transform-style: preserve-3d;
  transition: transform 0.4s ease;
}

.iso-grid {
  position: absolute;
  inset: -8%;
  background-color: transparent;
  background-image:
    linear-gradient(rgba(120, 150, 185, 0.22) 1px, transparent 1px),
    linear-gradient(90deg, rgba(120, 150, 185, 0.22) 1px, transparent 1px);
  background-size: 40px 40px;
  border-radius: 12px;
  mask-image: radial-gradient(ellipse 85% 75% at 50% 50%, #000 30%, transparent 100%);
  -webkit-mask-image: radial-gradient(ellipse 85% 75% at 50% 50%, #000 30%, transparent 100%);
}

.iso-arrows {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 1;
  pointer-events: none;
}

.iso-path {
  stroke: #3b82f6;
  filter: drop-shadow(0 5px 4px rgba(37, 99, 235, 0.35));
}

.iso-path-shadow {
  stroke: rgba(37, 99, 235, 0.22);
}

.iso-node {
  position: absolute;
  z-index: 2;
  transform: translate(-50%, -50%);
  transform-style: preserve-3d;
}

.iso-pedestal {
  position: relative;
  width: 72px;
  height: 48px;
  margin: 0 auto;
  transform-style: preserve-3d;
}

.iso-platform {
  position: relative;
  z-index: 2;
  width: 64px;
  height: 64px;
  margin: 0 auto;
  background: linear-gradient(145deg, #b8dcff 0%, #6eb3f7 45%, #4a9fe8 100%);
  border-radius: 14px;
  transform: rotate(45deg) scaleY(0.58);
  box-shadow: 0 10px 0 #3580c9, 0 16px 24px rgba(53, 128, 201, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
}

/* PNG 立体图标:隐藏蓝色台座,倾角由 iconTilt 控制 */
.iso-platform.is-image {
  width: auto;
  height: auto;
  background: transparent;
  border-radius: 0;
  transform: none;
  box-shadow: none;
  transform-style: preserve-3d;
}

/*
 * 抵消 iso-stage 的 rotateX + rotateZ,使图标正面朝向屏幕。
 * 父级 apply 顺序为 rotateX → rotateZ,逆变换须为 rotateZ(inv) → rotateX(inv)。
 */
.iso-icon-billboard {
  transform: rotateZ(var(--iso-rotate-z-inv)) rotateX(var(--iso-rotate-x-inv));
  transform-origin: center center;
  transform-style: preserve-3d;
  backface-visibility: hidden;
  transition: transform 0.25s ease;
  cursor: pointer;
}

.iso-icon-img {
  display: block;
  object-fit: contain;
  transform-origin: center center;
  filter: drop-shadow(0 6px 10px rgba(53, 128, 201, 0.28));
  pointer-events: none;
  user-select: none;
  transition: filter 0.25s ease;
}

/* 文字块位置(不负责倾角);倾角分别在 title / desc 上单独设置 */
.iso-label {
  margin-top: 30px;
  margin-left: 180px;
  min-width: 140px;
  max-width: 200px;
  text-align: left;
}

.iso-step-mark {
  display: block;
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--accent-blue);
  margin: 0 0 4px;
  line-height: 1;
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.8);
  transform-origin: left top;
  --mark-skew-y: -40deg;
  --mark-skew-x: 0deg;
  --mark-rotate: 90deg;
  transform: skewY(var(--mark-skew-y)) skewX(var(--mark-skew-x)) rotate(var(--mark-rotate));
}

.iso-label-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 8px;
  line-height: 1.3;
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.8);
  display: block;
  transform-origin: left top;
  --title-skew-y: -40deg;
  --title-skew-x: 0deg;
  --title-rotate: 90deg;
  transform: skewY(var(--title-skew-y)) skewX(var(--title-skew-x)) rotate(var(--title-rotate));
}

.iso-label-desc {
  font-size: 12px;
  color: var(--text-muted);
  margin-left: -25px;
  margin-top: -15px;
  line-height: 1.5;
  display: block;
  transform-origin: left top;
  --desc-skew-y: 0deg;
  --desc-skew-x: 0deg;
  --desc-rotate: 90deg;
  transform: skewY(var(--desc-skew-y)) skewX(var(--desc-skew-x)) rotate(var(--desc-rotate));
}

/* 底座左上的小编号徽章 */
.iso-pedestal-num {
  position: absolute;
  top: -10px;
  left: -10px;
  z-index: 6;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: var(--accent-blue-d);
  background: var(--bg-page);
  border: 1px solid var(--accent-blue);
  padding: 3px 7px;
  line-height: 1;
  border-radius: 2px;
  box-shadow: 0 2px 0 rgba(74, 141, 181, 0.18);
}

.iso-node:hover .iso-platform {
  transform: rotate(45deg) scaleY(0.58) translateY(-4px);
  box-shadow: 0 14px 0 #3580c9, 0 20px 28px rgba(53, 128, 201, 0.4);
  transition: all 0.25s ease;
}

.iso-node:hover .iso-platform.is-image {
  transform: none;
  box-shadow: none;
}

.iso-pedestal:hover .iso-icon-billboard {
  transform: rotateZ(var(--iso-rotate-z-inv)) rotateX(var(--iso-rotate-x-inv)) scale(1.08);
}

.iso-pedestal:hover .iso-icon-img {
  filter: drop-shadow(0 10px 16px rgba(53, 128, 201, 0.38));
}

/* ============================================
   Page 3 — 实时广场（布局同 Page 2）
============================================ */
.page-square {
  align-items: stretch;
  padding: 0;
}

.page-square .quickstart-body {
  align-items: flex-start;
  margin-top: -20px;
}

.square-agents-col {
  align-items: center;
  justify-content: flex-start;
  /* justify-content: center; */
  overflow: hidden;
  margin-top: -50px;
  margin-left: 60px;
}

.sq-waterfall {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  width: 100%;
  max-width: 920px;
  height: min(640px, 56vh);
  overflow: hidden;
}

.sq-waterfall-col {
  overflow: hidden;
  height: 100%;
  -webkit-mask-image: linear-gradient(to bottom, transparent 0%, #000 5%, #000 95%, transparent 100%);
  mask-image: linear-gradient(to bottom, transparent 0%, #000 5%, #000 95%, transparent 100%);
}

.sq-waterfall-track {
  display: flex;
  flex-direction: column;
  gap: 14px;
  will-change: transform;
}

.sq-waterfall-col.is-down .sq-waterfall-track {
  animation: sq-flow-down linear infinite;
}

.sq-waterfall-col.is-up .sq-waterfall-track {
  animation: sq-flow-up linear infinite;
}

.sq-waterfall-set {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

@keyframes sq-flow-down {
  from { transform: translateY(0); }
  to { transform: translateY(-50%); }
}

@keyframes sq-flow-up {
  from { transform: translateY(-50%); }
  to { transform: translateY(0); }
}

.sq-waterfall-col:hover .sq-waterfall-track {
  animation-play-state: paused;
}

.sq-card--flow {
  opacity: 1;
  transform: none;
  animation: none;
  flex-shrink: 0;
}

.sq-card--flow:hover {
  transform: translateY(-2px);
}

.sq-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
  width: 100%;
  max-width: 720px;
}

.sq-card {
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--r-3);
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition: all var(--t-base);
  position: relative;
  overflow: hidden;
  opacity: 0;
  transform: translateY(12px);
  animation: cardIn 0.5s var(--ease-out) forwards;
}

.sq-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--line-blue);
  transform: scaleX(0);
  transform-origin: left;
  transition: transform 0.4s var(--ease);
}

.sq-card:hover {
  border-color: var(--ink);
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.sq-card:hover::before {
  transform: scaleX(1);
  background: var(--accent-blue);
}

.sq-card.is-calling {
  border-color: var(--accent-blue-border);
}

.sq-card.is-calling::before {
  background: var(--accent-blue);
  transform: scaleX(1);
}

.sq-card-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.sq-card-id {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.sq-card-avatar {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--r-2);
  color: #fff;
  flex-shrink: 0;
}

.sq-card-initial {
  font-family: var(--font-editorial);
  font-size: 18px;
  font-style: italic;
  font-weight: 400;
}

.sq-card-meta {
  min-width: 0;
}

.sq-card-name {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  letter-spacing: -0.01em;
}

.sq-card-owner {
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.04em;
  color: var(--ink-3);
  margin-top: 1px;
}

.sq-card-status {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: var(--r-1);
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  font-weight: 500;
  white-space: nowrap;
}

.sq-card-status .scs-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}

.sq-card-status.calling {
  background: var(--accent-blue-bg);
  color: var(--accent-blue-d);
  border: 1px solid var(--accent-blue-border);
}

.sq-card-status.calling .scs-dot {
  animation: pulseDot 1.2s ease-in-out infinite;
}

.sq-card-status.online {
  background: var(--signal-positive-soft);
  color: var(--signal-positive);
  border: 1px solid rgba(16, 185, 129, 0.25);
}

.sq-card-snippet {
  background: var(--bg-card-soft);
  border: 1px solid var(--border-card);
  border-radius: var(--r-2);
  padding: 10px 12px;
  flex: 1;
}

.sq-card-snippet code {
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.5;
  color: var(--ink-2);
  display: block;
  white-space: pre-wrap;
  word-break: break-word;
  font-style: italic;
}

.sq-card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 10px;
  border-top: 1px solid var(--border-divider);
  gap: 8px;
}

.sq-card-tags {
  display: flex;
  gap: 6px;
}

.sq-tag {
  display: inline-flex;
  padding: 2px 8px;
  background: var(--bg-page-blue);
  border: 1px solid var(--line-blue);
  color: var(--accent-blue-d);
  border-radius: var(--r-1);
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.08em;
}

.sq-card-rating {
  display: flex;
  align-items: center;
  gap: 4px;
}

.sq-star {
  color: var(--ink);
  font-size: 12px;
}

.sq-rating {
  font-family: var(--font-editorial);
  font-size: 13px;
  font-style: italic;
  font-weight: 400;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}

.sq-calls {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--ink-3);
  margin-left: 4px;
}

.square-enter-btn {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin-top: 32px;
  padding: 14px 24px;
  background: var(--ink);
  color: var(--ink-inverse);
  border: 1px solid var(--ink);
  border-radius: var(--r-3);
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 500;
  text-decoration: none;
  transition: all var(--t-fast);
  align-self: flex-start;
}

.square-enter-btn:hover {
  background: var(--ink-2);
  transform: translateY(-1px);
  box-shadow: 0 6px 18px -4px rgba(20, 22, 26, 0.25);
}

/* ============================================
   Page 4 — 上传智能体（框架，布局同 Page 2/3）
============================================ */
.page-upload {
  align-items: stretch;
  padding: 0;
}

.page-upload .quickstart-body {
  align-items: flex-start;
  margin-top: -20px;
}

.upload-visual-col {
  align-items: center;
  justify-content: flex-start;
  overflow: visible;
  margin-top: -16px;
}

/* --- 分层组装主舞台 --- */
.upload-assembly {
  --asm-cycle: 9s;
  --asm-ease-bounce: cubic-bezier(0.34, 1.45, 0.64, 1);
  position: relative;
  width: 100%;
  max-width: 920px;
  height: min(640px, 56vh);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-left: 50px;
}

.upload-assembly:not(.is-active) .asm-layer,
.upload-assembly:not(.is-active) .asm-layer-legend,
.upload-assembly:not(.is-active) .asm-glow,
.upload-assembly:not(.is-active) .asm-ready-badge,
.upload-assembly:not(.is-active) .asm-card-shell,
.upload-assembly:not(.is-active) .asm-star-ring,
.upload-assembly:not(.is-active) .asm-star-ring * {
  animation-play-state: paused;
}

.asm-orbit-stage {
  position: relative;
  width: min(580px, 100%);
  height: min(580px, 52vh);
  display: flex;
  align-items: center;
  justify-content: center;
}

/* --- 旋转星环背景 --- */
.asm-star-ring {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.asm-ring {
  position: absolute;
  top: 50%;
  left: 50%;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  border: 1px solid rgba(74, 141, 181, 0.14);
}

.asm-ring--outer {
  width: 100%;
  height: 100%;
  border-style: dashed;
  border-color: rgba(74, 141, 181, 0.22);
  animation: asmRingPulse 4s ease-in-out infinite;
}

.asm-ring--mid {
  width: 82%;
  height: 82%;
  border-color: rgba(74, 141, 181, 0.16);
}

.asm-ring--inner {
  width: 64%;
  height: 64%;
  border-color: rgba(74, 141, 181, 0.1);
  background: radial-gradient(circle, rgba(74, 141, 181, 0.04) 0%, transparent 70%);
}

.asm-ring-sweep {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 100%;
  height: 100%;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  background: conic-gradient(
    from 0deg,
    transparent 0deg,
    transparent 260deg,
    rgba(74, 141, 181, 0.55) 300deg,
    rgba(111, 180, 211, 0.25) 330deg,
    transparent 360deg
  );
  -webkit-mask: radial-gradient(circle, transparent 58%, #000 59%, #000 66%, transparent 67%);
  mask: radial-gradient(circle, transparent 58%, #000 59%, #000 66%, transparent 67%);
  animation: asmRingSpin 10s linear infinite;
}

.asm-ring-sweep--reverse {
  width: 82%;
  height: 82%;
  background: conic-gradient(
    from 180deg,
    transparent 0deg,
    transparent 270deg,
    rgba(44, 102, 136, 0.35) 310deg,
    transparent 360deg
  );
  -webkit-mask: radial-gradient(circle, transparent 62%, #000 63%, #000 69%, transparent 70%);
  mask: radial-gradient(circle, transparent 62%, #000 63%, #000 69%, transparent 70%);
  animation: asmRingSpin 16s linear infinite reverse;
  opacity: 0.85;
}

.asm-spark {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 0;
  height: 0;
  transform: rotate(var(--spark-angle));
  animation: asmSparkTwinkle 3s ease-in-out infinite;
  animation-delay: var(--spark-delay, 0s);
}

.asm-spark::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 5px;
  height: 5px;
  margin: -2.5px 0 0 -2.5px;
  border-radius: 50%;
  background: var(--accent-blue-l);
  box-shadow: 0 0 8px rgba(74, 141, 181, 0.6);
  transform: translateY(calc(-1 * min(290px, 26vh)));
}

@keyframes asmRingSpin {
  to { transform: translate(-50%, -50%) rotate(360deg); }
}

@keyframes asmRingPulse {
  0%, 100% { opacity: 0.7; transform: translate(-50%, -50%) scale(1); }
  50% { opacity: 1; transform: translate(-50%, -50%) scale(1.015); }
}

@keyframes asmSparkTwinkle {
  0%, 100% { opacity: 0.35; }
  50% { opacity: 1; }
}

.asm-center {
  position: relative;
  z-index: 2;
  width: min(360px, 78%);
  transform: translateX(-22px);
}

.asm-card-shell {
  position: relative;
  width: 100%;
  padding: 0;
  border-radius: var(--r-3);
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  box-shadow: var(--shadow-sm);
  overflow: visible;
  display: grid;
  grid-template-rows: repeat(5, auto);
  animation: asmShellGlow var(--asm-cycle) ease-in-out infinite;
}

.asm-card-shell::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--line-blue);
  transform: scaleX(0);
  transform-origin: left;
  z-index: 2;
  animation: asmTopBar var(--asm-cycle) ease forwards infinite;
}

.asm-glow {
  position: absolute;
  inset: -20px;
  border-radius: calc(var(--r-3) + 8px);
  background: radial-gradient(ellipse at 50% 50%, rgba(74, 141, 181, 0.22) 0%, transparent 68%);
  opacity: 0;
  pointer-events: none;
  z-index: 0;
  animation: asmGlowPulse var(--asm-cycle) ease-in-out infinite;
}

.asm-layer {
  position: relative;
  padding: 0;
  border-bottom: 0 solid var(--border-divider);
  background: var(--bg-card);
  opacity: 0;
  max-height: 0;
  overflow: hidden;
  transform: translateY(80px) scale(0.94);
  z-index: 1;
  will-change: transform, opacity, max-height;
}

.asm-layer-inner {
  display: grid;
  grid-template-columns: 52px 1fr;
  gap: 10px;
  align-items: stretch;
  padding: 0 14px;
}

.asm-layer:first-child { border-radius: var(--r-3) var(--r-3) 0 0; }
.asm-layer--pricing { border-radius: 0 0 var(--r-3) var(--r-3); border-bottom: none; }

.asm-layer-legend {
  position: absolute;
  left: calc(100% + 14px);
  top: 50%;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: var(--r-pill);
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid var(--line-blue);
  box-shadow: 0 4px 14px -4px rgba(74, 141, 181, 0.25);
  white-space: nowrap;
  opacity: 0;
  transform: translateY(-50%) translateX(-10px);
  pointer-events: none;
  z-index: 4;
}

.asm-legend-text {
  font-family: var(--font-display);
  font-size: 11px;
  color: var(--ink-2);
}

.asm-legend-idx {
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.12em;
  color: var(--accent-blue-d);
  min-width: 18px;
}

.asm-skill-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.asm-skill-chip {
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.03em;
  color: var(--accent-blue-d);
  background: var(--accent-blue-bg);
  border: 1px solid var(--line-blue);
  border-radius: var(--r-pill);
  padding: 4px 8px;
}

.asm-layer-tag {
  font-family: var(--font-mono);
  font-size: 8px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent-blue-d);
  background: var(--accent-blue-bg);
  border: 1px solid var(--line-blue);
  border-radius: var(--r-pill);
  padding: 4px 6px;
  align-self: center;
  text-align: center;
  line-height: 1.2;
}

.asm-layer-body {
  min-width: 0;
}

.asm-layer-body--head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.asm-avatar {
  width: 36px;
  height: 36px;
  border-radius: var(--r-2);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
  font-family: var(--font-editorial);
  font-size: 18px;
  font-style: italic;
}

.asm-head-meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.asm-head-meta strong {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  letter-spacing: -0.01em;
}

.asm-head-meta span {
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--ink-3);
  letter-spacing: 0.04em;
}

.asm-prompt-text {
  margin: 0;
  font-family: var(--font-display);
  font-size: 11px;
  line-height: 1.55;
  color: var(--ink-2);
}

.asm-api-line {
  display: block;
  font-family: var(--font-mono);
  font-size: 10px;
  line-height: 1.5;
  color: var(--ink-2);
  background: var(--bg-card-soft);
  border: 1px solid var(--border-divider);
  border-radius: var(--r-1);
  padding: 6px 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.asm-layer-body--foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.asm-price {
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 600;
  color: var(--ink);
}

.asm-trial {
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--text-success);
  background: var(--signal-positive-soft);
  border-radius: var(--r-pill);
  padding: 3px 8px;
}

/* 依次飞入：Prompt → Skill → API → Pricing → Icon */
.asm-layer--icon    { grid-row: 1; animation: asmLayerIcon    var(--asm-cycle) var(--asm-ease-bounce) infinite; }
.asm-layer--prompt  { grid-row: 2; animation: asmLayerPrompt  var(--asm-cycle) var(--asm-ease-bounce) infinite; }
.asm-layer--skill   { grid-row: 3; animation: asmLayerSkill   var(--asm-cycle) var(--asm-ease-bounce) infinite; }
.asm-layer--api     { grid-row: 4; animation: asmLayerApi     var(--asm-cycle) var(--asm-ease-bounce) infinite; }
.asm-layer--pricing { grid-row: 5; animation: asmLayerPricing var(--asm-cycle) var(--asm-ease-bounce) infinite; }

.asm-layer--prompt  .asm-layer-legend { animation: asmLegendPrompt  var(--asm-cycle) ease forwards infinite; }
.asm-layer--skill   .asm-layer-legend { animation: asmLegendSkill   var(--asm-cycle) ease forwards infinite; }
.asm-layer--api     .asm-layer-legend { animation: asmLegendApi     var(--asm-cycle) ease forwards infinite; }
.asm-layer--pricing .asm-layer-legend { animation: asmLegendPricing var(--asm-cycle) ease forwards infinite; }
.asm-layer--icon    .asm-layer-legend { animation: asmLegendIcon    var(--asm-cycle) ease forwards infinite; }

@keyframes asmLayerPrompt {
  0%, 3%    { opacity: 0; max-height: 0; padding-top: 0; padding-bottom: 0; border-bottom-width: 0; transform: translateY(80px) scale(0.94); }
  5%        { opacity: 0; max-height: 0; padding-top: 0; padding-bottom: 0; border-bottom-width: 0; transform: translateY(80px) scale(0.94); }
  12%       { opacity: 1; max-height: 88px; padding-top: 12px; padding-bottom: 12px; border-bottom-width: 1px; transform: translateY(-8px) scale(1.01); }
  16%       { opacity: 1; max-height: 88px; padding-top: 12px; padding-bottom: 12px; border-bottom-width: 1px; transform: translateY(3px) scale(0.995); }
  20%, 70%  { opacity: 1; max-height: 88px; padding-top: 12px; padding-bottom: 12px; border-bottom-width: 1px; transform: translateY(0) scale(1); }
  78%, 100% { opacity: 0; max-height: 0; padding-top: 0; padding-bottom: 0; border-bottom-width: 0; transform: translateY(40px) scale(0.98); }
}

@keyframes asmLayerSkill {
  0%, 11%   { opacity: 0; max-height: 0; padding-top: 0; padding-bottom: 0; border-bottom-width: 0; transform: translateY(80px) scale(0.94); }
  13%       { opacity: 0; max-height: 0; padding-top: 0; padding-bottom: 0; border-bottom-width: 0; transform: translateY(80px) scale(0.94); }
  20%       { opacity: 1; max-height: 56px; padding-top: 12px; padding-bottom: 12px; border-bottom-width: 1px; transform: translateY(-8px) scale(1.01); }
  24%       { opacity: 1; max-height: 56px; padding-top: 12px; padding-bottom: 12px; border-bottom-width: 1px; transform: translateY(3px) scale(0.995); }
  28%, 70%  { opacity: 1; max-height: 56px; padding-top: 12px; padding-bottom: 12px; border-bottom-width: 1px; transform: translateY(0) scale(1); }
  78%, 100% { opacity: 0; max-height: 0; padding-top: 0; padding-bottom: 0; border-bottom-width: 0; transform: translateY(40px) scale(0.98); }
}

@keyframes asmLayerApi {
  0%, 19%   { opacity: 0; max-height: 0; padding-top: 0; padding-bottom: 0; border-bottom-width: 0; transform: translateY(80px) scale(0.94); }
  21%       { opacity: 0; max-height: 0; padding-top: 0; padding-bottom: 0; border-bottom-width: 0; transform: translateY(80px) scale(0.94); }
  28%       { opacity: 1; max-height: 72px; padding-top: 12px; padding-bottom: 12px; border-bottom-width: 1px; transform: translateY(-8px) scale(1.01); }
  32%       { opacity: 1; max-height: 72px; padding-top: 12px; padding-bottom: 12px; border-bottom-width: 1px; transform: translateY(3px) scale(0.995); }
  36%, 70%  { opacity: 1; max-height: 72px; padding-top: 12px; padding-bottom: 12px; border-bottom-width: 1px; transform: translateY(0) scale(1); }
  78%, 100% { opacity: 0; max-height: 0; padding-top: 0; padding-bottom: 0; border-bottom-width: 0; transform: translateY(40px) scale(0.98); }
}

@keyframes asmLayerPricing {
  0%, 27%   { opacity: 0; max-height: 0; padding-top: 0; padding-bottom: 0; border-bottom-width: 0; transform: translateY(80px) scale(0.94); }
  29%       { opacity: 0; max-height: 0; padding-top: 0; padding-bottom: 0; border-bottom-width: 0; transform: translateY(80px) scale(0.94); }
  36%       { opacity: 1; max-height: 56px; padding-top: 12px; padding-bottom: 12px; border-bottom-width: 1px; transform: translateY(-8px) scale(1.01); }
  40%       { opacity: 1; max-height: 56px; padding-top: 12px; padding-bottom: 12px; border-bottom-width: 1px; transform: translateY(3px) scale(0.995); }
  44%, 70%  { opacity: 1; max-height: 56px; padding-top: 12px; padding-bottom: 12px; border-bottom-width: 1px; transform: translateY(0) scale(1); }
  78%, 100% { opacity: 0; max-height: 0; padding-top: 0; padding-bottom: 0; border-bottom-width: 0; transform: translateY(40px) scale(0.98); }
}

@keyframes asmLayerIcon {
  0%, 35%   { opacity: 0; max-height: 0; padding-top: 0; padding-bottom: 0; border-bottom-width: 0; transform: translateY(80px) scale(0.94); }
  37%       { opacity: 0; max-height: 0; padding-top: 0; padding-bottom: 0; border-bottom-width: 0; transform: translateY(80px) scale(0.94); }
  44%       { opacity: 1; max-height: 64px; padding-top: 12px; padding-bottom: 12px; border-bottom-width: 0; transform: translateY(-8px) scale(1.01); }
  48%       { opacity: 1; max-height: 64px; padding-top: 12px; padding-bottom: 12px; border-bottom-width: 0; transform: translateY(3px) scale(0.995); }
  52%, 70%  { opacity: 1; max-height: 64px; padding-top: 12px; padding-bottom: 12px; border-bottom-width: 0; transform: translateY(0) scale(1); }
  78%, 100% { opacity: 0; max-height: 0; padding-top: 0; padding-bottom: 0; border-bottom-width: 0; transform: translateY(40px) scale(0.98); }
}

@keyframes asmLegendPrompt {
  0%, 15%   { opacity: 0; transform: translateY(-50%) translateX(-10px); }
  18%, 70%  { opacity: 1; transform: translateY(-50%) translateX(0); }
  78%, 100% { opacity: 0; transform: translateY(-50%) translateX(8px); }
}
@keyframes asmLegendSkill {
  0%, 23%   { opacity: 0; transform: translateY(-50%) translateX(-10px); }
  26%, 70%  { opacity: 1; transform: translateY(-50%) translateX(0); }
  78%, 100% { opacity: 0; transform: translateY(-50%) translateX(8px); }
}
@keyframes asmLegendApi {
  0%, 31%   { opacity: 0; transform: translateY(-50%) translateX(-10px); }
  34%, 70%  { opacity: 1; transform: translateY(-50%) translateX(0); }
  78%, 100% { opacity: 0; transform: translateY(-50%) translateX(8px); }
}
@keyframes asmLegendPricing {
  0%, 39%   { opacity: 0; transform: translateY(-50%) translateX(-10px); }
  42%, 70%  { opacity: 1; transform: translateY(-50%) translateX(0); }
  78%, 100% { opacity: 0; transform: translateY(-50%) translateX(8px); }
}
@keyframes asmLegendIcon {
  0%, 47%   { opacity: 0; transform: translateY(-50%) translateX(-10px); }
  50%, 70%  { opacity: 1; transform: translateY(-50%) translateX(0); }
  78%, 100% { opacity: 0; transform: translateY(-50%) translateX(8px); }
}

@keyframes asmShellGlow {
  0%, 50% {
    border-color: var(--border-card);
    box-shadow: var(--shadow-sm);
  }
  54%, 70% {
    border-color: var(--accent-blue-border);
    box-shadow:
      0 0 0 1px rgba(74, 141, 181, 0.15),
      0 12px 40px -8px rgba(74, 141, 181, 0.35),
      0 4px 16px -4px rgba(20, 22, 26, 0.12);
  }
  78%, 100% {
    border-color: var(--border-card);
    box-shadow: var(--shadow-sm);
  }
}

@keyframes asmTopBar {
  0%, 52% { transform: scaleX(0); background: var(--line-blue); }
  56%, 70% { transform: scaleX(1); background: var(--accent-blue); }
  78%, 100% { transform: scaleX(0); background: var(--line-blue); }
}

@keyframes asmGlowPulse {
  0%, 52% { opacity: 0; transform: scale(0.92); }
  56%, 68% { opacity: 1; transform: scale(1); }
  76%, 100% { opacity: 0; transform: scale(0.92); }
}

.asm-ready-badge {
  position: absolute;
  top: -12px;
  right: -8px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: var(--r-pill);
  background: var(--bg-card);
  border: 1px solid var(--accent-blue-border);
  box-shadow: 0 8px 24px -6px rgba(74, 141, 181, 0.35);
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 600;
  color: var(--accent-blue-d);
  opacity: 0;
  transform: translateY(8px) scale(0.9);
  z-index: 5;
  animation: asmReadyIn var(--asm-cycle) var(--asm-ease-bounce) infinite;
}

.asm-ready-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--signal-positive);
  box-shadow: 0 0 0 3px var(--signal-positive-soft);
  animation: pulseDot 1.4s ease-in-out infinite;
}

@keyframes asmReadyIn {
  0%, 52% {
    opacity: 0;
    transform: translateY(8px) scale(0.9);
  }
  56%, 70% {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
  78%, 100% {
    opacity: 0;
    transform: translateY(-4px) scale(0.96);
  }
}

@keyframes cardIn { to { opacity: 1; transform: translateY(0); } }
@keyframes pulseDot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.85); }
}

/* ============================================
   Page dots
============================================ */
.page-dots {
  position: fixed;
  right: 24px; top: 50%;
  transform: translateY(-50%);
  z-index: 50;
  display: flex; flex-direction: column; gap: 4px;
}
.dot {
  display: flex; align-items: center; gap: 12px;
  padding: 8px 12px;
  background: transparent; border: none;
  border-radius: var(--r-2);
  cursor: pointer; transition: all var(--t-fast);
  font-family: inherit; color: var(--ink-3); text-align: left;
}
.dot::before {
  content: ''; width: 6px; height: 6px;
  background: var(--ink-4);
  border-radius: 50%;
  transition: all var(--t-fast);
  flex-shrink: 0;
}
.dot:hover { color: var(--ink); background: var(--bg-card-soft); }
.dot:hover::before { background: var(--ink-2); transform: scale(1.2); }
.dot.active { color: var(--ink); }
.dot.active::before { width: 20px; background: var(--ink); border-radius: 3px; }
.dot-num {
  font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.16em; text-transform: uppercase;
  font-weight: 500; opacity: 0.5; transition: opacity var(--t-fast);
}
.dot-name {
  font-family: var(--font-display); font-size: 13px; font-weight: 500;
  letter-spacing: 0.01em;
  opacity: 0; max-width: 0; overflow: hidden; white-space: nowrap;
  transition: max-width 0.3s var(--ease), opacity 0.2s var(--ease);
}
.dot.active .dot-num, .dot:hover .dot-num { opacity: 0.7; }
.dot.active .dot-name, .dot:hover .dot-name { opacity: 1; max-width: 100px; }
.dot.active .dot-name { color: var(--accent-blue-d); font-weight: 600; }

/* ============================================
   Entry animations
============================================ */
.hero-left > * {
  opacity: 0;
  animation: heroIn 0.7s var(--ease-out) forwards;
}
.hero-left .masthead  { animation-delay: 0.1s; }
.hero-left .hero-title { animation-delay: 0.3s; }
.hero-left .hero-deck  { animation-delay: 0.45s; }
.hero-left .hero-actions { animation-delay: 0.6s; }
.hero-left .hero-footnote { animation-delay: 0.7s; }
.hero-left .hero-strip { animation-delay: 0.85s; }
@keyframes heroIn {
  from { opacity: 0; transform: translateY(20px); }
  to   { opacity: 1; transform: translateY(0); }
}

.mobile-home-only { display: none; }

/* ============================================
   Responsive
============================================ */
@media (max-width: 1100px) {
  .page { padding: 0 24px; }
  .quickstart-body {
    grid-template-columns: 1fr;
    gap: 28px;
  }
  .quickstart-side {
    height: auto;
    margin-right: 0;
    border-left: none;
    border-top: 1px solid rgba(20, 22, 26, 0.14);
    padding: 24px 0 0;
  }
  .quickstart-chart-col .iso-stage {
    width: min(960px, 100%);
    height: min(560px, 50vh);
  }
  .hero { grid-template-columns: 1fr; gap: 40px; }
  .hero-right { order: 2; align-items: stretch; }
  .chat-preview { margin: 0 auto; }
  .quickstart-chart-col { margin-right: 0; }
  .sq-waterfall {
    max-width: none;
    height: min(580px, 50vh);
    margin-top: 0;
  }
  .page-square .quickstart-body { margin-top: 0; }
  .square-agents-col { margin-top: 0; }
  .page-upload .quickstart-body { margin-top: 0; }
  .upload-visual-col { margin-top: 0; }
  .upload-assembly { height: min(580px, 50vh); }
  .asm-orbit-stage { width: min(480px, 100%); height: min(480px, 46vh); }
  .asm-layer-legend {
    left: calc(100% + 8px);
    padding: 5px 8px;
    font-size: 10px;
  }
  .asm-legend-text { font-size: 10px; }
  .asm-ready-badge {
    top: -8px;
    right: -4px;
  }
}
@media (max-width: 768px) {
  .hero-strip { gap: 14px; }
  .sq-waterfall {
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    height: min(520px, 46vh);
  }
  .sq-card { padding: 14px; }
  .sq-card-snippet code { font-size: 10px; }
  .float-card { display: none; }
  .page-dots { right: 12px; }
  .dot-name { display: none; }
  .hero-right-deco { display: none; }
  .masthead { flex-direction: column; align-items: flex-start; gap: 8px; }
  .iso-stage {
    --iso-rotate-x: 48deg;
    --iso-rotate-z: -28deg;
    --iso-rotate-x-inv: -48deg;
    --iso-rotate-z-inv: 28deg;
    transform: rotateX(var(--iso-rotate-x)) rotateZ(var(--iso-rotate-z)) scale(0.82);
  }
  .iso-label { max-width: 120px; font-size: 12px; }
  .iso-pedestal-num { font-size: 8px; padding: 2px 5px; top: -8px; left: -8px; }
  .iso-step-mark { font-size: 7px; letter-spacing: 0.14em; }
  .asm-layer-legend { display: none; }
  .asm-center { transform: none; }
  .asm-orbit-stage { width: min(380px, 92vw); height: min(380px, 42vh); }
}

@media (max-width: 768px) {
  .home {
    height: auto;
    min-height: 100vh;
    overflow-x: clip;
    overflow-y: visible;
  }
  .pages-track {
    height: auto;
    transform: none !important;
    transition: none;
  }
  .pages-track.animating { pointer-events: auto; }
  .page {
    display: block;
    height: auto;
    min-height: 0;
    padding: 72px 18px;
    overflow: hidden;
    border-top: 1px solid rgba(46, 122, 184, 0.16);
  }
  .page-hero {
    min-height: calc(100svh - 56px);
    padding: 24px 18px 50px;
    border-top: 0;
  }
  .hero {
    display: block;
    width: 100%;
    max-width: none;
    margin: 0;
    padding: 0;
  }
  .hero-left { width: 100%; max-width: none; }
  .masthead {
    display: block;
    padding-bottom: 12px;
    margin-bottom: 20px;
  }
  .renta-logo { height: 58px; }
  .hero-title {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
    margin-bottom: 22px;
    letter-spacing: 0;
  }
  .title-fragment {
    display: block;
    width: 100%;
    font-size: 50px;
    line-height: 0.96;
    letter-spacing: 0;
  }
  .title-fragment .cn {
    display: block;
    margin: 8px 0 0;
    font-size: 0.64em;
    line-height: 1.1;
    letter-spacing: 0;
  }
  .title-ai {
    font-size: 34px;
    padding: 6px 10px 8px;
    border-radius: 6px;
    letter-spacing: 0;
  }
  .title-caption {
    align-items: flex-start;
    margin: 0 0 20px;
    font-size: 16px;
    line-height: 1.65;
  }
  .title-caption .caption-mark { margin-top: 12px; width: 24px; }
  .hero-deck {
    margin-bottom: 22px;
    font-size: 16px;
    line-height: 1.55;
  }
  .hero-actions {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
    margin-bottom: 20px;
  }
  .hero-cta,
  .hero-cta-ghost {
    min-height: 48px;
    padding: 12px 14px;
    justify-content: center;
    font-size: 14px;
    border-radius: 8px;
  }
  .hero-cta { grid-column: 1 / -1; }
  .hero-strip,
  .hero-right,
  .scroll-hint,
  .page-dots,
  .desktop-story { display: none !important; }
  .mobile-home-only { display: block; }

  .page-quickstart,
  .page-square,
  .page-upload { padding: 72px 18px; }
  .page-square { background: rgba(255, 255, 255, 0.34); }
  .page-upload { padding-bottom: 88px; }
  .quickstart-iso {
    width: 100%;
    height: auto;
    margin: 0;
    padding: 0;
  }
  .section-header,
  .iso-header {
    margin: 0 0 28px;
    text-align: left;
    gap: 8px;
  }
  .iso-header .section-title {
    font-size: 38px;
    line-height: 1.04;
    letter-spacing: 0;
  }
  .iso-header .section-desc { font-size: 14px; line-height: 1.65; }
}

@media (max-width: 768px) {
  .mobile-signal-board {
    position: relative;
    overflow: hidden;
    padding: 14px;
    color: #f5fbff;
    background: #0e2a47;
    border: 1px solid rgba(125, 200, 235, 0.34);
    border-radius: 8px;
    box-shadow: 0 18px 40px -28px rgba(14, 42, 71, 0.9);
  }
  .mobile-signal-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: 10px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.14);
    font-family: var(--font-mono);
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.16em;
  }
  .mobile-signal-live { display: inline-flex; align-items: center; gap: 7px; }
  .mobile-signal-live i {
    width: 7px;
    height: 7px;
    background: #2dd4a3;
    border-radius: 50%;
    box-shadow: 0 0 0 5px rgba(45, 212, 163, 0.12);
    animation: mobileSignalPulse 1.8s ease-in-out infinite;
  }
  .mobile-signal-count { color: #9ed2ed; }
  .mobile-signal-list { display: grid; gap: 0; }
  .mobile-signal-row {
    display: grid;
    grid-template-columns: 30px minmax(0, 1fr) auto;
    align-items: center;
    gap: 10px;
    min-height: 48px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.09);
  }
  .mobile-signal-row:last-child { border-bottom: 0; }
  .mobile-signal-avatar {
    width: 28px;
    height: 28px;
    display: grid;
    place-items: center;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 700;
  }
  .mobile-signal-meta { min-width: 0; display: flex; flex-direction: column; gap: 1px; }
  .mobile-signal-meta strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; }
  .mobile-signal-meta small { color: rgba(226, 241, 250, 0.62); font-size: 10px; }
  .mobile-signal-ping { color: #2dd4a3; font-family: var(--font-mono); font-size: 8px; letter-spacing: 0.12em; }
  .mobile-signal-beam {
    position: absolute;
    top: 44px;
    bottom: 0;
    width: 1px;
    background: rgba(125, 200, 235, 0.78);
    box-shadow: 0 0 16px 3px rgba(125, 200, 235, 0.24);
    animation: mobileSignalSweep 4.2s ease-in-out infinite;
    pointer-events: none;
  }

  .mobile-step-list { border-top: 1px solid rgba(46, 122, 184, 0.22); }
  .mobile-step-row {
    display: grid;
    grid-template-columns: 28px 54px minmax(0, 1fr) auto;
    align-items: center;
    gap: 10px;
    min-height: 92px;
    border-bottom: 1px solid rgba(46, 122, 184, 0.18);
    animation: mobileRowIn 0.45s var(--ease-out) both;
  }
  .mobile-step-num { font-family: var(--font-mono); font-size: 10px; color: var(--accent-blue-d); }
  .mobile-step-icon {
    width: 52px;
    height: 52px;
    display: grid;
    place-items: center;
    background: rgba(255, 255, 255, 0.58);
    border: 1px solid rgba(46, 122, 184, 0.18);
    border-radius: 8px;
  }
  .mobile-step-icon img { width: 42px; height: 42px; object-fit: contain; }
  .mobile-step-copy { min-width: 0; display: flex; flex-direction: column; gap: 4px; }
  .mobile-step-copy strong { font-size: 15px; color: var(--ink); }
  .mobile-step-copy small { font-size: 12px; color: var(--ink-3); line-height: 1.45; }
  .mobile-step-state { font-family: var(--font-mono); font-size: 8px; color: #0f9f77; letter-spacing: 0.12em; }
  .mobile-expand-control {
    width: 100%;
    min-height: 48px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 12px;
    padding: 0 4px;
    border: 0;
    border-bottom: 1px solid rgba(46, 122, 184, 0.24);
    background: transparent;
    color: var(--accent-blue-d);
    font-family: inherit;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
  }
  .mobile-expand-control svg { transition: transform var(--t-fast); }
  .mobile-expand-control svg.rotated { transform: rotate(180deg); }

  .mobile-agent-list { display: grid; gap: 12px; }
  .mobile-agent-card {
    padding: 16px;
    overflow: hidden;
    background: rgba(255, 255, 255, 0.78);
    border: 1px solid rgba(46, 122, 184, 0.18);
    border-radius: 8px;
    box-shadow: 0 16px 34px -30px rgba(14, 42, 71, 0.7);
    animation: mobileRowIn 0.45s var(--ease-out) both;
  }
  .mobile-agent-card header {
    display: grid;
    grid-template-columns: 38px minmax(0, 1fr) auto;
    align-items: center;
    gap: 10px;
  }
  .mobile-agent-avatar {
    width: 38px;
    height: 38px;
    display: grid;
    place-items: center;
    border-radius: 7px;
    color: #fff;
    font-weight: 700;
  }
  .mobile-agent-id { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
  .mobile-agent-id strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 14px; }
  .mobile-agent-id small { color: var(--ink-3); font-family: var(--font-mono); font-size: 9px; }
  .mobile-agent-status { color: #0f9f77; font-family: var(--font-mono); font-size: 8px; letter-spacing: 0.08em; }
  .mobile-agent-status.calling { color: #c6771b; }
  .mobile-agent-card code {
    display: block;
    min-height: 48px;
    margin: 14px 0;
    padding: 10px;
    overflow-wrap: anywhere;
    white-space: pre-wrap;
    background: rgba(14, 42, 71, 0.05);
    border-left: 2px solid var(--accent-blue);
    color: var(--ink-2);
    font-size: 10px;
    line-height: 1.5;
  }
  .mobile-agent-card footer { display: flex; justify-content: space-between; gap: 12px; color: var(--ink-3); font-size: 10px; }
  .mobile-story-actions { display: grid; gap: 12px; margin-top: 14px; }
  .mobile-primary-link {
    min-height: 50px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 16px;
    background: var(--ink);
    color: #fff;
    border-radius: 8px;
    text-decoration: none;
    font-size: 14px;
    font-weight: 600;
  }

  .mobile-builder-stage {
    overflow: hidden;
    padding: 16px;
    background: #0e2a47;
    color: #fff;
    border: 1px solid rgba(125, 200, 235, 0.34);
    border-radius: 8px;
  }
  .mobile-builder-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: 14px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.14);
    font-family: var(--font-mono);
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
  }
  .mobile-builder-head span { display: inline-flex; align-items: center; gap: 8px; }
  .mobile-builder-head i { width: 7px; height: 7px; border-radius: 50%; background: #2dd4a3; }
  .mobile-builder-head strong { color: #2dd4a3; font-size: 9px; }
  .mobile-builder-layer {
    display: grid;
    grid-template-columns: 28px 72px minmax(0, 1fr);
    align-items: center;
    gap: 10px;
    min-height: 58px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    animation: mobileLayerIn 0.55s var(--ease-out) both;
    animation-delay: calc(var(--layer-index) * 90ms);
  }
  .mobile-builder-layer:last-child { border-bottom: 0; }
  .mobile-builder-index { color: #7dc8eb; font-family: var(--font-mono); font-size: 9px; }
  .mobile-builder-label { color: rgba(255, 255, 255, 0.56); font-family: var(--font-mono); font-size: 8px; text-transform: uppercase; letter-spacing: 0.1em; }
  .mobile-builder-layer strong { min-width: 0; color: #f5fbff; font-size: 12px; font-weight: 600; }
  .mobile-builder-copy { margin: 18px 0; color: var(--ink-2); font-size: 14px; line-height: 1.7; }
  .mobile-builder-link { background: var(--accent-blue-d); }

  @keyframes mobileSignalPulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.45; transform: scale(0.78); }
  }
  @keyframes mobileSignalSweep {
    0%, 100% { left: -2%; opacity: 0; }
    12%, 88% { opacity: 1; }
    50% { left: 102%; opacity: 0.72; }
  }
  @keyframes mobileRowIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }
  @keyframes mobileLayerIn {
    from { opacity: 0; transform: translateX(-12px); }
    to { opacity: 1; transform: translateX(0); }
  }
}

@media (prefers-reduced-motion: reduce) {
  .home-mesh, .float-card, .strip-pulse::after, .cp-pulse, .cp-typing span, .fc-dot, .scs-dot { animation: none !important; }
  .sq-waterfall-track { animation: none !important; }
  .hero-left > * { opacity: 1; }
  .upload-assembly .asm-layer {
    animation: none !important;
    opacity: 1;
    max-height: 120px;
    padding-top: 12px;
    padding-bottom: 12px;
    border-bottom-width: 1px;
    transform: none;
  }
  .upload-assembly .asm-layer--icon { border-bottom-width: 0; }
  .upload-assembly .asm-layer-legend {
    animation: none !important;
    opacity: 1;
    transform: translateY(-50%) translateX(0);
  }
  .upload-assembly .asm-star-ring,
  .upload-assembly .asm-star-ring * { animation: none !important; }
  .upload-assembly .asm-ring-sweep { opacity: 0.5; }
  .upload-assembly .asm-card-shell {
    animation: none !important;
    border-color: var(--accent-blue-border);
    box-shadow: 0 8px 28px -8px rgba(74, 141, 181, 0.28);
  }
  .upload-assembly .asm-card-shell::before { transform: scaleX(1); background: var(--accent-blue); }
  .upload-assembly .asm-glow { opacity: 0.6; animation: none !important; }
  .upload-assembly .asm-ready-badge { opacity: 1; transform: none; animation: none !important; }
  .mobile-signal-live i,
  .mobile-signal-beam,
  .mobile-step-row,
  .mobile-agent-card,
  .mobile-builder-layer { animation: none !important; }
}
</style>
