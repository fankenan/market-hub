<template>
  <div class="ipo-wrap">
    <!-- 顶部统计条 -->
    <div class="card head">
      <div class="h-left">
        <h2>新上股票</h2>
        <p class="sub">
          未来 <b>{{ days }}</b> 天内登陆 A 股的新股
          <span class="dot">·</span>
          共 <b class="up">{{ list.length }}</b> 只
          <span class="dot">·</span>
          数据源：东方财富
          <span v-if="updatedAt" class="dot">·</span>
          <span v-if="updatedAt">更新于 {{ updatedAt }}</span>
        </p>
      </div>
      <div class="h-right">
        <el-select v-model="days" size="small" style="width:104px" @change="load(true)">
          <el-option :value="15" label="未来15天" />
          <el-option :value="31" label="未来1个月" />
          <el-option :value="60" label="未来2个月" />
          <el-option :value="90" label="未来3个月" />
        </el-select>
        <el-button size="small" :loading="loading" @click="load(true)">刷新</el-button>
      </div>
    </div>

    <div class="split">
      <!-- 左栏：股票列表 -->
      <div class="card left">
        <div class="col-title">
          新股列表
          <span class="cnt">{{ list.length }}</span>
        </div>

        <div v-if="loading && !list.length" class="empty">加载中…</div>
        <div v-else-if="!list.length" class="empty">
          暂无未来 {{ days }} 天内上市的新股
          <span v-if="errTip" class="err">{{ errTip }}</span>
        </div>

        <ul v-else class="ipo-list">
          <li
            v-for="it in list"
            :key="it.symbol"
            :class="{ on: cur && cur.symbol === it.symbol }"
            @click="pick(it)">
            <div class="row1">
              <span class="nm">{{ it.name }}</span>
              <span class="tag" :class="tagClass(it)">{{ tagText(it) }}</span>
            </div>
            <div class="row2">
              <span class="code mono">{{ it.symbol }}</span>
              <span class="mkt">{{ it.market || it.board || '-' }}</span>
            </div>
            <div class="row3">
              <span class="lb">上市日</span>
              <span class="vl mono">{{ it.list_date || '待定' }}</span>
              <span v-if="it.days_left !== null && it.days_left !== undefined" class="cd">
                {{ it.days_left === 0 ? '今日' : 'T+' + it.days_left }}
              </span>
            </div>
          </li>
        </ul>
      </div>

      <!-- 右栏：公司信息 -->
      <div class="card right">
        <div v-if="!cur" class="empty big">
          <div class="hint-ico"></div>
          <p>点击左侧股票，查看该公司信息</p>
        </div>

        <div v-else-if="loadingCo" class="empty big">正在读取公司信息…</div>

        <div v-else class="co">
          <!-- 头部 -->
          <div class="co-head">
            <div class="co-name">
              <h3>{{ co.name || cur.name }}</h3>
              <span class="co-code mono">{{ cur.symbol }}</span>
              <span class="co-badge">{{ co.security_type || cur.board || '-' }}</span>
            </div>
            <div class="co-acts">
              <el-button size="small" type="primary" plain @click="goDetail(cur.symbol)">
                查看行情
              </el-button>
            </div>
          </div>
          <div class="co-full">{{ co.org_name || '—' }}</div>

          <!-- 一句话结论 -->
          <div class="verdict">
            <span class="v-label">公司画像</span>
            <span class="v-text">{{ summary }}</span>
          </div>

          <!-- 发行信息 -->
          <div class="sec">
            <div class="sec-t">发行信息</div>
            <div class="kv-grid">
              <div class="kv"><span>发行价</span><b class="mono">{{ fmt(cur.issue_price, '元') }}</b></div>
              <div class="kv"><span>发行市盈率</span><b class="mono">{{ fmt(cur.issue_pe) }}</b></div>
              <div class="kv"><span>发行数量</span><b class="mono">{{ fmt(cur.issue_num, '万股') }}</b></div>
              <div class="kv"><span>上市日</span><b class="mono">{{ cur.list_date || '待定' }}</b></div>
              <div class="kv"><span>招股日</span><b class="mono">{{ cur.apply_date || '—' }}</b></div>
              <div class="kv"><span>上市板块</span><b>{{ cur.board || '—' }}</b></div>
              <div class="kv"><span>交易市场</span><b>{{ cur.market || '—' }}</b></div>
              <div class="kv"><span>主承销商</span><b class="ell" :title="cur.lead_underwriter">{{ cur.lead_underwriter || '—' }}</b></div>
            </div>
          </div>

          <!-- 公司基本信息 -->
          <div class="sec">
            <div class="sec-t">基本信息</div>
            <div class="kv-grid">
              <div class="kv"><span>所属行业</span><b>{{ co.industry_em || '—' }}</b></div>
              <div class="kv"><span>证监会行业</span><b>{{ co.industry_csrc || '—' }}</b></div>
              <div class="kv"><span>公司性质</span><b>{{ nature }}</b></div>
              <div class="kv"><span>实际控制人</span><b class="ell" :title="co.actual_holder">{{ co.actual_holder || '—' }}</b></div>
              <div class="kv"><span>注册地</span><b>{{ co.province || '—' }}</b></div>
              <div class="kv"><span>注册资本</span><b class="mono">{{ fmt(co.reg_capital, '万元') }}</b></div>
              <div class="kv"><span>员工人数</span><b class="mono">{{ fmt(co.emp_num, '人') }}</b></div>
              <div class="kv"><span>董事长</span><b>{{ co.chairman || '—' }}</b></div>
              <div class="kv"><span>法定代表人</span><b>{{ co.legal_person || '—' }}</b></div>
              <div class="kv"><span>董秘</span><b>{{ co.secretary || '—' }}</b></div>
              <div class="kv"><span>联系电话</span><b class="mono">{{ co.org_tel || '—' }}</b></div>
              <div class="kv wide"><span>公司官网</span>
                <b>
                  <a v-if="co.org_web" :href="webUrl(co.org_web)" target="_blank" rel="noopener">{{ co.org_web }}</a>
                  <template v-else>—</template>
                </b>
              </div>
              <div class="kv wide"><span>注册地址</span><b>{{ co.reg_address || co.address || '—' }}</b></div>
            </div>
          </div>

          <!-- 盈利情况 -->
          <div class="sec">
            <div class="sec-t">
              盈利情况
              <span class="sec-sub" v-if="co.finance && co.finance.length">最近 {{ co.finance.length }} 期</span>
            </div>
            <div v-if="!co.finance || !co.finance.length" class="empty small">暂无财务数据</div>
            <table v-else class="fin">
              <thead>
                <tr>
                  <th>报告期</th><th>营收</th><th>同比</th>
                  <th>净利润</th><th>同比</th><th>EPS</th>
                  <th>ROE</th><th>毛利率</th><th>负债率</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="f in co.finance" :key="f.report_date">
                  <td class="mono">{{ f.report_date }}</td>
                  <td class="mono">{{ money(f.revenue) }}</td>
                  <td class="mono" :class="cls(f.revenue_yoy)">{{ pct(f.revenue_yoy) }}</td>
                  <td class="mono">{{ money(f.net_profit) }}</td>
                  <td class="mono" :class="cls(f.net_profit_yoy)">{{ pct(f.net_profit_yoy) }}</td>
                  <td class="mono">{{ fmt(f.eps) }}</td>
                  <td class="mono">{{ pct(f.roe, false) }}</td>
                  <td class="mono">{{ pct(f.gross_margin, false) }}</td>
                  <td class="mono">{{ pct(f.debt_ratio, false) }}</td>
                </tr>
              </tbody>
            </table>
            <div v-if="co.finance && co.finance.length" class="fin-note">
              盈利评级：<b :class="profitCls">{{ profitGrade }}</b>
              <span class="dot">·</span>{{ profitDesc }}
            </div>
          </div>

          <!-- 公司简介 -->
          <div class="sec" v-if="co.profile">
            <div class="sec-t">公司简介</div>
            <p class="profile">{{ co.profile }}</p>
          </div>

          <div class="src-line">
            数据来源：东方财富 F10
            <span v-if="coErr" class="err">（部分字段缺失：{{ coErr }}）</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'

const router = useRouter()
const days = ref(31)
const list = ref([])
const cur = ref(null)
const co = ref({})
const loading = ref(false)
const loadingCo = ref(false)
const errTip = ref('')
const coErr = ref('')
const updatedAt = ref('')

async function load(force) {
  loading.value = true
  errTip.value = ''
  try {
    const r = await api.get('/ipo/upcoming', {
      params: { days: days.value, refresh: force ? 1 : 0 }
    })
    list.value = r.data || []
    if (r.err) errTip.value = r.err
    if (r.cached_at) {
      updatedAt.value = new Date(r.cached_at * 1000).toLocaleTimeString('zh-CN', { hour12: false })
    } else {
      updatedAt.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
    }
    // 自动选中第一只
    if (list.value.length && (!cur.value || !list.value.some(x => x.symbol === cur.value.symbol))) {
      pick(list.value[0])
    } else if (!list.value.length) {
      cur.value = null; co.value = {}
    }
  } catch (e) {
    errTip.value = (e.response && e.response.data && e.response.data.detail) || '新股数据获取失败'
  } finally {
    loading.value = false
  }
}

async function pick(it) {
  cur.value = it
  co.value = {}
  coErr.value = ''
  loadingCo.value = true
  try {
    const r = await api.get('/company/' + it.symbol)
    co.value = r.data || {}
    if (r.org_err) coErr.value = r.org_err
  } catch (e) {
    coErr.value = (e.response && e.response.data && e.response.data.detail) || '公司信息获取失败'
  } finally {
    loadingCo.value = false
  }
}

/* ---------- 展示辅助 ---------- */
function fmt(v, unit) {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  if (!isFinite(n)) return String(v)
  const s = Math.abs(n) >= 1000 ? n.toLocaleString('zh-CN', { maximumFractionDigits: 2 }) : String(Math.round(n * 100) / 100)
  return unit ? s + ' ' + unit : s
}
function money(v) {
  if (v === null || v === undefined) return '—'
  const n = Number(v)
  if (!isFinite(n)) return '—'
  if (Math.abs(n) >= 1e8) return (n / 1e8).toFixed(2) + '亿'
  if (Math.abs(n) >= 1e4) return (n / 1e4).toFixed(2) + '万'
  return n.toFixed(2)
}
function pct(v, sign = true) {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  if (!isFinite(n)) return '—'
  return (sign && n > 0 ? '+' : '') + n.toFixed(2) + '%'
}
function cls(v) {
  const n = Number(v)
  if (!isFinite(n) || n === 0) return 'flat'
  return n > 0 ? 'up' : 'down'
}
function webUrl(w) {
  const s = String(w).trim()
  return /^https?:\/\//i.test(s) ? s : 'http://' + s
}
function tagText(it) {
  if (it.list_date) {
    const d = it.days_left
    if (d === 0) return '今日上市'
    if (d !== null && d !== undefined && d <= 3) return '即将上市'
    return '已定上市日'
  }
  return '待定上市日'
}
function tagClass(it) {
  if (!it.list_date) return 't-gray'
  const d = it.days_left
  if (d !== null && d !== undefined && d <= 3) return 't-red'
  return 't-blue'
}

/* 公司性质：依据「实际控制人」推导 */
const nature = computed(() => {
  const c = co.value
  const ah = String(c.actual_holder || '').trim()
  if (ah) {
    if (/国资委|国有资产|国有资|人民政府|财政部|国资|国有/.test(ah)) return '国有控股'
    if (/大学|学院|研究院|研究所|中科院/.test(ah)) return '校企控股'
    if (/外资|境外|香港/.test(ah)) return '外资控股'
    if (/^[\u4e00-\u9fa5]{2,4}([,，、\s]+[\u4e00-\u9fa5]{2,4})*$/.test(ah)) return '民营控股(自然人)'
    return '混合/其他'
  }
  if (!c.org_name) return '—'
  if (/国有|国资|集团控股/.test(c.org_name)) return '国有控股'
  if (/股份有限公司/.test(c.org_name)) return '民营股份公司'
  return '股份公司'
})

/* 盈利评级 */
const profitGrade = computed(() => {
  const f = co.value.finance
  if (!f || !f.length) return '—'
  let score = 0
  const latest = f[0]
  if (Number(latest.net_profit) > 0) score += 2
  if (Number(latest.revenue_yoy) > 0) score += 1
  if (Number(latest.net_profit_yoy) > 0) score += 1
  if (Number(latest.roe) >= 10) score += 1
  if (f.length > 1 && Number(f[0].net_profit) > Number(f[1].net_profit)) score += 1
  if (score >= 5) return '优秀'
  if (score >= 3) return '良好'
  if (score >= 2) return '一般'
  return '偏弱'
})
const profitCls = computed(() => {
  const g = profitGrade.value
  if (g === '优秀' || g === '良好') return 'up'
  if (g === '一般') return 'flat'
  return 'down'
})
const profitDesc = computed(() => {
  const f = co.value.finance
  if (!f || !f.length) return '暂无财务数据'
  const l = f[0]
  const parts = []
  parts.push(Number(l.net_profit) > 0 ? '已实现盈利' : '尚未盈利')
  parts.push('最新营收同比' + pct(l.revenue_yoy) + '，净利同比' + pct(l.net_profit_yoy))
  if (Number(l.roe) >= 10) parts.push('ROE 达 ' + pct(l.roe, false) + '，盈利质量较好')
  return parts.join('；')
})

/* 公司画像一句话 */
const summary = computed(() => {
  const c = co.value
  if (!c.name) return '点击左侧股票查看'
  const seg = []
  if (c.industry_em) seg.push(c.industry_em.split('-').slice(0, 2).join('·'))
  seg.push(nature.value)
  if (c.province) seg.push(c.province + '企业')
  if (c.emp_num) seg.push('员工 ' + Number(c.emp_num).toLocaleString('zh-CN') + ' 人')
  let s = seg.join('，')
  const f = c.finance
  if (f && f.length) {
    s += '。最新报告期 ' + f[0].report_date + '，营收 ' + money(f[0].revenue) +
      '、净利 ' + money(f[0].net_profit) + '，经营' + (Number(f[0].net_profit) > 0 ? '已盈利' : '尚未盈利') + '。'
  }
  return s
})

function goDetail(sym) {
  router.push('/stock/' + sym)
}

onMounted(() => load(false))
</script>

<style scoped>
.ipo-wrap { display: flex; flex-direction: column; gap: 12px; }

/* 顶部条 */
.head { display: flex; align-items: center; padding: 14px 18px; gap: 16px; }
.head h2 { margin: 0 0 4px; font-size: 17px; color: #0b1c33; }
.head .sub { margin: 0; font-size: 12px; color: #8a94a6; }
.head .sub b { color: #1485fe; }
.head .dot { margin: 0 6px; color: #c8d0dc; }
.h-right { margin-left: auto; display: flex; gap: 10px; align-items: center; }

/* 两栏 */
.split { display: grid; grid-template-columns: 360px 1fr; gap: 12px; align-items: start; }
@media (max-width: 1100px) { .split { grid-template-columns: 1fr; } }

.left { padding: 0; overflow: hidden; }
.col-title {
  padding: 12px 14px; font-size: 13px; font-weight: 600; color: #0b1c33;
  border-bottom: 1px solid #eef2f7; display: flex; align-items: center; gap: 8px;
}
.col-title .cnt {
  background: #eef5ff; color: #1485fe; border-radius: 9px;
  padding: 1px 8px; font-size: 11px;
}
.ipo-list { list-style: none; margin: 0; padding: 0; max-height: 640px; overflow-y: auto; }
.ipo-list li {
  padding: 11px 14px; border-bottom: 1px solid #f2f5fa; cursor: pointer;
  transition: background .15s;
}
.ipo-list li:hover { background: #f7faff; }
.ipo-list li.on { background: #eef5ff; box-shadow: inset 3px 0 0 #1485fe; }
.row1 { display: flex; align-items: center; gap: 8px; }
.row1 .nm { font-size: 14px; font-weight: 600; color: #0b1c33; }
.tag {
  font-size: 10px; padding: 1px 6px; border-radius: 4px; margin-left: auto;
  border: 1px solid transparent; white-space: nowrap;
}
.t-red { color: #e64545; background: #fdeeee; border-color: #f8d4d4; }
.t-blue { color: #1485fe; background: #eef5ff; border-color: #d6e6ff; }
.t-gray { color: #8a94a6; background: #f3f5f9; border-color: #e6eaf1; }
.row2 { display: flex; align-items: center; gap: 8px; margin-top: 4px; }
.row2 .code { font-size: 12px; color: #5a6472; }
.row2 .mkt { font-size: 11px; color: #a3adba; }
.row3 { display: flex; align-items: center; gap: 8px; margin-top: 5px; font-size: 11px; }
.row3 .lb { color: #a3adba; }
.row3 .vl { color: #5a6472; }
.row3 .cd { margin-left: auto; color: #1485fe; font-weight: 600; }

/* 右栏 */
.right { padding: 0; min-height: 420px; }
.empty { padding: 30px 20px; text-align: center; color: #a3adba; font-size: 13px; }
.empty.big { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 420px; }
.empty.small { padding: 16px; }
.empty .err { display: block; margin-top: 8px; color: #e64545; font-size: 12px; }
.hint-ico {
  width: 46px; height: 46px; border-radius: 50%; margin-bottom: 12px;
  background: linear-gradient(135deg, #eef5ff, #dbeaff);
  border: 1px solid #d6e6ff;
}

.co { padding: 16px 18px 20px; }
.co-head { display: flex; align-items: flex-start; gap: 12px; }
.co-name { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.co-name h3 { margin: 0; font-size: 20px; color: #0b1c33; }
.co-code { font-size: 14px; color: #1485fe; font-weight: 600; }
.co-badge {
  font-size: 11px; color: #5a6472; background: #f3f5f9;
  border: 1px solid #e6eaf1; border-radius: 4px; padding: 2px 8px;
}
.co-acts { margin-left: auto; }
.co-full { margin-top: 6px; font-size: 12px; color: #8a94a6; }

.verdict {
  margin-top: 12px; padding: 10px 12px; border-radius: 8px;
  background: linear-gradient(90deg, #f5f9ff, #fbfdff);
  border: 1px solid #e3edfb;
}
.v-label {
  display: inline-block; font-size: 11px; color: #1485fe; font-weight: 600;
  background: #fff; border: 1px solid #d6e6ff; border-radius: 4px;
  padding: 1px 7px; margin-right: 8px;
}
.v-text { font-size: 13px; color: #33404f; line-height: 1.7; }

.sec { margin-top: 18px; }
.sec-t {
  font-size: 13px; font-weight: 700; color: #0b1c33;
  padding-left: 9px; border-left: 3px solid #1485fe; margin-bottom: 10px;
  display: flex; align-items: center; gap: 8px;
}
.sec-sub { font-size: 11px; color: #a3adba; font-weight: 400; }

.kv-grid {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px;
  background: #eef2f7; border: 1px solid #eef2f7; border-radius: 8px; overflow: hidden;
}
@media (max-width: 900px) { .kv-grid { grid-template-columns: repeat(2, 1fr); } }
.kv { background: #fff; padding: 8px 11px; display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.kv.wide { grid-column: span 2; }
.kv span { font-size: 11px; color: #a3adba; }
.kv b { font-size: 13px; color: #1a1a2e; font-weight: 600; word-break: break-all; }
.kv b.ell { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kv b a { color: #1485fe; text-decoration: none; }

.fin { width: 100%; border-collapse: collapse; font-size: 12px; }
.fin th {
  background: #f7f9fc; color: #5a6472; font-weight: 600; text-align: right;
  padding: 8px 10px; border-bottom: 1px solid #eef2f7; white-space: nowrap;
}
.fin th:first-child { text-align: left; }
.fin td { padding: 8px 10px; text-align: right; border-bottom: 1px solid #f2f5fa; color: #33404f; }
.fin td:first-child { text-align: left; color: #5a6472; }
.fin tbody tr:hover { background: #fafcff; }
.fin-note { margin-top: 9px; font-size: 12px; color: #5a6472; }
.fin-note .dot { margin: 0 6px; color: #c8d0dc; }

.profile { margin: 0; font-size: 13px; line-height: 1.85; color: #44506b; text-align: justify; }

.src-line { margin-top: 18px; padding-top: 10px; border-top: 1px dashed #eef2f7; font-size: 11px; color: #a3adba; }
</style>
