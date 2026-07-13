<template>
  <div class="chat-page anim-panel-center" :class="{ ready: chatReady, 'history-open': showHistory }">
    <div class="chat-main">
      <!-- 顶栏 -->
      <header class="chat-header">
        <div class="header-left">
          <button @click="router.back()" class="back-btn" title="返回">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>
          </button>
          <div class="header-brand">
            <span class="header-brand-mark">
              <img src="/renta-logo-mark.png" alt="" />
            </span>
            <span class="header-brand-name">RenTA</span>
          </div>
          <button @click="newChat" class="new-chat-btn" title="新对话" aria-label="开启新对话">
            <span class="new-chat-plus" aria-hidden="true">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            </span>
            <span class="new-chat-text">新会话</span>
          </button>
          <div v-if="activeConvTitle" class="header-title">
            <span class="title-bar"></span>
            <span class="title-text">{{ activeConvTitle }}</span>
          </div>
        </div>

        <div class="header-center" />

        <div class="header-right">
          <button @click="toggleHistory" class="icon-btn history-toggle-btn" :class="{ active: showHistory }" title="对话历史" aria-label="打开或收起对话历史">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="5" width="16" height="14" rx="2"/><line x1="9" y1="5" x2="9" y2="19"/><line x1="12.5" y1="10" x2="16.5" y2="10"/><line x1="12.5" y1="14" x2="15.5" y2="14"/></svg>
          </button>
          <button v-if="!auth.isAdmin" @click="toggleWorkbench" class="icon-btn" :class="{ active: showWorkbench }" title="工作台">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
          </button>
          <!-- 分隔:工作台/历史 与 全局菜单/用户 -->
          <span class="header-divider"></span>

          <!-- MENU 触发按钮 (打开 AppMenu 命令面板) -->
          <button class="icon-btn chat-menu-trigger" @click="openAppMenu" title="打开导航菜单">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <line x1="3" y1="6"  x2="21" y2="6"/>
              <line x1="3" y1="12" x2="15" y2="12"/>
              <line x1="3" y1="18" x2="18" y2="18"/>
            </svg>
          </button>

          <!-- 用户头像 / 登录 -->
          <button v-if="auth.isLoggedIn" class="chat-user-btn" @click="goAccount" title="我的账户">
            <span class="user-avatar">{{ (auth.user?.username || 'U').slice(0,1).toUpperCase() }}</span>
          </button>
          <router-link v-else to="/auth" class="chat-login-link">登录</router-link>
        </div>
      </header>

      <!-- 对话区 -->
      <div class="chat-body" ref="bodyRef">
        <!-- 欢迎屏 -->
        <div v-if="messages.length === 0" class="welcome-screen">
          <div class="welcome-brand-logo">
            <div class="welcome-logo-shell">
              <img src="/renta-logo-mark.png" alt="RenTA" class="welcome-logo-img" />
            </div>
            <div class="welcome-logo-tagline">RenTA：IoA原生智能体交易平台</div>
          </div>
          <h1 class="welcome-title">
            <span class="title-line">有什么可以</span>
            <em class="title-emph">帮</em>
            <span class="title-line">你的?</span>
          </h1>
          <p class="welcome-sub">智能体应用商店 — 创建、管理、探索你的 AI 智能体</p>

          <!-- 建议问题(按类别) -->
          <div class="suggestion-groups">
            <div v-for="(group, gi) in suggestionGroups" :key="gi" class="sugg-group">
              <div class="sugg-group-head">
                <span class="sugg-group-label">{{ group.label }}</span>
                <span class="sugg-group-line"></span>
              </div>
              <div class="sugg-group-items">
                <button
                  v-for="(s, si) in group.items"
                  :key="si"
                  class="suggestion-chip"
                  :style="{ animationDelay: (gi * 80 + si * 50) + 'ms' }"
                  @click="sendSuggestion(s)"
                >
                  <span class="chip-num">{{ String(si + 1).padStart(2, '0') }}</span>
                  <span class="chip-text">{{ s }}</span>
                  <svg class="chip-arrow" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
                </button>
              </div>
            </div>
          </div>

        </div>

        <!-- 消息列表 -->
        <div v-for="(msg, i) in messages" :key="i" class="msg-wrapper" :class="msg.role">
          <!-- 用户消息 -->
          <div v-if="msg.role === 'user'" class="msg-row user">
            <div class="user-avatar">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            </div>
            <div class="user-bubble-wrap">
              <div class="user-bubble">{{ msg.content }}</div>
              <span class="msg-time">{{ formatMessageTime(msg.time) }}</span>
            </div>
          </div>

          <!-- AI 消息 -->
          <div v-else class="msg-row bot">
            <div class="bot-avatar">
              <img src="/renta-logo-mark.png" alt="RenTA" class="bot-logo" />
            </div>
            <div class="bot-card">
              <!-- 卡片顶栏 -->
              <div class="bot-card-head">
                <div class="bot-id">
                  <img src="/renta-logo-mark.png" alt="" class="bot-logo-mini" />
                  <span class="bot-name">RenTA</span>
                  <span class="bot-dot">·</span>
                  <span class="bot-model">{{ currentModel }}</span>
                </div>
                <div class="bot-card-right">
                  <span v-if="msg.tokens" class="bot-tokens">{{ msg.tokens }} tokens</span>
                  <span class="msg-time">{{ formatMessageTime(msg.time) }}</span>
                </div>
              </div>

              <!-- 思考过程 -->
              <div v-if="msg.thinking" class="thinking-block">
                <div class="thinking-header" @click="msg.thinkingOpen = !msg.thinkingOpen">
                  <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                  <span>{{ msg.thinkingTitle || 'Orchestration trace / 真实执行过程' }}</span>
                  <span v-if="msg.thinkingOpen" class="thinking-dots">
                    <span></span><span></span><span></span>
                  </span>
                  <svg class="thinking-chevron" :class="{ open: msg.thinkingOpen }" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
                </div>
                <div v-show="msg.thinkingOpen" class="thinking-body" v-html="renderMarkdown(msg.thinking)"></div>
              </div>

              <!-- 正文 -->
              <div class="bot-text" :ref="el => bindMarkdownRef(el, i)" v-html="renderMarkdown(msg.content)"></div>

              <!-- 文件产物 -->
              <div v-if="msg.artifacts?.length" class="message-artifacts">
                <article
                  v-for="a in msg.artifacts"
                  :key="a.id"
                  class="message-artifact-card"
                  :class="{ expanded: a.expanded }"
                >
                  <div class="message-artifact-main">
                    <div class="message-artifact-icon" aria-hidden="true">
                      <svg v-if="artifactKind(a) === 'html'" xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 0 20"/><path d="M12 2a15.3 15.3 0 0 0 0 20"/></svg>
                      <svg v-else xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M8 13h8"/><path d="M8 17h5"/></svg>
                    </div>
                    <div class="message-artifact-meta">
                      <div class="message-artifact-title">{{ a.title || a.filename || '文件产物' }}</div>
                      <div class="message-artifact-sub">
                        <span>{{ artifactKindLabel(a) }}</span>
                        <span v-if="a.agentName">{{ a.agentName }}</span>
                        <span v-if="artifactSizeLabel(a)">{{ artifactSizeLabel(a) }}</span>
                      </div>
                    </div>
                    <div class="message-artifact-actions">
                      <button
                        v-if="canPreviewArtifact(a)"
                        class="message-artifact-btn"
                        @click.stop="toggleMessageArtifact(a)"
                      >
                        {{ a.expanded ? '收起' : '预览' }}
                      </button>
                      <button class="message-artifact-btn primary" @click.stop="downloadArtifact(a)">下载</button>
                    </div>
                  </div>
                  <div v-if="a.expanded" class="message-artifact-preview">
                    <iframe
                      v-if="artifactKind(a) === 'html' && a.content"
                      class="message-artifact-frame"
                      sandbox="allow-scripts allow-same-origin"
                      :srcdoc="a.content"
                      title="文件预览"
                    ></iframe>
                    <pre v-else class="message-artifact-pre">{{ artifactPreviewText(a) }}</pre>
                  </div>
                </article>
              </div>

              <!-- 操作行 -->
              <div class="msg-actions">
                <button class="action-btn" @click="copyMessage(msg)" :title="msg.copied ? '已复制' : '复制'">
                  <svg v-if="!msg.copied" xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                  <svg v-else xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                  <span class="action-tip">{{ msg.copied ? '已复制' : '复制' }}</span>
                </button>
                <button class="action-btn" @click="regenerate(i)" :disabled="typing" title="重新生成">
                  <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                  <span class="action-tip">重新生成</span>
                </button>
                <button class="action-btn" :class="{ liked: msg.liked }" @click="msg.liked = !msg.liked; msg.disliked = false" title="有用">
                  <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 10v12"/><path d="M15 5.88L14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H7"/></svg>
                  <span class="action-tip">有用</span>
                </button>
                <button class="action-btn" :class="{ disliked: msg.disliked }" @click="msg.disliked = !msg.disliked; msg.liked = false" title="没用">
                  <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 14V2"/><path d="M9 18.12L10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H17"/></svg>
                  <span class="action-tip">没用</span>
                </button>
                <div class="action-spacer"></div>
                <span v-if="msg.model" class="action-meta">RenTA · {{ msg.model }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- AI 正在输入 -->
        <div v-if="typing" class="msg-wrapper bot">
          <div class="msg-row bot">
            <div class="bot-avatar"><img src="/renta-logo-mark.png" alt="RenTA" class="bot-logo thinking" /></div>
            <div class="bot-card typing-card">
              <div class="bot-card-head">
                <div class="bot-id">
                  <img src="/renta-logo-mark.png" alt="" class="bot-logo-mini" />
                  <span class="bot-name">RenTA</span>
                  <span class="bot-dot">·</span>
                  <span class="bot-model">{{ currentModel }}</span>
                </div>
                <span class="bot-status"><span class="status-dot"></span>正在思考</span>
              </div>
              <div class="typing-line">
                <span></span><span></span><span></span>
              </div>
            </div>
          </div>
        </div>

        <div class="scroll-anchor" ref="scrollAnchor"></div>
      </div>

      <!-- 输入栏 -->
      <div class="chat-footer">
        <div class="footer-inner">
          <div class="input-panel" :class="{ focused: inputFocused, hasText: input.length > 0 }">
            <div class="input-left">
              <button class="tool-btn" title="附加文件(即将推出)" disabled>
                <svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
                <span class="tool-tip">附加文件</span>
              </button>
            </div>
            <textarea
              ref="textareaRef"
              v-model="input"
              @keydown.enter.exact.prevent="send()"
              @keydown.enter.shift.exact="autoResize"
              @input="autoResize"
              @focus="inputFocused = true"
              @blur="inputFocused = false"
              placeholder="输入消息,Enter 发送,Shift + Enter 换行"
              rows="1"
              class="chat-textarea"
            ></textarea>
            <div class="input-right">
              <span v-if="input.length > 0" class="char-count">{{ input.length }}</span>
              <button class="send-btn" @click="send()" :disabled="!input.trim() || typing" title="发送 (Enter)">
                <svg v-if="!typing" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>
                <span v-if="!typing" class="send-pulse"></span>
              </button>
            </div>
          </div>
          <div class="footer-hint">
            <span>AI 生成内容可能不准确</span>
            <span v-if="totalTokens > 0" class="dot-sep">·</span>
            <span v-if="totalTokens > 0" class="mono">{{ totalTokens }} tokens</span>
            <span class="dot-sep">·</span>
            <span class="mono">Shift+Enter 换行</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 工作台面板 -->
    <aside class="workbench-panel" :class="{ open: showWorkbench, 'has-group-sim': groupSimOpen && !groupSimFullscreen }">
      <Workbench
        ref="workbenchRef"
        scene="office"
        :height="groupSimOpen && !groupSimFullscreen ? '18%' : '40%'"
        :show-progress="true"
        loading-text="工作台加载中..."
        @ready="onWorkbenchReady"
        @animation-change="onWorkbenchAnimationChange"
      />

          <!-- 内嵌多智能体执行卡片 (不弹全屏时显示) -->
      <div v-if="groupSimOpen && !groupSimFullscreen" class="wb-embedded-group">
        <header class="wb-embedded-head">
          <span class="wb-embedded-badge">真实执行</span>
          <span class="wb-embedded-progress">
            {{ groupSimRoles.filter(r => r.status === 'done').length }} / {{ groupSimRoles.length }} done
            <span v-if="groupSimFinishedAt" class="wb-embedded-cost">
              · {{ Math.round((groupSimFinishedAt - groupSimStartedAt) / 100) / 10 }}s
            </span>
          </span>
          <div class="wb-embedded-actions">
            <button class="wb-embedded-btn" @click="groupSimFullscreen = true" title="展开全屏">⛶</button>
            <button class="wb-embedded-btn" @click="closeGroupSim" title="关闭">×</button>
          </div>
        </header>
        <div class="wb-embedded-roles">
          <div
            v-for="role in groupSimRoles"
            :key="role.idx"
            class="wb-embedded-role"
            :class="['status-' + role.status]"
          >
            <div class="wb-embedded-role-head">
              <span class="wb-embedded-role-emoji">{{ role.palette?.emoji || '📄' }}</span>
              <span class="wb-embedded-role-name">{{ role.name }}</span>
              <span class="wb-embedded-role-status">
                <span :class="['wb-embedded-dot', 'dot-' + role.status]"></span>
                <span class="wb-embedded-status-text">{{ statusText(role.status) }}</span>
              </span>
            </div>
            <details v-if="role.status === 'done' && role.output" class="wb-embedded-output">
              <summary>📄 产物 ({{ role.outputLen }} 字符)</summary>
              <pre>{{ role.output.slice(0, 1500) }}{{ role.output.length > 1500 ? '\n\n... (展开看完整)' : '' }}</pre>
            </details>
            <div v-else-if="role.status === 'running'" class="wb-embedded-running">调用智能体中...</div>
            <div v-else-if="role.status === 'pending'" class="wb-embedded-pending">等待上游</div>
            <div v-else-if="role.status === 'error'" class="wb-embedded-error">失败 (可展开查看错误)</div>
          </div>
        </div>
        <footer v-if="groupSimFinishedAt" class="wb-embedded-footer">
          <button class="wb-embedded-export" @click="exportRunAsMarkdown">📥 导出 Markdown</button>
          <button class="wb-embedded-history" @click="toggleRunHistory">
            📚 历史 <span v-if="runHistory.length > 0" class="gs-run-badge">{{ runHistory.length }}</span>
          </button>
        </footer>
      </div>

      <!-- 下方 tab 切换: 日志 | 产物 -->
      <div class="wb-tabs">
        <button
          class="wb-tab"
          :class="{ active: wbTab === 'log' }"
          @click="wbTab = 'log'"
        >
          🤝 协同日志
          <span class="wb-tab-badge" v-if="agentLogs.length > 0">{{ agentLogs.length }}</span>
        </button>
        <button
          class="wb-tab"
          :class="{ active: wbTab === 'artifact' }"
          @click="wbTab = 'artifact'"
        >
          📦 产物列表
          <span class="wb-tab-badge" v-if="artifacts.length > 0">{{ artifacts.length }}</span>
        </button>
      </div>

      <div class="wb-tab-body">
        <!-- 日志 tab -->
        <AgentLog v-show="wbTab === 'log'" :messages="agentLogs" />

        <!-- 产物 tab -->
        <div v-show="wbTab === 'artifact'" class="wb-artifact-list">
          <div v-if="artifacts.length === 0" class="wb-artifact-empty">
            <div class="empty-ico">📦</div>
            <div>暂无产物</div>
            <div class="empty-sub">真实执行返回的 agent 产物会出现在这里</div>
          </div>
          <div
            v-for="a in [...artifacts].reverse()"
            :key="a.id"
            class="wb-artifact-item"
            :class="{ expanded: a.id === expandedArtifactId }"
          >
            <div class="wb-artifact-head" @click="toggleArtifact(a.id)">
              <div class="wb-artifact-ico">{{ a.icon || '📄' }}</div>
              <div class="wb-artifact-meta">
                <div class="wb-artifact-title">{{ a.title }}</div>
                <div class="wb-artifact-sub">
                  <span class="wb-artifact-agent">{{ a.agentName }}</span>
                  <span class="wb-artifact-time">{{ a.time }}</span>
                  <span class="wb-artifact-len">{{ a.content?.length || 0 }} 字符</span>
                </div>
              </div>
              <span class="wb-artifact-toggle">{{ a.id === expandedArtifactId ? '▼' : '▶' }}</span>
            </div>
            <div v-if="a.id === expandedArtifactId" class="wb-artifact-body">
              <iframe
                v-if="a.mime === 'text/html'"
                class="wb-artifact-html"
                sandbox="allow-scripts allow-same-origin"
                :srcdoc="a.content"
                title="HTML 产物预览"
              ></iframe>
              <pre v-else class="wb-artifact-content">{{ a.content }}</pre>
              <div class="wb-artifact-actions">
                <button class="wb-artifact-copy" @click.stop="copyArtifact(a)">
                  {{ a.copied ? '✓ 已复制' : '📋 复制' }}
                </button>
                <button class="wb-artifact-download" @click.stop="downloadArtifact(a)">
                  📥 下载
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </aside>

    <button v-if="showHistory" class="history-backdrop" type="button" aria-label="关闭对话历史" @click="toggleHistory"></button>

    <!-- 对话历史面板 -->
    <aside class="history-panel anim-panel-left" :class="{ open: showHistory, ready: chatReady }">
      <div class="history-brand-row">
        <div class="history-brand">
          <span class="history-brand-mark">
            <img src="/renta-logo-mark.png" alt="" />
          </span>
          <span class="history-brand-name">RenTA</span>
        </div>
        <button class="history-icon-btn" @click="toggleHistory" title="收起历史侧栏" aria-label="收起历史侧栏">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="5" width="16" height="14" rx="2"/><line x1="9" y1="5" x2="9" y2="19"/></svg>
        </button>
      </div>
      <button class="history-new-chat" @click="newChat" title="新对话">
        <span class="history-new-chat-icon" aria-hidden="true">
          <svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        </span>
        <span>新会话</span>
      </button>
      <div class="history-header">
        <span class="history-title">对话历史</span>
        <span class="history-count">{{ conversations.length }}</span>
      </div>
      <div class="history-search">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <input
          v-model="historySearch"
          type="text"
          placeholder="搜索会话..."
          class="history-search-input"
        />
      </div>
      <div class="history-list">
        <template v-for="(group, gi) in groupedConversations" :key="gi">
          <div class="history-group-label">{{ group.label }}</div>
          <div
            v-for="conv in group.items"
            :key="conv.id"
            class="history-item"
            :class="{ active: conv.id === activeConvId }"
            @click="loadConversation(conv.id)"
          >
            <span class="history-item-title">{{ conv.title }}</span>
            <span class="history-item-time">{{ formatTime(conv.createdAt) }}</span>
            <button class="history-delete-btn" @click.stop="deleteConversation(conv.id)" title="删除">
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
        </template>
        <div v-if="conversations.length === 0" class="history-empty">
          <div class="empty-ico">💬</div>
          <div>暂无对话记录</div>
          <div class="empty-sub">开启一段新对话,记录会自动保存在这里</div>
        </div>
      </div>
    </aside>

    <!-- ============================================================
         真实执行面板
         展示 mode-router 的 Orchestration trace 与真实 agent 执行记录
         ============================================================ -->
    <div v-if="groupSimOpen && groupSimFullscreen" class="group-sim-overlay" @click.self="closeGroupSim">
      <div class="group-sim-panel">
        <header class="group-sim-header">
          <div class="group-sim-title">
            <span class="group-sim-badge">真实执行</span>
            <h2>多智能体执行面板</h2>
            <p class="group-sim-task">任务: {{ groupSimTask }}</p>
          </div>
          <div class="group-sim-actions">
            <div class="group-sim-progress">
              <span>{{ groupSimRoles.filter(r => r.status === 'done').length }} / {{ groupSimRoles.length }} done</span>
              <span v-if="groupSimFinishedAt" class="group-sim-cost">
                耗时 {{ Math.round((groupSimFinishedAt - groupSimStartedAt) / 100) / 10 }}s
              </span>
            </div>
              <button class="group-sim-action-btn" @click="exportRunAsMarkdown" title="导出为 Markdown">
                📥 导出
              </button>
            <button class="group-sim-action-btn" @click="toggleRunHistory" title="查看历史 run">
              📚 历史 <span v-if="runHistory.length > 0" class="gs-run-badge">{{ runHistory.length }}</span>
            </button>
            <button class="group-sim-action-btn" @click="saveCurrentRun" :disabled="!groupSimFinishedAt" title="保存到本地">
              💾 保存
            </button>
            <button class="group-sim-action-btn" @click="groupSimFullscreen = false" title="最小化到工作台">⊟</button>
            <button class="group-sim-close" @click="closeGroupSim" aria-label="关闭">×</button>
          </div>
        </header>

        <div class="group-sim-body">
          <div v-if="groupSimRoles.length === 0" class="group-sim-empty">
            加载中...
          </div>
          <div v-else class="group-sim-roles">
            <div
              v-for="role in groupSimRoles"
              :key="role.idx"
              class="group-sim-role"
              :class="['status-' + role.status]"
            >
              <div class="role-header">
                <div class="role-avatar" :style="{ background: role.palette.bg }">
                  {{ role.palette.emoji }}
                </div>
                <div class="role-meta">
                  <div class="role-name">{{ role.name }}</div>
                  <div class="role-org" v-if="role.org">
                    {{ role.org }} · {{ role.dept || '—' }}
                  </div>
                </div>
                <div class="role-status">
                  <span v-if="role.status === 'pending'" class="status-dot dot-pending"></span>
                  <span v-else-if="role.status === 'running'" class="status-dot dot-running"></span>
                  <span v-else-if="role.status === 'done'" class="status-dot dot-done"></span>
                  <span v-else class="status-dot dot-error"></span>
                  <span class="status-text">{{ statusText(role.status) }}</span>
                </div>
              </div>

              <div class="role-skills">
                <span v-for="s in role.skills" :key="s" class="role-skill-tag">{{ s }}</span>
                <span v-if="role.skills.length === 0" class="role-skill-tag empty">未声明技能</span>
              </div>

              <div class="role-deps" v-if="role.dependsOn.length > 0">
                <span class="role-deps-label">依赖:</span>
                <span class="role-deps-ids">{{ role.dependsOn.map(d => d.slice(-12)).join(', ') }}</span>
              </div>

              <div class="role-progress-bar" v-if="role.status === 'running'">
                <div class="role-progress-fill"></div>
              </div>

              <details v-if="role.status === 'done'" class="role-output" open>
                <summary>
                  📄 产物 ({{ role.outputLen }} 字符) · 耗时 {{ role.endAt && role.startAt ? Math.round((role.endAt - role.startAt) / 100) / 10 : 0 }}s
                  <span v-if="role.feedbacks && role.feedbacks.length > 0" class="role-fb-badge">
                    🔁 {{ role.feedbacks.length }} 次反馈
                  </span>
                </summary>
                <pre>{{ role.output }}</pre>
                <div v-if="role.feedbacks && role.feedbacks.length > 0" class="role-fb-history">
                  <div v-for="(fb, i) in role.feedbacks" :key="i" class="role-fb-entry">
                    <div class="role-fb-entry-header">
                      <span class="role-fb-icon">💬</span>
                      <span class="role-fb-time">{{ fb.time }}</span>
                      <span v-if="fb.compressed" class="role-fb-compressed" title="上下文已压缩到 2600 字符">
                        ⏬ 已压缩
                      </span>
                    </div>
                    <div class="role-fb-text">{{ fb.text }}</div>
                  </div>
                </div>
              </details>

              <div v-if="role.status === 'pending'" class="role-waiting">
                ⏳ 等待上游完成 ({{ role.dependsOn.length }} 个依赖)...
              </div>
            </div>
          </div>
        </div>

        <footer class="group-sim-footer">
          <div class="group-sim-stats">
            <span>✅ done: {{ groupSimRoles.filter(r => r.status === 'done').length }}</span>
            <span>🔄 running: {{ groupSimRoles.filter(r => r.status === 'running').length }}</span>
            <span>⏳ pending: {{ groupSimRoles.filter(r => r.status === 'pending').length }}</span>
          </div>
          <div class="group-sim-tip">
            💡 这里展示的是后端真实执行记录。正式结果只保留在主消息和产物里，过程可以收起查看。
          </div>
        </footer>
      </div>

      <!-- 历史 run 抽屉 (右侧) -->
      <aside v-if="historyOpen" class="gs-history-drawer">
        <header class="gs-history-header">
          <h3>📚 历史执行</h3>
          <button class="gs-history-clear" @click="clearRunHistory" v-if="runHistory.length > 0">清空</button>
          <button class="gs-history-close" @click="historyOpen = false">×</button>
        </header>
        <div class="gs-history-list">
          <div v-if="runHistory.length === 0" class="gs-history-empty">
            <div class="empty-ico">📭</div>
            <div>暂无历史 run</div>
            <div class="empty-sub">完成一次真实执行后会自动保存</div>
          </div>
          <div
            v-for="run in runHistory"
            :key="run.id"
            class="gs-history-item"
            @click="openRunFromHistory(run)"
          >
            <div class="gs-history-item-head">
              <div class="gs-history-task">{{ run.task.slice(0, 40) }}{{ run.task.length > 40 ? '...' : '' }}</div>
              <span class="gs-history-mode">{{ run.mode || '?' }}</span>
            </div>
            <div class="gs-history-item-meta">
              <span>📅 {{ formatRunTime(run.startedAt) }}</span>
              <span>👥 {{ run.roles?.length || 0 }} agents</span>
              <span v-if="run.finishedAt">⏱️ {{ Math.round((run.finishedAt - run.startedAt) / 100) / 10 }}s</span>
            </div>
            <div class="gs-history-item-stats">
              <span class="gs-tag" :class="{ done: true }">✅ {{ run.roles?.filter(r => r.status === 'done').length || 0 }}</span>
              <span v-if="getTotalFeedbacks(run) > 0" class="gs-tag fb">🔁 {{ getTotalFeedbacks(run) }} 反馈</span>
            </div>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted, watch, inject } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { useToastStore } from '@/stores/toast'
import { useAuthStore } from '@/stores/auth'
import Workbench from '@/components/workbench/Workbench.vue'
import AgentLog from '@/components/AgentLog.vue'

const route = useRoute()
const router = useRouter()
const toast = useToastStore()
const auth = useAuthStore()
const openAppMenu = inject('openAppMenu', () => {})  // App.vue 提供的菜单打开方法

const goAccount = () => router.push('/account')

const messages = ref([])
const input = ref('')
const typing = ref(false)
const inputFocused = ref(false)
const bodyRef = ref(null)
const scrollAnchor = ref(null)
const textareaRef = ref(null)

const currentModel = 'DeepSeek-Chat'  // 固定默认模型(不再支持切换)

const showHistory = ref(false)
const historySearch = ref('')
const conversations = ref([])
const activeConvId = ref(null)
const saveTimer = ref(null)

const showWorkbench = ref(false)
const workbenchRef = ref(null)
const workbenchReady = ref(false)
const chatReady = ref(false)

// 工作台和历史互斥: 两个都绝对定位覆盖在 chat-main 上,同时开会重叠
const toggleHistory = () => {
  showHistory.value = !showHistory.value
  if (showHistory.value) showWorkbench.value = false
}
const toggleWorkbench = () => {
  showWorkbench.value = !showWorkbench.value
  if (showWorkbench.value) showHistory.value = false
}

/* ============================================================
 *  工作台 tab 切换: 日志 (默认) | 产物
 *  产物 (artifact) 全部来自后端真实响应 (role.output)
 *  每个产物: { id, title, agentName, time, content, icon, source, copied }
 * ============================================================ */
const wbTab = ref('log')                // 'log' | 'artifact'
const artifacts = ref([])                // 产物列表 (新→旧)
const expandedArtifactId = ref(null)     // 当前展开的产物
let artifactId = 0

const addArtifact = (entry) => {
  const content = entry.content || ''
  const mime = entry.mime || detectArtifactMime(content)
  const a = {
    id: 'a' + (++artifactId) + '_' + Date.now(),
    title: entry.title || '未命名产物',
    filename: entry.filename || '',
    agentName: entry.agentName || 'unknown',
    time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
    content,
    url: entry.url || entry.download_url || entry.downloadUrl || '',
    icon: entry.icon || '📄',
    source: entry.source || 'real-execution',
    mime,
    copied: false,
    expanded: false
  }
  artifacts.value.push(a)
  // 限制最多 100 条
  if (artifacts.value.length > 100) artifacts.value.shift()
  return a
}

const detectArtifactMime = (content) => {
  const text = String(content || '').trim().toLowerCase()
  if (text.startsWith('<!doctype html') || text.startsWith('<html') || (text.includes('<html') && text.includes('</html>'))) {
    return 'text/html'
  }
  return 'text/markdown'
}

const extractEmbeddedHtml = (content) => {
  const text = String(content || '').trim()
  if (!text) return ''
  const fenced = text.match(/```html\s*([\s\S]*?)```/i) || text.match(/```\s*(<!doctype html[\s\S]*?|<html[\s\S]*?)```/i)
  if (fenced?.[1]) return fenced[1].trim()
  const docStart = text.search(/<!doctype html|<html/i)
  if (docStart >= 0) {
    const fromDoc = text.slice(docStart)
    const close = fromDoc.toLowerCase().lastIndexOf('</html>')
    if (close >= 0) return fromDoc.slice(0, close + '</html>'.length).trim()
  }
  return ''
}

const extractPrimaryOutput = (content) => {
  const text = String(content || '').trim()
  if (!text) return ''
  const embeddedHtml = extractEmbeddedHtml(text)
  if (embeddedHtml) return embeddedHtml
  if (text.startsWith('{') || text.startsWith('[')) {
    try {
      const parsed = JSON.parse(text)
      const itemGroups = [
        parsed?.result?.products,
        parsed?.products,
        parsed?.result?.dataItems,
        parsed?.result?.data_items,
        parsed?.dataItems,
        parsed?.data_items
      ]
      for (const items of itemGroups) {
        if (!Array.isArray(items)) continue
        for (const item of items) {
          if (!item || typeof item !== 'object') continue
          const nestedItems = Array.isArray(item.dataItems) ? item.dataItems : (Array.isArray(item.data_items) ? item.data_items : null)
          if (nestedItems) {
            for (const nested of nestedItems) {
              if (!nested || typeof nested !== 'object') continue
              const nestedText = typeof nested.text === 'string' ? nested.text : (typeof nested.content === 'string' ? nested.content : '')
              const nestedHtml = extractEmbeddedHtml(nestedText)
              if (nestedHtml) return nestedHtml
              if (nestedText.trim()) return nestedText
            }
          }
          if (typeof item.content === 'string' && item.content.trim()) return item.content
          if (typeof item.text === 'string' && item.text.trim()) return item.text
        }
      }
      if (typeof parsed?.result?.content === 'string' && parsed.result.content.trim()) return parsed.result.content
      if (typeof parsed?.result?.text === 'string' && parsed.result.text.trim()) return parsed.result.text
      if (typeof parsed?.content === 'string' && parsed.content.trim()) return parsed.content
      if (typeof parsed?.text === 'string' && parsed.text.trim()) return parsed.text
    } catch {}
  }
  return text
}

const artifactDownloadName = (a) => {
  if (a.filename) return String(a.filename).split(/[\\/]/).pop()
  const ext = a.mime === 'text/html' ? 'html' : 'md'
  return `${a.id}_${a.title.slice(0, 30).replace(/[^\w\u4e00-\u9fa5-]/g, '_')}.${ext}`
}

const artifactKind = (a) => {
  const mime = String(a?.mime || '').toLowerCase()
  const filename = String(a?.filename || '').toLowerCase()
  if (mime.includes('html') || filename.endsWith('.html') || filename.endsWith('.htm')) return 'html'
  if (mime.includes('json') || filename.endsWith('.json')) return 'json'
  if (mime.includes('csv') || filename.endsWith('.csv')) return 'csv'
  if (mime.includes('text') || mime.includes('markdown') || filename.endsWith('.md') || filename.endsWith('.txt')) return 'text'
  return 'file'
}

const artifactKindLabel = (a) => {
  const kind = artifactKind(a)
  if (kind === 'html') return '网页预览'
  if (kind === 'json') return 'JSON 文件'
  if (kind === 'csv') return 'CSV 文件'
  if (kind === 'text') return '文本文件'
  return '文件'
}

const artifactSizeLabel = (a) => {
  const len = String(a?.content || '').length
  if (!len) return ''
  if (len > 1000000) return `${(len / 1000000).toFixed(1)}M 字符`
  if (len > 1000) return `${Math.round(len / 1000)}K 字符`
  return `${len} 字符`
}

const canPreviewArtifact = (a) => {
  if (a?.content) return ['html', 'json', 'csv', 'text'].includes(artifactKind(a))
  return Boolean(a?.url)
}

const artifactPreviewText = (a) => {
  const text = String(a?.content || '')
  if (!text) return a?.url ? `可通过链接打开: ${a.url}` : '暂无可预览内容'
  if (text.length <= 12000) return text
  return text.slice(0, 12000) + '\n...[预览已截断, 下载可查看完整文件]...'
}

const toggleMessageArtifact = (a) => {
  if (!a.content && a.url) {
    window.open(a.url, '_blank', 'noopener,noreferrer')
    return
  }
  a.expanded = !a.expanded
}

const toggleArtifact = (id) => {
  expandedArtifactId.value = expandedArtifactId.value === id ? null : id
}

const copyArtifact = async (a) => {
  try {
    await navigator.clipboard.writeText(a.content)
    a.copied = true
    setTimeout(() => { a.copied = false }, 2000)
  } catch {}
}

const downloadArtifact = (a) => {
  if (!a.content && a.url) {
    const link = document.createElement('a')
    link.href = a.url
    link.download = artifactDownloadName(a)
    link.target = '_blank'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    return
  }
  const blob = new Blob([a.content], { type: `${a.mime || 'text/markdown'};charset=utf-8` })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = artifactDownloadName(a)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
const agentLogs = ref([])
const logId = ref(0)

/* ============================================================
 *  真实执行面板
 *  - 展示 mode-router 返回的 execution.runs
 *  - 状态来自真实后端调用结果，不在前端伪造产物
 *  - 实时 addLog 到右侧 agentLogs
 * ============================================================ */
const groupSimOpen = ref(false)             // 面板显示
const groupSimFullscreen = ref(false)      // 是否用全屏 overlay (默认 false,改用工作台内嵌)
const groupSimTask = ref('')                  // 当前任务描述
const groupSimRoles = ref([])                 // [{ id, name, aic, skills, status, output, log, duration, dependsOn }]
const groupSimStartedAt = ref(null)
const groupSimFinishedAt = ref(null)
const groupSimRunId = ref(0)
const groupSimMode = ref('')                  // mode_0 / mode_1 / mode_2
const currentPlanSnapshot = ref(null)         // 触发本次执行的 plan (用于导出 + 历史)
const currentRouteSnapshot = ref(null)        // 路由分类
const currentRvSnapshot = ref(null)           // registry_validation

const ROLE_PALETTE = [
  { bg: 'linear-gradient(135deg, #6366f1, #4338ca)', emoji: '🧭' },  // 蓝紫 - search/planner
  { bg: 'linear-gradient(135deg, #10b981, #047857)', emoji: '🔬' },  // 绿 - analysis
  { bg: 'linear-gradient(135deg, #f59e0b, #d97706)', emoji: '✍️' },  // 黄 - writing
  { bg: 'linear-gradient(135deg, #ec4899, #be185d)', emoji: '⚙️' },  // 粉 - 实施/工程
  { bg: 'linear-gradient(135deg, #06b6d4, #0e7490)', emoji: '🧪' },  // 青 - QA
  { bg: 'linear-gradient(135deg, #8b5cf6, #6d28d9)', emoji: '🎨' },  // 紫 - 可视化
]

/* ============================================================
 *  真实执行面板状态
 *  由 /mode-router/orchestrator/execute 的 execution.runs 填充。
 * ============================================================ */
const closeGroupSim = () => {
  groupSimOpen.value = false
  groupSimRoles.value = []
}

const statusText = (s) => ({ pending: '等待', running: '执行中', done: '完成', error: '失败' }[s] || s)

/* ============================================================
 *  Persistence + 历史 run 抽屉
 *  - 自动: 全部 done 时落盘
 *  - 手动: header "💾 保存" 按钮
 *  - 列表: 抽屉显示所有 run
 *  - 复用: 点列表项重新打开 (只读模式)
 *  - 导出: 一键 Markdown
 *  仿 mode-router 真实 literature_runs/ 目录结构
 * ============================================================ */
const RUNS_STORAGE_KEY = 'mavis_group_runs_v1'
const runHistory = ref([])          // [{ id, task, mode, startedAt, finishedAt, plan, roles, route, rv }]
const historyOpen = ref(false)
const currentRunId = ref(null)      // 当前面板关联的 run id (只读模式时 = 历史 id)
const isViewingHistory = ref(false)

const loadRunHistory = () => {
  try {
    const raw = localStorage.getItem(RUNS_STORAGE_KEY)
    runHistory.value = raw ? JSON.parse(raw) : []
  } catch { runHistory.value = [] }
}

const persistRunHistory = () => {
  try {
    localStorage.setItem(RUNS_STORAGE_KEY, JSON.stringify(runHistory.value))
  } catch (e) {
    console.warn('[execution-panel] persist failed', e)
  }
}

const snapshotRoles = () => groupSimRoles.value.map(r => ({
  idx: r.idx, aic: r.aic, name: r.name, org: r.org, dept: r.dept,
  objective: r.objective, skills: r.skills, endpoint: r.endpoint,
  dispatchMode: r.dispatchMode, dependsOn: r.dependsOn,
  palette: r.palette, status: r.status,
  output: r.output, outputLen: r.outputLen,
  startAt: r.startAt, endAt: r.endAt,
  feedbacks: r.feedbacks || []
}))

const buildCurrentRun = () => ({
  id: currentRunId.value || ('run_' + Date.now() + '_' + Math.random().toString(36).slice(2, 6)),
  task: groupSimTask.value,
  mode: groupSimMode.value,
  plan: currentPlanSnapshot.value,
  route: currentRouteSnapshot.value,
  rv: currentRvSnapshot.value,
  roles: snapshotRoles(),
  startedAt: groupSimStartedAt.value,
  finishedAt: groupSimFinishedAt.value || Date.now(),
  feedbacksCount: groupSimRoles.value.reduce((s, r) => s + (r.feedbacks?.length || 0), 0)
})

const saveCurrentRun = () => {
  if (!groupSimFinishedAt.value) {
    addLog('系统', '请等待执行完成', 'info', '#888')
    return
  }
  const run = buildCurrentRun()
  const idx = runHistory.value.findIndex(r => r.id === run.id)
  if (idx >= 0) runHistory.value[idx] = run
  else runHistory.value.unshift(run)
  if (runHistory.value.length > 50) runHistory.value = runHistory.value.slice(0, 50)
  currentRunId.value = run.id
  persistRunHistory()
  addLog('系统', `已保存 run #${run.id.slice(-8)} (${runHistory.value.length} 个历史)`, 'result', '#10b981')
}

const toggleRunHistory = () => {
  historyOpen.value = !historyOpen.value
}

const clearRunHistory = () => {
  if (!confirm('清空所有历史 run?此操作不可恢复。')) return
  runHistory.value = []
  persistRunHistory()
}

const getTotalFeedbacks = (run) => (run.roles || []).reduce((s, r) => s + (r.feedbacks?.length || 0), 0)

const formatRunTime = (ts) => {
  if (!ts) return '?'
  const d = new Date(ts)
  const now = new Date()
  const sameDay = d.toDateString() === now.toDateString()
  const pad = (n) => String(n).padStart(2, '0')
  return sameDay
    ? `${pad(d.getHours())}:${pad(d.getMinutes())}`
    : `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const openRunFromHistory = (run) => {
  // 只读模式打开历史 run
  isViewingHistory.value = true
  currentRunId.value = run.id
  groupSimTask.value = run.task
  groupSimMode.value = run.mode
  currentPlanSnapshot.value = run.plan
  currentRouteSnapshot.value = run.route
  currentRvSnapshot.value = run.rv
  groupSimStartedAt.value = run.startedAt
  groupSimFinishedAt.value = run.finishedAt
  // 恢复 roles (只读, 重新计算 log id 等不重置)
  groupSimRoles.value = (run.roles || []).map(r => ({
    ...r,
    feedbackOpen: false,
    feedbackDraft: '',
    feedbackPending: false,
    log: []
  }))
  historyOpen.value = false
  groupSimOpen.value = true
  addLog('系统', `已加载历史 run #${run.id.slice(-8)} (只读模式)`, 'info', '#6366f1')
}

const exportRunAsMarkdown = () => {
  const run = buildCurrentRun()
  const lines = []
  lines.push(`# ${run.task}`)
  lines.push('')
  lines.push(`> Run ID: \`${run.id}\``)
  lines.push(`> Mode: \`${run.mode}\``)
  lines.push(`> 开始: ${new Date(run.startedAt).toISOString()}`)
  lines.push(`> 结束: ${run.finishedAt ? new Date(run.finishedAt).toISOString() : '未完成'}`)
  lines.push(`> 耗时: ${run.finishedAt ? Math.round((run.finishedAt - run.startedAt) / 100) / 10 : '?'}s`)
  lines.push(`> Agent 数: ${run.roles.length}`)
  lines.push(`> 反馈次数: ${run.feedbacksCount}`)
  lines.push('')
  lines.push('---')
  lines.push('')
  if (run.route) {
    lines.push('## 路由决策')
    lines.push('')
    lines.push('- Label: `' + (run.route.label || '?') + '`')
    lines.push('- Mode: `' + (run.route.mode || '?') + '`')
    if (run.route.scores) {
      const s = run.route.scores
      lines.push('- 评分: ' + `LLM=${s.LLM?.toFixed?.(2)} · Agent=${s.Agent?.toFixed?.(2)} · 多Agent=${s['多Agent']?.toFixed?.(2)}`)
    }
    lines.push('')
  }
  if (run.rv) {
    lines.push('## Dispatch Guard')
    lines.push('')
    lines.push(`- Status: \`${run.rv.status}\``)
    lines.push(`- Checked: ${run.rv.checked_agents}`)
    lines.push(`- Blocked: ${(run.rv.blocked_agents || []).length}`)
    lines.push('')
  }
  lines.push('## 执行产物')
  lines.push('')
  run.roles.forEach((r, i) => {
    lines.push(`### ${i + 1}. ${r.name}`)
    lines.push('')
    if (r.org) lines.push(`- **提供方**: ${r.org} · ${r.dept || '—'}`)
    if (r.skills.length > 0) lines.push(`- **技能**: ${r.skills.join(' / ')}`)
    if (r.endpoint) lines.push(`- **端点**: \`${r.endpoint}\``)
    if (r.dependsOn.length > 0) lines.push(`- **依赖**: ${r.dependsOn.map(d => '`' + d.slice(-12) + '`').join(', ')}`)
    lines.push(`- **状态**: ${statusText(r.status)} · 产物 ${r.outputLen} 字符`)
    if (r.feedbacks && r.feedbacks.length > 0) {
      lines.push(`- **反馈** (${r.feedbacks.length} 次):`)
      r.feedbacks.forEach((fb, j) => {
        const compressed = fb.compressed ? ' _(已压缩)_' : ''
        lines.push(`  ${j + 1}. [${fb.time}]${compressed} ${fb.text}`)
      })
    }
    lines.push('')
    lines.push('```markdown')
    lines.push(r.output || '(无输出)')
    lines.push('```')
    lines.push('')
  })
  lines.push('---')
  lines.push('')
  lines.push('*Generated by RenTA real execution · ' + new Date().toISOString() + '*')
  const md = lines.join('\n')
  // 触发下载
  const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${run.id}_${run.task.slice(0, 30).replace(/[^\w\u4e00-\u9fa5-]/g, '_')}.md`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  addLog('系统', `已导出 Markdown: ${a.download}`, 'result', '#10b981')
}

function addLog(agent, text, type = 'info', color = '#888') {
  agentLogs.value.push({ id: ++logId.value, agent, text, type, color, time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) })
  if (agentLogs.value.length > 50) agentLogs.value.shift()
}

/* ---------- 时间 / 招呼 ---------- */
const currentDate = computed(() => {
  const d = new Date()
  return `${d.getMonth() + 1}月${d.getDate()}日`
})
const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 5) return 'CHAT · Late Night'
  if (h < 11) return 'CHAT · Good Morning'
  if (h < 14) return 'CHAT · Good Afternoon'
  if (h < 18) return 'CHAT · Good Afternoon'
  if (h < 22) return 'CHAT · Good Evening'
  return 'CHAT · Late Night'
})

const suggestionGroups = [
  {
    label: '上手指南',
    items: [
      '如何创建一个新的智能体?',
      '智能体应用商店有哪些推荐?'
    ]
  },
  {
    label: '进阶使用',
    items: [
      '帮我优化智能体的描述',
      '智能体如何设置收费模式?',
      '查看我的智能体使用情况',
      '智能体 API 调用指南'
    ]
  }
]

const activeConvTitle = computed(() => {
  if (!activeConvId.value) return ''
  const conv = conversations.value.find(c => c.id === activeConvId.value)
  return conv ? conv.title : ''
})

const formatMessageTime = (ts) => {
  if (!ts) {
    const d = new Date()
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  const d = new Date(ts)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

marked.setOptions({ breaks: true, gfm: true })

const renderMarkdown = (text) => {
  if (!text) return ''
  try { return DOMPurify.sanitize(marked.parse(text)) }
  catch { return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;') }
}

/* ---------- 给 <pre> 代码块注入"复制 + 语言标签"按钮 ---------- */
const bindMarkdownRef = (el, msgIdx) => {
  if (!el) return
  nextTick(() => {
    const blocks = el.querySelectorAll('pre')
    blocks.forEach((pre) => {
      if (pre.dataset.enhanced) return
      pre.dataset.enhanced = '1'
      // 提取语言:从 class="language-xxx" 或第一个词
      const code = pre.querySelector('code')
      let lang = ''
      if (code) {
        const m = (code.className || '').match(/language-([\w-]+)/)
        lang = m ? m[1] : ''
      }
      // 包装一层
      const wrap = document.createElement('div')
      wrap.className = 'code-block'
      pre.parentNode.insertBefore(wrap, pre)
      wrap.appendChild(pre)
      // 顶部栏
      const bar = document.createElement('div')
      bar.className = 'code-bar'
      bar.innerHTML = `
        <div class="code-bar-left">
          <span class="code-dots">
            <span></span><span></span><span></span>
          </span>
          <span class="code-lang">${lang || 'text'}</span>
        </div>
        <button class="code-copy" type="button">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
          <span>复制</span>
        </button>
      `
      wrap.insertBefore(bar, pre)
      // 复制行为
      bar.querySelector('.code-copy').addEventListener('click', async () => {
        const txt = code ? code.innerText : pre.innerText
        try {
          await navigator.clipboard.writeText(txt)
          const span = bar.querySelector('.code-copy span')
          const orig = span.textContent
          span.textContent = '已复制'
          bar.querySelector('.code-copy').classList.add('copied')
          setTimeout(() => {
            span.textContent = orig
            bar.querySelector('.code-copy').classList.remove('copied')
          }, 1600)
        } catch { /* ignore */ }
      })
    })
  })
}

const totalTokens = computed(() => messages.value.reduce((s, m) => s + (m.tokens || 0), 0))

const STORAGE_KEY = 'chat_conversations'

const loadConversations = () => {
  try { const raw = localStorage.getItem(STORAGE_KEY); if (raw) conversations.value = JSON.parse(raw) }
  catch { conversations.value = [] }
}
const saveConversations = () => { localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations.value)) }

const syncCurrentConv = () => {
  if (!activeConvId.value || messages.value.length === 0) return
  const conv = conversations.value.find(c => c.id === activeConvId.value)
  if (!conv) return
  conv.messages = JSON.parse(JSON.stringify(messages.value))
  conv.model = currentModel
  saveConversations()
}

const autoSave = () => { clearTimeout(saveTimer.value); saveTimer.value = setTimeout(syncCurrentConv, 500) }

const createConversation = () => {
  const id = Date.now().toString(36) + Math.random().toString(36).slice(2, 6)
  const conv = { id, title: '新对话', messages: [], model: currentModel, createdAt: Date.now() }
  conversations.value.unshift(conv); saveConversations()
  return conv
}

const updateConvTitle = () => {
  const conv = conversations.value.find(c => c.id === activeConvId.value)
  if (!conv || conv.title !== '新对话') return
  const firstUser = messages.value.find(m => m.role === 'user')
  if (firstUser) { conv.title = firstUser.content.slice(0, 24) + (firstUser.content.length > 24 ? '…' : ''); saveConversations() }
}

const newChat = () => { messages.value = []; input.value = ''; typing.value = false; activeConvId.value = null; autoResize() }

const loadConversation = (id) => {
  const conv = conversations.value.find(c => c.id === id)
  if (!conv) return
  activeConvId.value = id; messages.value = JSON.parse(JSON.stringify(conv.messages))
  if (conv.model) {/* 模型固定,忽略存储的 model 字段 */}
  scrollDown()
}

const deleteConversation = (id) => {
  conversations.value = conversations.value.filter(c => c.id !== id)
  if (activeConvId.value === id) { activeConvId.value = null; messages.value = [] }
  saveConversations()
}

const formatTime = (ts) => {
  const d = new Date(ts); const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  const time = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  if (isToday) return time
  return `${d.getMonth() + 1}/${d.getDate()}`
}

/* 按日期分组(今天 / 昨天 / 更早) */
const groupedConversations = computed(() => {
  const q = historySearch.value.trim().toLowerCase()
  const filtered = q
    ? conversations.value.filter(c => (c.title || '').toLowerCase().includes(q))
    : conversations.value

  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const yesterday = today - 86400000
  const week = today - 7 * 86400000

  const groups = [
    { label: '今天', items: [] },
    { label: '昨天', items: [] },
    { label: '本周', items: [] },
    { label: '更早', items: [] }
  ]
  filtered.forEach(c => {
    const t = c.createdAt || 0
    if (t >= today) groups[0].items.push(c)
    else if (t >= yesterday) groups[1].items.push(c)
    else if (t >= week) groups[2].items.push(c)
    else groups[3].items.push(c)
  })
  return groups.filter(g => g.items.length > 0)
})

watch(() => messages.value.length, () => { autoSave() }, { flush: 'post' })

const estimateTokens = (text) => {
  if (!text) return 0
  let tokens = 0
  for (const ch of text) {
    const code = ch.codePointAt(0)
    if (code >= 0x4e00 && code <= 0x9fff) tokens += 1
    else if (code >= 0x3000 && code <= 0x303f) tokens += 1
    else if (code >= 0xff00 && code <= 0xffef) tokens += 1
    else if (/\s/.test(ch)) tokens += 0.25
    else tokens += 0.25
  }
  return Math.round(tokens)
}

const createBotMessage = (content, thinking = '', tokens = null, artifacts = []) => ({
  role: 'bot', content, thinking, thinkingTitle: thinking ? 'Orchestration trace / 真实执行过程' : '', thinkingOpen: false, copied: false, liked: false, disliked: false,
  tokens: tokens ?? (estimateTokens(content) + estimateTokens(thinking)),
  model: currentModel, time: Date.now(), artifacts
})

const scrollDown = () => { nextTick(() => { scrollAnchor.value?.scrollIntoView({ behavior: 'smooth' }) }) }
const autoResize = () => { const el = textareaRef.value; if (!el) return; el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 160) + 'px' }
const sendSuggestion = (text) => send(text)

const PLATFORM_BASE_URL = 'http://10.126.126.8:8888'

const _routeModeRouterExecute = async (query) => {
  const payload = {
    task: query,
    registry_url: PLATFORM_BASE_URL,
    discovery_url: `${PLATFORM_BASE_URL}/acps-adp-v2/discover`,
    limit: 20,
    save_report: false,
    candidate_source: 'registry_public_recent',
    execution_transport: 'http_jsonrpc',
    timeout: 180,
    agent_timeout: 0,
    execution_timeout: 0,
    max_concurrent_agents: 8,
    requester_user_id: auth.userId || '',
    hints: {
      requires_independent_roles: true,
      parallelizable: true
    }
  }
  const r = await fetch(`${PLATFORM_BASE_URL}/mode-router/orchestrator/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  const text = await r.text()
  if (!r.ok) {
    throw new Error(`HTTP ${r.status} — ${text.slice(0, 400)}`)
  }
  return JSON.parse(text)
}

const formatOrchestrationTrace = (resp, task) => {
  const route = resp.route_classification || {}
  const plan = resp.plan || {}
  const execution = resp.execution || {}
  const lines = []
  lines.push(`### Orchestration trace`)
  lines.push(`- Task: ${task}`)
  if (route.label || plan.mode) {
    lines.push(`- Route: ${route.label || '?'} → \`${plan.mode || '?'}\` · strategy \`${plan.strategy || '?'}\``)
  }
  if (route.scores) {
    const s = route.scores
    lines.push(`- Scores: LLM=${s.LLM?.toFixed?.(2)} · Agent=${s.Agent?.toFixed?.(2)} · MultiAgent=${s['多Agent']?.toFixed?.(2)}`)
  }
  if (resp.candidate_source) {
    lines.push(`- Candidate source: \`${resp.candidate_source}\``)
  }
  if (resp.normalized_skill_count !== undefined) {
    lines.push(`- Normalized skills: ${resp.normalized_skill_count}`)
  }
  if (plan.work_packages?.length) {
    lines.push(`- Work packages: ${plan.work_packages.length}`)
    plan.work_packages.forEach((wp, idx) => {
      const agent = wp.agent || {}
      const aic = agent.aic || wp.aic || '?'
      const name = agent.name || wp.agent_name || wp.objective || `Package ${idx + 1}`
      lines.push(`  - ${idx + 1}. ${name} (${aic})`)
      if (wp.endpoint) lines.push(`    - endpoint: ${wp.endpoint}`)
      if (wp.depends_on?.length) lines.push(`    - depends_on: ${wp.depends_on.join(', ')}`)
    })
  }
  if (execution.status) {
    lines.push(`- Execution status: \`${execution.status}\``)
  }
  return lines.join('\n')
}

const formatExecutionTrace = (resp) => {
  const execution = resp.execution || {}
  const runs = execution.runs || []
  const lines = []
  lines.push(`### Real execution`)
  if (execution.message) lines.push(`- ${execution.message}`)
  if (execution.final_result) {
    lines.push('- Final result ready')
  }
  runs.forEach((run, idx) => {
    const name = run.agent_name || run.agent?.name || run.package_id || `run-${idx + 1}`
    lines.push(`- ${idx + 1}. ${name}`)
    if (run.endpoint) lines.push(`  - endpoint: ${run.endpoint}`)
    lines.push(`  - status: ${run.status || '?'}`)
    lines.push(`  - agent_rpc_called: ${run.agent_rpc_called ? 'true' : 'false'}`)
    if (run.duration_ms !== undefined) lines.push(`  - duration_ms: ${run.duration_ms}`)
    if (run.error) lines.push(`  - error: ${String(run.error).slice(0, 300)}`)
  })
  return lines.join('\n')
}

const summarizeExecutionResult = (resp) => {
  const execution = resp.execution || {}
  const finalText = extractPrimaryOutput(execution.final_result || resp.final_result || '')
  const runs = execution.runs || []
  if (finalText) {
    if (detectArtifactMime(finalText) === 'text/html') {
      return { text: '已生成可视化文件，文件产物已附在下方，可直接预览或下载。', mime: 'text/markdown' }
    }
    return { text: finalText, mime: 'text/markdown' }
  }
  const htmlRun = [...runs].reverse().find(run => {
    const text = extractPrimaryOutput(run.output_text || '').trim().toLowerCase()
    return text.startsWith('<html') || text.includes('<html') || text.startsWith('<!doctype html')
  })
  if (htmlRun?.output_text) {
    return { text: '已生成可视化文件，文件产物已附在下方，可直接预览或下载。', mime: 'text/markdown' }
  }
  return { text: execution.message || '无正式结果', mime: 'text/markdown' }
}

const mergeRunsIntoArtifacts = (resp) => {
  const execution = resp.execution || {}
  const runs = execution.runs || []
  const inlineArtifacts = []
  const executionArtifacts = Array.isArray(execution.artifacts) ? execution.artifacts : []
  executionArtifacts.forEach((entry, idx) => {
    const content = extractPrimaryOutput(entry.content || '')
    const item = addArtifact({
      title: entry.title || entry.filename || `文件 ${idx + 1}`,
      filename: entry.filename || '',
      agentName: entry.agent_name || entry.agentName || entry.package_id || 'Mode Router',
      content,
      url: entry.url || entry.download_url || entry.downloadUrl || '',
      mime: entry.mime || detectArtifactMime(content),
      icon: detectArtifactMime(content) === 'text/html' ? '🌐' : '📄',
      source: entry.source || 'execution-artifact'
    })
    inlineArtifacts.push(item)
  })
  if (inlineArtifacts.length > 0) return inlineArtifacts

  runs.forEach((run, idx) => {
    const content = extractPrimaryOutput(run.output_text || '')
    if (!content || detectArtifactMime(content) !== 'text/html') return
    const item = addArtifact({
      title: run.agent_name || run.agent?.name || run.package_id || `运行 ${idx + 1}`,
      agentName: run.agent_name || run.agent?.name || run.package_id || 'unknown',
      content,
      mime: detectArtifactMime(content),
      icon: detectArtifactMime(content) === 'text/html' ? '🌐' : '📄',
      source: 'real-execution'
    })
    inlineArtifacts.push(item)
  })
  return inlineArtifacts
}

const send = async (textOverride, options = {}) => {
  const text = (textOverride !== undefined ? textOverride : input.value).trim()
  if (!text || typing.value) return
  if (!activeConvId.value) { const conv = createConversation(); activeConvId.value = conv.id }

  workbenchRef.value?.triggerEvent('userSendMessage')
  agentLogs.value = []
  addLog('用户', text, 'info', '#0f0f0f')

  if (options.skipUserMessage !== true) {
    messages.value.push({ role: 'user', content: text, time: Date.now() })
  }
  input.value = ''; autoResize(); scrollDown(); typing.value = true; syncCurrentConv()

  workbenchRef.value?.triggerEvent('aiThinking')
  addLog('RenTA', '正在分析问题...', 'thinking', '#4a8db5')

  try {
    const resp = await _routeModeRouterExecute(text)
    const traceText = formatOrchestrationTrace(resp, text)
    const execText = formatExecutionTrace(resp)
    const result = summarizeExecutionResult(resp)
    const inlineArtifacts = mergeRunsIntoArtifacts(resp)

    const bot = createBotMessage(result.text, [traceText, execText].filter(Boolean).join('\n\n'), estimateTokens(traceText) + estimateTokens(execText) + estimateTokens(result.text), inlineArtifacts)
    bot.thinkingOpen = true
    if (typeof options.insertBotAt === 'number' && options.insertBotAt >= 0 && options.insertBotAt <= messages.value.length) {
      messages.value.splice(options.insertBotAt, 0, bot)
    } else {
      messages.value.push(bot)
    }

    const execution = resp.execution || {}
    const executionRuns = execution.runs || []
    groupSimTask.value = text
    groupSimRoles.value = executionRuns.map((run, idx) => {
      const agent = run.agent || {}
      const output = extractPrimaryOutput(run.output_text || '')
      return {
        idx,
        aic: run.agent_aic || agent.aic || '',
        name: run.agent_name || agent.name || run.package_id || `角色${idx + 1}`,
        org: agent.provider?.organization || agent.organization || '',
        dept: agent.provider?.department || agent.department || '',
        objective: run.objective || '',
        skills: (run.skills || []).map(s => s.skill_name || s.skillid).filter(Boolean),
        endpoint: run.endpoint || '',
        dispatchMode: (run.depends_on || []).length > 0 ? 'sequential' : 'parallel',
        dependsOn: run.depends_on || [],
        status: run.status === 'completed' ? 'done' : 'error',
        output,
        outputLen: output.length,
        startAt: Date.now() - Math.max(0, run.duration_ms || 0),
        endAt: Date.now(),
        log: [],
        feedbacks: [],
        feedbackOpen: false,
        feedbackDraft: '',
        feedbackPending: false,
        palette: ROLE_PALETTE[idx % ROLE_PALETTE.length]
      }
    })
    groupSimStartedAt.value = Date.now()
    groupSimFinishedAt.value = Date.now()
    groupSimRunId.value++
    groupSimOpen.value = executionRuns.length > 0
    groupSimFullscreen.value = false
    currentPlanSnapshot.value = resp.plan || null
    currentRouteSnapshot.value = resp.route_classification || null
    currentRvSnapshot.value = resp.plan?.registry_validation || null
    groupSimMode.value = resp.plan?.mode || ''
    currentRunId.value = null
    isViewingHistory.value = false
    addLog('系统', `执行完成: ${execution.status || 'unknown'}`, execution.status === 'done' ? 'result' : 'error', execution.status === 'done' ? '#10b981' : '#ef4444')
  } catch (e) {
    const errText = `❌ **真实执行失败**\n\n\`\`\`\n${e.message}\n\`\`\``
    const bot = createBotMessage(errText, '', estimateTokens(errText))
    if (typeof options.insertBotAt === 'number' && options.insertBotAt >= 0 && options.insertBotAt <= messages.value.length) {
      messages.value.splice(options.insertBotAt, 0, bot)
    } else {
      messages.value.push(bot)
    }
    addLog('系统', e.message.slice(0, 120), 'error', '#ef4444')
    groupSimOpen.value = false
  } finally {
    typing.value = false
    workbenchRef.value?.triggerEvent('aiResponse')
    updateConvTitle(); syncCurrentConv(); scrollDown()
  }
}

const regenerate = async (index) => {
  const userMsg = [...messages.value.slice(0, index)].reverse().find(m => m.role === 'user')
  if (!userMsg) { toast.warning('找不到原问题'); return }
  messages.value.splice(index, 1)
  await send(userMsg.content, { skipUserMessage: true, insertBotAt: index })
}

const copyMessage = async (msg) => {
  try { await navigator.clipboard.writeText(msg.content); msg.copied = true; setTimeout(() => msg.copied = false, 2000) }
  catch { toast.error('复制失败') }
}

const onWorkbenchReady = () => { workbenchReady.value = true }
const onWorkbenchAnimationChange = (animName) => { console.debug('Workbench animation:', animName) }

onMounted(async () => {
  loadConversations()
  loadRunHistory()
  // 前端只调用 mode-router 主链路；是否选择广场智能体由后端按 mode 决定。
  const msg = route.query.message
  if (msg) {
    input.value = msg
    await nextTick()
    try { await send() } catch {}
  }
  nextTick(() => { chatReady.value = true })
})

onUnmounted(() => { if (saveTimer.value) clearTimeout(saveTimer.value) })
</script>

/* ============================================================
   真实执行面板
   ============================================================ */
.group-sim-overlay {
  position: fixed; inset: 0; z-index: 50;
  background: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center;
  padding: 24px;
  animation: gsFadeIn 0.25s var(--ease-out);
}
@keyframes gsFadeIn { from { opacity: 0 } to { opacity: 1 } }

.group-sim-panel {
  width: 100%; max-width: 1400px; height: 90vh;
  background: var(--bg-page);
  border-radius: 16px;
  display: flex; flex-direction: column;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.35);
  overflow: hidden;
  animation: gsSlideUp 0.35s var(--ease-out);
}
@keyframes gsSlideUp { from { transform: translateY(20px); opacity: 0 } to { transform: translateY(0); opacity: 1 } }

.group-sim-header {
  display: flex; align-items: flex-start; justify-content: space-between;
  padding: 20px 28px;
  background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
  color: #f1f5f9;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.group-sim-title h2 { margin: 6px 0 4px; font-size: 18px; font-weight: 600 }
.group-sim-badge {
  display: inline-block; padding: 4px 10px;
  background: rgba(99, 102, 241, 0.2); color: #c7d2fe;
  border-radius: 12px; font-size: 12px; font-weight: 600;
  letter-spacing: 0.5px;
}
.group-sim-task { margin: 0; font-size: 13px; color: #94a3b8; max-width: 800px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.group-sim-actions { display: flex; align-items: center; gap: 16px }
.group-sim-progress { display: flex; flex-direction: column; align-items: flex-end; font-size: 13px; gap: 4px }
.group-sim-progress span:first-child { color: #10b981; font-weight: 600 }
.group-sim-cost { color: #94a3b8; font-size: 12px }
.group-sim-close {
  background: rgba(255, 255, 255, 0.08); border: none; color: #f1f5f9;
  width: 32px; height: 32px; border-radius: 50%;
  font-size: 20px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: background 0.2s;
}
.group-sim-close:hover { background: rgba(239, 68, 68, 0.4) }

.group-sim-body {
  flex: 1; overflow: auto; padding: 24px 28px;
  background: #f8fafc;
}
.group-sim-empty { text-align: center; padding: 60px; color: #94a3b8 }

.group-sim-roles {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
  align-items: start;
}

.group-sim-role {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  border: 1px solid #e2e8f0;
  transition: all 0.3s var(--ease-out);
  position: relative;
  overflow: hidden;
}
.group-sim-role::before {
  content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
  background: #cbd5e1;
  transition: background 0.3s;
}
.group-sim-role.status-running { border-color: #3b82f6; box-shadow: 0 4px 20px rgba(59, 130, 246, 0.2) }
.group-sim-role.status-running::before { background: #3b82f6 }
.group-sim-role.status-done { border-color: #10b981; box-shadow: 0 4px 20px rgba(16, 185, 129, 0.15) }
.group-sim-role.status-done::before { background: #10b981 }
.group-sim-role.status-error { border-color: #ef4444 }
.group-sim-role.status-error::before { background: #ef4444 }

.role-header { display: flex; align-items: center; gap: 10px; margin-bottom: 12px }
.role-avatar {
  width: 40px; height: 40px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 20px; color: #fff;
  flex-shrink: 0;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
}
.role-meta { flex: 1; min-width: 0 }
.role-name { font-weight: 600; font-size: 14px; color: #0f172a;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.role-org { font-size: 11px; color: #64748b; margin-top: 2px }

.role-status { display: flex; align-items: center; gap: 6px; flex-shrink: 0 }
.status-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: #cbd5e1;
}
.dot-pending { background: #cbd5e1 }
.dot-running { background: #3b82f6; box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.6);
  animation: dotPulse 1.2s infinite }
@keyframes dotPulse {
  0% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.6) }
  70% { box-shadow: 0 0 0 6px rgba(59, 130, 246, 0) }
  100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0) }
}
.dot-done { background: #10b981 }
.dot-error { background: #ef4444 }
.status-text { font-size: 12px; color: #64748b; font-weight: 500 }

.role-skills { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px }
.role-skill-tag {
  background: #f1f5f9; color: #475569;
  padding: 3px 8px; border-radius: 6px; font-size: 11px;
  border: 1px solid #e2e8f0;
}
.role-skill-tag.empty { color: #94a3b8; font-style: italic }

.role-deps {
  font-size: 11px; color: #64748b;
  background: #fef3c7; border: 1px solid #fde68a;
  padding: 6px 10px; border-radius: 6px;
  margin-bottom: 10px;
}
.role-deps-label { font-weight: 600; color: #92400e; margin-right: 4px }
.role-deps-ids { font-family: ui-monospace, monospace; font-size: 10px; color: #78350f }

.role-progress-bar {
  height: 3px; background: #e2e8f0; border-radius: 2px;
  overflow: hidden; margin-bottom: 10px;
}
.role-progress-fill {
  height: 100%; background: linear-gradient(90deg, #3b82f6, #60a5fa);
  animation: progressIndeterminate 1.4s infinite ease-in-out;
}
@keyframes progressIndeterminate {
  0% { width: 0%; margin-left: 0 }
  50% { width: 70%; margin-left: 15% }
  100% { width: 0%; margin-left: 100% }
}

.role-output { margin-top: 8px }
.role-output summary {
  cursor: pointer; font-size: 12px; color: #10b981;
  font-weight: 600; padding: 6px 0;
  list-style: none;
}
.role-output summary::-webkit-details-marker { display: none }
.role-output summary::before { content: '▶ '; font-size: 9px; margin-right: 4px }
.role-output[open] summary::before { content: '▼ ' }
.role-output pre {
  background: #f8fafc; border: 1px solid #e2e8f0;
  padding: 12px; border-radius: 8px; font-size: 12px;
  line-height: 1.6; color: #334155;
  white-space: pre-wrap; word-wrap: break-word;
  max-height: 280px; overflow: auto;
  font-family: ui-monospace, monospace;
  margin: 8px 0 0;
}

.role-waiting {
  font-size: 12px; color: #94a3b8;
  padding: 12px; text-align: center;
  background: #f8fafc; border-radius: 8px;
  border: 1px dashed #cbd5e1;
}

.group-sim-footer {
  padding: 12px 28px;
  background: #fff;
  border-top: 1px solid #e2e8f0;
  display: flex; align-items: center; justify-content: space-between;
  gap: 16px;
}
.group-sim-stats { display: flex; gap: 16px; font-size: 12px; color: #64748b; font-weight: 500 }
.group-sim-stats span { display: flex; align-items: center; gap: 4px }
.group-sim-tip { font-size: 12px; color: #94a3b8; max-width: 60%; text-align: right }
.group-sim-tip strong { color: #6366f1 }

/* ============================================================
   反馈注入 UI (文档 §6.9)
   ============================================================ */
.role-output summary { display: flex; align-items: center; gap: 8px; flex-wrap: wrap }
.role-fb-badge {
  background: #fef3c7; color: #92400e;
  padding: 2px 8px; border-radius: 10px;
  font-size: 10px; font-weight: 600;
}
.role-fb-history {
  margin-top: 8px; padding-top: 8px;
  border-top: 1px dashed #e2e8f0;
  display: flex; flex-direction: column; gap: 6px;
}
.role-fb-entry {
  background: #fffbeb; border: 1px solid #fde68a;
  border-radius: 6px; padding: 6px 10px;
  font-size: 11px;
}
.role-fb-entry-header { display: flex; align-items: center; gap: 6px; color: #92400e; font-weight: 600; margin-bottom: 3px }
.role-fb-icon { font-size: 12px }
.role-fb-time { font-size: 10px; color: #b45309; font-weight: 400 }
.role-fb-compressed { font-size: 9px; background: #dbeafe; color: #1e40af; padding: 1px 5px; border-radius: 3px; font-weight: 500 }
.role-fb-text { color: #78350f; line-height: 1.5 }

.role-fb-trigger {
  display: flex; align-items: center; gap: 8px;
  margin-top: 8px; padding-top: 8px;
  border-top: 1px dashed #e2e8f0;
}
.role-fb-btn {
  background: #6366f1; color: #fff; border: none;
  padding: 5px 12px; border-radius: 6px;
  font-size: 12px; font-weight: 500;
  cursor: pointer; transition: background 0.2s;
  display: flex; align-items: center; gap: 4px;
}
.role-fb-btn:hover:not(:disabled) { background: #4f46e5 }
.role-fb-btn:disabled { opacity: 0.5; cursor: not-allowed }
.role-fb-hint { font-size: 11px; color: #94a3b8 }

.role-fb-form {
  margin-top: 8px; padding: 10px;
  background: #f8fafc; border: 1px solid #e2e8f0;
  border-radius: 8px;
}
.role-fb-textarea {
  width: 100%; min-height: 60px;
  border: 1px solid #cbd5e1; border-radius: 6px;
  padding: 8px 10px; font-size: 12px;
  font-family: inherit; resize: vertical;
  background: #fff; color: #1e293b;
  box-sizing: border-box;
}
.role-fb-textarea:focus { outline: none; border-color: #6366f1; box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1) }
.role-fb-form-actions { display: flex; justify-content: flex-end; gap: 6px; margin-top: 8px }
.role-fb-btn-secondary {
  background: #fff; color: #475569; border: 1px solid #cbd5e1;
  padding: 5px 12px; border-radius: 6px;
  font-size: 12px; cursor: pointer;
}
.role-fb-btn-secondary:hover { background: #f1f5f9 }
.role-fb-btn-primary {
  background: #10b981; color: #fff; border: none;
  padding: 5px 12px; border-radius: 6px;
  font-size: 12px; font-weight: 500;
  cursor: pointer;
}
.role-fb-btn-primary:hover:not(:disabled) { background: #059669 }
.role-fb-btn-primary:disabled { opacity: 0.5; cursor: not-allowed }

/* ============================================================
   真实执行面板 header 动作按钮 + 历史抽屉
   ============================================================ */
.group-sim-action-btn {
  background: rgba(255, 255, 255, 0.1); border: 1px solid rgba(255, 255, 255, 0.15);
  color: #f1f5f9;
  padding: 6px 12px; border-radius: 6px;
  font-size: 12px; font-weight: 500;
  cursor: pointer;
  display: flex; align-items: center; gap: 4px;
  transition: background 0.2s;
  white-space: nowrap;
}
.group-sim-action-btn:hover:not(:disabled) { background: rgba(255, 255, 255, 0.18) }
.group-sim-action-btn:disabled { opacity: 0.4; cursor: not-allowed }
.gs-run-badge {
  background: #f59e0b; color: #fff;
  font-size: 10px; padding: 1px 6px;
  border-radius: 8px; font-weight: 600;
  margin-left: 2px;
}

.gs-history-drawer {
  position: absolute; top: 0; right: 0; bottom: 0;
  width: 380px; max-width: 90%;
  background: #fff;
  border-left: 1px solid #e2e8f0;
  box-shadow: -8px 0 24px rgba(0, 0, 0, 0.15);
  display: flex; flex-direction: column;
  z-index: 60;
  animation: gsHistorySlide 0.3s var(--ease-out);
}
@keyframes gsHistorySlide { from { transform: translateX(100%) } to { transform: translateX(0) } }

.gs-history-header {
  padding: 16px 20px;
  background: linear-gradient(135deg, #1e293b, #0f172a);
  color: #f1f5f9;
  display: flex; align-items: center; justify-content: space-between;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.gs-history-header h3 { margin: 0; font-size: 15px; font-weight: 600 }
.gs-history-clear {
  background: transparent; border: 1px solid rgba(255, 255, 255, 0.2);
  color: #fca5a5;
  padding: 4px 10px; border-radius: 4px;
  font-size: 11px; cursor: pointer;
  margin-right: 8px;
}
.gs-history-clear:hover { background: rgba(239, 68, 68, 0.2) }
.gs-history-close {
  background: transparent; border: none; color: #f1f5f9;
  font-size: 22px; cursor: pointer;
  width: 28px; height: 28px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 4px;
}
.gs-history-close:hover { background: rgba(255, 255, 255, 0.1) }

.gs-history-list {
  flex: 1; overflow: auto; padding: 12px;
  background: #f8fafc;
}
.gs-history-empty {
  text-align: center; padding: 60px 20px; color: #94a3b8;
}
.gs-history-empty .empty-ico { font-size: 32px; margin-bottom: 8px }
.gs-history-empty .empty-sub { font-size: 12px; margin-top: 4px; color: #cbd5e1 }

.gs-history-item {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.15s;
}
.gs-history-item:hover { border-color: #6366f1; box-shadow: 0 2px 8px rgba(99, 102, 241, 0.15); transform: translateY(-1px) }
.gs-history-item-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; gap: 8px }
.gs-history-task {
  font-size: 13px; font-weight: 600; color: #1e293b;
  flex: 1;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.gs-history-mode {
  background: #eef2ff; color: #4338ca;
  padding: 2px 8px; border-radius: 4px;
  font-size: 10px; font-weight: 600; font-family: ui-monospace, monospace;
}
.gs-history-item-meta {
  display: flex; gap: 10px; font-size: 11px; color: #64748b; margin-bottom: 6px;
}
.gs-history-item-stats { display: flex; gap: 6px }
.gs-tag {
  font-size: 10px; padding: 2px 6px; border-radius: 3px;
  font-weight: 500;
}
.gs-tag.done { background: #d1fae5; color: #065f46 }
.gs-tag.fb { background: #fef3c7; color: #92400e }

@media (max-width: 768px) {
  .group-sim-overlay { padding: 0 }
  .group-sim-panel { height: 100vh; border-radius: 0; max-width: 100% }
  .group-sim-roles { grid-template-columns: 1fr }
  .group-sim-footer { flex-direction: column; align-items: stretch; gap: 8px }
  .group-sim-tip { max-width: 100%; text-align: left }
}

<style scoped>
/* ============================================================
   聊天页 - 浅蓝编辑感配色
   关键:用 position: fixed 锚定视口,完全脱离 <main> 的 flex 链
   原因:上游 flex 链(App.vue 的 <main> → #app)有不可控的约束,
        导致 chat-page 在 flex item 角色下被压成 50% 宽。
   副作用:工作台/历史面板改用 inset 定位贴到右侧。
   ============================================================ */
.chat-page {
  position: fixed;
  inset: 0;
  z-index: 1;
  display: flex;
  background: var(--bg-page);
  overflow: hidden;
}
/* chat-main 必须显式填满,否则它作为 chat-page 里唯一非 absolute 的 flex item,
   会被收成内容自然宽度,导致整页内容挤在左半边 */
.chat-main {
  flex: 1 1 0%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  position: relative;
}
/* 全局极淡极光底色 */
.chat-page::before {
  content: "";
  position: absolute; inset: 0;
  background:
    radial-gradient(ellipse 700px 400px at 20% 0%, rgba(46, 122, 184, 0.06) 0%, transparent 60%),
    radial-gradient(ellipse 600px 400px at 100% 100%, rgba(212, 144, 106, 0.04) 0%, transparent 60%);
  pointer-events: none;
  z-index: 0;
}
.chat-page > * { position: relative; z-index: 1; }
.history-backdrop { display: none; }

/* ============================================================ 顶栏 */
.chat-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 16px;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--line-blue);
  flex-shrink: 0;
  gap: 8px;
}
.header-left { display: flex; align-items: center; gap: 6px; min-width: 0; flex: 1; }
.header-right { display: flex; align-items: center; gap: 4px; }

.back-btn, .new-chat-btn, .icon-btn {
  width: 36px; height: 36px; border-radius: 10px; border: none;
  background: transparent; color: var(--text-muted);
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  transition: all 0.18s cubic-bezier(0.4, 0, 0.2, 1);
  flex-shrink: 0;
}
.back-btn:hover, .new-chat-btn:hover, .icon-btn:hover {
  background: var(--accent-blue-bg);
  color: var(--accent-blue-d);
}
.icon-btn.active {
  background: var(--accent-blue);
  color: #fff;
  box-shadow: 0 2px 8px -2px rgba(46, 122, 184, 0.4);
}

/* header 内部分隔线:工作台/历史 与 全局菜单/用户 之间 */
.header-divider {
  display: inline-block;
  width: 1px;
  height: 20px;
  background: var(--line-blue);
  margin: 0 2px;
  flex-shrink: 0;
}

/* MENU 触发按钮(开 AppMenu): 默认三条横线, hover 时用 MEMU 字替换 */
.chat-menu-trigger {
  position: relative;
}
.chat-menu-trigger svg {
  transition: opacity var(--t-fast);
}
.chat-menu-trigger::after {
  content: 'MEMU';
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.18em;
  color: transparent;
  pointer-events: none;
  transition: color var(--t-fast);
}
.chat-menu-trigger:hover svg { opacity: 0; }
.chat-menu-trigger:hover::after { color: var(--accent-blue-d); }

/* 聊天页用户头像按钮(圆形 + 蓝底 + hover 蓝环扩散) */
.chat-user-btn {
  position: relative;
  display: inline-flex; align-items: center; justify-content: center;
  width: 32px; height: 32px;
  background: transparent;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  padding: 0;
  flex-shrink: 0;
  transition: background var(--t-fast);
}
.chat-user-btn:hover { background: transparent; }
.chat-user-btn .user-avatar {
  width: 32px; height: 32px;
  display: flex; align-items: center; justify-content: center;
  background: var(--accent-blue);
  color: #fff;
  border-radius: 50%;
  font-size: 13px; font-weight: 600;
  font-family: var(--font-text);
  transition: transform var(--t-fast), box-shadow var(--t-fast);
  position: relative;
  z-index: 1;
}
.chat-user-btn:hover .user-avatar {
  transform: scale(1.1);
  box-shadow: 0 4px 12px -2px rgba(46, 122, 184, 0.5);
}
/* 蓝色 ring 扩散 */
.chat-user-btn::before {
  content: "";
  position: absolute;
  inset: 0;
  margin: auto;
  width: 32px; height: 32px;
  border-radius: 50%;
  border: 1px solid var(--accent-blue);
  opacity: 0;
  transform: scale(0.6);
  transition: transform var(--t-base), opacity var(--t-base);
  pointer-events: none;
}
.chat-user-btn:hover::before {
  opacity: 1;
  transform: scale(1.3);
}

/* 聊天页登录链接 */
.chat-login-link {
  display: inline-flex; align-items: center;
  padding: 7px 14px;
  background: var(--accent-blue);
  color: #fff;
  border-radius: 8px;
  font-size: 13px; font-weight: 500;
  text-decoration: none;
  flex-shrink: 0;
  transition: background var(--t-fast);
}
.chat-login-link:hover { background: var(--accent-blue-d); }

/* Model pill (已移除,保留空 class 防样式失效) */
.model-pill { display: none !important; }

/* 当前对话标题 */
.header-title {
  display: flex; align-items: center; gap: 10px;
  margin-left: 8px;
  min-width: 0;
  animation: titleFadeIn 0.4s ease both;
}
.title-bar {
  width: 2px; height: 18px;
  background: linear-gradient(180deg, var(--accent-blue) 0%, var(--accent-clay) 100%);
  border-radius: 2px;
  flex-shrink: 0;
}
.title-text {
  font-size: 14px; font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  max-width: 240px;
}
@keyframes titleFadeIn { from { opacity: 0; transform: translateX(-8px); } to { opacity: 1; transform: translateX(0); } }

.header-center { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.model-pill {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 6px 12px 6px 10px;
  background: var(--bg-card);
  border: 1px solid var(--line-blue);
  border-radius: 999px;
  font-size: 13px; font-weight: 500;
  color: var(--text-primary);
  cursor: pointer;
  font-family: inherit;
  transition: all 0.2s;
}
.model-pill:hover {
  border-color: var(--accent-blue-border);
  background: var(--accent-blue-bg);
  transform: translateY(-1px);
  box-shadow: 0 4px 10px -4px rgba(46, 122, 184, 0.25);
}
.model-orb {
  width: 8px; height: 8px; border-radius: 50%;
  background: conic-gradient(from 0deg, #4a8db5, #6fb4d3, #4a8db5);
  animation: orbSpin 4s linear infinite;
  box-shadow: 0 0 6px rgba(46, 122, 184, 0.5);
}
@keyframes orbSpin { to { transform: rotate(360deg); } }
.model-chev { color: var(--text-muted); transition: transform 0.2s; }
.model-pill:hover .model-chev { transform: translateY(1px); }

.header-toggle-btn {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 0 12px;
  height: 36px;
  background: transparent;
  border: 1px solid var(--border-card);
  border-radius: var(--r-2);
  font-family: var(--font-mono);
  font-size: 10px; font-weight: 500;
  letter-spacing: 0.16em; text-transform: uppercase;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--t-fast);
  flex-shrink: 0;
}
.header-toggle-btn:hover {
  border-color: var(--accent-blue);
  color: var(--accent-blue-d);
  background: var(--accent-blue-bg);
}
.header-toggle-btn.active {
  background: var(--accent-blue);
  border-color: var(--accent-blue);
  color: #fff;
  box-shadow: 0 2px 8px -2px rgba(46, 122, 184, 0.4);
}
.header-toggle-btn.active:hover {
  background: var(--accent-blue-d);
  border-color: var(--accent-blue-d);
}

/* ============================================================ 对话区 */
.chat-body {
  flex: 1; overflow-y: auto;
  padding: 32px 16px 0;
  scroll-behavior: smooth;
  scrollbar-gutter: stable;
}
.chat-body::-webkit-scrollbar { width: 8px; }
.chat-body::-webkit-scrollbar-thumb { background: var(--line-blue); border-radius: 4px; }
.chat-body::-webkit-scrollbar-thumb:hover { background: var(--accent-blue-l); }

/* ---------- 欢迎屏 ---------- */
.welcome-screen {
  display: flex; flex-direction: column; align-items: center;
  padding: 60px 24px 32px; text-align: center;
  max-width: 760px; margin: 0 auto;
  animation: welcomeIn 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
}
@keyframes welcomeIn { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }

.welcome-orb {
  position: relative;
  width: 96px; height: 96px; margin-bottom: 32px;
}
.orb-ring {
  position: absolute; top: 50%; left: 50%;
  border-radius: 50%;
  transform: translate(-50%, -50%);
}
.orb-ring.r1 {
  width: 96px; height: 96px;
  border: 1.2px solid var(--accent-blue);
  opacity: 0.45;
  animation: orbRing 18s linear infinite;
}
.orb-ring.r2 {
  width: 72px; height: 72px;
  border: 1.2px dashed var(--accent-blue-l);
  opacity: 0.55;
  animation: orbRing 12s linear infinite reverse;
}
.orb-ring.r3 {
  width: 56px; height: 56px;
  border: 1px solid var(--accent-clay);
  opacity: 0.35;
  animation: orbRing 24s linear infinite;
}
.orb-core {
  position: absolute; top: 50%; left: 50%;
  width: 40px; height: 40px; border-radius: 50%;
  transform: translate(-50%, -50%);
  background: radial-gradient(circle at 30% 25%, #ffffff 0%, #B5D2E5 30%, #2E7AB8 80%, #0E2A47 100%);
  box-shadow:
    inset -4px -4px 10px rgba(14, 42, 71, 0.5),
    inset 3px 3px 6px rgba(255,255,255,0.35),
    0 10px 28px -4px rgba(46,122,184,0.5);
  animation: orbFloat 6s ease-in-out infinite;
}
.orb-shine {
  position: absolute; top: 50%; left: 50%;
  width: 8px; height: 8px; border-radius: 50%;
  transform: translate(-50%, -50%);
  background: radial-gradient(circle, rgba(255,255,255,0.95) 0%, transparent 70%);
  filter: blur(0.5px);
  pointer-events: none;
  animation: shineDrift 4s ease-in-out infinite;
}
@keyframes orbRing { to { transform: translate(-50%, -50%) rotate(360deg); } }
@keyframes orbFloat {
  0%, 100% { transform: translate(-50%, -50%); }
  50% { transform: translate(-50%, calc(-50% - 5px)); }
}
@keyframes shineDrift {
  0%, 100% { transform: translate(calc(-50% - 6px), calc(-50% - 6px)); opacity: 0.7; }
  50% { transform: translate(calc(-50% + 6px), calc(-50% + 6px)); opacity: 1; }
}

.welcome-issue {
  display: inline-flex; align-items: center; gap: 12px;
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--accent-blue-d);
  margin-bottom: 18px;
}
.welcome-issue::before, .welcome-issue::after {
  content: ""; width: 24px; height: 1px;
  background: var(--accent-blue-border);
}

.welcome-title {
  font-family: var(--font-display);
  font-size: clamp(32px, 4vw, 44px);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 14px;
  letter-spacing: -0.02em;
  line-height: 1.1;
  display: flex; align-items: baseline; justify-content: center; flex-wrap: wrap; gap: 4px 12px;
}
.welcome-title .title-emph {
  font-family: var(--font-display);
  font-style: normal; font-weight: 700;
  color: var(--accent-blue);
  font-size: 1.15em;
  position: relative;
  display: inline-block;
}
.welcome-title .title-emph::after {
  content: ""; position: absolute;
  left: 0; right: 0; bottom: 4px;
  height: 6px;
  background: linear-gradient(90deg, var(--accent-clay) 0%, transparent 100%);
  opacity: 0.25;
  z-index: -1;
  border-radius: 3px;
}

.welcome-sub {
  font-size: 14px; color: var(--text-muted);
  margin: 0 0 28px;
  max-width: 460px; line-height: 1.7;
}

@keyframes chipIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }

/* 建议分组 */
.suggestion-groups { width: 100%; max-width: 600px; margin-bottom: 28px; }
.sugg-group { margin-bottom: 14px; }
.sugg-group-head {
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 8px;
}
.sugg-group-label {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.18em; text-transform: uppercase;
  color: var(--text-muted);
  font-weight: 600;
}
.sugg-group-line {
  flex: 1; height: 1px;
  background: linear-gradient(90deg, var(--line-blue) 0%, transparent 100%);
}
.sugg-group-items {
  display: grid; grid-template-columns: 1fr 1fr; gap: 8px;
}
.suggestion-chip {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 14px;
  background: var(--bg-card);
  border: 1px solid var(--line-blue);
  border-radius: 12px;
  text-align: left;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  font-family: inherit;
  color: inherit;
  position: relative;
  overflow: hidden;
  opacity: 0; animation: chipIn 0.4s ease forwards;
}
.suggestion-chip::before {
  content: "";
  position: absolute; inset: 0;
  background: linear-gradient(135deg, var(--accent-blue-bg) 0%, transparent 100%);
  opacity: 0; transition: opacity 0.25s;
  pointer-events: none;
}
.suggestion-chip:hover {
  border-color: var(--accent-blue-border);
  transform: translateY(-2px);
  box-shadow: 0 10px 24px -10px rgba(46, 122, 184, 0.35);
}
.suggestion-chip:hover::before { opacity: 1; }
.suggestion-chip:hover .chip-arrow { transform: translateX(2px); color: var(--accent-blue-d); }
.chip-num {
  font-family: var(--font-mono);
  font-size: 11px; letter-spacing: 0.1em;
  color: var(--accent-blue); font-weight: 600;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
  position: relative;
}
.chip-text {
  flex: 1; min-width: 0;
  font-size: 13px; color: var(--text-primary);
  line-height: 1.4;
  position: relative;
}
.chip-arrow {
  color: var(--text-placeholder);
  flex-shrink: 0;
  transition: transform 0.25s, color 0.25s;
  position: relative;
}

/* ---------- 消息 ---------- */
.msg-wrapper {
  max-width: 800px;
  margin: 0 auto 28px;
  animation: msgIn 0.4s cubic-bezier(0.16, 1, 0.3, 1) both;
}
.msg-wrapper.user { animation-delay: 0ms; }
.msg-wrapper.bot { animation-delay: 60ms; }
@keyframes msgIn {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

.msg-row { display: flex; gap: 12px; align-items: flex-start; }
.msg-row.user { flex-direction: row-reverse; }

.user-avatar {
  width: 36px; height: 36px; border-radius: 50%;
  background: var(--accent-blue-bg);
  color: var(--accent-blue-d);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  border: 1px solid var(--accent-blue-border);
  font-weight: 600;
  font-size: 13px;
  position: relative;
}
.user-avatar::after {
  content: ""; position: absolute;
  right: -1px; bottom: -1px;
  width: 10px; height: 10px;
  background: var(--accent-success);
  border: 2px solid var(--bg-page);
  border-radius: 50%;
}
.user-bubble-wrap {
  display: flex; flex-direction: column; align-items: flex-end;
  max-width: 70%;
}
.user-bubble {
  max-width: 100%;
  padding: 12px 18px;
  background: linear-gradient(135deg, var(--accent-blue) 0%, var(--accent-blue-d) 100%);
  color: #fff;
  border-radius: 20px 20px 4px 20px;
  font-size: 14.5px; line-height: 1.6;
  word-break: break-word;
  white-space: pre-wrap;
  box-shadow: 0 6px 18px -6px rgba(46, 122, 184, 0.5);
  position: relative;
}
.user-bubble::after {
  content: ""; position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  border-radius: inherit;
  background: linear-gradient(135deg, rgba(255,255,255,0.18) 0%, transparent 50%);
  pointer-events: none;
}
.msg-time {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.04em;
  color: var(--text-placeholder);
  margin-top: 4px;
  padding: 0 4px;
  font-variant-numeric: tabular-nums;
  opacity: 0.7;
}

/* ---------- AI 消息卡片 ---------- */
.bot-avatar {
  width: 52px; height: 52px; border-radius: 50%;
  background: linear-gradient(135deg, #f0f7fc 0%, #e3eef6 100%);
  border: 1px solid var(--line-blue);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  position: relative;
  box-shadow: 0 6px 18px -10px rgba(27, 90, 142, 0.34);
  overflow: visible;
}
.bot-logo {
  display: block;
  width: 46px; height: 40px;
  object-fit: contain;
  filter: drop-shadow(0 5px 8px rgba(27, 90, 142, 0.22));
}
.bot-logo.thinking {
  animation: thinkingPulse 1.4s ease-in-out infinite;
}
@keyframes thinkingPulse {
  0%, 100% { transform: scale(1); filter: drop-shadow(0 5px 8px rgba(27, 90, 142, 0.22)); }
  50%      { transform: scale(1.06); filter: drop-shadow(0 7px 12px rgba(27, 90, 142, 0.32)); }
}

.bot-card {
  flex: 1; min-width: 0;
  background: var(--bg-card);
  border: 1px solid var(--line-blue);
  border-radius: 4px 20px 20px 20px;
  box-shadow: 0 2px 8px -2px rgba(13, 36, 56, 0.04);
  transition: border-color 0.2s, box-shadow 0.2s, transform 0.2s;
  overflow: hidden;
}
.bot-card:hover {
  border-color: var(--accent-blue-border);
  box-shadow: 0 8px 24px -10px rgba(13, 36, 56, 0.08);
}

.bot-card-head {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px;
  padding: 10px 16px;
  background: linear-gradient(180deg, rgba(46,122,184,0.04) 0%, transparent 100%);
  border-bottom: 1px solid var(--line-blue);
}
.bot-id { display: flex; align-items: center; gap: 6px; }
.bot-logo-mini {
  width: 18px; height: 15px;
  object-fit: contain;
  flex-shrink: 0;
  filter: drop-shadow(0 2px 3px rgba(27, 90, 142, 0.18));
}
.bot-name {
  font-family: var(--font-display);
  font-size: 13px; font-weight: 600;
  color: var(--text-primary);
  letter-spacing: -0.005em;
}
.bot-dot { color: var(--text-placeholder); }
.bot-model {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.1em;
  color: var(--text-muted);
}
.bot-card-right { display: flex; align-items: center; gap: 10px; }
.bot-tokens {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.08em;
  color: var(--text-placeholder);
  font-variant-numeric: tabular-nums;
  padding: 1px 6px;
  background: var(--bg-page-blue);
  border-radius: 4px;
}
.bot-card .msg-time { margin: 0; }
.bot-card .bot-card-right .msg-time { padding: 0; }
.bot-status {
  display: inline-flex; align-items: center; gap: 6px;
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.1em;
  color: var(--accent-blue-d);
}
.status-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--accent-blue);
  animation: pulse 1.4s ease-in-out infinite;
}
@keyframes pulse { 50% { opacity: 0.4; } }

/* 思考过程 */
.thinking-block {
  margin: 12px 16px 0;
  border: 1px solid var(--line-blue);
  border-radius: 10px;
  overflow: hidden;
  background: var(--bg-page-blue);
}
.thinking-header {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 14px;
  background: rgba(255,255,255,0.6);
  cursor: pointer;
  font-family: var(--font-mono);
  font-size: 11px; letter-spacing: 0.08em;
  color: var(--text-muted);
  user-select: none;
  transition: background 0.15s;
}
.thinking-header:hover { background: rgba(255,255,255,0.9); }
.thinking-dots {
  display: inline-flex; gap: 3px; margin-left: 4px;
}
.thinking-dots span {
  width: 4px; height: 4px; border-radius: 50%;
  background: var(--accent-blue);
  animation: dotBounce 1.4s infinite ease-in-out both;
  opacity: 0.6;
}
.thinking-dots span:nth-child(1) { animation-delay: -0.32s; }
.thinking-dots span:nth-child(2) { animation-delay: -0.16s; }
.thinking-chevron { margin-left: auto; transition: transform 0.2s; }
.thinking-chevron.open { transform: rotate(180deg); }
.thinking-body {
  padding: 12px 14px;
  font-size: 12px; color: var(--text-muted);
  line-height: 1.7;
  white-space: pre-wrap;
  border-top: 1px solid var(--line-blue);
  max-height: 240px; overflow-y: auto;
}

/* ---------- Markdown 正文 ---------- */
.bot-text {
  padding: 14px 18px 4px;
  font-size: 14.5px; line-height: 1.7; color: var(--text-primary);
  word-break: break-word;
}
.bot-text :deep(p) { margin: 0 0 10px; }
.bot-text :deep(p:last-child) { margin-bottom: 0; }
.bot-text :deep(h1), .bot-text :deep(h2), .bot-text :deep(h3), .bot-text :deep(h4) {
  font-family: var(--font-display);
  font-weight: 600; color: var(--text-primary);
  margin: 16px 0 8px; letter-spacing: -0.01em;
}
.bot-text :deep(h3) { font-size: 17px; }
.bot-text :deep(h4) { font-size: 15px; }
.bot-text :deep(strong) { font-weight: 600; color: var(--text-primary); }
.bot-text :deep(em) { font-style: italic; }
.bot-text :deep(ul), .bot-text :deep(ol) { margin: 8px 0; padding-left: 22px; }
.bot-text :deep(li) { margin-bottom: 4px; }
.bot-text :deep(li::marker) { color: var(--accent-blue); }
.bot-text :deep(a) { color: var(--accent-blue-d); text-decoration: none; border-bottom: 1px solid var(--accent-blue-border); }
.bot-text :deep(a:hover) { color: var(--accent-blue); border-color: var(--accent-blue); }
.bot-text :deep(blockquote) {
  border-left: 3px solid var(--accent-blue);
  background: var(--accent-blue-bg);
  padding: 10px 14px;
  margin: 10px 0;
  color: var(--text-primary);
  border-radius: 0 8px 8px 0;
  font-style: italic;
}
.bot-text :deep(table) {
  border-collapse: collapse;
  margin: 10px 0;
  width: 100%;
  font-size: 13px;
  border: 1px solid var(--line-blue);
  border-radius: 8px;
  overflow: hidden;
}
.bot-text :deep(th), .bot-text :deep(td) {
  border: 1px solid var(--line-blue);
  padding: 8px 12px;
  text-align: left;
}
.bot-text :deep(th) {
  background: var(--bg-page-blue);
  font-weight: 600;
  color: var(--text-primary);
}
.bot-text :deep(code) {
  background: var(--accent-blue-bg);
  color: var(--accent-blue-d);
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 0.88em;
  font-family: var(--font-mono);
  border: 1px solid var(--accent-blue-border);
}
.bot-text :deep(pre) {
  margin: 0;
  background: transparent;
  border-radius: 0;
  overflow: visible;
}
.bot-text :deep(pre code) {
  display: block;
  padding: 14px 16px;
  font-size: 13px;
  line-height: 1.6;
  color: #e6edf3;
  overflow-x: auto;
  white-space: pre;
  background: transparent;
  border: none;
  border-radius: 0;
}

/* ---------- 代码块外壳(JS 注入) ---------- */
:deep(.code-block) {
  position: relative;
  background: linear-gradient(180deg, #0d2438 0%, #0a1a2a 100%);
  border-radius: 12px;
  overflow: hidden;
  margin: 12px 0;
  border: 1px solid #1a3050;
  box-shadow: 0 8px 20px -8px rgba(13, 36, 56, 0.4);
}
:deep(.code-bar) {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 12px 8px 14px;
  background: rgba(255,255,255,0.03);
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
:deep(.code-bar-left) { display: flex; align-items: center; gap: 10px; }
:deep(.code-dots) { display: flex; gap: 5px; }
:deep(.code-dots span) {
  width: 9px; height: 9px; border-radius: 50%;
  background: rgba(255,255,255,0.15);
  display: block;
}
:deep(.code-dots span:nth-child(1)) { background: rgba(255, 95, 86, 0.7); }
:deep(.code-dots span:nth-child(2)) { background: rgba(255, 189, 46, 0.7); }
:deep(.code-dots span:nth-child(3)) { background: rgba(39, 201, 63, 0.7); }
:deep(.code-lang) {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.12em; text-transform: uppercase;
  color: #8aa1b3;
  font-weight: 500;
}
:deep(.code-copy) {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 3px 8px;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 5px;
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.08em;
  color: #8aa1b3;
  cursor: pointer;
  transition: all 0.15s;
}
:deep(.code-copy:hover) {
  background: rgba(255,255,255,0.12);
  color: #fff;
}
:deep(.code-copy.copied) {
  background: rgba(16, 185, 129, 0.15);
  border-color: rgba(16, 185, 129, 0.3);
  color: #10b981;
}

/* ---------- 回答内文件产物 ---------- */
.message-artifacts {
  margin: 10px 16px 8px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.message-artifact-card {
  border: 1px solid var(--line-blue);
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
  transition: border-color 0.16s ease, box-shadow 0.16s ease;
}
.message-artifact-card:hover,
.message-artifact-card.expanded {
  border-color: var(--accent-blue-border);
  box-shadow: 0 8px 22px -16px rgba(27, 90, 142, 0.24);
}
.message-artifact-main {
  min-height: 78px;
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr) auto;
  align-items: center;
  gap: 14px;
  padding: 12px 14px;
}
.message-artifact-icon {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent-blue-d);
  background: var(--bg-page-blue);
  border: 1px solid var(--line-blue);
}
.message-artifact-meta {
  min-width: 0;
}
.message-artifact-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.message-artifact-sub {
  margin-top: 4px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px 10px;
  font-size: 12px;
  color: var(--text-muted);
}
.message-artifact-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.message-artifact-btn {
  height: 32px;
  padding: 0 12px;
  border-radius: 7px;
  border: 1px solid var(--line-blue);
  background: #fff;
  color: var(--accent-blue-d);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
}
.message-artifact-btn:hover {
  background: var(--bg-page-blue);
  border-color: var(--accent-blue-border);
}
.message-artifact-btn.primary {
  background: var(--accent-blue);
  border-color: var(--accent-blue);
  color: #fff;
}
.message-artifact-btn.primary:hover {
  background: var(--accent-blue-d);
  border-color: var(--accent-blue-d);
}
.message-artifact-preview {
  border-top: 1px solid var(--line-blue);
  background: #f8fbfe;
  padding: 12px;
}
.message-artifact-frame {
  width: 100%;
  height: min(58vh, 520px);
  border: 1px solid var(--line-blue);
  border-radius: 8px;
  background: #fff;
}
.message-artifact-pre {
  margin: 0;
  max-height: 420px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--line-blue);
  background: #fff;
  color: var(--text-primary);
  font: 12px/1.6 var(--font-mono);
}

/* ---------- 操作行 ---------- */
.msg-actions {
  display: flex; align-items: center; gap: 2px;
  margin: 4px 10px 8px;
  padding-top: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}
.msg-row.bot:hover .msg-actions,
.msg-row.bot:focus-within .msg-actions { opacity: 1; }
.action-btn {
  position: relative;
  width: 28px; height: 28px;
  border-radius: 6px; border: none;
  background: transparent; color: var(--text-muted);
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.15s;
}
.action-btn:hover { background: var(--accent-blue-bg); color: var(--accent-blue-d); }
.action-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.action-btn.liked { color: #10b981; background: rgba(16, 185, 129, 0.1); }
.action-btn.disliked { color: #ef4444; background: rgba(239, 68, 68, 0.1); }
.action-tip {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 50%; transform: translateX(-50%) translateY(2px);
  padding: 3px 8px;
  background: var(--text-primary);
  color: var(--text-inverse);
  font-size: 11px;
  border-radius: 5px;
  white-space: nowrap;
  pointer-events: none;
  opacity: 0;
  transition: all 0.18s cubic-bezier(0.4, 0, 0.2, 1);
  font-family: var(--font-text);
  letter-spacing: 0;
  z-index: 10;
}
.action-tip::after {
  content: "";
  position: absolute;
  top: 100%; left: 50%;
  transform: translateX(-50%);
  border: 4px solid transparent;
  border-top-color: var(--text-primary);
}
.action-btn:hover .action-tip {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}
.action-spacer { flex: 1; }
.action-meta {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.04em;
  color: var(--text-placeholder);
  padding: 0 6px;
}

/* ---------- 输入中(typing) ---------- */
.typing-line {
  display: inline-flex; gap: 5px; padding: 8px 18px 14px;
}
.typing-line span {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--accent-blue);
  animation: dotBounce 1.4s infinite ease-in-out both;
  opacity: 0.5;
}
.typing-line span:nth-child(1) { animation-delay: -0.32s; }
.typing-line span:nth-child(2) { animation-delay: -0.16s; }
@keyframes dotBounce {
  0%, 80%, 100% { transform: scale(0.5); opacity: 0.3; }
  40%           { transform: scale(1);   opacity: 1; }
}

/* ============================================================ 输入栏 */
.chat-footer {
  flex-shrink: 0;
  padding: 12px 16px 20px;
  background: linear-gradient(180deg, transparent 0%, var(--bg-page) 40%);
}
.footer-inner { max-width: 800px; margin: 0 auto; }

.input-panel {
  display: flex; align-items: flex-end; gap: 10px;
  padding: 8px 8px 8px 12px;
  background: var(--bg-card);
  border: 1.5px solid var(--line-blue);
  border-radius: 22px;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 2px 12px -4px rgba(13, 36, 56, 0.06);
}
.input-panel.focused {
  border-color: var(--accent-blue);
  box-shadow:
    0 0 0 4px rgba(46, 122, 184, 0.10),
    0 6px 20px -4px rgba(13, 36, 56, 0.08);
}
.input-panel.hasText {
  border-color: var(--accent-blue-border);
}
.input-left { display: flex; align-items: center; gap: 2px; flex-shrink: 0; }
.input-right { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.tool-btn {
  position: relative;
  width: 34px; height: 34px; border-radius: 10px; border: none;
  background: transparent; color: var(--text-muted);
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.15s;
}
.tool-btn:hover:not(:disabled) { background: var(--accent-blue-bg); color: var(--accent-blue-d); }
.tool-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.tool-btn.active {
  background: var(--accent-blue);
  color: #fff;
  box-shadow: 0 2px 8px -2px rgba(46, 122, 184, 0.4);
}
.tool-tip {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 50%; transform: translateX(-50%) translateY(2px);
  padding: 3px 8px;
  background: var(--text-primary);
  color: var(--text-inverse);
  font-size: 11px;
  border-radius: 5px;
  white-space: nowrap;
  pointer-events: none;
  opacity: 0;
  transition: all 0.18s cubic-bezier(0.4, 0, 0.2, 1);
  font-family: var(--font-text);
  z-index: 10;
}
.tool-tip::after {
  content: "";
  position: absolute;
  top: 100%; left: 50%;
  transform: translateX(-50%);
  border: 4px solid transparent;
  border-top-color: var(--text-primary);
}
.tool-btn:hover:not(:disabled) .tool-tip {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}

.chat-textarea {
  flex: 1;
  border: none !important; outline: none !important;
  background: transparent !important;
  font-size: 14.5px;
  color: var(--text-primary);
  resize: none;
  min-height: 26px; max-height: 160px;
  font-family: inherit; line-height: 1.6;
  padding: 7px 0;
  box-shadow: none !important;
  overflow-y: auto;
}
.chat-textarea::placeholder { color: var(--text-placeholder); }

.char-count {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-placeholder);
  letter-spacing: 0.04em;
  font-variant-numeric: tabular-nums;
  padding: 0 4px;
  animation: countIn 0.2s ease;
}
@keyframes countIn { from { opacity: 0; transform: scale(0.8); } to { opacity: 1; transform: scale(1); } }

.send-btn {
  position: relative;
  width: 38px; height: 38px;
  border-radius: 50%; border: none;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.2s ease;
  flex-shrink: 0;
  background: linear-gradient(135deg, var(--accent-blue) 0%, var(--accent-blue-d) 100%);
  color: #fff;
  box-shadow: 0 4px 12px -2px rgba(46, 122, 184, 0.5);
  overflow: visible;
}
.send-btn:enabled:hover {
  transform: scale(1.05) rotate(-12deg);
  box-shadow: 0 8px 20px -2px rgba(46, 122, 184, 0.6);
}
.send-btn:enabled:active { transform: scale(0.92) rotate(0deg); }
.send-btn:disabled {
  background: var(--bg-hover);
  color: var(--text-placeholder);
  cursor: not-allowed;
  box-shadow: none;
}
.send-pulse {
  position: absolute; inset: -3px;
  border-radius: 50%;
  border: 2px solid var(--accent-blue);
  opacity: 0;
  animation: sendPulse 2s ease-out infinite;
  pointer-events: none;
}
@keyframes sendPulse {
  0% { opacity: 0.5; transform: scale(1); }
  100% { opacity: 0; transform: scale(1.4); }
}

.footer-hint {
  display: flex; justify-content: center; align-items: center; gap: 8px;
  font-size: 11px; color: var(--text-muted);
  margin: 10px 0 0;
  flex-wrap: wrap;
}
.footer-hint .mono { font-family: var(--font-mono); letter-spacing: 0.06em; }
.footer-hint .dot-sep { opacity: 0.5; }

.scroll-anchor { height: 1px; }

/* ============================================================ 工作台面板 */
.workbench-panel {
  position: absolute;
  top: var(--chat-header-h, 56px); right: 0; bottom: 0;
  width: 0; overflow: hidden;
  display: flex; flex-direction: column; gap: 12px;
  padding: 12px;
  transition: width 0.3s cubic-bezier(.4,.05,.58,1.27);
  border-left: 1px solid var(--line-blue);
  background: rgba(255,255,255,0.4);
  z-index: 5;
}
.workbench-panel.open { width: 520px; }
.workbench-panel.has-group-sim { width: 560px; }

/* ============================================================
   工作台内嵌真实执行卡片
   ============================================================ */
.wb-embedded-group {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  overflow: hidden;
  display: flex; flex-direction: column;
  flex: 1; min-height: 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}
.wb-embedded-head {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px;
  background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
  color: #f1f5f9;
  flex-shrink: 0;
}
.wb-embedded-badge {
  font-size: 11px; font-weight: 600;
  background: rgba(99, 102, 241, 0.2); color: #c7d2fe;
  padding: 3px 8px; border-radius: 8px;
  letter-spacing: 0.5px;
}
.wb-embedded-progress {
  flex: 1; font-size: 12px; color: #94a3b8;
}
.wb-embedded-progress .wb-embedded-cost { color: #10b981; font-weight: 600 }
.wb-embedded-actions { display: flex; gap: 4px }
.wb-embedded-btn {
  background: rgba(255, 255, 255, 0.08); border: 1px solid rgba(255, 255, 255, 0.15);
  color: #f1f5f9;
  width: 24px; height: 24px; border-radius: 4px;
  font-size: 14px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.wb-embedded-btn:hover { background: rgba(255, 255, 255, 0.18) }

.wb-embedded-roles {
  flex: 1; overflow: auto;
  padding: 8px;
  display: flex; flex-direction: column; gap: 6px;
}
.wb-embedded-role {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 12px;
  position: relative;
  overflow: hidden;
}
.wb-embedded-role::before {
  content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
  background: #cbd5e1;
}
.wb-embedded-role.status-running { border-color: #3b82f6; background: #eff6ff }
.wb-embedded-role.status-running::before { background: #3b82f6 }
.wb-embedded-role.status-done { border-color: #10b981; background: #f0fdf4 }
.wb-embedded-role.status-done::before { background: #10b981 }
.wb-embedded-role.status-error { border-color: #ef4444; background: #fef2f2 }
.wb-embedded-role.status-error::before { background: #ef4444 }

.wb-embedded-role-head {
  display: flex; align-items: center; gap: 6px;
}
.wb-embedded-role-emoji { font-size: 14px }
.wb-embedded-role-name { flex: 1; font-weight: 600; color: #1e293b; font-size: 12px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.wb-embedded-role-status { display: flex; align-items: center; gap: 4px }
.wb-embedded-dot { width: 6px; height: 6px; border-radius: 50%; background: #cbd5e1 }
.wb-embedded-dot.dot-running { background: #3b82f6; box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.6);
  animation: dotPulse 1.2s infinite }
.wb-embedded-dot.dot-done { background: #10b981 }
.wb-embedded-dot.dot-error { background: #ef4444 }
.wb-embedded-status-text { font-size: 10px; color: #64748b }
@keyframes dotPulse {
  0% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.6) }
  70% { box-shadow: 0 0 0 4px rgba(59, 130, 246, 0) }
  100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0) }
}

.wb-embedded-running, .wb-embedded-pending, .wb-embedded-error {
  font-size: 11px; padding: 4px 0; color: #64748b;
}
.wb-embedded-running { color: #3b82f6 }
.wb-embedded-error { color: #ef4444 }

.wb-embedded-output { margin-top: 4px }
.wb-embedded-output summary {
  cursor: pointer; font-size: 11px; color: #10b981;
  font-weight: 600; padding: 2px 0; list-style: none;
}
.wb-embedded-output summary::-webkit-details-marker { display: none }
.wb-embedded-output summary::before { content: '▶ '; font-size: 9px; margin-right: 4px }
.wb-embedded-output[open] summary::before { content: '▼ ' }
.wb-embedded-output pre {
  background: #fff; border: 1px solid #e2e8f0;
  border-radius: 4px; padding: 6px 8px;
  font-size: 10px; line-height: 1.5;
  color: #334155;
  white-space: pre-wrap; word-wrap: break-word;
  max-height: 200px; overflow: auto;
  font-family: ui-monospace, monospace;
  margin: 4px 0 0;
}

.wb-embedded-footer {
  display: flex; gap: 6px; padding: 8px;
  border-top: 1px solid #e2e8f0;
  background: #f8fafc;
  flex-shrink: 0;
}
.wb-embedded-export, .wb-embedded-history {
  flex: 1; background: #fff; border: 1px solid #cbd5e1;
  color: #475569; padding: 5px 8px;
  border-radius: 4px; font-size: 11px;
  cursor: pointer; transition: all 0.15s;
  display: flex; align-items: center; justify-content: center; gap: 4px;
}
.wb-embedded-export:hover, .wb-embedded-history:hover { background: #f1f5f9 }

/* ============================================================
   工作台 tab 切换: 日志 | 产物
   ============================================================ */
.wb-tabs {
  display: flex; gap: 4px;
  background: rgba(241, 245, 249, 0.8);
  border-radius: 8px;
  padding: 4px;
  border: 1px solid #e2e8f0;
}
.wb-tab {
  flex: 1;
  display: flex; align-items: center; justify-content: center; gap: 6px;
  padding: 7px 10px;
  background: transparent;
  border: none;
  border-radius: 6px;
  font-size: 12px; font-weight: 500;
  color: #64748b;
  cursor: pointer;
  transition: all 0.2s;
}
.wb-tab:hover { color: #1e293b }
.wb-tab.active {
  background: #fff;
  color: #6366f1;
  box-shadow: 0 1px 3px rgba(99, 102, 241, 0.2);
}
.wb-tab-badge {
  background: #e0e7ff; color: #4338ca;
  font-size: 10px; padding: 1px 6px;
  border-radius: 8px; font-weight: 600;
  min-width: 18px; text-align: center;
}
.wb-tab.active .wb-tab-badge { background: #6366f1; color: #fff }

.wb-tab-body {
  flex: 1;
  min-height: 0;
  display: flex; flex-direction: column;
  overflow: hidden;
}

/* 产物列表 */
.wb-artifact-list {
  flex: 1; overflow: auto;
  display: flex; flex-direction: column; gap: 6px;
  padding-right: 2px;
}
.wb-artifact-empty {
  text-align: center; padding: 40px 12px;
  color: #94a3b8; font-size: 12px;
}
.wb-artifact-empty .empty-ico { font-size: 32px; margin-bottom: 8px }
.wb-artifact-empty .empty-sub { font-size: 11px; color: #cbd5e1; margin-top: 4px }

.wb-artifact-item {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
  transition: all 0.15s;
}
.wb-artifact-item:hover { border-color: #cbd5e1 }
.wb-artifact-item.expanded { border-color: #6366f1; box-shadow: 0 2px 8px rgba(99, 102, 241, 0.12) }

.wb-artifact-head {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 10px;
  cursor: pointer;
  user-select: none;
}
.wb-artifact-head:hover { background: #f8fafc }

.wb-artifact-ico {
  width: 28px; height: 28px;
  background: linear-gradient(135deg, #6366f1, #4338ca);
  border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; color: #fff;
  flex-shrink: 0;
}
.wb-artifact-meta { flex: 1; min-width: 0 }
.wb-artifact-title {
  font-size: 12px; font-weight: 600; color: #1e293b;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.wb-artifact-sub {
  display: flex; gap: 6px;
  font-size: 10px; color: #94a3b8;
  margin-top: 2px;
}
.wb-artifact-agent { color: #6366f1; font-weight: 500 }
.wb-artifact-toggle {
  font-size: 10px; color: #94a3b8; flex-shrink: 0;
}

.wb-artifact-body {
  border-top: 1px solid #e2e8f0;
  background: #f8fafc;
  padding: 8px 10px;
  display: flex; flex-direction: column; gap: 8px;
}
.wb-artifact-content {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px;
  font-size: 11px; line-height: 1.5;
  font-family: ui-monospace, monospace;
  color: #334155;
  white-space: pre-wrap; word-wrap: break-word;
  max-height: 280px; overflow: auto;
  margin: 0;
}
.wb-artifact-actions {
  display: flex; gap: 6px; justify-content: flex-end;
}
.wb-artifact-copy, .wb-artifact-download {
  background: #fff;
  border: 1px solid #cbd5e1;
  color: #475569;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s;
}
.wb-artifact-copy:hover, .wb-artifact-download:hover { background: #f1f5f9; border-color: #94a3b8 }

/* ============================================================ 对话历史 */
.history-panel {
  position: absolute;
  top: var(--chat-header-h, 56px); right: 0; bottom: 0;
  width: 0; overflow: hidden;
  background: var(--bg-card);
  border-left: 1px solid var(--line-blue);
  display: flex; flex-direction: column;
  transition: width 0.25s ease;
  z-index: 6;
}
.history-panel.open { width: 300px; }

.history-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 16px 12px;
  border-bottom: 1px solid var(--line-blue);
}
.history-title {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.18em; text-transform: uppercase;
  color: var(--accent-blue-d);
  font-weight: 600;
}
.history-actions { display: flex; align-items: center; gap: 8px; }
.history-icon-btn {
  width: 24px; height: 24px;
  border-radius: 6px; border: 1px solid var(--line-blue);
  background: var(--bg-card);
  color: var(--text-muted);
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.15s;
}
.history-icon-btn:hover { border-color: var(--accent-blue); color: var(--accent-blue-d); }
.history-count {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-muted);
  background: var(--accent-blue-bg);
  padding: 2px 8px; border-radius: 999px;
  font-variant-numeric: tabular-nums;
}

.history-search {
  display: flex; align-items: center; gap: 8px;
  margin: 10px 12px 6px;
  padding: 7px 12px;
  background: var(--bg-page);
  border: 1px solid var(--line-blue);
  border-radius: 8px;
  color: var(--text-muted);
  transition: border-color 0.2s;
}
.history-search:focus-within { border-color: var(--accent-blue); }
.history-search-input {
  flex: 1;
  border: none !important; outline: none !important;
  background: transparent !important;
  box-shadow: none !important;
  padding: 0 !important;
  font-size: 13px;
  color: var(--text-primary);
  font-family: inherit;
}
.history-search-input::placeholder { color: var(--text-placeholder); }

.history-list { flex: 1; overflow-y: auto; padding: 6px 8px 12px; }
.history-group-label {
  font-family: var(--font-mono);
  font-size: 9px; letter-spacing: 0.18em; text-transform: uppercase;
  color: var(--text-placeholder);
  padding: 12px 8px 4px;
  font-weight: 600;
}
.history-group-label:first-child { padding-top: 4px; }
.history-item {
  display: flex; align-items: center; gap: 8px;
  padding: 9px 10px; border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
  position: relative;
}
.history-item:hover { background: var(--accent-blue-bg); }
.history-item.active {
  background: linear-gradient(90deg, var(--accent-blue-bg) 0%, transparent 100%);
  box-shadow: inset 2px 0 0 var(--accent-blue);
}
.history-item.active .history-item-title { color: var(--accent-blue-d); font-weight: 600; }
.history-item-title {
  flex: 1; font-size: 13px; color: var(--text-primary);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.history-item-time {
  font-family: var(--font-mono);
  font-size: 10px; color: var(--text-muted); flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}
.history-delete-btn {
  width: 22px; height: 22px; border-radius: 4px; border: none;
  background: transparent; color: var(--text-placeholder);
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  opacity: 0; transition: all 0.15s; flex-shrink: 0;
}
.history-item:hover .history-delete-btn { opacity: 1; }
.history-delete-btn:hover { background: rgba(239, 68, 68, 0.1); color: var(--accent-danger); }

.history-empty {
  text-align: center; padding: 40px 16px;
  font-size: 13px; color: var(--text-muted);
}
.history-empty .empty-ico {
  font-size: 32px;
  margin-bottom: 12px;
  opacity: 0.6;
}
.history-empty .empty-sub {
  font-size: 11px; color: var(--text-placeholder);
  margin-top: 6px; line-height: 1.5;
}

/* ============================================================ DeepSeek-inspired chat shell refresh */
.header-left { gap: 10px; }
.header-brand {
  display: inline-flex; align-items: center; gap: 8px;
  height: 36px; padding: 0 4px 0 2px;
  color: var(--text-primary); flex-shrink: 0;
}
.header-brand-mark {
  width: 34px; height: 28px;
  display: inline-flex; align-items: center; justify-content: center;
  overflow: visible;
}
.header-brand-mark img {
  width: 100%; height: 100%; object-fit: contain;
  filter: drop-shadow(0 3px 8px rgba(27, 90, 142, 0.18));
}
.header-brand-name {
  font-family: var(--font-display); font-size: 16px; font-weight: 800;
  line-height: 1; color: var(--accent-blue-d);
}
.new-chat-btn {
  width: auto; min-width: 106px; height: 36px;
  padding: 0 16px 0 10px; border-radius: 999px;
  border: 1px solid rgba(181, 210, 229, 0.85);
  background: rgba(255, 255, 255, 0.92); color: var(--text-primary);
  gap: 8px;
  box-shadow: 0 6px 18px -12px rgba(14, 42, 71, 0.36), 0 1px 0 rgba(255,255,255,0.9) inset;
}
.new-chat-btn:hover {
  background: #fff; border-color: rgba(46, 122, 184, 0.34);
  color: var(--accent-blue-d); transform: translateY(-1px);
  box-shadow: 0 10px 24px -14px rgba(14, 42, 71, 0.42), 0 1px 0 rgba(255,255,255,0.95) inset;
}
.new-chat-plus {
  width: 22px; height: 22px; border-radius: 999px;
  display: inline-flex; align-items: center; justify-content: center;
  background: rgba(46, 122, 184, 0.10); color: var(--accent-blue-d);
  flex-shrink: 0;
}
.new-chat-text { font-size: 13px; font-weight: 650; letter-spacing: 0; white-space: nowrap; }
.history-toggle-btn { border: 1px solid transparent; background: rgba(255, 255, 255, 0.62); }
.history-toggle-btn:hover {
  border-color: rgba(46, 122, 184, 0.24);
  box-shadow: 0 8px 18px -14px rgba(14, 42, 71, 0.45);
}
.history-toggle-btn.active {
  border-color: rgba(46, 122, 184, 0.35); background: var(--accent-blue); color: #fff;
}
.welcome-screen { padding-top: 30px; }
.welcome-brand-logo {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: min(420px, 86vw);
  margin: 0 auto 24px;
  isolation: isolate;
}
.welcome-brand-logo::before {
  content: ""; position: absolute; inset: 12%; border-radius: 38px;
  background: radial-gradient(circle, rgba(91, 160, 214, 0.20) 0%, rgba(91, 160, 214, 0.06) 48%, transparent 72%);
  filter: blur(18px); z-index: -1;
}
.welcome-logo-shell {
  width: clamp(210px, 22vw, 280px); height: clamp(168px, 17.5vw, 222px);
  display: flex; align-items: center; justify-content: center;
  border-radius: 0; overflow: visible; background: transparent;
  border: none;
  box-shadow: none;
}
.welcome-logo-img {
  display: block;
  width: 100%; height: 100%;
  object-fit: contain;
  filter: drop-shadow(0 14px 22px rgba(27, 90, 142, 0.18));
}
.welcome-logo-tagline {
  display: inline-flex; align-items: center; justify-content: center; gap: 12px;
  margin-top: 10px;
  font-family: var(--font-mono);
  font-size: 15px;
  font-weight: 850;
  letter-spacing: 0.12em;
  color: #0d3474;
  line-height: 1.1;
  white-space: nowrap;
}
.welcome-logo-tagline::before,
.welcome-logo-tagline::after {
  content: "";
  width: 32px; height: 2px;
  background: linear-gradient(90deg, transparent, #0d3474 46%, transparent);
  opacity: 0.9;
}
.chat-page .history-panel {
  position: relative; order: -1; top: auto; right: auto; bottom: auto; left: auto;
  flex: 0 0 0; width: 0; height: 100%; padding: 0; overflow: hidden;
  background: rgba(248, 251, 254, 0.98); border-left: none;
  border-right: 1px solid rgba(181, 210, 229, 0.72);
  box-shadow: 14px 0 30px -30px rgba(14, 42, 71, 0.45);
  opacity: 0; visibility: hidden; pointer-events: none;
  transition: flex-basis 0.28s cubic-bezier(0.16, 1, 0.3, 1), width 0.28s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.18s ease, visibility 0s linear 0.28s;
  z-index: 8;
}
.chat-page .history-panel.open {
  flex-basis: 318px; width: 318px; opacity: 1; visibility: visible; pointer-events: auto;
  transition: flex-basis 0.28s cubic-bezier(0.16, 1, 0.3, 1), width 0.28s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.18s ease;
}
.chat-page.history-open .chat-main { box-shadow: inset 1px 0 0 rgba(181, 210, 229, 0.40); }
.workbench-panel:not(.open) {
  width: 0;
  padding: 0;
  border-left: 0;
  gap: 0;
  background: transparent;
  visibility: hidden;
  pointer-events: none;
}
.workbench-panel.open {
  padding: 12px;
  border-left: 1px solid var(--line-blue);
  background: rgba(255,255,255,0.4);
  visibility: visible;
  pointer-events: auto;
}
.history-brand-row {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  height: 64px; padding: 14px 16px 8px; flex-shrink: 0;
}
.history-brand { display: inline-flex; align-items: center; gap: 10px; min-width: 0; }
.history-brand-mark {
  width: 42px; height: 34px; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.history-brand-mark img {
  width: 100%; height: 100%; object-fit: contain;
  filter: drop-shadow(0 4px 10px rgba(27, 90, 142, 0.22));
}
.history-brand-name {
  font-family: var(--font-display); font-size: 21px; font-weight: 800;
  line-height: 1; color: var(--accent-blue-d); letter-spacing: -0.01em;
}
.history-new-chat {
  width: calc(100% - 32px); height: 46px; margin: 8px 16px 16px;
  border-radius: 999px; border: 1px solid rgba(181, 210, 229, 0.86);
  background: #fff; color: var(--text-primary); font-family: inherit;
  font-size: 15px; font-weight: 650; cursor: pointer;
  display: flex; align-items: center; justify-content: center; gap: 9px;
  box-shadow: 0 14px 28px -22px rgba(14, 42, 71, 0.52), 0 1px 0 rgba(255,255,255,0.9) inset;
  transition: transform var(--t-fast), border-color var(--t-fast), box-shadow var(--t-fast), color var(--t-fast);
}
.history-new-chat:hover {
  transform: translateY(-1px); border-color: rgba(46, 122, 184, 0.34); color: var(--accent-blue-d);
  box-shadow: 0 18px 34px -24px rgba(14, 42, 71, 0.62), 0 1px 0 rgba(255,255,255,0.95) inset;
}
.history-new-chat-icon {
  width: 22px; height: 22px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center;
  color: var(--accent-blue-d); background: rgba(46, 122, 184, 0.10);
}
.chat-page .history-header { padding: 0 16px 8px; border-bottom: none; }
.chat-page .history-title {
  font-family: var(--font-text); font-size: 12px; letter-spacing: 0; text-transform: none;
  color: var(--text-muted); font-weight: 700;
}
.chat-page .history-count {
  font-size: 11px; background: #edf5fb; color: var(--text-muted);
  border: 1px solid rgba(181, 210, 229, 0.72);
}
.chat-page .history-icon-btn { width: 32px; height: 32px; border-radius: 10px; background: transparent; }
.chat-page .history-search { margin: 0 16px 14px; padding: 10px 12px; border-radius: 13px; background: #edf5fb; }
.chat-page .history-list { padding: 0 10px 16px; }
.chat-page .history-group-label {
  font-family: var(--font-text); font-size: 12px; letter-spacing: 0; text-transform: none;
  color: #8a98a8; padding: 14px 12px 6px; font-weight: 700;
}
.chat-page .history-item { padding: 10px 12px; border-radius: 10px; }
.chat-page .history-item:hover { background: #eef6fc; }
.chat-page .history-item.active { background: #e8f3fb; box-shadow: inset 3px 0 0 var(--accent-blue); }
.chat-page .history-item-title { font-size: 14px; }
/* ============================================================ 动画 */
.anim-panel-left, .anim-panel-right, .anim-panel-center {
  opacity: 0; transform: translateY(8px);
  transition: opacity 0.4s cubic-bezier(0.16, 1, 0.3, 1), transform 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}
.anim-panel-right { transform: translateX(16px); }
.anim-panel-left  { transform: translateX(-16px); }
.ready.anim-panel-left, .ready.anim-panel-right, .ready.anim-panel-center {
  opacity: 1; transform: translate(0, 0);
}

/* ============================================================ 响应式 */
@media (max-width: 768px) {
  .history-panel.open { width: 240px; }
  .workbench-panel.open { width: 300px; }
  .chat-body { padding: 16px 12px 0; }
  .chat-footer { padding: 8px 8px 12px; }
  .user-bubble-wrap { max-width: 85%; }
  .welcome-screen { padding: 32px 16px 24px; }
  .welcome-title { font-size: 26px; }
  .sugg-group-items { grid-template-columns: 1fr; }
  .model-pill { padding: 5px 10px 5px 8px; font-size: 12px; }
  .header-toggle-btn { padding: 0 8px; font-size: 9px; }
  .title-text { max-width: 140px; }
  .bot-text { padding: 12px 14px 4px; }
  .thinking-block { margin: 12px 14px 0; }
  .message-artifacts { margin: 10px 14px 8px; }
  .message-artifact-main {
    grid-template-columns: 42px minmax(0, 1fr);
    gap: 10px;
  }
  .message-artifact-icon { width: 42px; height: 42px; }
  .message-artifact-actions {
    grid-column: 1 / -1;
    justify-content: flex-end;
  }
  .message-artifact-frame { height: 420px; }
}
/* ============================================================ DeepSeek-inspired responsive refresh */
@media (max-width: 768px) {
  .header-brand-name { display: none; }
  .back-btn, .new-chat-btn, .icon-btn { width: 44px; height: 44px; }
  .new-chat-btn { min-width: 44px; width: 44px; padding: 0; border-radius: 14px; }
  .new-chat-text { display: none; }
  .new-chat-plus { background: transparent; }
  .history-backdrop {
    position: absolute;
    inset: 0;
    z-index: 7;
    display: block;
    border: 0;
    background: rgba(14, 42, 71, 0.24);
    backdrop-filter: blur(2px);
    -webkit-backdrop-filter: blur(2px);
  }
  .chat-page .history-panel {
    position: absolute;
    inset: 0;
    order: initial;
    width: 100%;
    height: 100%;
    flex: 0 0 auto;
    transform: translateX(-100%);
    border-right: 0;
    opacity: 1;
    visibility: hidden;
    transition: transform 0.28s cubic-bezier(0.16, 1, 0.3, 1), visibility 0s linear 0.28s;
  }
  .chat-page .history-panel.open {
    width: 100%;
    flex-basis: auto;
    transform: translateX(0);
    visibility: visible;
    transition: transform 0.28s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .chat-page .history-icon-btn { width: 44px; height: 44px; }
  .welcome-logo-shell { width: 180px; height: 144px; }
  .welcome-logo-tagline { font-size: 12px; letter-spacing: 0.07em; white-space: normal; }
  .welcome-logo-tagline::before,
  .welcome-logo-tagline::after { width: 20px; }
  .welcome-brand-logo { margin-bottom: 20px; }
}
@media (max-width: 520px) { .header-brand { display: none; } }
@media (prefers-reduced-motion: reduce) {
  .msg-wrapper, .orb-ring, .orb-core, .model-orb, .bot-logo, .status-dot, .typing-line span,
  .thinking-dots span, .send-pulse, .suggestion-chip, .welcome-screen {
    animation: none !important;
    opacity: 1 !important;
    transform: none !important;
  }
}
</style>
