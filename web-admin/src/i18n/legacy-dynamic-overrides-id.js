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
  // 档案批量导出
  { pattern: /^批量导出PDF（(\d+)）$/, replace: (_, n) => `Ekspor PDF massal (${n})` },
  { pattern: /^正在导出：(.+)$/, replace: (_, name) => `Mengekspor: ${name}` },
  { pattern: /^已完成 (\d+)\/(\d+)$/, replace: (_, a, b) => `Selesai ${a}/${b}` },
  { pattern: /^成功 (\d+) 个，失败 (\d+) 个$/, replace: (_, a, b) => `${a} berhasil, ${b} gagal` },
  { pattern: /^导出全部（(\d+)）$/, replace: (_, n) => `Ekspor semua (${n})` },
  { pattern: /^共 (\d+) 个档案$/, replace: (_, n) => `Total ${n} arsip` },
  { pattern: /^已生成 (\d+) 个，需新生成 (\d+) 个$/, replace: (_, a, b) => `${a} sudah dibuat, ${b} perlu dibuat` },
  { pattern: /^(\d+) 个档案不存在，将跳过$/, replace: (_, n) => `${n} arsip tidak ditemukan; akan dilewati` },
  { pattern: /^预计大小：约 (.+)，分 (\d+) 卷下载$/, replace: (_, s, p) => `Perkiraan ukuran: sekitar ${s}, diunduh dalam ${p} bagian` },
  { pattern: /^预计大小：约 (.+)$/, replace: (_, s) => `Perkiraan ukuran: sekitar ${s}` },
  { pattern: /^预计等待：约 (\d+) 分钟$/, replace: (_, m) => `Perkiraan waktu tunggu: sekitar ${m} menit` },
  { pattern: /^预计等待：约 (\d+) 小时 (\d+) 分钟$/, replace: (_, h, m) => `Perkiraan waktu tunggu: sekitar ${h} jam ${m} menit` },
  { pattern: /^前面有 (\d+) 个导出任务排队$/, replace: (_, n) => `${n} tugas ekspor di antrean sebelumnya` },
  { pattern: /^其中 (\d+) 个直接使用已生成的PDF$/, replace: (_, n) => `${n} memakai PDF yang sudah dibuat` },
  { pattern: /^第 (\d+) 卷：(\d+) 个档案，(.+)$/, replace: (_, i, n, s) => `Bagian ${i}: ${n} arsip, ${s}` },
  // 设备拆除/移机
  { pattern: /^拆除\/移机：(.+)$/, replace: (_, r) => `Bongkar/pindah: ${r}` },
  { pattern: /^共 (\d+) 台，可拆除 (\d+) 台$/, replace: (_, a, b) => `Total ${a} perangkat, ${b} dapat dibongkar` },
  { pattern: /^将拆除 (\d+) 台设备，另有 (\d+) 台不满足条件将跳过。确认继续？$/, replace: (_, a, b) => `${a} perangkat akan dibongkar; ${b} perangkat yang tidak memenuhi syarat akan dilewati. Lanjutkan?` },
  { pattern: /^将拆除 (\d+) 台设备，确认继续？$/, replace: (_, a) => `${a} perangkat akan dibongkar. Lanjutkan?` },
  { pattern: /^已拆除 (\d+) 台设备$/, replace: (_, a) => `${a} perangkat telah dibongkar` },
]

export default legacyDynamicOverridesId
