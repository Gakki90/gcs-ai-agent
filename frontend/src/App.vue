<template>
  <main class="shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">AutoGLM Phone Cluster</p>
        <h1>手机集群任务工作台</h1>
      </div>
      <div class="top-actions">
        <span class="device-live">{{ deviceSocketStatus }}</span>
        <button class="icon-btn" title="刷新设备" @click="loadDevices" :disabled="loadingDevices">↻</button>
      </div>
    </header>

    <section class="workspace">
      <aside class="left-pane">
        <section class="section">
          <div class="section-head">
            <h2>源设备</h2>
            <span class="count">{{ readyDevices.length }} 在线</span>
          </div>
          <div class="device-list">
            <label v-for="device in devices" :key="device.serial" class="device-row">
              <input
                type="radio"
                name="source-device"
                :value="device.serial"
                v-model="sourceDeviceId"
                :disabled="device.state !== 'device'"
              />
              <span>
                <strong>{{ device.serial }}</strong>
                <small>{{ device.state }}</small>
              </span>
            </label>
          </div>
          <p v-if="deviceError" class="error-text">{{ deviceError }}</p>
          <button class="secondary full setup-btn" :disabled="!sourceDeviceId || busy" @click="setupAdbKeyboard">
            安装并启用 ADB Keyboard
          </button>
          <div v-if="keyboardSetupResult" class="setup-result">
            <p :class="keyboardSetupResult.ok ? 'result-line ok' : 'result-line bad'">
              {{ keyboardSetupResult.ok ? "ADB Keyboard 已就绪" : "ADB Keyboard 设置未完全成功" }}
            </p>
            <p v-for="step in keyboardSetupResult.steps" :key="step.name" :class="['result-line', step.ok ? 'ok' : 'bad']">
              {{ step.name }} · {{ step.message }}
            </p>
          </div>
        </section>

        <section class="section">
          <div class="section-head">
            <h2>回放设备</h2>
            <span class="count">{{ targetDeviceIds.length }} 台已选</span>
          </div>
          <div class="device-list replay-device-list">
            <label v-for="device in devices" :key="`replay-${device.serial}`" class="device-row">
              <input
                type="checkbox"
                :value="device.serial"
                v-model="targetDeviceIds"
                :disabled="device.state !== 'device'"
              />
              <span>
                <strong>{{ device.serial }}</strong>
                <small>{{ device.state }}</small>
              </span>
            </label>
          </div>
          <button class="primary full" :disabled="!canReplay || busy" @click="replayToTargets">确认无误并重新执行</button>
          <div class="result-list">
            <p v-for="item in replayResults" :key="item.device_id" :class="['result-line', item.ok ? 'ok' : 'bad']">
              {{ item.device_id }} · {{ item.message }}
            </p>
          </div>
        </section>
      </aside>

      <section class="chat-pane">
        <div class="section chat-card">
          <div class="section-head">
            <h2>任务对话</h2>
            <span class="status">{{ session ? `${session.status} · ${session.platform}` : "未开始" }}</span>
          </div>

          <div ref="messagesRef" class="messages">
            <article v-for="(message, index) in displayMessages" :key="index" :class="['bubble', message.role]">
              <p>{{ message.content }}</p>
            </article>
            <div v-if="showLatestActions" class="latest-actions">
              <button class="secondary" :disabled="busy" @click="runNextStep">继续下一步</button>
              <button class="danger" :disabled="busy" @click="finishSession">结束任务</button>
            </div>
            <div v-else-if="showNewConversation" class="latest-actions">
              <button class="primary" :disabled="busy" @click="newConversation">新对话</button>
            </div>
          </div>

          <div class="composer">
            <textarea
              v-model="composerText"
              class="hint-input"
              :placeholder="session ? '输入人工提示，例如：先别下单，只停在搜索结果页' : '输入任务，例如：打开京东，搜索夜魔键盘'"
            ></textarea>
            <button class="send-btn" :disabled="!canSubmitComposer || busy" title="发送" @click="submitComposer">↑</button>
          </div>
        </div>
      </section>

      <aside class="right-pane">
        <section class="section">
          <div class="section-head">
            <h2>手机画面</h2>
            <button class="small-btn" :disabled="!sourceDeviceId" @click="refreshScreen">刷新</button>
          </div>
          <div class="phone-frame">
            <img v-if="screenUrl" :src="screenUrl" alt="source phone screen" />
            <span v-else>选择源设备</span>
          </div>
        </section>

        <section class="section steps-section">
          <div class="section-head">
            <h2>已记录步骤</h2>
            <span class="count">{{ session?.steps.length || 0 }}</span>
          </div>
          <ol class="steps">
            <li v-for="step in session?.steps || []" :key="step.index">
              <img v-if="step.image_url" :src="apiUrl(step.image_url)" alt="" />
              <div>
                <strong>{{ step.index }}. {{ stepTitle(step) }}</strong>
                <small v-if="step.point_norm">坐标 {{ step.point_norm.join(", ") }}</small>
                <p>{{ stepSummary(step) }}</p>
              </div>
            </li>
          </ol>
        </section>

        <section class="section workflow-section">
          <div class="section-head">
            <h2>下发流程 Prompt</h2>
            <span class="count">{{ session?.workflow_prompt ? "已生成" : "等待步骤" }}</span>
          </div>
          <pre class="workflow-preview">{{ session?.workflow_prompt || "主手机执行后会生成给其他手机复用的 workflow prompt。" }}</pre>
        </section>
      </aside>
    </section>
  </main>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";

const API_BASE = import.meta.env.VITE_API_BASE || "";

const devices = ref([]);
const sourceDeviceId = ref("");
const targetDeviceIds = ref([]);
const task = ref("");
const DEFAULT_MAX_STEPS = 30;
const session = ref(null);
const composerText = ref("");
const screenUrl = ref("");
const replayResults = ref([]);
const keyboardSetupResult = ref(null);
const busy = ref(false);
const loadingDevices = ref(false);
const deviceError = ref("");
const messagesRef = ref(null);
let screenRefreshTimer = null;
let screenRefreshTimer2 = null;
let deviceSocket = null;
let deviceSocketReconnectTimer = null;
const deviceSocketStatus = ref("设备实时检测未连接");

const readyDevices = computed(() => devices.value.filter((device) => device.state === "device"));
const sessionEnded = computed(() => session.value && ["finished", "max_steps"].includes(session.value.status));
const canSubmitComposer = computed(() => {
  if (!composerText.value.trim()) return false;
  if (!session.value) return Boolean(sourceDeviceId.value);
  return !sessionEnded.value;
});
const canReplay = computed(() => session.value?.steps?.length && targetDeviceIds.value.length);
const showLatestActions = computed(() => {
  return session.value && !sessionEnded.value;
});
const showNewConversation = computed(() => sessionEnded.value);
const displayMessages = computed(() => {
  if (!session.value) {
    if (!sourceDeviceId.value) {
      return [{ role: "system", content: "请选择源设备。" }];
    }
    return [{ role: "system", content: `已选择源设备：${sourceDeviceId.value}` }];
  }
  return session.value.messages;
});

function apiUrl(path) {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  return `${API_BASE}${path}`;
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || response.statusText);
  }
  return response.json();
}

async function loadDevices() {
  loadingDevices.value = true;
  deviceError.value = "";
  try {
    applyDeviceSnapshot(await request("/api/devices"));
  } catch (error) {
    devices.value = [];
    sourceDeviceId.value = "";
    deviceError.value = error.message;
  } finally {
    loadingDevices.value = false;
  }
}

function applyDeviceSnapshot(nextDevices) {
  devices.value = nextDevices;
  const ready = nextDevices.filter((device) => device.state === "device");

  if (sourceDeviceId.value && !ready.some((device) => device.serial === sourceDeviceId.value)) {
    sourceDeviceId.value = "";
  }
  if (!sourceDeviceId.value && ready.length) {
    sourceDeviceId.value = ready[0].serial;
  }

  targetDeviceIds.value = targetDeviceIds.value.filter((id) => ready.some((device) => device.serial === id));
}

function deviceWebSocketUrl() {
  const base = API_BASE || window.location.origin;
  const url = new URL(base, window.location.origin);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/ws/devices";
  url.search = "";
  return url.toString();
}

function connectDeviceSocket() {
  if (deviceSocket) {
    deviceSocket.close();
  }
  deviceSocketStatus.value = "设备实时检测连接中";
  deviceSocket = new WebSocket(deviceWebSocketUrl());

  deviceSocket.onopen = () => {
    deviceSocketStatus.value = "设备实时检测中";
    deviceError.value = "";
  };

  deviceSocket.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    if (payload.error) {
      deviceError.value = payload.error;
      devices.value = [];
      sourceDeviceId.value = "";
      targetDeviceIds.value = [];
      return;
    }
    deviceError.value = "";
    applyDeviceSnapshot(payload.devices || []);
  };

  deviceSocket.onerror = () => {
    deviceSocketStatus.value = "设备实时检测异常";
  };

  deviceSocket.onclose = () => {
    deviceSocket = null;
    deviceSocketStatus.value = "设备实时检测已断开";
    if (deviceSocketReconnectTimer) clearTimeout(deviceSocketReconnectTimer);
    deviceSocketReconnectTimer = setTimeout(connectDeviceSocket, 2000);
  };
}

async function startSession() {
  busy.value = true;
  replayResults.value = [];
  const content = composerText.value.trim();
  task.value = content;
  composerText.value = "";
  try {
    session.value = await request("/api/sessions", {
      method: "POST",
      body: JSON.stringify({
        task: content,
        device_id: sourceDeviceId.value,
        max_steps: DEFAULT_MAX_STEPS
      })
    });
    await runNextStep();
  } catch (error) {
    composerText.value = content;
    task.value = "";
    alert(error.message);
  } finally {
    busy.value = false;
  }
}

async function runNextStep() {
  if (!session.value) return;
  busy.value = true;
  try {
    session.value = await request(`/api/sessions/${session.value.id}/step`, {
      method: "POST",
      body: JSON.stringify({ hint: null })
    });
    refreshScreenAfterAction();
  } catch (error) {
    alert(error.message);
  } finally {
    busy.value = false;
  }
}

async function sendHint() {
  if (!session.value || !composerText.value.trim()) return;
  const content = composerText.value.trim();
  composerText.value = "";
  busy.value = true;
  try {
    session.value = await request(`/api/sessions/${session.value.id}/step`, {
      method: "POST",
      body: JSON.stringify({ hint: content })
    });
    refreshScreenAfterAction();
  } catch (error) {
    composerText.value = content;
    alert(error.message);
  } finally {
    busy.value = false;
  }
}

function submitComposer() {
  if (!session.value) {
    startSession();
    return;
  }
  sendHint();
}

async function finishSession() {
  if (!session.value) return;
  busy.value = true;
  try {
    session.value = await request(`/api/sessions/${session.value.id}/finish`, {
      method: "POST",
      body: JSON.stringify({})
    });
  } catch (error) {
    alert(error.message);
  } finally {
    busy.value = false;
  }
}

function newConversation() {
  session.value = null;
  task.value = "";
  composerText.value = "";
  replayResults.value = [];
  keyboardSetupResult.value = null;
}

async function replayToTargets() {
  busy.value = true;
  try {
    const response = await request(`/api/sessions/${session.value.id}/replay`, {
      method: "POST",
      body: JSON.stringify({
        target_device_ids: targetDeviceIds.value,
        max_steps: DEFAULT_MAX_STEPS,
        device_gap_seconds: 30
      })
    });
    replayResults.value = response.results;
  } catch (error) {
    alert(error.message);
  } finally {
    busy.value = false;
  }
}

async function setupAdbKeyboard() {
  if (!sourceDeviceId.value) return;
  busy.value = true;
  keyboardSetupResult.value = null;
  try {
    keyboardSetupResult.value = await request(`/api/devices/${encodeURIComponent(sourceDeviceId.value)}/adb-keyboard/setup`, {
      method: "POST",
      body: JSON.stringify({})
    });
  } catch (error) {
    keyboardSetupResult.value = {
      ok: false,
      steps: [{ name: "setup", ok: false, message: error.message }]
    };
  } finally {
    busy.value = false;
  }
}

function refreshScreen() {
  if (!sourceDeviceId.value) {
    screenUrl.value = "";
    return;
  }
  screenUrl.value = `${API_BASE}/api/devices/${encodeURIComponent(sourceDeviceId.value)}/screen?t=${Date.now()}`;
}

function refreshScreenAfterAction() {
  refreshScreen();
  if (screenRefreshTimer) clearTimeout(screenRefreshTimer);
  if (screenRefreshTimer2) clearTimeout(screenRefreshTimer2);
  screenRefreshTimer = setTimeout(refreshScreen, 850);
  screenRefreshTimer2 = setTimeout(refreshScreen, 1800);
}

function stepTitle(step) {
  const action = step.action || {};
  const name = step.action_name || (action._metadata === "finish" ? "Finish" : "动作");
  if (name === "Launch") return `启动 ${action.app || ""}`.trim();
  if (name === "Tap") return "点击";
  if (name === "Type" || name === "Type_Name") return "输入文本";
  if (name === "Swipe") return "滑动";
  if (name === "Wait") return "等待";
  if (name === "Back") return "返回";
  if (name === "Home") return "回到桌面";
  if (name === "Take_over") return "请求接管";
  return name;
}

function stepSummary(step) {
  const action = step.action || {};
  if (step.message) return cleanStepText(step.message);
  if (step.action_name === "Type" || step.action_name === "Type_Name") {
    return `输入：${action.text || ""}`;
  }
  if (step.action_name === "Tap" && step.thinking) {
    return cleanStepText(step.thinking);
  }
  if (step.action_name === "Swipe") {
    return "滑动页面继续查找或浏览。";
  }
  if (step.action_name === "Launch") {
    return `打开目标应用：${action.app || ""}`;
  }
  return cleanStepText(step.thinking) || "已记录该步骤。";
}

function cleanStepText(text) {
  const cleaned = String(text || "").replace(/\s+/g, " ").trim();
  if (cleaned.length <= 140) return cleaned;
  return `${cleaned.slice(0, 140)}...`;
}

watch(sourceDeviceId, () => {
  refreshScreen();
});

watch(
  () => session.value?.messages?.length,
  async () => {
    await nextTick();
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight;
    }
  }
);

onMounted(() => {
  loadDevices();
  connectDeviceSocket();
});

onUnmounted(() => {
  if (screenRefreshTimer) clearTimeout(screenRefreshTimer);
  if (screenRefreshTimer2) clearTimeout(screenRefreshTimer2);
  if (deviceSocketReconnectTimer) clearTimeout(deviceSocketReconnectTimer);
  if (deviceSocket) {
    deviceSocket.onclose = null;
    deviceSocket.close();
  }
});
</script>
