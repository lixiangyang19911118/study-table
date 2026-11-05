<script setup lang="ts">
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
    <h1>孩子端 · 今日</h1>
    <p>骨架已就位，页面内容按里程碑逐步替换。下面这张表就是 M2–M3 的施工清单。</p>
  </section>

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
</style>
