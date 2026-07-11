const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const sourcePath = path.join(__dirname, "assets", "agent-apply-bridge.js");
const source = fs.readFileSync(sourcePath, "utf8");
const storage = new Map([
  ["user", JSON.stringify({ username: "stage4", email: "stage4@example.com" })]
]);
const window = {
  __RENTA_STAGE4_TEST__: true,
  localStorage: {
    getItem(key) { return storage.has(key) ? storage.get(key) : null; },
    setItem(key, value) { storage.set(key, String(value)); }
  }
};
vm.runInNewContext(source, { window, URL, Date, Promise, console }, { filename: sourcePath });

const bridge = window.__RenTAAgentApplyTest;
assert.ok(bridge, "test helpers should be available only in the explicit test context");

function values(overrides = {}) {
  return Object.assign({
    protocolVersion: "02.00",
    name: "Stage 4 Agent",
    version: "1.0.0",
    description: "Gateway compatibility test agent",
    logoUrl: "",
    isOntology: false,
    providerAccountName: "stage4",
    providerAccountEmail: "stage4@example.com",
    organization: "RenTA",
    department: "",
    countryCode: "CN",
    providerUrl: "",
    license: "",
    maintainerName: "",
    email: "stage4@example.com",
    endpointUrl: "https://agent.example.com/rpc",
    transport: "JSONRPC",
    schemeName: "mtls",
    challengeUrl: "http://10.126.126.8:8888/acps-atr-v2",
    amqpUrl: "",
    messageQueueVersion: "rabbitmq:>=4.2",
    certificateDns: "",
    certificateIp: "",
    requestedValidity: "365",
    skillId: "stage4.skill",
    skillName: "Stage 4 Skill",
    skillVersion: "1.0.0",
    skillDescription: "Exercises the Stage 4 payload builder",
    selectedTags: ["general"],
    customTags: "",
    examples: "example",
    inputModes: ["text/plain", "application/json"],
    outputModes: ["application/json"],
    streaming: false,
    notification: false,
    entityUserId: "",
    documentationUrl: "",
    webAppUrl: ""
  }, overrides);
}

const legacy = bridge.buildPayload(values()).acs;
assert.equal(legacy.protocolVersion, "02.00");
assert.match(legacy.aic, /^1\.2\.156\.3088\./);
assert.equal(legacy.endPoints[0].transport, "JSONRPC");
assert.equal(legacy.securitySchemes.mtls["x-caChallengeBaseUrl"], "http://10.126.126.8:8888/acps-atr-v2");
assert.equal(Object.prototype.hasOwnProperty.call(legacy, "certificate"), false);

const v21Values = values({
  protocolVersion: "02.01",
  endpointUrl: "https://agent.example.com/api/v2",
  transport: "HTTP_JSON",
  challengeUrl: "",
  amqpUrl: "amqps://mq.example.com:5671/acps?inbox=inbox_{AIC}",
  certificateDns: "agent.example.com, mq.example.com",
  certificateIp: "127.0.0.1",
  requestedValidity: "49"
});
const v21 = bridge.buildPayload(v21Values).acs;
assert.equal(v21.protocolVersion, "02.01");
assert.equal(v21.aic, "{AIC}");
assert.equal(v21.endPoints.length, 2);
assert.equal(v21.endPoints[0].transport, "HTTP_JSON");
assert.equal(v21.endPoints[1].transport, "AMQP");
assert.equal(v21.capabilities.messageQueue[0], "rabbitmq:>=4.2");
assert.equal(v21.certificate.requestedValidity, 49);
assert.equal(v21.certificate.altNames.dns.join(","), "agent.example.com,mq.example.com");
assert.equal(v21.certificate.altNames.ip[0], "127.0.0.1");
assert.equal(Object.prototype.hasOwnProperty.call(v21.securitySchemes.mtls, "x-caChallengeBaseUrl"), false);

assert.equal(bridge.inferTransport("https://agent.example.com/api/chat", "02.00"), "HTTP");
assert.equal(bridge.inferTransport("https://agent.example.com/api/chat", "02.01"), "HTTP_JSON");
assert.deepEqual(Array.from(bridge.protocolTransportOptions("02.01"), item => item.value), ["JSONRPC", "HTTP_JSON"]);

const invalid = bridge.validate(values({
  protocolVersion: "02.01",
  transport: "HTTP",
  requestedValidity: "0",
  amqpUrl: "https://mq.example.com",
  messageQueueVersion: "rabbitmq latest"
}));
assert.ok(invalid.transport);
assert.ok(invalid.requestedValidity);
assert.ok(invalid.amqpUrl);
assert.ok(invalid.messageQueueVersion);

assert.equal(/localStorage\.setItem\([^\n]*(eab|macKey|keyId)/i.test(source), false);
assert.match(
  source,
  /function removeBridge\(\)[\s\S]*?removeAttribute\(["']data-agent-apply-bridge["']\)/
);
console.log("agent-apply bridge: 02.00 compatibility and 02.01 payload tests passed");
