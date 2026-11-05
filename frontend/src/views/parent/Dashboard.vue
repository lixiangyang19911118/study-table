<script setup lang="ts">
const planned = [
  { name: '布置作业 · 粘贴导入', note: '识别段落头与科目，生成待确认清单', m: 'M2' },
  { name: '任务编辑 / 删除 / 调序', note: 'PRD 列为第一阻塞项', m: 'M2' },
  { name: '审核与退回', note: '通过时写星星流水，不是直接改余额', m: 'M2' },
  { name: '错题录入与重做记录', note: '含 OCR 结果核对页', m: 'M3' },
  { name: '教材资源管理', note: 'PDF 存磁盘，按年级科目分类', m: 'M4' },
  { name: '周报', note: '实时聚合，不读快照', m: 'M4' },
]
</script>

<template>
  <section class="head">
    <h1>家长端 · 总览</h1>
    <p>同一套骨架，另一组路由。家长端和孩子端共用接口，差别只在权限与信息密度。</p>
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
