<template>
  <main class="min-h-screen bg-background text-foreground">
    <div class="mx-auto flex min-h-screen max-w-[1720px] flex-col gap-5 px-6 py-5">
      <header class="flex items-center justify-between gap-4 rounded-lg border bg-card px-5 py-4 shadow-sm">
        <div class="min-w-0">
          <h1 class="text-2xl font-semibold tracking-tight">手机集群任务工作台</h1>
        </div>
        <div class="relative flex items-center gap-2">
          <span class="inline-flex h-8 items-center gap-2 rounded-md border bg-muted px-3 text-xs text-muted-foreground">
            <span class="h-2 w-2 rounded-full bg-emerald-500"></span>
            {{ deviceSocketStatus }}
          </span>
          <button class="btn btn-outline h-9 px-3" @click="setupPanelOpen = !setupPanelOpen">
            <Keyboard class="h-4 w-4" />
            输入法设置
          </button>
          <button class="btn btn-outline btn-icon" title="刷新设备" :disabled="loadingDevices" @click="loadDevices">
            <RefreshCw class="h-4 w-4" />
          </button>

          <div v-if="setupPanelOpen" class="absolute right-0 top-12 z-50 w-[420px] rounded-lg border bg-card p-3 shadow-2xl">
            <div class="flex items-center justify-between border-b pb-2">
              <h2 class="text-sm font-semibold">输入法设置</h2>
              <button class="btn btn-outline h-8 w-8 p-0" @click="setupPanelOpen = false">
                <X class="h-4 w-4" />
              </button>
            </div>
            <div class="mt-3 grid max-h-[360px] gap-2 overflow-auto">
              <div v-for="device in devices" :key="`keyboard-${device.serial}`" class="grid grid-cols-[1fr_auto] gap-3 rounded-md border p-3">
                <div class="min-w-0">
                  <p class="truncate text-sm font-medium">{{ device.serial }}</p>
                  <p :class="device.state === 'device' ? 'result-ok' : 'result-bad'">{{ device.state }}</p>
                  <p
                    v-if="keyboardSetupByDevice[device.serial]"
                    :class="keyboardSetupByDevice[device.serial].ok ? 'result-ok' : 'result-bad'"
                  >
                    {{ keyboardSetupByDevice[device.serial].message }}
                  </p>
                </div>
                <button
                  class="btn btn-secondary"
                  :disabled="device.state !== 'device' || installingDeviceId === device.serial || busy"
                  @click="setupDeviceKeyboard(device.serial)"
                >
                  {{ installingDeviceId === device.serial ? "安装中" : "安装" }}
                </button>
              </div>
              <p v-if="!devices.length" class="empty-state">暂无设备</p>
            </div>
          </div>
        </div>
      </header>

      <section class="grid flex-1 grid-cols-[300px_minmax(460px,1fr)_380px] gap-5 max-xl:grid-cols-1">
        <aside class="grid content-start gap-5">
          <section class="card">
            <div class="card-head">
              <div>
                <h2 class="card-title">源设备</h2>
              </div>
              <span class="badge badge-success">{{ readyDevices.length }} 在线</span>
            </div>

            <div class="mt-4 grid gap-2">
              <label
                v-for="device in devices"
                :key="device.serial"
                :class="[
                  'device-row',
                  sourceDeviceId === device.serial ? 'device-row-active' : '',
                  device.state !== 'device' ? 'opacity-50' : ''
                ]"
              >
                <input
                  v-model="sourceDeviceId"
                  class="mt-1"
                  type="radio"
                  name="source-device"
                  :value="device.serial"
                  :disabled="device.state !== 'device'"
                />
                <Smartphone class="mt-0.5 h-4 w-4 text-muted-foreground" />
                <span class="min-w-0">
                  <strong class="block truncate text-sm font-medium">{{ device.serial }}</strong>
                  <small class="text-xs text-muted-foreground">{{ device.state }}</small>
                </span>
              </label>
              <p v-if="!devices.length && !deviceError" class="empty-state">等待设备接入</p>
            </div>

            <p v-if="deviceError" class="mt-3 text-sm text-destructive">{{ deviceError }}</p>
          </section>

          <section class="card">
            <div class="card-head">
              <div>
                <h2 class="card-title">回放设备</h2>
              </div>
              <span class="badge">{{ targetDeviceIds.length }} 台已选</span>
            </div>

            <div class="mt-4 grid gap-2">
              <label
                v-for="device in devices"
                :key="`replay-${device.serial}`"
                :class="[
                  'device-row',
                  targetDeviceIds.includes(device.serial) ? 'device-row-active' : '',
                  device.state !== 'device' ? 'opacity-50' : ''
                ]"
              >
                <input
                  v-model="targetDeviceIds"
                  class="mt-1"
                  type="checkbox"
                  :value="device.serial"
                  :disabled="device.state !== 'device'"
                />
                <CopyCheck class="mt-0.5 h-4 w-4 text-muted-foreground" />
                <span class="min-w-0">
                  <strong class="block truncate text-sm font-medium">{{ device.serial }}</strong>
                  <small class="text-xs text-muted-foreground">{{ device.state }}</small>
                </span>
              </label>
            </div>

            <button class="btn btn-primary mt-4 w-full" :disabled="!canReplay || busy" @click="replayToTargets">
              <Play class="h-4 w-4" />
              确认无误并重新执行
            </button>

            <div v-if="replayResults.length" class="mt-4 grid gap-2 rounded-md border bg-muted/40 p-3">
              <p v-for="item in replayResults" :key="item.device_id" :class="item.ok ? 'result-ok' : 'result-bad'">
                {{ item.device_id }} · {{ item.message }}
              </p>
            </div>
          </section>
        </aside>

        <section class="card flex h-[calc(100vh-132px)] min-h-[560px] flex-col overflow-hidden max-xl:h-[720px]">
          <div class="card-head">
            <div>
              <h2 class="card-title">任务对话</h2>
            </div>
            <span class="badge">{{ session ? `${session.status} · ${session.platform}` : "未开始" }}</span>
          </div>

          <div ref="messagesRef" class="mt-4 flex min-h-0 flex-1 flex-col gap-3 overflow-auto rounded-lg border bg-muted/30 p-4">
            <article v-for="(message, index) in displayMessages" :key="index" :class="bubbleClass(message.role)">
              <p class="whitespace-pre-wrap break-words text-sm leading-6">{{ message.content }}</p>
            </article>

            <div v-if="showLatestActions" class="flex flex-wrap gap-2">
              <button class="btn btn-secondary" :disabled="busy" @click="continueSession">
                <Play class="h-4 w-4" />
                {{ continueButtonText }}
              </button>
              <button class="btn btn-destructive" :disabled="busy && !autoRunning" @click="finishSession">
                <Square class="h-4 w-4" />
                {{ stopButtonText }}
              </button>
            </div>
            <div v-else-if="showNewConversation" class="flex flex-wrap gap-2">
              <button class="btn btn-primary" :disabled="busy" @click="newConversation">
                <Plus class="h-4 w-4" />
                新对话
              </button>
            </div>
          </div>

          <div class="mt-4 flex items-end gap-3 rounded-xl border bg-card p-3 shadow-sm">
            <div v-if="!session" class="relative self-end">
              <button class="btn btn-outline h-11 px-3" @click="runModePanelOpen = !runModePanelOpen">
                <Monitor class="h-4 w-4" />
                {{ autoRun ? "自动执行" : "单步调试" }}
                <ChevronDown class="h-4 w-4" />
              </button>
              <div v-if="runModePanelOpen" class="absolute bottom-12 left-0 z-40 w-72 rounded-lg border bg-card p-2 shadow-2xl">
                <button class="menu-item" @click="selectRunMode(true)">
                  <Monitor class="h-4 w-4" />
                  <span class="flex-1 text-left">自动执行</span>
                  <Check v-if="autoRun" class="h-4 w-4" />
                </button>
                <button class="menu-item" @click="selectRunMode(false)">
                  <ListChecks class="h-4 w-4" />
                  <span class="flex-1 text-left">单步调试</span>
                  <Check v-if="!autoRun" class="h-4 w-4" />
                </button>
                <div class="my-2 border-t"></div>
                <p class="px-2 pb-1 text-xs leading-5 text-muted-foreground">
                  自动执行会连续运行任务，不在每一步询问；遇到登录、验证、支付等情况会停下等待人工处理。
                </p>
              </div>
            </div>
            <textarea
              v-model="composerText"
              class="min-h-[56px] flex-1 resize-y border-0 bg-transparent px-1 py-2 text-sm outline-none placeholder:text-muted-foreground"
              :placeholder="session ? '输入人工提示，例如：先别下单，只停在搜索结果页' : '输入任务，例如：打开京东，搜索夜魔键盘'"
            ></textarea>
            <button class="btn btn-primary h-11 w-11 rounded-full p-0" :disabled="!canSubmitComposer || busy" title="发送" @click="submitComposer">
              <ArrowUp class="h-5 w-5" />
            </button>
          </div>
        </section>

        <aside class="grid content-start gap-5">
          <section class="card">
            <div class="card-head">
              <div>
                <h2 class="card-title">手机画面</h2>
              </div>
              <button class="btn btn-outline h-8 px-3 text-xs" :disabled="!sourceDeviceId" @click="refreshScreen">
                <RefreshCw class="h-3.5 w-3.5" />
                刷新
              </button>
            </div>
            <div class="mx-auto mt-4 grid aspect-[9/19.5] w-[min(285px,100%)] place-items-center rounded-[28px] border bg-slate-950 p-3 shadow-2xl shadow-slate-900/20">
              <img v-if="screenUrl" class="h-full w-full rounded-[20px] object-cover" :src="screenUrl" alt="source phone screen" />
              <span v-else class="text-sm text-slate-400">选择源设备</span>
            </div>
          </section>

          <section class="card max-h-[390px] overflow-auto">
            <div class="card-head sticky -top-4 z-10 bg-card pb-3">
              <div>
                <h2 class="card-title">已记录步骤</h2>
              </div>
              <span class="badge">{{ session?.steps.length || 0 }}</span>
            </div>

            <ol class="mt-3 grid gap-3">
              <li v-for="step in session?.steps || []" :key="step.index" class="grid grid-cols-[58px_1fr] gap-3 rounded-md border bg-muted/30 p-2">
                <img v-if="step.image_url" class="h-[94px] w-[58px] rounded bg-slate-950 object-cover" :src="apiUrl(step.image_url)" alt="" />
                <div v-else class="h-[94px] w-[58px] rounded bg-slate-950"></div>
                <div class="min-w-0">
                  <strong class="block truncate text-sm font-medium">{{ step.index }}. {{ stepTitle(step) }}</strong>
                  <small v-if="step.point_norm" class="mt-1 block text-xs text-muted-foreground">坐标 {{ step.point_norm.join(", ") }}</small>
                  <p class="mt-1 text-xs leading-5 text-muted-foreground">{{ stepSummary(step) }}</p>
                </div>
              </li>
              <li v-if="!session?.steps?.length" class="empty-state">这里会保存模型实际执行过的动作、截图和关键参数，方便排查问题或复现任务。</li>
            </ol>
          </section>

          <section class="card max-h-[330px] overflow-auto">
            <div class="card-head sticky -top-4 z-10 bg-card pb-3">
              <div>
                <h2 class="card-title">下发给其他手机的指令</h2>
              </div>
              <span class="badge">{{ session?.workflow_prompt ? "已生成" : "等待步骤" }}</span>
            </div>
            <pre class="mt-3 whitespace-pre-wrap break-words rounded-md border bg-muted/40 p-3 text-xs leading-5 text-muted-foreground">{{ session?.workflow_prompt || "主手机执行后，会把任务目标和关键步骤整理成一段复用指令。回放设备会根据这段指令重新调用模型执行，而不是简单照抄坐标。" }}</pre>
          </section>
        </aside>
      </section>
    </div>
  </main>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import {
  ArrowUp,
  Check,
  ChevronDown,
  CopyCheck,
  Keyboard,
  ListChecks,
  Monitor,
  Play,
  Plus,
  RefreshCw,
  Smartphone,
  Square,
  X,
} from "lucide-vue-next";

const API_BASE = import.meta.env.VITE_API_BASE || "";

const devices = ref([]);
const sourceDeviceId = ref("");
const targetDeviceIds = ref([]);
const task = ref("");
const DEFAULT_MAX_STEPS = 30;
const session = ref(null);
const autoRun = ref(false);
const runModePanelOpen = ref(false);
const setupPanelOpen = ref(false);
const composerText = ref("");
const screenUrl = ref("");
const replayResults = ref([]);
const keyboardSetupByDevice = ref({});
const installingDeviceId = ref("");
const busy = ref(false);
const autoRunning = ref(false);
const stopRequested = ref(false);
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
const executionMode = computed(() => (autoRun.value ? "auto" : "step"));
const continueButtonText = computed(() => (autoRun.value ? "继续执行" : "继续下一步"));
const stopButtonText = computed(() => (autoRunning.value && stopRequested.value ? "正在停止" : "结束任务"));
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

function bubbleClass(role) {
  if (role === "user") {
    return "max-w-[86%] self-end rounded-lg bg-primary px-3 py-2 text-primary-foreground shadow-sm";
  }
  if (role === "assistant") {
    return "max-w-[86%] self-start rounded-lg border bg-card px-3 py-2 shadow-sm";
  }
  return "max-w-[86%] self-start rounded-lg border bg-muted px-3 py-2 text-muted-foreground";
}

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
    if (executionMode.value === "auto") {
      await runAutoSteps();
    } else {
      await runNextStep();
    }
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

async function runAutoSteps(hint = null) {
  if (!session.value) return;
  autoRunning.value = true;
  stopRequested.value = false;
  busy.value = true;
  let nextHint = hint;
  try {
    while (session.value && !sessionEnded.value && !stopRequested.value) {
      session.value = await request(`/api/sessions/${session.value.id}/step`, {
        method: "POST",
        body: JSON.stringify({ hint: nextHint })
      });
      nextHint = null;
      refreshScreenAfterAction();
      await nextTick();
    }
    if (stopRequested.value && session.value && !sessionEnded.value) {
      await finishSessionNow();
    }
  } catch (error) {
    alert(error.message);
  } finally {
    autoRunning.value = false;
    stopRequested.value = false;
    busy.value = false;
  }
}

async function sendHint() {
  if (!session.value || !composerText.value.trim()) return;
  const content = composerText.value.trim();
  composerText.value = "";
  busy.value = true;
  try {
    if (executionMode.value === "auto") {
      await runAutoSteps(content);
    } else {
      session.value = await request(`/api/sessions/${session.value.id}/step`, {
        method: "POST",
        body: JSON.stringify({ hint: content })
      });
      refreshScreenAfterAction();
    }
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

function continueSession() {
  if (executionMode.value === "auto") {
    runAutoSteps();
    return;
  }
  runNextStep();
}

function selectRunMode(enabled) {
  autoRun.value = enabled;
  runModePanelOpen.value = false;
}

async function finishSession() {
  if (!session.value) return;
  if (autoRunning.value) {
    stopRequested.value = true;
    return;
  }
  busy.value = true;
  try {
    await finishSessionNow();
  } catch (error) {
    alert(error.message);
  } finally {
    busy.value = false;
  }
}

async function finishSessionNow() {
  session.value = await request(`/api/sessions/${session.value.id}/finish`, {
    method: "POST",
    body: JSON.stringify({})
  });
}

function newConversation() {
  session.value = null;
  task.value = "";
  composerText.value = "";
  replayResults.value = [];
  runModePanelOpen.value = false;
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

async function setupDeviceKeyboard(deviceId) {
  if (!deviceId) return;
  installingDeviceId.value = deviceId;
  try {
    const result = await request(`/api/devices/${encodeURIComponent(deviceId)}/adb-keyboard/setup`, {
      method: "POST",
      body: JSON.stringify({})
    });
    keyboardSetupByDevice.value = {
      ...keyboardSetupByDevice.value,
      [deviceId]: {
        ok: result.ok,
        message: result.ok ? "已安装并启用" : "设置未完全成功"
      }
    };
  } catch (error) {
    keyboardSetupByDevice.value = {
      ...keyboardSetupByDevice.value,
      [deviceId]: {
        ok: false,
        message: error.message
      }
    };
  } finally {
    installingDeviceId.value = "";
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
