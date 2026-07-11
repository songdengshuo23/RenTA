(function () {
  "use strict";

  var ROUTE = "/agent-apply";
  var ROOT_ID = "agent-apply-bridge";
  var VERSION = "20260710-acps-v21-stage4";
  var DEFAULT_SCHEME_NAME = "mtls";
  var DEFAULT_CHALLENGE_URL = "http://10.126.126.8:8888/acps-atr-v2";
  var DEFAULT_CA_DIRECTORY_URL = "/acps-atr-v2/acme/directory";
  var EAB_DISPLAY_TTL_MS = 5 * 60 * 1000;
  var renderTimer = null;
  var observer = null;
  var featureConfig = {
    acpsV21FrontendEnabled: false,
    eabIssuanceEnabled: false,
    caDirectoryUrl: DEFAULT_CA_DIRECTORY_URL
  };

  var categoryOptions = [
    { label: "通用", value: "general" },
    { label: "旅行", value: "travel" },
    { label: "数据", value: "data" },
    { label: "检索", value: "search" },
    { label: "办公", value: "office" },
    { label: "代码", value: "code" },
    { label: "客服", value: "service" }
  ];

  var modeOptions = [
    { value: "text/plain", label: "纯文本" },
    { value: "application/json", label: "JSON 数据" },
    { value: "text/markdown", label: "Markdown 文档" },
    { value: "text/html", label: "HTML 页面" },
    { value: "image/png", label: "PNG 图片" },
    { value: "image/jpeg", label: "JPEG 图片" },
    { value: "audio/mpeg", label: "音频" }
  ];

  var countryOptions = [
    ["CN", "中国"], ["AF", "阿富汗"], ["AL", "阿尔巴尼亚"], ["DZ", "阿尔及利亚"],
    ["AR", "阿根廷"], ["AU", "澳大利亚"], ["AT", "奥地利"], ["BD", "孟加拉国"],
    ["BE", "比利时"], ["BR", "巴西"], ["CA", "加拿大"], ["CH", "瑞士"],
    ["CL", "智利"], ["DE", "德国"], ["DK", "丹麦"], ["EG", "埃及"],
    ["ES", "西班牙"], ["FI", "芬兰"], ["FR", "法国"], ["GB", "英国"],
    ["GR", "希腊"], ["ID", "印度尼西亚"], ["IE", "爱尔兰"], ["IN", "印度"],
    ["IT", "意大利"], ["JP", "日本"], ["KR", "韩国"], ["MX", "墨西哥"],
    ["MY", "马来西亚"], ["NL", "荷兰"], ["NO", "挪威"], ["NZ", "新西兰"],
    ["PH", "菲律宾"], ["PK", "巴基斯坦"], ["RU", "俄罗斯"], ["SA", "沙特阿拉伯"],
    ["SE", "瑞典"], ["SG", "新加坡"], ["TH", "泰国"], ["TR", "土耳其"],
    ["US", "美国"], ["VN", "越南"], ["ZA", "南非"]
  ].map(function (item) {
    return { code: item[0], name: item[1], label: item[0] + "（" + item[1] + "）" };
  });

  var transportOptions = [
    { value: "JSONRPC", label: "JSONRPC（平台 Agent 标准）", protocols: ["02.00", "02.01"] },
    { value: "HTTP", label: "HTTP（普通接口）", protocols: ["02.00"] },
    { value: "SSE", label: "SSE（事件流）", protocols: ["02.00"] },
    { value: "WEBSOCKET", label: "WebSocket（长连接）", protocols: ["02.00"] },
    { value: "HTTP_JSON", label: "HTTP JSON（ACPs 02.01）", protocols: ["02.01"] }
  ];

  function safeJson(value, fallback) {
    try {
      return JSON.parse(value);
    } catch (error) {
      return fallback;
    }
  }

  function loadFeatureConfig() {
    if (!window.fetch) return Promise.resolve(featureConfig);
    return window.fetch("/renta-config", { cache: "no-store" })
      .then(function (response) {
        if (!response.ok) throw new Error("config unavailable");
        return response.json();
      })
      .then(function (config) {
        var nextConfig = {
          acpsV21FrontendEnabled: config.acpsV21FrontendEnabled === true,
          eabIssuanceEnabled: config.eabIssuanceEnabled === true,
          caDirectoryUrl: config.caDirectoryUrl || DEFAULT_CA_DIRECTORY_URL
        };
        var changed = nextConfig.acpsV21FrontendEnabled !== featureConfig.acpsV21FrontendEnabled ||
          nextConfig.eabIssuanceEnabled !== featureConfig.eabIssuanceEnabled ||
          nextConfig.caDirectoryUrl !== featureConfig.caDirectoryUrl;
        featureConfig = nextConfig;
        if (isRoute() && (changed || !document.getElementById(ROOT_ID))) render(true);
        return featureConfig;
      })
      .catch(function () { return featureConfig; });
  }

  function isLegacyPricingUrl(url) {
    var text = String(url && url.url ? url.url : url || "");
    return text.indexOf("/api/agents/pricing-suggestion") >= 0 || text.indexOf("/agents/pricing-suggestion") >= 0;
  }

  function installLegacyPricingGuard() {
    if (window.__agentApplyPricingGuard) return;
    window.__agentApplyPricingGuard = true;

    var body = JSON.stringify({
      status: "success",
      data: { sample_count: 0, min: 0, max: 0, p25: 0, p50: 0, p75: 0 }
    });

    if (window.fetch) {
      var nativeFetch = window.fetch;
      window.fetch = function (input, init) {
        if (isLegacyPricingUrl(input)) {
          return Promise.resolve(new Response(body, {
            status: 200,
            headers: { "Content-Type": "application/json" }
          }));
        }
        return nativeFetch.apply(this, arguments);
      };
    }

    if (window.XMLHttpRequest && window.XMLHttpRequest.prototype) {
      var proto = window.XMLHttpRequest.prototype;
      var nativeOpen = proto.open;
      var nativeSend = proto.send;
      proto.open = function (method, url) {
        this.__agentApplyPricingRequest = isLegacyPricingUrl(url);
        return nativeOpen.apply(this, arguments);
      };
      proto.send = function () {
        if (!this.__agentApplyPricingRequest) {
          return nativeSend.apply(this, arguments);
        }
        var xhr = this;
        window.setTimeout(function () {
          try {
            Object.defineProperty(xhr, "readyState", { value: 4, configurable: true });
            Object.defineProperty(xhr, "status", { value: 200, configurable: true });
            Object.defineProperty(xhr, "statusText", { value: "OK", configurable: true });
            Object.defineProperty(xhr, "responseText", { value: body, configurable: true });
            Object.defineProperty(xhr, "response", { value: body, configurable: true });
          } catch (error) {}
          if (typeof xhr.onreadystatechange === "function") xhr.onreadystatechange();
          if (typeof xhr.onload === "function") xhr.onload(new Event("load"));
          if (typeof xhr.onloadend === "function") xhr.onloadend(new Event("loadend"));
        }, 0);
      };
    }
  }

  function getUser() {
    return safeJson(window.localStorage.getItem("user") || "null", null) || {};
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function isRoute() {
    return window.location.pathname === ROUTE;
  }

  function getHost() {
    return document.querySelector(".main-content") || document.querySelector("#app main");
  }

  function removeBridge() {
    var root = document.getElementById(ROOT_ID);
    if (root) {
      clearEabCredential(root);
      root.remove();
    }
    var host = getHost();
    if (host) host.removeAttribute("data-agent-apply-bridge");
  }

  function scheduleRender(delay) {
    window.clearTimeout(renderTimer);
    if (!isRoute()) {
      removeBridge();
      return;
    }
    renderTimer = window.setTimeout(function () {
      render(false);
    }, delay == null ? 80 : delay);
  }

  function slug(value) {
    var text = String(value || "")
      .trim()
      .toLowerCase()
      .replace(/[\u4e00-\u9fa5]+/g, " agent ")
      .replace(/[^a-z0-9]+/g, ".")
      .replace(/^\.+|\.+$/g, "");
    return text || "agent.skill";
  }

  function textHash(value) {
    var hash = 2166136261;
    var text = String(value || "");
    for (var i = 0; i < text.length; i += 1) {
      hash ^= text.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0).toString(36);
  }

  function skillSlug(values) {
    var source = values.skillName || values.name || "agent.skill";
    var id = slug(source);
    if (id === "agent" || id === "agent.skill") return "skill." + textHash(source);
    return id;
  }

  function buildAic(name) {
    var code = slug(name).replace(/[^a-z0-9]/g, "").toUpperCase().slice(0, 6).padEnd(6, "0");
    var serial = String(Date.now()).slice(-6).padStart(6, "0");
    return "1.2.156.3088.0001.00001." + code + "." + serial + ".1.0001";
  }

  function displayName(user) {
    return user.name || user.username || user.email || "当前登录账号";
  }

  function accountEmail(user) {
    if (user.email) return user.email;
    var base = String(user.username || user.name || "agent-owner")
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9._-]+/g, "-")
      .replace(/^-+|-+$/g, "");
    return (base || "agent-owner") + "@local.account";
  }

  function defaults() {
    var user = getUser();
    return {
      protocolVersion: featureConfig.acpsV21FrontendEnabled ? "02.01" : "02.00",
      name: "",
      version: "1.0.0",
      description: "",
      logoUrl: "",
      isOntology: false,
      providerAccountName: displayName(user),
      providerAccountEmail: accountEmail(user),
      organization: "",
      department: "",
      countryCode: user.country_code || "CN",
      providerUrl: "",
      license: "",
      maintainerName: "",
      email: "",
      endpointUrl: "",
      transport: "",
      schemeName: "",
      challengeUrl: "",
      amqpUrl: "",
      messageQueueVersion: "rabbitmq:>=4.2",
      certificateDns: "",
      certificateIp: "",
      requestedValidity: "365",
      skillId: "",
      skillName: "",
      skillVersion: "",
      skillDescription: "",
      selectedTags: ["general"],
      customTags: "",
      examples: "",
      inputModes: ["text/plain", "application/json"],
      outputModes: ["text/plain", "application/json", "text/markdown"],
      streaming: false,
      notification: false,
      entityUserId: "",
      documentationUrl: "",
      webAppUrl: ""
    };
  }

  function render(force) {
    if (!isRoute()) return;
    var host = getHost();
    if (!host) {
      scheduleRender(120);
      return;
    }

    var existing = host.querySelector("#" + ROOT_ID);
    if (existing && host.dataset.agentApplyBridge === VERSION && !force) return;

    var state = defaults();
    host.dataset.agentApplyBridge = VERSION;
    if (force && existing) existing.remove();
    host.insertAdjacentHTML("afterbegin", template(state));
    hydrate(host.querySelector("#" + ROOT_ID));
  }

  function field(name, label, required, value, attrs, hint) {
    attrs = attrs || "";
    var badge = required ? "必填" : "可选";
    return (
      '<div class="aab-field">' +
      '<label class="aab-label" for="aab-' + name + '"><span>' + label + '</span><b>' + badge + "</b></label>" +
      '<div class="aab-input"><input id="aab-' + name + '" name="' + name + '" value="' + escapeHtml(value) + '" ' + attrs + "></div>" +
      (hint ? '<p class="aab-hint">' + hint + "</p>" : "") +
      '<p class="aab-error" data-error-for="' + name + '"></p>' +
      "</div>"
    );
  }

  function readonlyField(label, value, hint) {
    return (
      '<div class="aab-field">' +
      '<label class="aab-label"><span>' + label + '</span><b>默认</b></label>' +
      '<div class="aab-readonly">' + escapeHtml(value || "当前登录账号") + "</div>" +
      (hint ? '<p class="aab-hint">' + hint + "</p>" : "") +
      "</div>"
    );
  }

  function textarea(name, label, required, value, attrs, hint) {
    attrs = attrs || "";
    var badge = required ? "必填" : "可选";
    return (
      '<div class="aab-field">' +
      '<label class="aab-label" for="aab-' + name + '"><span>' + label + '</span><b>' + badge + "</b></label>" +
      '<div class="aab-textarea"><textarea id="aab-' + name + '" name="' + name + '" ' + attrs + ">" + escapeHtml(value) + "</textarea></div>" +
      (hint ? '<p class="aab-hint">' + hint + "</p>" : "") +
      '<p class="aab-error" data-error-for="' + name + '"></p>' +
      "</div>"
    );
  }

  function sectionLegend(num, cn, en) {
    return (
      '<legend class="aab-section-legend">' +
      '<span class="aab-legend-num">' + num + "</span>" +
      '<span class="aab-legend-line"></span>' +
      '<span class="aab-legend-title">' + cn + "</span>" +
      '<span class="aab-legend-en">/ ' + en + "</span>" +
      "</legend>"
    );
  }

  function checkbox(name, value, label, checked, hint) {
    return (
      '<label class="aab-check">' +
      '<input type="checkbox" name="' + name + '" value="' + value + '"' + (checked ? " checked" : "") + ">" +
      '<span>' + label + (hint ? '<small>' + hint + "</small>" : "") + "</span>" +
      "</label>"
    );
  }

  function more(content) {
    return (
      '<details class="aab-more">' +
      '<summary><span>更多</span><em>/ Optional</em></summary>' +
      '<div class="aab-more-body">' + content + "</div>" +
      "</details>"
    );
  }

  function countryPicker(state) {
    return (
      '<div class="aab-field aab-combo-field" data-combo="country">' +
      '<label class="aab-label" for="aab-countryCode"><span>国家代码</span><b>默认</b></label>' +
      '<div class="aab-combo">' +
      '<input id="aab-countryCode" name="countryCode" value="' + escapeHtml(state.countryCode) + '" maxlength="8" autocomplete="off" placeholder="CN">' +
      '<button type="button" class="aab-combo-arrow" data-action="toggle-country" aria-label="展开国家代码">⌄</button>' +
      '<div class="aab-combo-menu" data-country-menu hidden></div>' +
      "</div>" +
      '<p class="aab-hint">默认 CN。可输入首字母筛选，也可以展开选择常见国家代码。</p>' +
      '<p class="aab-error" data-error-for="countryCode"></p>' +
      "</div>"
    );
  }

  function protocolTransportOptions(protocolVersion) {
    return transportOptions.filter(function (item) {
      return item.protocols.indexOf(protocolVersion || "02.00") >= 0;
    });
  }

  function protocolPicker(state) {
    if (!featureConfig.acpsV21FrontendEnabled) return "";
    return (
      '<fieldset class="aab-section aab-protocol-section">' +
      sectionLegend("00", "协议版本", "Protocol") +
      '<div class="aab-segmented" role="radiogroup" aria-label="ACPs 协议版本">' +
      '<label><input type="radio" name="protocolVersion" value="02.01"' + (state.protocolVersion === "02.01" ? " checked" : "") + '><span>ACPs 02.01</span></label>' +
      '<label><input type="radio" name="protocolVersion" value="02.00"' + (state.protocolVersion === "02.00" ? " checked" : "") + '><span>兼容 02.00</span></label>' +
      "</div>" +
      "</fieldset>"
    );
  }

  function transportSelect(state) {
    var options = ['<option value="">先填写端点后自动推荐</option>'].concat(protocolTransportOptions(state.protocolVersion).map(function (item) {
      return '<option value="' + item.value + '"' + (state.transport === item.value ? " selected" : "") + ">" + item.label + "</option>";
    })).join("");
    return (
      '<div class="aab-field">' +
      '<label class="aab-label" for="aab-transport"><span>传输协议</span><b>必填</b></label>' +
      '<div class="aab-input"><select id="aab-transport" name="transport">' + options + "</select></div>" +
      '<p class="aab-hint" data-transport-hint>填写端点后平台会自动推荐协议，用户仍可手动调整。</p>' +
      '<p class="aab-error" data-error-for="transport"></p>' +
      "</div>"
    );
  }

  function v21Configuration(state) {
    if (!featureConfig.acpsV21FrontendEnabled) return "";
    return (
      '<fieldset class="aab-section" data-protocol-only="02.01">' +
      sectionLegend("03A", "证书与消息队列", "ACPs 02.01") +
      '<div class="aab-grid">' +
      field("certificateDns", "证书 DNS SAN", false, state.certificateDns, 'placeholder="多个域名用逗号或换行分隔"') +
      field("certificateIp", "证书 IP SAN", false, state.certificateIp, 'placeholder="多个 IP 用逗号或换行分隔"') +
      field("requestedValidity", "证书有效期（天）", true, state.requestedValidity, 'type="number" min="1" step="1" inputmode="numeric"') +
      field("amqpUrl", "AMQP Endpoint", false, state.amqpUrl, 'placeholder="amqps://mq.example.com:5671/acps?inbox=inbox_{AIC}"') +
      field("messageQueueVersion", "消息队列版本", false, state.messageQueueVersion, 'placeholder="rabbitmq:>=4.2"') +
      "</div>" +
      "</fieldset>"
    );
  }

  function eabPanel() {
    if (!featureConfig.eabIssuanceEnabled) return "";
    return (
      '<section class="aab-section aab-eab-section">' +
      sectionLegend("EAB", "外部账户绑定", "Certificate") +
      '<form class="aab-eab-form" novalidate>' +
      '<div class="aab-eab-row">' +
      field("eabAic", "已审核 AIC", true, "", 'autocomplete="off" placeholder="输入已审核并激活的 02.01 Agent AIC"') +
      '<button type="submit" class="aab-btn aab-btn-primary" data-eab-submit>获取 EAB</button>' +
      "</div>" +
      '<p class="aab-hint">CA Directory：<a href="' + escapeHtml(featureConfig.caDirectoryUrl) + '" target="_blank" rel="noopener">' + escapeHtml(featureConfig.caDirectoryUrl) + "</a></p>" +
      '<div class="aab-alert aab-eab-alert" role="status" aria-live="polite" hidden></div>' +
      '<div class="aab-eab-result" hidden></div>' +
      "</form>" +
      "</section>"
    );
  }

  function modeChecks(name, selected) {
    return modeOptions.map(function (item) {
      return checkbox(name, item.value, item.label, selected.indexOf(item.value) >= 0, item.value);
    }).join("");
  }

  function template(state) {
    var tags = categoryOptions.map(function (item) {
      var active = state.selectedTags.indexOf(item.value) >= 0 ? " is-active" : "";
      return '<button type="button" class="aab-chip' + active + '" data-tag="' + item.value + '">' + item.label + "</button>";
    }).join("");

    return (
      '<section id="' + ROOT_ID + '" class="aab-page">' +
      '<div class="aab-bg" aria-hidden="true"><div class="aab-bg-grid"></div><div class="aab-bg-glow"></div></div>' +
      '<div class="aab-container">' +
      '<header class="aab-header">' +
      '<div class="aab-eyebrow"><span class="aab-dot"></span><span>注册向导</span><span class="aab-line"></span><span>Agent Capability Spec</span></div>' +
      '<h1>注册智能体到 <span>Registry</span></h1>' +
      '<p>只填写必要信息。平台会自动补齐账号提供方、协议安全、技能 ID 和 ACS 必需字段。</p>' +
      "</header>" +
      '<form class="aab-form" novalidate>' +
      protocolPicker(state) +
      '<fieldset class="aab-section">' +
      sectionLegend("01", "基础信息", "Identity") +
      '<div class="aab-grid">' +
      field("name", "智能体名称", true, state.name, 'maxlength="255" autocomplete="off" placeholder="例：云南亲子旅行规划 Agent"') +
      field("version", "版本", true, state.version, 'maxlength="64" autocomplete="off" placeholder="例：1.0.0"') +
      "</div>" +
      textarea("description", "能力描述", true, state.description, 'maxlength="2000" rows="5" placeholder="用中文说明智能体能做什么、适合处理什么请求、能力边界在哪里。"') +
      more('<div class="aab-grid">' +
        field("logoUrl", "图标 URL", false, state.logoUrl, 'type="url" placeholder="例：https://example.com/icon.png"') +
        '<div class="aab-field aab-toggle-field">' +
        '<label class="aab-label"><span>Ontology 本体</span><b>可选</b></label>' +
        '<label class="aab-switch"><input type="checkbox" name="isOntology"><span></span><em>允许后续派生实体 Agent</em></label>' +
        "</div>" +
        "</div>") +
      "</fieldset>" +
      '<fieldset class="aab-section">' +
      sectionLegend("02", "提供方", "Provider") +
      readonlyField("默认提供方", state.providerAccountName, "默认使用上传 Agent 的当前登录账号。") +
      more('<div class="aab-grid">' +
        field("organization", "组织或团队名称", false, state.organization, 'maxlength="255" autocomplete="organization" placeholder="以组织或团队名义上传时填写"') +
        field("email", "组织联系邮箱", false, state.email, 'type="email" autocomplete="email" placeholder="例：team@example.com"') +
        countryPicker(state) +
        field("department", "部门", false, state.department, 'maxlength="255" placeholder="例：智能体研发部"') +
        field("providerUrl", "组织主页", false, state.providerUrl, 'type="url" placeholder="例：https://example.com"') +
        field("license", "授权方式", false, state.license, 'maxlength="120" placeholder="例：商业授权 / MIT / 内部使用"') +
        field("maintainerName", "维护人", false, state.maintainerName, 'maxlength="120" placeholder="例：张三"') +
        "</div>") +
      "</fieldset>" +
      '<fieldset class="aab-section">' +
      sectionLegend("03", "端点与安全", "Endpoint") +
      field("endpointUrl", "RPC Endpoint", true, state.endpointUrl, 'type="url" placeholder="例：http://travel-agent-proxy:8099/agents/demo/rpc"') +
      transportSelect(state) +
      '<div data-protocol-only="02.00">' + more('<div class="aab-grid">' +
        field("schemeName", "安全方案名", false, state.schemeName, 'maxlength="64" placeholder="默认使用：mtls"') +
        field("challengeUrl", "CA Challenge URL", false, state.challengeUrl, 'type="url" placeholder="默认使用平台 CA Challenge 服务地址"') +
        "</div>") + "</div>" +
      "</fieldset>" +
      v21Configuration(state) +
      '<fieldset class="aab-section">' +
      sectionLegend("04", "技能描述", "Skill") +
      '<div class="aab-grid">' +
      field("skillName", "当前技能名称", true, state.skillName, 'maxlength="255" placeholder="例：亲子旅游规划"') +
      textarea("skillDescription", "技能说明", true, state.skillDescription, 'rows="4" maxlength="1200" placeholder="用中文说明该技能接收什么输入、生成什么结果，以及不适合处理什么。"') +
      "</div>" +
      '<div class="aab-field"><label class="aab-label"><span>技能标签</span><b>必填</b></label><div class="aab-chip-row">' + tags + '</div><p class="aab-error" data-error-for="tags"></p></div>' +
      '<div class="aab-grid">' +
      '<div class="aab-field"><label class="aab-label"><span>输入格式</span><b>必填</b></label><div class="aab-check-row">' + modeChecks("inputModes", state.inputModes) + '</div><p class="aab-hint">默认支持“纯文本”和“JSON 数据”。</p><p class="aab-error" data-error-for="inputModes"></p></div>' +
      '<div class="aab-field"><label class="aab-label"><span>输出格式</span><b>必填</b></label><div class="aab-check-row">' + modeChecks("outputModes", state.outputModes) + '</div><p class="aab-hint">默认支持“纯文本”、“JSON 数据”和“Markdown 文档”。</p><p class="aab-error" data-error-for="outputModes"></p></div>' +
      "</div>" +
      more('<div class="aab-grid">' +
        field("skillId", "技能 ID", false, state.skillId, 'maxlength="120" autocomplete="off" placeholder="平台会根据技能名称自动生成"') +
        field("skillVersion", "技能版本", false, state.skillVersion, 'maxlength="64" placeholder="默认跟随 Agent 版本"') +
        '</div>' +
        '<div class="aab-field"><label class="aab-label"><span>补充标签</span><b>可选</b></label><div class="aab-input aab-tag-input"><input name="customTags" value="' + escapeHtml(state.customTags) + '" placeholder="用中文逗号或英文逗号分隔"></div><p class="aab-hint">例如：亲子，行程，预算。</p></div>' +
        textarea("examples", "调用示例", false, state.examples, 'rows="3" placeholder="每行一个示例，例如：帮我规划 5 天大理丽江亲子游"')) +
      "</fieldset>" +
      '<fieldset class="aab-section">' +
      sectionLegend("05", "高级配置", "Advanced") +
      more('<div class="aab-grid">' +
        '<div class="aab-field"><label class="aab-label"><span>交互能力</span><b>可选</b></label><div class="aab-check-row">' +
        checkbox("streaming", "true", "流式返回", state.streaming, "适合长文本逐步输出") +
        checkbox("notification", "true", "通知回调", state.notification, "适合异步任务完成提醒") +
        "</div></div>" +
        field("entityUserId", "实体用户 ID", false, state.entityUserId, 'maxlength="255" placeholder="需要绑定具体实体用户时填写"') +
        field("documentationUrl", "文档地址", false, state.documentationUrl, 'type="url" placeholder="例：https://docs.example.com/agent"') +
        field("webAppUrl", "演示地址", false, state.webAppUrl, 'type="url" placeholder="例：https://app.example.com/agent"') +
        "</div>") +
      "</fieldset>" +
      '<div class="aab-alert" role="status" aria-live="polite" hidden></div>' +
      '<div class="aab-actions">' +
      '<button type="button" class="aab-btn aab-btn-ghost" data-action="reset">清空</button>' +
      '<button type="button" class="aab-btn aab-btn-ghost" data-action="preview">预览 ACS</button>' +
      '<button type="submit" class="aab-btn aab-btn-primary"><span class="aab-btn-text">创建并提交</span><span class="aab-spinner" aria-hidden="true"></span></button>' +
      "</div>" +
      "</form>" +
      eabPanel() +
      '<div class="aab-result" hidden></div>' +
      "</div>" +
      '<div class="aab-modal" hidden><div class="aab-modal-card" role="dialog" aria-modal="true" aria-label="ACS 预览"><div class="aab-modal-head"><h2>ACS 预览</h2><button type="button" data-action="close-preview">×</button></div><pre></pre></div></div>' +
      "</section>"
    );
  }

  function readForm(root) {
    var form = root.querySelector(".aab-form");
    var fd = new FormData(form);
    var selectedTags = Array.prototype.slice.call(root.querySelectorAll(".aab-chip.is-active"))
      .map(function (item) { return item.dataset.tag; });
    var values = {};
    fd.forEach(function (value, key) {
      if (key === "inputModes" || key === "outputModes") return;
      values[key] = String(value).trim();
    });
    values.selectedTags = selectedTags;
    values.inputModes = Array.prototype.slice.call(root.querySelectorAll('input[name="inputModes"]:checked')).map(function (item) { return item.value; });
    values.outputModes = Array.prototype.slice.call(root.querySelectorAll('input[name="outputModes"]:checked')).map(function (item) { return item.value; });
    values.isOntology = !!root.querySelector('input[name="isOntology"]:checked');
    values.streaming = !!root.querySelector('input[name="streaming"]:checked');
    values.notification = !!root.querySelector('input[name="notification"]:checked');
    values.protocolVersion = values.protocolVersion || "02.00";

    var user = getUser();
    values.providerAccountName = displayName(user);
    values.providerAccountEmail = accountEmail(user);
    values.countryCode = normalizeCountry(values.countryCode || "CN");
    values.transport = values.transport || inferTransport(values.endpointUrl, values.protocolVersion);
    values.schemeName = values.schemeName || DEFAULT_SCHEME_NAME;
    if (values.protocolVersion === "02.00") values.challengeUrl = values.challengeUrl || DEFAULT_CHALLENGE_URL;
    values.skillId = values.skillId || skillSlug(values);
    values.skillVersion = values.skillVersion || values.version;
    values.email = values.email || values.providerAccountEmail || accountEmail(user);
    return values;
  }

  function splitList(value) {
    return String(value || "")
      .split(/[\n,，]+/)
      .map(function (item) { return item.trim(); })
      .filter(Boolean);
  }

  function tagsFor(values) {
    var custom = splitList(values.customTags);
    var combined = values.selectedTags.concat(custom);
    return Array.from(new Set(combined)).filter(Boolean);
  }

  function normalizeCountry(value) {
    var text = String(value || "").trim().toUpperCase();
    var found = countryOptions.find(function (item) {
      return item.code === text || item.label.toUpperCase() === text;
    });
    return found ? found.code : text;
  }

  function isUrl(value, required) {
    if (!value && !required) return true;
    try {
      var url = new URL(value);
      return url.protocol === "http:" || url.protocol === "https:";
    } catch (error) {
      return false;
    }
  }

  function isAmqpUrl(value) {
    if (!value) return true;
    return /^amqps?:\/\/[^\s]+$/i.test(value);
  }

  function inferTransport(endpoint, protocolVersion) {
    if (!endpoint) return "";
    var lower = String(endpoint).toLowerCase();
    if (lower.indexOf("/rpc") >= 0 || lower.indexOf("travel-agent-proxy") >= 0 || lower.indexOf("/agents/") >= 0) return "JSONRPC";
    if (lower.indexOf("/api/") >= 0 || /\/(chat|invoke|completion|generate)(\/|$)/.test(lower)) {
      return protocolVersion === "02.01" ? "HTTP_JSON" : "HTTP";
    }
    return "JSONRPC";
  }

  function transportLabel(value) {
    var found = transportOptions.find(function (item) { return item.value === value; });
    return found ? found.label : value;
  }

  function validate(values) {
    var errors = {};
    var isV21 = values.protocolVersion === "02.01";
    if (!values.name) errors.name = "请填写智能体名称";
    if (!values.version) errors.version = "请填写版本";
    if (!values.description) errors.description = "请填写能力描述";
    if (values.logoUrl && !isUrl(values.logoUrl, false)) errors.logoUrl = "图标 URL 格式不正确";
    if (values.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email)) errors.email = "邮箱格式不正确";
    if (!values.countryCode) errors.countryCode = "请选择或填写国家代码";
    if (values.providerUrl && !isUrl(values.providerUrl, false)) errors.providerUrl = "组织主页 URL 格式不正确";
    if (!isUrl(values.endpointUrl, true)) errors.endpointUrl = "请填写可访问的 RPC Endpoint";
    if (!values.transport) errors.transport = "请确认传输协议";
    if (isV21 && ["JSONRPC", "HTTP_JSON"].indexOf(values.transport) < 0) errors.transport = "02.01 端点仅支持 JSONRPC 或 HTTP JSON";
    if (!isV21 && values.challengeUrl && !isUrl(values.challengeUrl, true)) errors.challengeUrl = "CA Challenge URL 格式不正确";
    if (isV21) {
      var validity = Number(values.requestedValidity);
      if (!Number.isInteger(validity) || validity < 1) errors.requestedValidity = "请输入不少于 1 天的整数";
      if (values.amqpUrl && !isAmqpUrl(values.amqpUrl)) errors.amqpUrl = "请填写 amqp:// 或 amqps:// 地址";
      if (values.amqpUrl && values.messageQueueVersion && !/^(mqtt|amqp|kafka|redis|rabbitmq):(>=)?\d+\.(\*|\d+(\.\d+)?)( <\d+\.\d+(\.\d+)?)?$/.test(values.messageQueueVersion)) {
        errors.messageQueueVersion = "消息队列版本格式不正确";
      }
    }
    if (!values.skillName) errors.skillName = "请填写当前技能名称";
    if (!values.skillDescription) errors.skillDescription = "请填写技能说明";
    if (tagsFor(values).length === 0) errors.tags = "请至少选择一个技能标签";
    if (values.inputModes.length === 0) errors.inputModes = "请至少选择一种输入格式";
    if (values.outputModes.length === 0) errors.outputModes = "请至少选择一种输出格式";
    if (values.documentationUrl && !isUrl(values.documentationUrl, false)) errors.documentationUrl = "文档地址格式不正确";
    if (values.webAppUrl && !isUrl(values.webAppUrl, false)) errors.webAppUrl = "演示地址格式不正确";
    return errors;
  }

  function showErrors(root, errors) {
    root.querySelectorAll(".aab-error").forEach(function (item) {
      item.textContent = "";
    });
    root.querySelectorAll(".aab-field").forEach(function (item) {
      item.classList.remove("has-error");
    });

    Object.keys(errors).forEach(function (key) {
      var target = root.querySelector('[data-error-for="' + key + '"]');
      if (target) {
        target.textContent = errors[key];
        var fieldNode = target.closest(".aab-field");
        if (fieldNode) fieldNode.classList.add("has-error");
      }
    });

    var first = Object.keys(errors)[0];
    if (first) {
      var input = root.querySelector('[name="' + first + '"], [data-error-for="' + first + '"]');
      if (input && input.scrollIntoView) input.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  function compactObject(input) {
    var output = {};
    Object.keys(input).forEach(function (key) {
      var value = input[key];
      if (value !== "" && value != null) output[key] = value;
    });
    return output;
  }

  function buildPayload(values) {
    var schemeName = values.schemeName || DEFAULT_SCHEME_NAME;
    var isV21 = values.protocolVersion === "02.01";
    var now = new Date().toISOString();
    var skillDescription = values.skillDescription || values.description;
    var examples = splitList(values.examples);
    var user = getUser();
    var accountName = values.providerAccountName || displayName(user);
    var provider = compactObject({
      countryCode: values.countryCode || "CN",
      organization: values.organization || accountName,
      department: values.department,
      url: values.providerUrl,
      license: values.license,
      name: values.maintainerName || accountName,
      email: values.email || values.providerAccountEmail || accountEmail(user)
    });

    var securityRequirement = (function () {
      var item = {};
      item[schemeName] = [];
      return item;
    })();
    var endPoints = [
      {
        url: values.endpointUrl,
        transport: values.transport || "JSONRPC",
        security: [securityRequirement]
      }
    ];
    if (isV21 && values.amqpUrl) {
      endPoints.push({
        url: values.amqpUrl,
        transport: "AMQP",
        security: [securityRequirement]
      });
    }

    var messageQueue = isV21 && values.amqpUrl
      ? splitList(values.messageQueueVersion || "rabbitmq:>=4.2")
      : [];
    var acs = compactObject({
      aic: isV21 ? "{AIC}" : buildAic(values.name),
      active: true,
      lastModifiedTime: now,
      protocolVersion: isV21 ? "02.01" : "02.00",
      name: values.name,
      description: values.description,
      version: values.version,
      iconUrl: values.logoUrl,
      documentationUrl: values.documentationUrl,
      webAppUrl: values.webAppUrl,
      provider: provider,
      securitySchemes: {},
      endPoints: endPoints,
      capabilities: {
        streaming: !!values.streaming,
        notification: !!values.notification,
        messageQueue: messageQueue
      },
      defaultInputModes: values.inputModes,
      defaultOutputModes: values.outputModes,
      skills: [
        {
          id: values.skillId || skillSlug(values),
          name: values.skillName,
          description: skillDescription,
          version: values.skillVersion || values.version,
          tags: tagsFor(values),
          examples: examples.length ? examples : [skillDescription],
          inputModes: values.inputModes,
          outputModes: values.outputModes
        }
      ],
      entityUserId: values.entityUserId
    });

    var securityScheme = {
      type: "mutualTLS",
      description: "Agent 调用使用 mTLS 双向认证"
    };
    if (!isV21) securityScheme["x-caChallengeBaseUrl"] = values.challengeUrl || DEFAULT_CHALLENGE_URL;
    acs.securitySchemes[schemeName] = securityScheme;

    if (isV21) {
      var dnsNames = splitList(values.certificateDns);
      var ipAddresses = splitList(values.certificateIp);
      acs.certificate = {
        altNames: {},
        requestedValidity: Number(values.requestedValidity)
      };
      if (dnsNames.length) acs.certificate.altNames.dns = dnsNames;
      if (ipAddresses.length) acs.certificate.altNames.ip = ipAddresses;
    }

    return {
      name: values.name,
      version: values.version,
      description: values.description,
      logo_url: values.logoUrl || null,
      is_ontology: !!values.isOntology,
      acs: acs
    };
  }

  function setBusy(root, busy) {
    var button = root.querySelector('button[type="submit"]');
    if (!button) return;
    button.disabled = busy;
    root.classList.toggle("is-busy", busy);
    button.querySelector(".aab-btn-text").textContent = busy ? "提交中" : "创建并提交";
  }

  function showAlert(root, type, message) {
    var alert = root.querySelector(".aab-alert");
    if (!alert) return;
    alert.hidden = false;
    alert.className = "aab-alert is-" + type;
    alert.textContent = message;
  }

  function hideAlert(root) {
    var alert = root.querySelector(".aab-alert");
    if (alert) alert.hidden = true;
  }

  function unwrap(data, response) {
    if (data && typeof data === "object") {
      if (typeof data.status_code === "number" && data.status_code >= 400) {
        throw new Error(data.error_msg || data.error_name || "请求失败");
      }
      if ("detail" in data && !("data" in data)) {
        throw new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail));
      }
      if ("status" in data && "data" in data) {
        if (data.status === "error") throw new Error(data.message || "请求失败");
        return data.data;
      }
    }
    if (!response.ok) {
      throw new Error((data && (data.error_msg || data.message || data.detail)) || ("HTTP " + response.status));
    }
    return data;
  }

  async function refreshToken() {
    var token = window.localStorage.getItem("refresh_token");
    if (!token) return false;
    var response = await window.fetch("/api/auth/refresh-token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: token })
    });
    if (!response.ok) return false;
    var data = await response.json();
    var next = data.access_token || data.token || (data.data && (data.data.access_token || data.data.token));
    if (!next) return false;
    window.localStorage.setItem("access_token", next);
    if (data.refresh_token || (data.data && data.data.refresh_token)) {
      window.localStorage.setItem("refresh_token", data.refresh_token || data.data.refresh_token);
    }
    return true;
  }

  async function api(path, options, retried) {
    var token = window.localStorage.getItem("access_token");
    if (!token) {
      throw new Error("请先登录 CLIENT 账号");
    }
    var response = await window.fetch("/api" + path, {
      method: options.method || "GET",
      headers: Object.assign({
        "Content-Type": "application/json",
        Authorization: "Bearer " + token
      }, options.headers || {}),
      body: options.body == null ? undefined : JSON.stringify(options.body)
    });
    if (response.status === 401 && !retried && await refreshToken()) {
      return api(path, options, true);
    }
    var text = await response.text();
    var data = text ? safeJson(text, text) : null;
    return unwrap(data, response);
  }

  async function registryApi(path, options, retried) {
    var token = window.localStorage.getItem("access_token");
    if (!token) throw new Error("请先登录 CLIENT 账号");
    var response = await window.fetch(path, {
      method: options.method || "GET",
      headers: Object.assign({
        "Content-Type": "application/json",
        Authorization: "Bearer " + token
      }, options.headers || {}),
      body: options.body == null ? undefined : JSON.stringify(options.body)
    });
    if (response.status === 401 && !retried && await refreshToken()) {
      return registryApi(path, options, true);
    }
    var text = await response.text();
    var data = text ? safeJson(text, text) : null;
    return unwrap(data, response);
  }

  function setEabBusy(root, busy) {
    var button = root.querySelector("[data-eab-submit]");
    if (!button) return;
    button.disabled = busy;
    button.textContent = busy ? "获取中" : "获取 EAB";
  }

  function showEabAlert(root, type, message) {
    var alert = root.querySelector(".aab-eab-alert");
    if (!alert) return;
    alert.hidden = false;
    alert.className = "aab-alert aab-eab-alert is-" + type;
    alert.textContent = message;
  }

  function clearEabCredential(root) {
    if (!root) return;
    window.clearTimeout(root.__eabClearTimer);
    root.__eabClearTimer = null;
    root.__eabCredential = null;
    var box = root.querySelector(".aab-eab-result");
    if (box) {
      box.textContent = "";
      box.hidden = true;
    }
  }

  function showEabCredential(root, credential) {
    clearEabCredential(root);
    root.__eabCredential = {
      keyId: String(credential.keyId || ""),
      macKey: String(credential.macKey || ""),
      aic: String(credential.aic || ""),
      expiresAt: String(credential.expiresAt || "")
    };
    var box = root.querySelector(".aab-eab-result");
    if (!box) return;
    box.hidden = false;
    box.innerHTML =
      '<dl>' +
      '<div><dt>Key ID</dt><dd>' + escapeHtml(root.__eabCredential.keyId) + "</dd></div>" +
      '<div><dt>MAC Key</dt><dd>' + escapeHtml(root.__eabCredential.macKey) + "</dd></div>" +
      '<div><dt>AIC</dt><dd>' + escapeHtml(root.__eabCredential.aic) + "</dd></div>" +
      '<div><dt>失效时间</dt><dd>' + escapeHtml(root.__eabCredential.expiresAt) + "</dd></div>" +
      "</dl>" +
      '<div class="aab-result-actions">' +
      '<button type="button" class="aab-btn aab-btn-primary" data-action="copy-eab">复制凭据</button>' +
      '<button type="button" class="aab-btn aab-btn-ghost" data-action="clear-eab">清除</button>' +
      "</div>";
    root.__eabClearTimer = window.setTimeout(function () {
      clearEabCredential(root);
      showEabAlert(root, "warn", "EAB 凭据已从页面清除。");
    }, EAB_DISPLAY_TTL_MS);
  }

  async function requestEab(root) {
    var input = root.querySelector('[name="eabAic"]');
    var aic = input ? input.value.trim() : "";
    if (!aic) {
      showEabAlert(root, "warn", "请输入已审核 Agent 的 AIC。");
      return;
    }
    setEabBusy(root, true);
    try {
      var credential = await registryApi("/acps-atr-v2/eab/" + encodeURIComponent(aic), { method: "POST" });
      if (!credential || !credential.keyId || !credential.macKey) throw new Error("Registry 未返回完整 EAB 凭据");
      showEabCredential(root, credential);
      showEabAlert(root, "success", "EAB 凭据已生成，请立即用于 ACME new-account。");
    } catch (error) {
      clearEabCredential(root);
      showEabAlert(root, "error", error.message || "EAB 获取失败");
    } finally {
      setEabBusy(root, false);
    }
  }

  async function copyEabCredential(root, button) {
    var credential = root.__eabCredential;
    if (!credential || !credential.macKey) return;
    var text = JSON.stringify(credential, null, 2);
    if (window.navigator.clipboard && window.navigator.clipboard.writeText) {
      await window.navigator.clipboard.writeText(text);
    } else {
      var textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.setAttribute("readonly", "");
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      var copied = document.execCommand("copy");
      textarea.remove();
      if (!copied) throw new Error("clipboard unavailable");
    }
    if (button) {
      button.textContent = "已复制";
      window.setTimeout(function () { button.textContent = "复制凭据"; }, 1600);
    }
  }

  function resultValue(agent, submitResult) {
    var source = submitResult || agent || {};
    return {
      id: source.id || agent.id || "",
      name: source.name || agent.name || "",
      status: source.approval_status || source.status || agent.approval_status || "",
      aic: source.aic || agent.aic || "",
      passport: source.passport_id || source.passportId || ""
    };
  }

  function showResult(root, agent, submitResult) {
    var data = resultValue(agent, submitResult);
    var box = root.querySelector(".aab-result");
    if (!box) return;
    box.hidden = false;
    box.innerHTML =
      '<div class="aab-result-icon">✓</div>' +
      '<div class="aab-result-main">' +
      '<h2>注册请求已提交</h2>' +
      '<p>' + escapeHtml(data.name || "智能体") + ' 已创建并进入 Registry 审核流程。</p>' +
      '<dl>' +
      '<div><dt>Agent ID</dt><dd>' + escapeHtml(data.id || "-") + "</dd></div>" +
      '<div><dt>审核状态</dt><dd>' + escapeHtml(data.status || "-") + "</dd></div>" +
      '<div><dt>AIC</dt><dd>' + escapeHtml(data.aic || "审核通过后返回") + "</dd></div>" +
      "</dl>" +
      '<div class="aab-result-actions"><a class="aab-btn aab-btn-primary" href="/square">查看广场</a><button type="button" class="aab-btn aab-btn-ghost" data-action="reset">再注册一个</button></div>' +
      "</div>";
    box.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function openPreview(root) {
    var values = readForm(root);
    var payload = buildPayload(values);
    var modal = root.querySelector(".aab-modal");
    modal.querySelector("pre").textContent = JSON.stringify(payload.acs, null, 2);
    modal.hidden = false;
  }

  function closePreview(root) {
    var modal = root.querySelector(".aab-modal");
    if (modal) modal.hidden = true;
  }

  function resetForm(root) {
    clearEabCredential(root);
    var host = root.parentElement;
    if (host) {
      host.dataset.agentApplyBridge = "";
      render(true);
    }
  }

  function updateCountryMenu(root) {
    var input = root.querySelector('[name="countryCode"]');
    var menu = root.querySelector("[data-country-menu]");
    if (!input || !menu) return;
    var query = input.value.trim().toUpperCase();
    var options = countryOptions.filter(function (item) {
      return !query || item.code.indexOf(query) === 0 || item.name.indexOf(query) === 0 || item.label.toUpperCase().indexOf(query) >= 0;
    }).slice(0, 12);
    if (!options.length) {
      options = [{ code: query || "CN", label: query ? query + "（自定义）" : "CN（中国）" }];
    }
    menu.innerHTML = options.map(function (item) {
      return '<button type="button" data-country="' + escapeHtml(item.code) + '">' + escapeHtml(item.label) + "</button>";
    }).join("");
  }

  function toggleCountryMenu(root, open) {
    var menu = root.querySelector("[data-country-menu]");
    if (!menu) return;
    updateCountryMenu(root);
    menu.hidden = open == null ? !menu.hidden : !open;
  }

  function syncEndpointTransport(root, force) {
    var endpoint = root.querySelector('[name="endpointUrl"]');
    var transport = root.querySelector('[name="transport"]');
    var hint = root.querySelector("[data-transport-hint]");
    if (!endpoint || !transport) return;
    var protocol = root.querySelector('[name="protocolVersion"]:checked');
    var inferred = inferTransport(endpoint.value, protocol ? protocol.value : "02.00");
    if (!endpoint.value.trim()) {
      transport.value = "";
      if (hint) hint.textContent = "填写端点后平台会自动推荐协议，用户仍可手动调整。";
      return;
    }
    if (force || !transport.dataset.userChanged || !transport.value) {
      transport.value = inferred;
      transport.dataset.autoValue = inferred;
    }
    if (hint) hint.textContent = "已根据端点推荐：" + transportLabel(transport.value || inferred) + "。";
  }

  function syncProtocolUi(root) {
    var selected = root.querySelector('[name="protocolVersion"]:checked');
    var protocolVersion = selected ? selected.value : "02.00";
    root.querySelectorAll("[data-protocol-only]").forEach(function (item) {
      item.hidden = item.dataset.protocolOnly !== protocolVersion;
    });

    var select = root.querySelector('[name="transport"]');
    if (select) {
      var previous = select.value;
      var options = protocolTransportOptions(protocolVersion);
      select.innerHTML = '<option value="">先填写端点后自动推荐</option>' + options.map(function (item) {
        return '<option value="' + item.value + '">' + item.label + "</option>";
      }).join("");
      if (options.some(function (item) { return item.value === previous; })) select.value = previous;
      else select.dataset.userChanged = "";
    }
    syncEndpointTransport(root, true);
  }

  function syncSkillDefaults(root) {
    var version = root.querySelector('[name="version"]');
    var skillVersion = root.querySelector('[name="skillVersion"]');
    var skillName = root.querySelector('[name="skillName"]');
    var skillId = root.querySelector('[name="skillId"]');
    if (skillVersion && version && (!skillVersion.value.trim() || skillVersion.dataset.auto === "1")) {
      skillVersion.value = version.value;
      skillVersion.dataset.auto = "1";
    }
    if (skillId && (!skillId.value.trim() || skillId.dataset.auto === "1")) {
      skillId.value = skillSlug({ skillName: skillName ? skillName.value : "", name: root.querySelector('[name="name"]') ? root.querySelector('[name="name"]').value : "" });
      skillId.dataset.auto = "1";
    }
  }

  function hydrate(root) {
    if (!root) return;
    updateCountryMenu(root);
    syncProtocolUi(root);
    syncSkillDefaults(root);

    root.addEventListener("click", function (event) {
      var country = event.target.closest("[data-country]");
      if (country) {
        var input = root.querySelector('[name="countryCode"]');
        if (input) input.value = country.dataset.country;
        toggleCountryMenu(root, false);
        return;
      }

      var chip = event.target.closest(".aab-chip");
      if (chip) {
        chip.classList.toggle("is-active");
        return;
      }
      var action = event.target.closest("[data-action]");
      if (!action) return;
      var name = action.dataset.action;
      if (name === "preview") openPreview(root);
      if (name === "close-preview") closePreview(root);
      if (name === "reset") resetForm(root);
      if (name === "toggle-country") toggleCountryMenu(root);
      if (name === "clear-eab") clearEabCredential(root);
      if (name === "copy-eab") {
        copyEabCredential(root, action).catch(function () {
          showEabAlert(root, "error", "无法写入剪贴板，请检查浏览器权限。");
        });
      }
    });

    root.addEventListener("input", function (event) {
      var target = event.target;
      if (!target) return;
      if (target.name === "endpointUrl") syncEndpointTransport(root, true);
      if (target.name === "countryCode") toggleCountryMenu(root, true);
      if (target.name === "version" || target.name === "skillName" || target.name === "name") syncSkillDefaults(root);
      if (target.name === "skillId") target.dataset.auto = target.value.trim() ? "0" : "1";
      if (target.name === "skillVersion") target.dataset.auto = target.value.trim() ? "0" : "1";
    });

    root.addEventListener("change", function (event) {
      if (event.target && event.target.name === "transport") event.target.dataset.userChanged = "1";
      if (event.target && event.target.name === "protocolVersion") syncProtocolUi(root);
    });

    document.addEventListener("click", function (event) {
      if (!root.contains(event.target)) toggleCountryMenu(root, false);
    });

    root.querySelector(".aab-form").addEventListener("submit", async function (event) {
      event.preventDefault();
      hideAlert(root);
      var values = readForm(root);
      var errors = validate(values);
      showErrors(root, errors);
      if (Object.keys(errors).length) {
        showAlert(root, "warn", "请先修正表单中标红的字段。");
        return;
      }

      var payload = buildPayload(values);
      setBusy(root, true);
      try {
        var created = await api("/agent/client", { method: "POST", body: payload });
        if (!created || !created.id) throw new Error("创建智能体失败：后端未返回 id");
        var submitted = await api("/agent/client/" + encodeURIComponent(created.id) + "/submit", { method: "POST" });
        showAlert(root, "success", "创建成功，已提交 Registry 审核。");
        showResult(root, created, submitted);
      } catch (error) {
        showAlert(root, "error", error.message || "注册失败");
      } finally {
        setBusy(root, false);
      }
    });

    var eabForm = root.querySelector(".aab-eab-form");
    if (eabForm) {
      eabForm.addEventListener("submit", function (event) {
        event.preventDefault();
        requestEab(root);
      });
    }
  }

  function installRouteHooks() {
    if (window.__agentApplyBridgeHooks) return;
    window.__agentApplyBridgeHooks = true;
    ["pushState", "replaceState"].forEach(function (method) {
      var original = history[method];
      history[method] = function () {
        var result = original.apply(this, arguments);
        scheduleRender(120);
        return result;
      };
    });
    window.addEventListener("popstate", function () { scheduleRender(120); });
    window.addEventListener("pagehide", function () {
      clearEabCredential(document.getElementById(ROOT_ID));
    });
    document.addEventListener("DOMContentLoaded", function () { scheduleRender(160); });
    window.addEventListener("load", function () { scheduleRender(160); });

    observer = new MutationObserver(function () {
      if (!isRoute()) {
        removeBridge();
        return;
      }
      var host = getHost();
      if (!host || !host.querySelector("#" + ROOT_ID)) scheduleRender(120);
    });
    var app = document.querySelector("#app") || document.documentElement;
    observer.observe(app, { childList: true, subtree: true });
    scheduleRender(200);
  }

  if (window.__RENTA_STAGE4_TEST__ === true) {
    window.__RenTAAgentApplyTest = {
      buildPayload: buildPayload,
      validate: validate,
      inferTransport: inferTransport,
      protocolTransportOptions: protocolTransportOptions,
      splitList: splitList
    };
  } else {
    installLegacyPricingGuard();
    installRouteHooks();
    loadFeatureConfig();
  }
})();
