// 手工维护：印尼语动态文字规则（legacy-dynamic-patterns-id.js 为自动生成，请勿在其中手改）
const legacyDynamicOverridesId = [
  { pattern: /^(⚠️\s*)?当前共有 (\d+) 个工单关联此模板$/, replace: (_, icon, n) => `${icon || ''}${n} perintah kerja saat ini memakai template ini` },
  { pattern: /^立即同步：(\d+) 个进行中\/驳回工单$/, replace: (_, n) => `Sinkron sekarang: ${n} perintah kerja berjalan/ditolak` },
  { pattern: /^待重提生效：(\d+) 个已提交\/审核中工单$/, replace: (_, n) => `Berlaku saat diajukan ulang: ${n} perintah kerja diajukan/ditinjau` },
  { pattern: /^冻结不影响：(\d+) 个已完成\/已归档工单$/, replace: (_, n) => `Dibekukan (tidak terpengaruh): ${n} perintah kerja selesai/diarsipkan` },
  { pattern: /^立即同步 (\d+) 个，待重提生效 (\d+) 个，冻结不影响 (\d+) 个$/, replace: (_, a, b, c) => `${a} sinkron sekarang, ${b} berlaku saat diajukan ulang, ${c} dibekukan` },
  { pattern: /^(\d+) 项$/, replace: (_, n) => `${n} item` },
  { pattern: /^(\d+)\/(\d+) 启用$/, replace: (_, a, b) => `${a}/${b} aktif` },
  { pattern: /^已按覆盖、冲突、跳过、写入优先展示；当前样例显示 (\d+)\/(\d+) 条$/, replace: (_, a, b) => `Diurutkan: timpa, konflik, lewati, tulis; menampilkan ${a}/${b} contoh` },
]

export default legacyDynamicOverridesId
