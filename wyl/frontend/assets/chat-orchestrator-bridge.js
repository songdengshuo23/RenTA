(function () {
  "use strict";

  var VERSION = "20260615-final-result-first-v3";
  var PLATFORM_BASE_URL = "http://10.126.126.8:8888";
  var ORCHESTRATOR_EXECUTE_URL = PLATFORM_BASE_URL + "/mode-router/orchestrator/execute";
  var DEFAULT_REGISTRY_URL = PLATFORM_BASE_URL;
  var DEFAULT_DISCOVERY_URL = PLATFORM_BASE_URL + "/acps-adp-v2/discover";
  var runsByTask = new Map();

  if (window.__chatOrchestratorBridge === VERSION) return;
  window.__chatOrchestratorBridge = VERSION;

  var nativeFetch = window.fetch ? window.fetch.bind(window) : null;
  if (!nativeFetch) return;

  function isChatRoute() {
    return window.location.pathname === "/chat";
  }

  function pathOf(input) {
    var raw = "";
    if (typeof input === "string") raw = input;
    else if (input && typeof input.url === "string") raw = input.url;
    try {
      return new URL(raw, window.location.origin).pathname;
    } catch (error) {
      return raw;
    }
  }

  function readBody(init) {
    if (!init || typeof init.body !== "string") return {};
    try {
      return JSON.parse(init.body);
    } catch (error) {
      return {};
    }
  }

  function taskFromPayload(payload) {
    return String(
      payload.task ||
      payload.task_description ||
      payload.query ||
      payload.message ||
      ""
    ).trim();
  }

  function registryUrl(payload) {
    var value = String(payload.registry_url || payload.registryUrl || "").trim();
    if (!value) return DEFAULT_REGISTRY_URL;
    return value;
  }

  function jsonResponse(payload, status) {
    return new Response(JSON.stringify(payload), {
      status: status || 200,
      headers: { "Content-Type": "application/json; charset=utf-8" }
    });
  }

  function buildExecutePayload(source) {
    var payload = Object.assign({}, source || {});
    return {
      task: taskFromPayload(payload),
      registry_url: registryUrl(payload),
      discovery_url: String(payload.discovery_url || payload.discoveryUrl || DEFAULT_DISCOVERY_URL),
      limit: Number(payload.limit || payload.discovery_limit || payload.discoveryLimit || 10),
      registry_limit: Number(payload.registry_limit || payload.registryLimit || payload.limit || 25),
      registry_timeout: Number(payload.registry_timeout || payload.registryTimeout || payload.timeout || 20),
      discovery_timeout: Number(payload.discovery_timeout || payload.discoveryTimeout || payload.timeout || 20),
      save_report: false,
      dry_run: Boolean(payload.dry_run || payload.dryRun || false),
      check_dispatch: Boolean(payload.check_dispatch || payload.checkDispatch || false),
      hints: Object.assign(
        {
          requires_independent_roles: true,
          parallelizable: true
        },
        payload.hints || {}
      ),
      config: payload.config || {}
    };
  }

  function withoutFrontendWorkPackages(data) {
    if (!data || typeof data !== "object") return data;
    var shaped = Object.assign({}, data);
    var plan = Object.assign({}, shaped.plan || {});
    shaped.__orchestrator_plan = shaped.plan || {};
    plan.work_packages = [];
    shaped.plan = plan;
    return shaped;
  }

  function modeLabel(data) {
    var decision = data && data.decision || {};
    var plan = data && (data.__orchestrator_plan || data.plan) || {};
    var route = data && data.route_classification || {};
    return (decision.label || route.label || "?") + " -> " + (decision.mode || plan.mode || "?");
  }

  function formatExecution(data) {
    data = data || {};
    var plan = data.__orchestrator_plan || data.plan || {};
    var execution = data.execution || {};
    var lines = [];
    var finalResult = execution.final_result || data.final_result || "";

    if (finalResult) {
      lines.push(String(finalResult));
      lines.push("");
      lines.push("---");
      lines.push("");
      lines.push("#### Orchestration trace");
      lines.push("");
      lines.push("- Task: " + (data.task || (plan && plan.task) || "-"));
      lines.push("- Mode route: `" + modeLabel(data) + "`");
      lines.push("- Plan: `" + (plan.strategy || "?") + "` / `" + (plan.status || "?") + "`");
      lines.push("- Execution: `" + (execution.status || "?") + "`");
      if (execution.execution_id) lines.push("- Execution ID: `" + execution.execution_id + "`");
      if (execution.session_id) lines.push("- Group session: `" + execution.session_id + "`");
      if (Array.isArray(execution.runs) && execution.runs.length) {
        lines.push("- Runs: " + execution.runs.map(function (run) {
          var agent = run.agent || {};
          return (agent.name || run.agent_name || run.executor || run.package_id || "executor") + " (`" + (run.status || "?") + "`)";
        }).join(", "));
      }
      return lines.join("\n");
    }

    lines.push("### No final result returned");
    lines.push("");
    lines.push("- Task: " + (data.task || (plan && plan.task) || "-"));
    lines.push("- Mode route: `" + modeLabel(data) + "`");
    lines.push("- Plan: `" + (plan.strategy || "?") + "` / `" + (plan.status || "?") + "`");
    lines.push("- Execution: `" + (execution.status || "?") + "`");
    if (execution.execution_id) lines.push("- Execution ID: `" + execution.execution_id + "`");
    if (execution.session_id) lines.push("- Group session: `" + execution.session_id + "`");
    lines.push("");

    if (data.llm_result && data.llm_result.content) {
      lines.push("#### Fallback output");
      lines.push("");
      lines.push(String(data.llm_result.content));
      return lines.join("\n");
    }

    if (Array.isArray(execution.runs) && execution.runs.length) {
      lines.push("#### Agent runs");
      execution.runs.forEach(function (run, index) {
        var agent = run.agent || {};
        lines.push((index + 1) + ". " + (agent.name || run.package_id || "agent") + " - `" + (run.status || "?") + "`");
        if (run.output_text) {
          lines.push("");
          lines.push(String(run.output_text));
          lines.push("");
        }
      });
      return lines.join("\n");
    }

    if (execution.message) {
      lines.push("#### Execution note");
      lines.push("");
      lines.push(String(execution.message));
      lines.push("");
    }

    if (Array.isArray(plan.phases) && plan.phases.length) {
      lines.push("#### Work mode phases");
      plan.phases.forEach(function (phase, index) {
        lines.push((index + 1) + ". `" + (phase.phase || "?") + "` - " + (phase.description || ""));
      });
      lines.push("");
    }

    if (data.error || data.message) {
      lines.push("#### Orchestrator error");
      lines.push("");
      lines.push("`" + (data.error || "error") + "` " + (data.message || ""));
      lines.push("");
    }
    return lines.join("\n");
  }

  async function callOrchestrator(sourcePayload) {
    var executePayload = buildExecutePayload(sourcePayload);
    if (!executePayload.task) {
      return jsonResponse({ error: "missing_task", message: "task/message is required" }, 400);
    }

    var response = await nativeFetch(ORCHESTRATOR_EXECUTE_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(executePayload)
    });
    var text = await response.text();
    var data = {};
    try {
      data = text ? JSON.parse(text) : {};
    } catch (error) {
      data = { error: "invalid_orchestrator_json", message: text };
    }
    data.task = data.task || executePayload.task;
    runsByTask.set(executePayload.task, { ok: response.ok, status: response.status, data: data });
    return jsonResponse(response.ok ? withoutFrontendWorkPackages(data) : data, response.status);
  }

  async function finalResultForChat(sourcePayload) {
    var task = taskFromPayload(sourcePayload);
    var cached = task ? runsByTask.get(task) : null;
    if (!cached) {
      var executeResponse = await callOrchestrator(sourcePayload);
      var executeData = await executeResponse.clone().json().catch(function () { return {}; });
      cached = { ok: executeResponse.ok, status: executeResponse.status, data: executeData };
    }
    return jsonResponse({
      result: formatExecution(cached.data),
      model: "mode-router-orchestrator",
      usage: {}
    }, 200);
  }

  window.fetch = function (input, init) {
    if (!isChatRoute()) return nativeFetch(input, init);

    var path = pathOf(input);
    if (path === "/mode-router/pipeline/registry") {
      return callOrchestrator(readBody(init));
    }
    if (path === "/agent-rpc/chat" || path === "/agent-rpc/task") {
      return finalResultForChat(readBody(init));
    }
    return nativeFetch(input, init);
  };
})();
