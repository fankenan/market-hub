<template>
  <div>
    <!-- 总资产汇总卡 -->
    <div class="card summary">
      <div class="sum-item">
        <div class="k">持仓市值</div>
        <div class="v mono">{{ money(sum.market_value) }}</div>
      </div>
      <div class="sum-item">
        <div class="k">持仓成本</div>
        <div class="v mono">{{ money(sum.total_cost) }}</div>
      </div>
      <div class="sum-item">
        <div class="k">浮动盈亏</div>
        <div class="v mono" :class="cls(sum.unrealized_pnl)">{{ pnl(sum.unrealized_pnl) }}</div>
      </div>
      <div class="sum-item">
        <div class="k">累计已实现</div>
        <div class="v mono" :class="cls(sum.realized_pnl)">{{ pnl(sum.realized_pnl) }}</div>
      </div>
      <div class="sum-item big">
        <div class="k">总盈亏</div>
        <div class="v mono" :class="cls(sum.total_pnl)">{{ pnl(sum.total_pnl) }}</div>
      </div>
      <div class="sum-side">
        <span class="dot" :class="{ live: auto }"></span>
        <span class="meta">{{ auto ? '自动刷新 ' + interval + 's' : '已暂停' }} · {{ updatedAt || '—' }}</span>
      </div>
    </div>

    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="tabs">
        <button class="tab" :class="{ on: tab === 'open' }" @click="tab = 'open'">
          持仓中 ({{ openRows.length }})
        </button>
        <button class="tab" :class="{ on: tab === 'closed' }" @click="tab = 'closed'">
          已清仓 ({{ closedRows.length }})
        </button>
      </div>
      <div class="ops">
        <el-switch v-model="auto" active-text="自动" />
        <el-select v-model="interval" style="width: 86px" size="default">
          <el-option :value="5" label="5 秒" />
          <el-option :value="10" label="10 秒" />
          <el-option :value="30" label="30 秒" />
        </el-select>
        <el-button type="primary" @click="openAdd()">＋ 添加持仓</el-button>
      </div>
    </div>

    <!-- 持仓中 -->
    <div class="card" v-show="tab === 'open'">
      <el-table :data="openRows" style="width: 100%" size="default"
                :row-style="{ height: '42px' }"
                :row-class-name="rowCls">
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="lots">
              <div class="lot" v-for="l in row.lots" :key="l.id">
                <span>买入 {{ l.buy_date }}</span>
                <span class="mono">{{ fmt(l.buy_price) }} 元 × {{ l.qty }} 股</span>
                <span class="mono cost">成本 {{ money(l.buy_price * l.qty) }}</span>
                <el-button link type="danger" size="small"
                           @click="delLot(row, l.id)">删除此笔</el-button>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="symbol" label="代码" width="90">
          <template #default="{ row }">
            <a class="sym" @click.prevent="goDetail(row)">{{ row.symbol }}</a>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" width="110">
          <template #default="{ row }">
            <a class="sym" @click.prevent="goDetail(row)">{{ row.name }}</a>
          </template>
        </el-table-column>
        <el-table-column label="持有数量" width="100" align="right">
          <template #default="{ row }"><span class="mono">{{ row.total_qty }}</span></template>
        </el-table-column>
        <el-table-column label="平均成本" width="100" align="right">
          <template #default="{ row }"><span class="mono">{{ fmt(row.avg_cost) }}</span></template>
        </el-table-column>
        <el-table-column label="现价" width="100" align="right">
          <template #default="{ row }">
            <span class="mono" :class="cls(row.change_pct)">{{ fmt(row.price) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="今日涨跌" width="95" align="right">
          <template #default="{ row }">
            <span class="mono" :class="cls(row.change_pct)">{{ pct(row.change_pct) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="浮动盈亏" width="110" align="right">
          <template #default="{ row }">
            <span class="mono" :class="cls(row.unrealized_pnl)">{{ pnl(row.unrealized_pnl) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="盈亏比例" width="95" align="right">
          <template #default="{ row }">
            <span class="mono" :class="cls(row.unrealized_pct)">{{ pct(row.unrealized_pct) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="市值" width="110" align="right">
          <template #default="{ row }"><span class="mono">{{ money(row.market_value) }}</span></template>
        </el-table-column>
        <el-table-column label="首次买入" width="105" align="center">
          <template #default="{ row }">{{ row.first_buy }}</template>
        </el-table-column>
        <el-table-column label="操作" width="210" align="center" fixed="right">
          <template #default="{ row }">
            <el-button type="warning" size="small" plain @click="openSell(row)">卖出</el-button>
            <el-button size="small" plain @click="openAdd(row.symbol)">加仓</el-button>
            <el-button type="danger" size="small" plain @click="delStock(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无持仓，点右上角「添加持仓」开始记账" :image-size="72" />
        </template>
      </el-table>
    </div>

    <!-- 已清仓 -->
    <div class="card" v-show="tab === 'closed'">
      <el-table :data="closedRows" style="width: 100%" size="default"
                :row-style="{ height: '42px' }">
        <el-table-column prop="symbol" label="代码" width="90" />
        <el-table-column prop="name" label="名称" width="110" />
        <el-table-column prop="buy_date" label="首次买入" width="105" align="center" />
        <el-table-column prop="sell_date" label="卖出日期" width="105" align="center" />
        <el-table-column label="平均成本" width="100" align="right">
          <template #default="{ row }"><span class="mono">{{ fmt(row.avg_cost) }}</span></template>
        </el-table-column>
        <el-table-column label="卖出价" width="100" align="right">
          <template #default="{ row }"><span class="mono">{{ fmt(row.sell_price) }}</span></template>
        </el-table-column>
        <el-table-column label="数量" width="90" align="right">
          <template #default="{ row }"><span class="mono">{{ row.total_qty }}</span></template>
        </el-table-column>
        <el-table-column label="本笔盈亏" width="110" align="right">
          <template #default="{ row }">
            <span class="mono" :class="cls(row.pnl)">{{ pnl(row.pnl) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="收益率" width="100" align="right">
          <template #default="{ row }">
            <span class="mono" :class="cls(row.pnl_pct)">{{ pct(row.pnl_pct) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center" fixed="right">
          <template #default="{ row }">
            <el-button type="danger" size="small" plain @click="delClosed(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无已清仓记录" :image-size="72" />
        </template>
      </el-table>
    </div>

    <!-- 添加/加仓弹窗 -->
    <el-dialog v-model="addDlg" :title="addForm.symbol ? '加仓 — ' + addName : '添加持仓'"
               width="420px" destroy-on-close>
      <el-form label-width="82px">
        <el-form-item label="股票代码">
          <el-input v-model="addForm.symbol" placeholder="如 600519" maxlength="8"
                    :disabled="!!addLockSymbol" @blur="fetchName" />
        </el-form-item>
        <el-form-item label="名称">
          <span class="mono">{{ addName || '—' }}</span>
        </el-form-item>
        <el-form-item label="买入日期">
          <el-date-picker v-model="addForm.buy_date" type="date" value-format="YYYY-MM-DD"
                          style="width: 100%" :clearable="false" />
        </el-form-item>
        <el-form-item label="买入价">
          <el-input-number v-model="addForm.buy_price" :min="0.01" :precision="3" :step="0.01"
                           style="width: 100%" />
        </el-form-item>
        <el-form-item label="数量(股)">
          <el-input-number v-model="addForm.qty" :min="1" :step="100" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addDlg = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveAdd">保存</el-button>
      </template>
    </el-dialog>

    <!-- 卖出弹窗 -->
    <el-dialog v-model="sellDlg" title="卖出持仓" width="420px" destroy-on-close>
      <div class="sell-info" v-if="sellRow">
        <div class="si"><span>{{ sellRow.name }}（{{ sellRow.symbol }}）</span></div>
        <div class="si"><span>持有数量</span><b class="mono">{{ sellRow.total_qty }} 股</b></div>
        <div class="si"><span>平均成本</span><b class="mono">{{ fmt(sellRow.avg_cost) }}</b></div>
        <div class="si"><span>现价</span><b class="mono" :class="cls(sellRow.change_pct)">{{ fmt(sellRow.price) }}</b></div>
      </div>
      <el-form label-width="82px" style="margin-top: 10px">
        <el-form-item label="卖出价">
          <el-input-number v-model="sellForm.sell_price" :min="0.01" :precision="3" :step="0.01"
                           style="width: 100%" />
        </el-form-item>
        <el-form-item label="卖出日期">
          <el-date-picker v-model="sellForm.sell_date" type="date" value-format="YYYY-MM-DD"
                          style="width: 100%" :clearable="false" />
        </el-form-item>
      </el-form>
      <div class="sell-est" v-if="estPnl !== null">
        预计本笔盈亏：
        <b class="mono" :class="cls(estPnl)">{{ pnl(estPnl) }}（{{ pct(estPct) }}）</b>
      </div>
      <template #footer>
        <el-button @click="sellDlg = false">取消</el-button>
        <el-button type="warning" :loading="saving" @click="doSell">确认卖出</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'

const router = useRouter()

const openRows = ref([])
const closedRows = ref([])
const sum = ref({})
const src = ref('')
const updatedAt = ref('')
const tab = ref('open')

const auto = ref(true)
const interval = ref(10)
let timer = null

const addDlg = ref(false)
const addForm = ref({ symbol: '', buy_date: today(), buy_price: null, qty: 100 })
const addName = ref('')
const addLockSymbol = ref('')
const sellDlg = ref(false)
const sellRow = ref(null)
const sellForm = ref({ sell_price: null, sell_date: today() })
const saving = ref(false)

function today() { return new Date().toISOString().slice(0, 10) }

// ---------- 格式化 ----------
function cls(v) { return v > 0 ? 'up' : v < 0 ? 'down' : 'flat' }
function fmt(v) { return v === null || v === undefined || v === '' ? '—' : Number(v).toFixed(2) }
function pct(v) { return v === null || v === undefined || v === '' ? '—' : (v > 0 ? '+' : '') + Number(v).toFixed(2) + '%' }
function pnl(v) { return v === null || v === undefined || v === '' ? '—' : (v > 0 ? '+' : '') + Number(v).toFixed(2) }
function money(v) {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  if (Math.abs(n) >= 1e8) return (n / 1e8).toFixed(2) + '亿'
  if (Math.abs(n) >= 1e4) return (n / 1e4).toFixed(2) + '万'
  return n.toFixed(2)
}
function rowCls({ row }) {
  return row.unrealized_pnl > 0 ? 'row-up' : row.unrealized_pnl < 0 ? 'row-down' : ''
}

const estPnl = computed(() => {
  if (!sellRow.value || !sellForm.value.sell_price) return null
  return (sellForm.value.sell_price - sellRow.value.avg_cost) * sellRow.value.total_qty
})
const estPct = computed(() => {
  if (!sellRow.value || !sellRow.value.avg_cost || estPnl.value === null) return null
  return estPnl.value / (sellRow.value.avg_cost * sellRow.value.total_qty) * 100
})

// ---------- 数据 ----------
async function load() {
  try {
    const [po, pc] = await Promise.all([
      api.get('/portfolio'),
      api.get('/portfolio/closed')
    ])
    openRows.value = po.data.open || []
    sum.value = po.data.summary || {}
    closedRows.value = pc.data || []
    src.value = po.source || ''
    updatedAt.value = new Date().toLocaleTimeString('zh-CN')
  } catch (e) { console.error(e) }
}

async function fetchName() {
  const s = (addForm.value.symbol || '').trim().replace(/^(sh|sz|bj)/i, '')
  if (!/^\d{6}$/.test(s)) { addName.value = ''; return }
  try {
    const r = await api.get('/quote', { params: { symbols: s } })
    addName.value = (r.data && r.data[0] && r.data[0].name) || ''
  } catch (e) { addName.value = '' }
}

function openAdd(symbol) {
  addLockSymbol.value = symbol || ''
  addForm.value = { symbol: symbol || '', buy_date: today(), buy_price: null, qty: 100 }
  addName.value = ''
  addDlg.value = true
  if (symbol) fetchName()
}

async function saveAdd() {
  const f = addForm.value
  if (!f.symbol || !f.buy_date || !f.buy_price || !f.qty) {
    ElMessage.warning('请填完整：代码、日期、价格、数量')
    return
  }
  saving.value = true
  try {
    await api.post('/portfolio', f)
    ElMessage.success('已添加持仓')
    addDlg.value = false
    await load()
  } catch (e) {
    ElMessage.error((e.response && e.response.data && e.response.data.detail) || '保存失败')
  } finally { saving.value = false }
}

function openSell(row) {
  sellRow.value = row
  sellForm.value = { sell_price: row.price || row.avg_cost, sell_date: today() }
  sellDlg.value = true
}

async function doSell() {
  const r = sellRow.value
  if (!r || !sellForm.value.sell_price || !sellForm.value.sell_date) {
    ElMessage.warning('请填写卖出价与卖出日期')
    return
  }
  saving.value = true
  try {
    const res = await api.post('/portfolio/sell', {
      symbol: r.symbol,
      sell_price: sellForm.value.sell_price,
      sell_date: sellForm.value.sell_date
    })
    const d = res.data || {}
    ElMessage.success('已卖出 ' + d.qty + ' 股，本笔盈亏 ' + pnl(d.pnl))
    sellDlg.value = false
    await load()
  } catch (e) {
    ElMessage.error((e.response && e.response.data && e.response.data.detail) || '卖出失败')
  } finally { saving.value = false }
}

async function delLot(row, id) {
  try {
    await ElMessageBox.confirm('删除该笔买入记录？删除后不可恢复。', '确认', { type: 'warning' })
  } catch (e) { return }
  try {
    await api.delete('/portfolio/' + id)
    ElMessage.success('已删除')
    await load()
  } catch (e) {
    ElMessage.error((e.response && e.response.data && e.response.data.detail) || '删除失败')
  }
}

async function delStock(row) {
  const n = (row.lots || []).length
  try {
    await ElMessageBox.confirm(
      `删除 ${row.name}(${row.symbol}) 的全部持仓记录？\n共 ${n} 笔买入、${row.total_qty} 股。\n` +
      '注意：这是「删除」不是「卖出」，不会计入盈亏统计，删除后不可恢复。',
      '确认删除整只股票', { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' })
  } catch (e) { return }
  try {
    await api.delete('/portfolio/symbol/' + row.symbol)
    ElMessage.success('已删除 ' + row.symbol + ' 的持仓记录')
    await load()
  } catch (e) {
    ElMessage.error((e.response && e.response.data && e.response.data.detail) || '删除失败')
  }
}

async function delClosed(row) {
  try {
    await ElMessageBox.confirm(
      `删除 ${row.name}(${row.symbol}) 的已清仓记录？\n删除后该笔盈亏将不再计入统计，且不可恢复。`,
      '确认删除', { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' })
  } catch (e) { return }
  try {
    await api.delete('/portfolio/symbol/' + row.symbol)
    ElMessage.success('已删除 ' + row.symbol + ' 的历史记录')
    await load()
  } catch (e) {
    ElMessage.error((e.response && e.response.data && e.response.data.detail) || '删除失败')
  }
}

function goDetail(row) { router.push('/stock/' + row.symbol) }

function restart() {
  if (timer) clearInterval(timer)
  if (auto.value) timer = setInterval(() => {
    if (document.visibilityState === 'visible') load()
  }, interval.value * 1000)
}
watch([auto, interval], restart)

onMounted(async () => { await load(); restart() })
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<style scoped>
.summary {
  display: flex; align-items: center; gap: 34px;
  padding: 16px 22px; margin-bottom: 12px; flex-wrap: wrap;
}
.sum-item .k { font-size: 12px; color: #8a94a6; margin-bottom: 4px; }
.sum-item .v { font-size: 18px; font-weight: 600; }
.sum-item.big .v { font-size: 22px; }
.sum-side { margin-left: auto; display: flex; align-items: center; gap: 6px; }
.meta { font-size: 11px; color: #a8adb6; }
.dot { width: 7px; height: 7px; border-radius: 50%; background: #c9ced6; }
.dot.live { background: #2fa36b; box-shadow: 0 0 0 3px rgba(47,163,107,.15); }

.toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.tabs { display: flex; gap: 4px; }
.tab {
  border: none; background: transparent; font-size: 14px; padding: 6px 14px;
  color: #5a6472; cursor: pointer; border-radius: 6px;
}
.tab.on { color: #1485fe; background: rgba(20,133,254,.08); font-weight: 600; }
.ops { display: flex; gap: 10px; align-items: center; }

.sym { color: #1a1a2e; text-decoration: none; cursor: pointer; font-weight: 500; }
.sym:hover { color: #1485fe; }

.lots { padding: 4px 12px 8px 48px; display: flex; flex-direction: column; gap: 6px; }
.lot {
  display: flex; gap: 18px; align-items: center; font-size: 12px; color: #5a6472;
  background: #f7f9fc; border-radius: 6px; padding: 6px 12px;
}
.lot .cost { color: #8a94a6; }

:deep(.row-up) { background: rgba(230,69,69,.03) !important; }
:deep(.row-down) { background: rgba(47,163,107,.035) !important; }

.sell-info { background: #f7f9fc; border-radius: 8px; padding: 10px 14px; display: flex; flex-direction: column; gap: 6px; font-size: 13px; }
.si { display: flex; justify-content: space-between; }
.sell-est { font-size: 13px; margin-top: 8px; color: #5a6472; }
</style>
