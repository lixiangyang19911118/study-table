<script setup lang="ts">
import { computed } from 'vue'

import { useSession } from '../../stores/session'

const session = useSession()

const GRADE_TEXT = ['一', '二', '三', '四', '五', '六']

const gradeText = computed(() => {
  const g = session.child?.grade
  return g ? `${GRADE_TEXT[g - 1] ?? g} 年级` : '年级未设置'
})

const planned = [
  { name: '今日任务列表', note: '含错题自动生成的条目', m: 'M2' },
  { name: '开始计时 / 卡住了', note: 'spent_sec 落库，doing 状态持久化', m: 'M2' },
  { name: '拍照提交作业', note: '走 POST /files，压缩后上传', m: 'M2' },
  { name: '口算练习', note: '服务端出题与判分', m: 'M3' },
  { name: '我的错题', note: '间隔复习 1/2/4/7 天', m: 'M3' },
  { name: '星星商店', note: '余额由 star_ledger 聚合', m: 'M3' },
]
</script>

<template>
  <section class="head">
    <h1>{{ session.child ? `${session.child.name}，今天想先做哪一样？` : '孩子端 · 今日' }}</h1>
    <p>
      {{ session.child
        ? `${gradeText} · ${session.child.edition}`
        : '账号下还没有孩子档案' }}
      · 页面内容按里程碑逐步替换
    </p>
  </section>

  <!-- 没有孩子档案时的引导：所有业务表都挂 child_id，没有它什么都写不了 -->
  <div v-if="!session.child" class="empty">
    <strong>先去家长端建一个孩子档案</strong>
    <p>
      所有任务、错题、教材都挂在 <code>child_id</code> 上，没有档案就写不进数据。
    </p>
    <RouterLink class="link" to="/parent/dashboard">去家长端设置</RouterLink>
  </div>

  <div v-else class="idcard">
    <div class="row">
      <span class="k">昵称</span><span class="v">{{ session.child.name }}</span>
    </div>
    <div class="row">
      <span class="k">年级</span><span class="v">{{ gradeText }}</span>
    </div>
    <div class="row">
      <span class="k">教材</span><span class="v">{{ session.child.edition }}</span>
    </div>
    <div class="row">
      <span class="k">档案编号</span><span class="v mono">#{{ session.child.id }}</span>
    </div>
    <span class="stamp">读自 MySQL · child 表</span>
  </div>

  <div class="card">
    <div v-for="item in planned" :key="item.name" class="item">
      <div class="left">
        <span class="name">{{ item.name }}</span>
        <span class="note">{{ item.note }}</span>
      </div>
      <span class="tag">{{ item.m }}</span>
    </div>
  </div>
</template>

<style scoped>
.head { margin-bottom: 22px; }
h1 { font-size: 21px; font-weight: 500; margin-bottom: 6px; }
.head p { font-size: 13px; color: var(--muted); }

.idcard {
  position: relative;
  display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px 20px;
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--r-md); padding: 16px 18px 14px;
  margin-bottom: 22px;
}
.row { display: flex; flex-direction: column; gap: 2px; }
.k { font-size: 11.5px; color: var(--hint); }
.v { font-size: 13.5px; }
.mono { font-family: "SF Mono", Menlo, monospace; font-size: 12.5px; }
.stamp {
  position: absolute; top: 14px; right: 16px;
  font-size: 10.5px; color: var(--hint);
  border: 1px dashed var(--line); border-radius: 5px;
  padding: 2px 8px;
}

.empty {
  background: var(--card); border: 1px dashed var(--line);
  border-radius: var(--r-md); padding: 18px; margin-bottom: 22px;
}
.empty strong { font-size: 13.5px; font-weight: 500; }
.empty p { font-size: 12.5px; color: var(--muted); margin-top: 6px; }
.link { font-size: 12.5px; display: inline-block; margin-top: 10px; }

.card {
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--r-md); overflow: hidden;
}
.item {
  display: flex; align-items: center; gap: 12px;
  padding: 13px 18px; border-bottom: 1px solid #f0f2f4;
}
.item:last-child { border-bottom: none; }
.left { display: flex; flex-direction: column; }
.name { font-size: 13.5px; }
.note { font-size: 11.5px; color: var(--hint); margin-top: 1px; }
.tag {
  margin-left: auto; flex: 0 0 auto;
  font-size: 11px; color: var(--muted);
  background: var(--page); border: 1px solid var(--line);
  border-radius: 5px; padding: 2px 7px;
}

@media (max-width: 720px) {
  .idcard { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .stamp { display: none; }
}
</style>
