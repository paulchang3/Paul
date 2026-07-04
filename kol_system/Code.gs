/************************************************************
 * KOL 聯絡與國際合作上市計畫 — 管理系統 v2.0
 * Google Apps Script 主程式
 *
 * v2.0 依「曝光策略」重新設計（見 STRATEGY.md）：
 *  【被動曝光】
 *   - 內容行事曆（構想→草稿→已發布 管線管理）
 *   - RSS 情報來源 → 每週一自動彙整信（內容素材自動送上門）
 *   - 法規動態季報：每季自動由範本生成文件
 *   - 電子報：對訂閱的 A/B 級 KOL 個人化群發，自動回寫接觸紀錄
 *   - 公開洞察頁（Web App）：自動發布已發布內容，取代 Google Sites
 *  【主動曝光】
 *   - 等級化跟進節奏引擎（A:14天 / B:30天 / C:90天，記錄接觸即自動排程）
 *   - 每日 08:00 跟進摘要信（到期 + 逾期 + 關係降溫警示，附鉤子）
 *   - 話術模板一鍵產生 Gmail 開發信草稿
 *   - 跟進日一鍵同步 Google Calendar
 *  【系統】
 *   - 一鍵初始化 / 自我檢查 / 自動修復（沿用 v1，涵蓋新分頁與觸發器）
 *   - v1 資料完全相容：自動修復會補上 v2 新增欄位與分頁
 ************************************************************/

const CONFIG = {
  VERSION: '2.0.0',
  SHEETS: {
    KOL: 'KOL名單',
    CONTACT: '接觸紀錄',
    CONTENT: '內容行事曆',
    INTEL: '情報來源',
    NEWSLETTER: '電子報發送紀錄',
    SETTINGS: '系統設定',
    LOG: '系統日誌'
  },
  KOL_HEADERS: [
    'ID', '姓名', '職稱', '公司', '等級(A/B/C)', '市場專長',
    '接觸管道', 'Email', 'LinkedIn', '首次接觸日', '最近接觸日',
    '關係溫度(1-5)', '合作階段(1-4)', '下次跟進日', '下次跟進鉤子', '備註',
    '訂閱電子報(Y/N)', '曝光來源'
  ],
  CONTACT_HEADERS: ['ID', 'KOL_ID', '日期', '接觸方式', '內容摘要', '下一步'],
  CONTENT_HEADERS: [
    'ID', '標題', '內容支柱', '目標管道', '狀態',
    '預計發布日', '實際發布日', '連結', '公開摘要', '成效備註'
  ],
  INTEL_HEADERS: ['名稱', 'RSS網址', '市場', '啟用(Y/N)'],
  NEWSLETTER_HEADERS: ['時間', '主旨', '收件人數', '成功', '失敗', '備註'],

  // 主動曝光：等級化跟進節奏（天）
  CADENCE_DAYS: { A: 14, B: 30, C: 90 },
  // 關係降溫警示門檻（超過 N 天未接觸）
  STALE_DAYS: { A: 30, B: 60, C: 120 },

  DRIVE_ROOT_FOLDER: 'KOL管理系統資料',
  DRIVE_SUBFOLDERS: ['分享素材', '範本文件', '季度動態報告'],
  TEMPLATE_DOC_NAME: '法規動態季報_範本',

  // 自動化觸發器（handler 名稱 → 說明）
  TRIGGERS: {
    dailyFollowUpDigest: '每日 08:00 跟進摘要信',
    weeklyIntelDigest: '每週一 08:00 情報彙整信',
    quarterlyKickoff: '每季首日 09:00 自動生成季報文件'
  },

  // 情報來源種子（官方來源的 RSS 網址請自行確認補上）
  INTEL_DEFAULTS: [
    ['MedTech Dive（產業新聞）', 'https://www.medtechdive.com/feeds/news/', '美國/全球', 'Y'],
    ['MassDevice（產業新聞）', 'https://www.massdevice.com/feed/', '美國/全球', 'Y'],
    ['FDA 器材動態（請填入RSS網址後啟用）', '', 'FDA', 'N'],
    ['EU MDR 動態（請填入RSS網址後啟用）', '', 'EU', 'N'],
    ['TFDA 公告（請填入RSS網址後啟用）', '', 'TW', 'N'],
    ['NMPA 動態（請填入RSS網址後啟用）', '', 'CN', 'N'],
    ['PMDA 動態（請填入RSS網址後啟用）', '', 'JP', 'N']
  ]
};

// 主動曝光：開發信話術模板（{姓名}{公司}{鉤子}{我的姓名} 會自動代入）
const OUTREACH_TEMPLATES = {
  '首次接觸-保守型（資深/謹慎對象）': {
    subject: '跨國醫材法規協調交流',
    body: '{姓名} 您好，\n\n我一直在關注 {公司} 在多國上市策略上的布局。我專注於醫材跨國法規協調（FDA / EU MDR / TFDA / NMPA / PMDA），過去協助團隊處理過多國同步送件的實務挑戰。\n\n若您方便，很樂意交流一些跨市場的觀察，不一定要有立即的合作目的。\n\n{我的姓名} 敬上'
  },
  '首次接觸-價值導向型（務實決策者）': {
    subject: '一個能縮短多國審查時間的實務做法，供您參考',
    body: '{姓名} 您好，\n\n我們最近協助一個案子把 FDA 與 EU MDR 的臨床資料驗證流程做了整合，讓歐美同步送件的時程明顯縮短。不確定 {公司} 目前是否也面臨類似的多國時程壓力，若有興趣交流實務作法，很樂意約 15 分鐘聊聊。\n\n{我的姓名} 敬上'
  },
  '首次接觸-高階型（高管/投資人）': {
    subject: '關於多國同步上市的策略交流',
    body: '{姓名} 您好，\n\n我長期在觀察醫材產業「多國同步上市」這個趨勢——尤其是資金與時程效率如何決定產品的市場先機。您在 {公司} 的布局讓我很好奇：您們目前如何看待 FDA、MDR、NMPA 三地審查邏輯差異帶來的策略選擇？\n\n我在這個領域累積了不少跨國協調的實戰案例，如果您願意，很樂意交換觀點。\n\n{我的姓名} 敬上'
  },
  '跟進-分享價值型': {
    subject: '一份您可能有興趣的資料 — {鉤子}',
    body: '{姓名} 您好，\n\n上次交流提到「{鉤子}」，剛好整理了一份相關資料，附上供您參考。如果有不同看法或延伸問題，很樂意再交流。\n\n{我的姓名} 敬上'
  },
  '跟進-詢問近況型': {
    subject: '近期在「{鉤子}」上的進展如何？',
    body: '{姓名} 您好，\n\n一陣子沒聯繫，想跟您請教 {公司} 在「{鉤子}」上目前的進展。最近剛好接觸到一些相關市場的新規定變化，如果對您有幫助的話很樂意分享。\n\n{我的姓名} 敬上'
  },
  '跟進-提出合作測試型': {
    subject: '一個可以先小規模試試看的想法',
    body: '{姓名} 您好，\n\n我們聊了幾次關於「{鉤子}」，我在想與其一開始就討論大框架，不如先從一個具體的小專案開始，讓您實際感受一下跨國協調的效果，之後再看是否值得擴大範圍。您覺得如何？\n\n{我的姓名} 敬上'
  }
};

/* ================= 選單 / 進入點 ================= */

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('🗂 KOL管理系統')
    .addItem('🖥 開啟管理主控台', 'openDashboard')
    .addItem('🚀 一鍵部署 / 初始化系統', 'initializeSystem')
    .addSeparator()
    .addItem('⚡ 啟用全部自動化排程', 'menuSetupTriggers')
    .addItem('📬 立即寄送：每日跟進摘要', 'dailyFollowUpDigest')
    .addItem('📰 立即寄送：每週情報彙整', 'weeklyIntelDigest')
    .addItem('📄 產生本季季報文件', 'menuQuarterlyReport')
    .addSeparator()
    .addItem('🔍 系統自我檢查', 'runSelfCheckUI')
    .addItem('🛠 自動修復系統', 'runAutoFixUI')
    .addItem('ℹ️ 關於此系統', 'showAbout')
    .addToUi();
}

function openDashboard() {
  const html = HtmlService.createHtmlOutputFromFile('Dashboard')
    .setTitle('KOL 管理主控台 v' + CONFIG.VERSION)
    .setWidth(440);
  SpreadsheetApp.getUi().showSidebar(html);
}

/**
 * Web App 進入點。
 * - 擁有者開啟 → 完整主控台
 * - 匿名/其他訪客開啟（或 ?view=insights）→ 公開洞察頁（被動曝光用，只含已發布內容，不含名單資料）
 * 要對外公開洞察頁時，部署設定需為「執行身分：我 / 存取權：任何人」，詳見 README。
 */
function doGet(e) {
  const view = (e && e.parameter && e.parameter.view) || '';
  const visitor = Session.getActiveUser().getEmail();
  const owner = Session.getEffectiveUser().getEmail();
  if (view === 'insights' || !visitor || visitor !== owner) {
    return renderInsightsPage_();
  }
  return HtmlService.createHtmlOutputFromFile('Dashboard')
    .setTitle('KOL 管理主控台')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

function showAbout() {
  SpreadsheetApp.getUi().alert(
    'KOL 管理系統 v' + CONFIG.VERSION +
    '\n\n以「被動曝光（內容/季報/洞察頁）＋主動曝光（節奏化跟進/開發信）」\n雙軌策略設計的 KOL 關係管理系統。\n\n若資料異常，請執行「系統自我檢查」與「自動修復系統」。'
  );
}

function menuSetupTriggers() {
  const r = api_setupTriggers();
  SpreadsheetApp.getUi().alert('⚡ 已啟用自動化排程：\n\n' + r.enabled.join('\n'));
}

function menuQuarterlyReport() {
  const r = api_generateQuarterlyReport();
  SpreadsheetApp.getUi().alert('📄 已建立季報文件：\n' + r.name + '\n\n' + r.url);
}

/* ================= 一鍵初始化 / 部署 ================= */

function initializeSystem() {
  const result = { sheets: [], folders: [], docs: [], errors: [] };
  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();

    ensureSheet_(ss, CONFIG.SHEETS.KOL, CONFIG.KOL_HEADERS, result);
    ensureSheet_(ss, CONFIG.SHEETS.CONTACT, CONFIG.CONTACT_HEADERS, result);
    ensureSheet_(ss, CONFIG.SHEETS.CONTENT, CONFIG.CONTENT_HEADERS, result);
    ensureSheet_(ss, CONFIG.SHEETS.INTEL, CONFIG.INTEL_HEADERS, result);
    ensureSheet_(ss, CONFIG.SHEETS.NEWSLETTER, CONFIG.NEWSLETTER_HEADERS, result);
    ensureSheet_(ss, CONFIG.SHEETS.SETTINGS, ['KEY', 'VALUE'], result);
    ensureSheet_(ss, CONFIG.SHEETS.LOG, ['時間', '動作', '結果'], result);

    seedIntelSources_();

    const rootFolder = ensureDriveFolder_(CONFIG.DRIVE_ROOT_FOLDER, null, result);
    CONFIG.DRIVE_SUBFOLDERS.forEach(name => ensureDriveFolder_(name, rootFolder, result));
    ensureTemplateDoc_(rootFolder, result);

    writeSetting_('ROOT_FOLDER_ID', rootFolder.getId());
    writeSetting_('INIT_DATE', new Date().toISOString());
    writeSetting_('VERSION', CONFIG.VERSION);
    if (!readSetting_('SENDER_NAME')) writeSetting_('SENDER_NAME', '');
    if (!readSetting_('SIGNATURE')) {
      writeSetting_('SIGNATURE', '跨國醫材法規協調（FDA / EU MDR / TFDA / NMPA / PMDA）');
    }
    if (!readSetting_('PUBLIC_TITLE')) writeSetting_('PUBLIC_TITLE', '跨國醫材法規洞察');
    if (!readSetting_('PUBLIC_TAGLINE')) {
      writeSetting_('PUBLIC_TAGLINE', '把「多國個別註冊」重組為「一次策略、多國同步」— FDA / EU MDR / TFDA / NMPA / PMDA 實務觀察');
    }

    logAction_('初始化系統', '成功：' + JSON.stringify(result));
    SpreadsheetApp.getUi().alert(
      '✅ 初始化完成\n\n已建立分頁：' + (result.sheets.join('、') || '（皆已存在）') +
      '\n已建立資料夾：' + (result.folders.join('、') || '（皆已存在）') +
      (result.docs.length ? '\n已建立文件：' + result.docs.join('、') : '') +
      '\n\n下一步：到主控台「自動化」分頁啟用排程，' +
      '並在「情報來源」分頁確認 RSS 網址。'
    );
  } catch (e) {
    logAction_('初始化系統', '失敗：' + e.message);
    SpreadsheetApp.getUi().alert('❌ 初始化過程發生錯誤：' + e.message);
  }
  return result;
}

function seedIntelSources_() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(CONFIG.SHEETS.INTEL);
  if (!sheet || sheet.getLastRow() > 1) return;
  CONFIG.INTEL_DEFAULTS.forEach(row => sheet.appendRow(row));
}

/* ================= 自我檢查 / 自動修復 ================= */

function runSelfCheckUI() {
  const report = selfCheck();
  const ui = SpreadsheetApp.getUi();
  ui.alert('系統自我檢查結果', formatCheckReport_(report), ui.ButtonSet.OK);
}

function selfCheck() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const report = { ok: true, issues: [], details: [] };

  allSheetSpecs_().forEach(spec => checkSheet_(ss, spec.name, spec.headers, report));

  const rootId = readSetting_('ROOT_FOLDER_ID');
  if (!rootId) {
    report.ok = false;
    report.issues.push('找不到系統資料夾設定（尚未初始化，或設定遺失）');
  } else {
    try {
      DriveApp.getFolderById(rootId);
      report.details.push('Drive 根資料夾正常');
    } catch (e) {
      report.ok = false;
      report.issues.push('系統資料夾ID無效或已被刪除：' + rootId);
    }
  }

  const active = activeTriggerHandlers_();
  const missing = Object.keys(CONFIG.TRIGGERS).filter(h => active.indexOf(h) === -1);
  if (missing.length === Object.keys(CONFIG.TRIGGERS).length) {
    report.details.push('自動化排程尚未啟用（可在主控台「自動化」分頁一鍵啟用）');
  } else if (missing.length > 0) {
    report.issues.push('部分自動化排程未啟用：' + missing.map(h => CONFIG.TRIGGERS[h]).join('、'));
    report.ok = false;
  } else {
    report.details.push('自動化排程（每日摘要／每週情報／季報）全部啟用中');
  }

  logAction_('自我檢查', report.ok ? '正常' : '發現問題：' + report.issues.join('；'));
  return report;
}

function allSheetSpecs_() {
  return [
    { name: CONFIG.SHEETS.KOL, headers: CONFIG.KOL_HEADERS },
    { name: CONFIG.SHEETS.CONTACT, headers: CONFIG.CONTACT_HEADERS },
    { name: CONFIG.SHEETS.CONTENT, headers: CONFIG.CONTENT_HEADERS },
    { name: CONFIG.SHEETS.INTEL, headers: CONFIG.INTEL_HEADERS },
    { name: CONFIG.SHEETS.NEWSLETTER, headers: CONFIG.NEWSLETTER_HEADERS },
    { name: CONFIG.SHEETS.SETTINGS, headers: ['KEY', 'VALUE'] },
    { name: CONFIG.SHEETS.LOG, headers: ['時間', '動作', '結果'] }
  ];
}

function checkSheet_(ss, name, headers, report) {
  const sheet = ss.getSheetByName(name);
  if (!sheet) {
    report.ok = false;
    report.issues.push('缺少分頁：' + name);
    return;
  }
  const lastCol = Math.max(sheet.getLastColumn(), 1);
  const existing = sheet.getRange(1, 1, 1, lastCol).getValues()[0].map(String);
  const missing = headers.filter(h => existing.indexOf(h) === -1);
  if (missing.length > 0) {
    report.ok = false;
    report.issues.push(`分頁「${name}」缺少欄位：${missing.join('、')}`);
  } else {
    report.details.push(`分頁「${name}」結構正常`);
  }
}

function runAutoFixUI() {
  const result = autoFix();
  SpreadsheetApp.getUi().alert(
    '🛠 自動修復完成\n\n' +
    (result.fixed.length ? '已修復：\n' + result.fixed.join('\n') : '沒有發現需要修復的項目')
  );
}

function autoFix() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const result = { fixed: [] };

  allSheetSpecs_().forEach(spec => fixSheet_(ss, spec.name, spec.headers, result));
  seedIntelSources_();

  const rootId = readSetting_('ROOT_FOLDER_ID');
  let rootFolder = null;
  try {
    rootFolder = rootId ? DriveApp.getFolderById(rootId) : null;
  } catch (e) {
    rootFolder = null;
  }
  if (!rootFolder) {
    rootFolder = ensureDriveFolder_(CONFIG.DRIVE_ROOT_FOLDER, null, { folders: [] });
    writeSetting_('ROOT_FOLDER_ID', rootFolder.getId());
    result.fixed.push('重建系統資料夾：' + CONFIG.DRIVE_ROOT_FOLDER);
  }
  CONFIG.DRIVE_SUBFOLDERS.forEach(name => {
    if (!rootFolder.getFoldersByName(name).hasNext()) {
      rootFolder.createFolder(name);
      result.fixed.push('補建子資料夾：' + name);
    }
  });

  logAction_('自動修復', result.fixed.length ? result.fixed.join('；') : '無需修復');
  return result;
}

function fixSheet_(ss, name, headers, result) {
  let sheet = ss.getSheetByName(name);
  if (!sheet) {
    sheet = ss.insertSheet(name);
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    formatHeaderRow_(sheet, headers.length);
    result.fixed.push('建立缺少的分頁：' + name);
    return;
  }
  const lastCol = Math.max(sheet.getLastColumn(), 1);
  const existing = sheet.getRange(1, 1, 1, lastCol).getValues()[0].map(String);
  let changed = false;
  headers.forEach(h => {
    if (existing.indexOf(h) === -1) {
      sheet.getRange(1, sheet.getLastColumn() + 1).setValue(h);
      changed = true;
    }
  });
  if (changed) {
    formatHeaderRow_(sheet, sheet.getLastColumn());
    result.fixed.push('補齊分頁「' + name + '」缺少的欄位');
  }
}

/* ================= 共用工具函式 ================= */

function ss_() {
  return SpreadsheetApp.getActiveSpreadsheet();
}

function mustSheet_(name) {
  const sheet = ss_().getSheetByName(name);
  if (!sheet) throw new Error('找不到「' + name + '」分頁，請先執行初始化（主控台「自動化」分頁）');
  return sheet;
}

function getHeaders_(sheet) {
  const lastCol = Math.max(sheet.getLastColumn(), 1);
  return sheet.getRange(1, 1, 1, lastCol).getValues()[0].map(String);
}

/** 讀整張表為物件陣列（以實際表頭為 key；日期轉 ISO 字串以便傳到前端） */
function readTable_(name) {
  const sheet = ss_().getSheetByName(name);
  if (!sheet || sheet.getLastRow() < 2) return [];
  const values = sheet.getDataRange().getValues();
  const headers = values[0].map(String);
  return values.slice(1).map(r => {
    const o = {};
    headers.forEach((h, j) => {
      const v = r[j];
      o[h] = (v instanceof Date) ? v.toISOString() : v;
    });
    return o;
  });
}

function setCellByHeader_(sheet, headers, rowIndex1, headerName, value) {
  const col = headers.indexOf(headerName);
  if (col === -1) return;
  sheet.getRange(rowIndex1, col + 1).setValue(value);
}

function ensureSheet_(ss, name, headers, result) {
  let sheet = ss.getSheetByName(name);
  if (!sheet) {
    sheet = ss.insertSheet(name);
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    formatHeaderRow_(sheet, headers.length);
    result.sheets.push(name);
  }
  return sheet;
}

function formatHeaderRow_(sheet, numCols) {
  const range = sheet.getRange(1, 1, 1, numCols);
  range.setFontWeight('bold').setBackground('#14213D').setFontColor('#FFFFFF');
  sheet.setFrozenRows(1);
  sheet.autoResizeColumns(1, numCols);
}

function ensureDriveFolder_(name, parent, result) {
  const iterator = parent ? parent.getFoldersByName(name) : DriveApp.getFoldersByName(name);
  if (iterator.hasNext()) return iterator.next();
  const folder = parent ? parent.createFolder(name) : DriveApp.createFolder(name);
  if (result && result.folders) result.folders.push(name);
  return folder;
}

function ensureTemplateDoc_(rootFolder, result) {
  const templatesFolder = ensureDriveFolder_('範本文件', rootFolder, result);
  const iterator = templatesFolder.getFilesByName(CONFIG.TEMPLATE_DOC_NAME);
  if (iterator.hasNext()) return iterator.next();

  const doc = DocumentApp.create(CONFIG.TEMPLATE_DOC_NAME);
  const body = doc.getBody();
  body.appendParagraph('法規動態季報').setHeading(DocumentApp.ParagraphHeading.TITLE);
  body.appendParagraph('期間：____年 Q_').setHeading(DocumentApp.ParagraphHeading.NORMAL);
  ['FDA 動態', 'EU MDR 動態', 'TFDA 動態', 'NMPA 動態', 'PMDA 動態', '本季觀點與建議']
    .forEach(section => {
      body.appendParagraph(section).setHeading(DocumentApp.ParagraphHeading.HEADING2);
      body.appendParagraph('（請填寫本節重點...）');
    });
  doc.saveAndClose();

  const file = DriveApp.getFileById(doc.getId());
  file.moveTo(templatesFolder);
  if (result && result.docs) result.docs.push(CONFIG.TEMPLATE_DOC_NAME);
  return file;
}

function writeSetting_(key, value) {
  const ss = ss_();
  const sheet = ss.getSheetByName(CONFIG.SHEETS.SETTINGS) || ss.insertSheet(CONFIG.SHEETS.SETTINGS);
  const data = sheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (data[i][0] === key) {
      sheet.getRange(i + 1, 2).setValue(value);
      return;
    }
  }
  sheet.appendRow([key, value]);
}

function readSetting_(key) {
  const sheet = ss_().getSheetByName(CONFIG.SHEETS.SETTINGS);
  if (!sheet) return null;
  const data = sheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (data[i][0] === key) return data[i][1];
  }
  return null;
}

function logAction_(action, resultText) {
  try {
    const ss = ss_();
    const sheet = ss.getSheetByName(CONFIG.SHEETS.LOG) || ss.insertSheet(CONFIG.SHEETS.LOG);
    if (sheet.getLastRow() === 0) {
      sheet.appendRow(['時間', '動作', '結果']);
      formatHeaderRow_(sheet, 3);
    }
    sheet.appendRow([new Date(), action, resultText]);
  } catch (e) {
    // 記錄失敗不應中斷主流程
  }
}

function formatCheckReport_(report) {
  let msg = report.ok ? '✅ 系統結構完整正常\n\n' : '⚠️ 發現以下問題：\n';
  if (!report.ok) {
    report.issues.forEach(i => msg += '・' + i + '\n');
    msg += '\n可執行「自動修復系統」自動修正上述問題。';
  }
  if (report.details.length) {
    msg += '\n\n詳細檢查項目：\n' + report.details.map(d => '・' + d).join('\n');
  }
  return msg;
}

function toDate_(v) {
  if (!v) return null;
  const d = (v instanceof Date) ? v : new Date(v);
  return isNaN(d.getTime()) ? null : d;
}

function startOfDay_(d) {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}

function fmtDate_(v) {
  const d = toDate_(v);
  if (!d) return '';
  return Utilities.formatDate(d, Session.getScriptTimeZone(), 'yyyy/MM/dd');
}

function daysSince_(v) {
  const d = toDate_(v);
  if (!d) return null;
  return Math.floor((startOfDay_(new Date()) - startOfDay_(d)) / 86400000);
}

function escapeHtml_(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function ownerEmail_() {
  return Session.getEffectiveUser().getEmail() || Session.getActiveUser().getEmail();
}

function senderName_() {
  return String(readSetting_('SENDER_NAME') || '').trim() || ownerEmail_();
}

function tierOf_(kol) {
  return String(kol['等級(A/B/C)'] || 'C').charAt(0).toUpperCase();
}

/* ================= KOL 名單 API ================= */

function api_getKolList() {
  return readTable_(CONFIG.SHEETS.KOL).filter(k => k['姓名']);
}

function api_saveKol(kol) {
  const sheet = mustSheet_(CONFIG.SHEETS.KOL);
  const headers = getHeaders_(sheet);

  if (kol['ID']) {
    const data = sheet.getDataRange().getValues();
    for (let i = 1; i < data.length; i++) {
      if (String(data[i][0]) === String(kol['ID'])) {
        const row = data[i].slice(0, headers.length);
        headers.forEach((h, j) => {
          if (kol[h] !== undefined) row[j] = kol[h];
        });
        sheet.getRange(i + 1, 1, 1, headers.length).setValues([row]);
        return { status: 'updated', id: kol['ID'] };
      }
    }
  }
  const newId = 'K' + Date.now();
  const row = headers.map(h => (kol[h] !== undefined ? kol[h] : ''));
  row[0] = newId;
  sheet.appendRow(row);
  return { status: 'created', id: newId };
}

function api_deleteKol(id) {
  const sheet = mustSheet_(CONFIG.SHEETS.KOL);
  const data = sheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]) === String(id)) {
      sheet.deleteRow(i + 1);
      return { status: 'deleted' };
    }
  }
  return { status: 'not_found' };
}

/* ================= 接觸紀錄 API（含跟進節奏引擎） ================= */

/**
 * 記錄一次接觸：
 *  1. 寫入接觸紀錄
 *  2. 更新 KOL「最近接觸日」
 *  3. 若「下次跟進日」為空或已過期 → 依等級節奏（A:14/B:30/C:90 天）自動排下一次
 *  4. 「下一步」自動寫入「下次跟進鉤子」（鉤子式跟進，見 STRATEGY.md §3.2）
 */
function api_logContact(entry) {
  const sheet = mustSheet_(CONFIG.SHEETS.CONTACT);
  const newId = 'C' + Date.now();
  const when = entry.date ? new Date(entry.date) : new Date();
  sheet.appendRow([newId, entry.kolId, when, entry.method, entry.summary, entry.nextStep]);

  const kolSheet = mustSheet_(CONFIG.SHEETS.KOL);
  const headers = getHeaders_(kolSheet);
  const data = kolSheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]) !== String(entry.kolId)) continue;
    const rowIdx = i + 1;
    setCellByHeader_(kolSheet, headers, rowIdx, '最近接觸日', when);

    const tier = String(data[i][headers.indexOf('等級(A/B/C)')] || 'C').charAt(0).toUpperCase();
    const cadence = CONFIG.CADENCE_DAYS[tier] || CONFIG.CADENCE_DAYS.C;
    const curNextIdx = headers.indexOf('下次跟進日');
    const curNext = curNextIdx === -1 ? null : toDate_(data[i][curNextIdx]);
    let scheduled = curNext;
    if (!curNext || curNext <= startOfDay_(new Date())) {
      scheduled = new Date(startOfDay_(when).getTime() + cadence * 86400000);
      setCellByHeader_(kolSheet, headers, rowIdx, '下次跟進日', scheduled);
    }
    if (entry.nextStep) {
      setCellByHeader_(kolSheet, headers, rowIdx, '下次跟進鉤子', entry.nextStep);
    }
    return { status: 'ok', id: newId, nextFollowUp: fmtDate_(scheduled) };
  }
  return { status: 'ok', id: newId, warning: '找不到對應 KOL，未更新跟進排程' };
}

function api_getContactsByKol(kolId) {
  return readTable_(CONFIG.SHEETS.CONTACT)
    .filter(c => String(c['KOL_ID']) === String(kolId));
}

/**
 * 待跟進清單：
 *  due   — 下次跟進日 ≤ 今天
 *  stale — 關係降溫警示：超過等級門檻天數未接觸（A:30/B:60/C:120）
 */
function api_getDueFollowUps() {
  const list = api_getKolList();
  const today = startOfDay_(new Date());
  const due = [];
  const stale = [];

  list.forEach(k => {
    const next = toDate_(k['下次跟進日']);
    if (next && startOfDay_(next) <= today) {
      due.push(k);
      return;
    }
    const tier = tierOf_(k);
    const threshold = CONFIG.STALE_DAYS[tier] || CONFIG.STALE_DAYS.C;
    const last = k['最近接觸日'] || k['首次接觸日'];
    const days = daysSince_(last);
    if (days === null) {
      const kk = Object.assign({}, k);
      kk['_降溫天數'] = -1; // 從未記錄接觸
      stale.push(kk);
    } else if (days > threshold) {
      const kk = Object.assign({}, k);
      kk['_降溫天數'] = days;
      stale.push(kk);
    }
  });

  stale.sort((a, b) => b['_降溫天數'] - a['_降溫天數']);
  return { due: due, stale: stale };
}

/* ================= 內容行事曆 API（被動曝光管線） ================= */

function api_getContentList() {
  return readTable_(CONFIG.SHEETS.CONTENT).filter(c => c['標題']);
}

function api_saveContent(item) {
  const sheet = mustSheet_(CONFIG.SHEETS.CONTENT);
  const headers = getHeaders_(sheet);

  if (item['ID']) {
    const data = sheet.getDataRange().getValues();
    for (let i = 1; i < data.length; i++) {
      if (String(data[i][0]) === String(item['ID'])) {
        const row = data[i].slice(0, headers.length);
        headers.forEach((h, j) => {
          if (item[h] !== undefined) row[j] = item[h];
        });
        sheet.getRange(i + 1, 1, 1, headers.length).setValues([row]);
        return { status: 'updated', id: item['ID'] };
      }
    }
  }
  const newId = 'P' + Date.now();
  const row = headers.map(h => (item[h] !== undefined ? item[h] : ''));
  row[0] = newId;
  sheet.appendRow(row);
  return { status: 'created', id: newId };
}

function api_deleteContent(id) {
  const sheet = mustSheet_(CONFIG.SHEETS.CONTENT);
  const data = sheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]) === String(id)) {
      sheet.deleteRow(i + 1);
      return { status: 'deleted' };
    }
  }
  return { status: 'not_found' };
}

function getPublishedContent_() {
  return api_getContentList()
    .filter(c => c['狀態'] === '已發布')
    .sort((a, b) => {
      const da = toDate_(a['實際發布日'] || a['預計發布日']) || new Date(0);
      const db = toDate_(b['實際發布日'] || b['預計發布日']) || new Date(0);
      return db - da;
    })
    .slice(0, 30)
    .map(c => ({
      title: c['標題'],
      pillar: c['內容支柱'],
      channel: c['目標管道'],
      date: fmtDate_(c['實際發布日'] || c['預計發布日']),
      link: c['連結'] || '',
      summary: c['公開摘要'] || ''
    }));
}

/* ================= 總覽儀表板 API ================= */

function api_getDashboardStats() {
  const kols = api_getKolList();
  const today = startOfDay_(new Date());

  const byTier = { A: 0, B: 0, C: 0 };
  const byStage = { 1: 0, 2: 0, 3: 0, 4: 0 };
  let overdue = 0;
  let subscribers = 0;

  kols.forEach(k => {
    const t = tierOf_(k);
    if (byTier[t] !== undefined) byTier[t]++;
    const st = parseInt(k['合作階段(1-4)'], 10);
    if (byStage[st] !== undefined) byStage[st]++;
    const next = toDate_(k['下次跟進日']);
    if (next && startOfDay_(next) <= today) overdue++;
    if (String(k['訂閱電子報(Y/N)'] || '').toUpperCase() === 'Y' && k['Email']) subscribers++;
  });

  const contacts = readTable_(CONFIG.SHEETS.CONTACT);
  const contacts30d = contacts.filter(c => {
    const d = daysSince_(c['日期']);
    return d !== null && d <= 30;
  }).length;

  const content = api_getContentList();
  const published30d = content.filter(c => {
    if (c['狀態'] !== '已發布') return false;
    const d = daysSince_(c['實際發布日'] || c['預計發布日']);
    return d !== null && d <= 30;
  }).length;
  const pipeline = { '構想': 0, '草稿': 0, '已發布': 0 };
  content.forEach(c => {
    if (pipeline[c['狀態']] !== undefined) pipeline[c['狀態']]++;
  });

  const stale = api_getDueFollowUps().stale.length;

  const nlLog = readTable_(CONFIG.SHEETS.NEWSLETTER);
  const lastNewsletter = nlLog.length
    ? fmtDate_(nlLog[nlLog.length - 1]['時間']) + '「' + nlLog[nlLog.length - 1]['主旨'] + '」'
    : '尚未寄送過';

  return {
    total: kols.length,
    byTier: byTier,
    byStage: byStage,
    overdue: overdue,
    stale: stale,
    contacts30d: contacts30d,
    published30d: published30d,
    pipeline: pipeline,
    subscribers: subscribers,
    lastNewsletter: lastNewsletter
  };
}

/* ================= 電子報模組（被動曝光：定期信息分享） ================= */

function newsletterRecipients_(includeC) {
  return api_getKolList().filter(k => {
    if (String(k['訂閱電子報(Y/N)'] || '').toUpperCase() !== 'Y') return false;
    if (!k['Email']) return false;
    const tier = tierOf_(k);
    return includeC ? true : (tier === 'A' || tier === 'B');
  });
}

function api_previewNewsletter(includeC) {
  const recipients = newsletterRecipients_(includeC);
  return {
    count: recipients.length,
    remainingQuota: MailApp.getRemainingDailyQuota(),
    sample: recipients.slice(0, 10).map(k => k['姓名'] + '（' + tierOf_(k) + '級 · ' + k['Email'] + '）')
  };
}

/**
 * 寄送電子報：
 *  - 對象：訂閱電子報 = Y 且有 Email 的 A/B 級（可選含 C 級）
 *  - 逐一個人化稱謂寄送
 *  - 每位收件人自動寫入接觸紀錄（方式：電子報）並更新「最近接觸日」
 *  - 寫入電子報發送紀錄
 * payload: { subject, body, includeC, includeRecent }
 */
function api_sendNewsletter(payload) {
  const subject = String(payload.subject || '').trim();
  const bodyText = String(payload.body || '').trim();
  if (!subject || !bodyText) throw new Error('主旨與內文皆不可為空');

  const recipients = newsletterRecipients_(!!payload.includeC);
  if (!recipients.length) throw new Error('沒有符合條件的收件人（請確認 KOL 的「訂閱電子報(Y/N)」與 Email 欄位）');

  const quota = MailApp.getRemainingDailyQuota();
  if (quota < recipients.length) {
    throw new Error('今日 Gmail 剩餘寄送額度（' + quota + '）不足以寄給 ' + recipients.length + ' 位收件人，請縮小名單或明日再寄');
  }

  let recentHtml = '';
  if (payload.includeRecent) {
    const items = getPublishedContent_().slice(0, 5);
    if (items.length) {
      recentHtml =
        '<h3 style="margin:24px 0 8px;font-size:15px;color:#14213D;">近期發布</h3><ul style="padding-left:20px;">' +
        items.map(it =>
          '<li style="margin-bottom:6px;">' +
          (it.link
            ? '<a href="' + escapeHtml_(it.link) + '" style="color:#0A5D5C;">' + escapeHtml_(it.title) + '</a>'
            : escapeHtml_(it.title)) +
          (it.summary ? '<br><span style="color:#5B6472;font-size:13px;">' + escapeHtml_(it.summary) + '</span>' : '') +
          '</li>'
        ).join('') +
        '</ul>';
    }
  }

  const signature = escapeHtml_(senderName_()) +
    '<br>' + escapeHtml_(String(readSetting_('SIGNATURE') || ''));
  const bodyHtml = escapeHtml_(bodyText).replace(/\n/g, '<br>');

  const contactSheet = mustSheet_(CONFIG.SHEETS.CONTACT);
  const kolSheet = mustSheet_(CONFIG.SHEETS.KOL);
  const kolHeaders = getHeaders_(kolSheet);
  const kolData = kolSheet.getDataRange().getValues();
  const rowById = {};
  for (let i = 1; i < kolData.length; i++) rowById[String(kolData[i][0])] = i + 1;

  const now = new Date();
  let sent = 0;
  const failed = [];

  recipients.forEach(k => {
    const html =
      '<div style="font-family:-apple-system,\'Noto Sans TC\',sans-serif;max-width:640px;color:#14213D;line-height:1.8;">' +
      '<p>' + escapeHtml_(k['姓名']) + ' 您好，</p>' +
      '<div>' + bodyHtml + '</div>' +
      recentHtml +
      '<hr style="border:none;border-top:1px solid #D9DEE6;margin:28px 0 12px;">' +
      '<p style="color:#5B6472;font-size:12.5px;">' + signature + '</p>' +
      '</div>';
    try {
      GmailApp.sendEmail(String(k['Email']).trim(), subject, bodyText, {
        htmlBody: html,
        name: senderName_()
      });
      sent++;
      contactSheet.appendRow(['C' + Date.now() + '_' + sent, k['ID'], now, '電子報', '電子報：' + subject, '']);
      const rowIdx = rowById[String(k['ID'])];
      if (rowIdx) setCellByHeader_(kolSheet, kolHeaders, rowIdx, '最近接觸日', now);
    } catch (e) {
      failed.push(k['姓名'] + '：' + e.message);
    }
  });

  const nlSheet = mustSheet_(CONFIG.SHEETS.NEWSLETTER);
  nlSheet.appendRow([now, subject, recipients.length, sent, failed.length, failed.join('；')]);
  logAction_('寄送電子報', '「' + subject + '」成功 ' + sent + '／失敗 ' + failed.length);

  return { sent: sent, failed: failed };
}

/* ================= 情報彙整模組（被動曝光：素材自動送上門） ================= */

function fetchFeedItems_(url) {
  const resp = UrlFetchApp.fetch(url, { muteHttpExceptions: true, followRedirects: true });
  if (resp.getResponseCode() >= 400) throw new Error('HTTP ' + resp.getResponseCode());
  const root = XmlService.parse(resp.getContentText()).getRootElement();
  const items = [];

  if (root.getName() === 'rss') {
    const channel = root.getChild('channel');
    if (channel) {
      channel.getChildren('item').forEach(it => {
        items.push({
          title: it.getChildText('title') || '(無標題)',
          link: it.getChildText('link') || '',
          date: toDate_(it.getChildText('pubDate'))
        });
      });
    }
  } else if (root.getName() === 'feed') { // Atom
    const ns = root.getNamespace();
    root.getChildren('entry', ns).forEach(en => {
      let link = '';
      const linkEls = en.getChildren('link', ns);
      for (let i = 0; i < linkEls.length; i++) {
        const rel = linkEls[i].getAttribute('rel');
        if (!rel || rel.getValue() === 'alternate') {
          const href = linkEls[i].getAttribute('href');
          link = href ? href.getValue() : '';
          break;
        }
      }
      items.push({
        title: en.getChildText('title', ns) || '(無標題)',
        link: link,
        date: toDate_(en.getChildText('updated', ns) || en.getChildText('published', ns))
      });
    });
  }
  return items;
}

/**
 * 每週情報彙整（時間觸發器：每週一 08:00）
 * 抓取「情報來源」分頁中啟用的 RSS，彙整近 8 天新聞，寄給自己。
 * 目的：把「找素材 2 小時」壓成「挑一則寫觀點 15 分鐘」。
 */
function weeklyIntelDigest() {
  const sources = readTable_(CONFIG.SHEETS.INTEL).filter(s =>
    String(s['啟用(Y/N)'] || '').toUpperCase() === 'Y' && String(s['RSS網址'] || '').trim()
  );
  if (!sources.length) {
    logAction_('每週情報彙整', '略過：沒有啟用中的情報來源');
    return;
  }

  const cutoff = Date.now() - 8 * 86400000;
  const sections = [];
  const errors = [];

  sources.forEach(s => {
    try {
      const items = fetchFeedItems_(String(s['RSS網址']).trim())
        .filter(it => !it.date || it.date.getTime() >= cutoff)
        .slice(0, 6);
      if (items.length) {
        sections.push(
          '<h3 style="margin:20px 0 6px;font-size:14.5px;color:#0A5D5C;">【' +
          escapeHtml_(s['市場']) + '】' + escapeHtml_(s['名稱']) + '</h3><ul style="padding-left:20px;margin:0;">' +
          items.map(it =>
            '<li style="margin-bottom:4px;font-size:13.5px;">' +
            (it.link ? '<a href="' + escapeHtml_(it.link) + '" style="color:#14213D;">' + escapeHtml_(it.title) + '</a>' : escapeHtml_(it.title)) +
            (it.date ? ' <span style="color:#8A93A0;font-size:12px;">(' + fmtDate_(it.date) + ')</span>' : '') +
            '</li>'
          ).join('') + '</ul>'
        );
      }
    } catch (e) {
      errors.push(s['名稱'] + '：' + e.message);
    }
  });

  const today = fmtDate_(new Date());
  const html =
    '<div style="font-family:-apple-system,\'Noto Sans TC\',sans-serif;max-width:680px;color:#14213D;line-height:1.7;">' +
    '<h2 style="font-size:17px;border-bottom:2px solid #14213D;padding-bottom:8px;">📰 每週法規／產業情報彙整 ' + today + '</h2>' +
    (sections.length ? sections.join('') : '<p>本週各情報來源沒有新項目。</p>') +
    '<div style="margin-top:24px;padding:12px 16px;background:#F1F6F5;border-left:3px solid #0E7C7B;font-size:13px;">' +
    '💡 <b>本週動作</b>：從上面挑 1–2 則，加上你的跨市場解讀，寫成 LinkedIn 貼文並登記到「內容行事曆」。' +
    '被動曝光的複利就是這樣累積的。</div>' +
    (errors.length ? '<p style="color:#B5792B;font-size:12px;margin-top:16px;">⚠️ 讀取失敗的來源（請到「情報來源」分頁檢查網址）：<br>' + errors.map(escapeHtml_).join('<br>') + '</p>' : '') +
    '</div>';

  GmailApp.sendEmail(ownerEmail_(), '【KOL系統】每週情報彙整 ' + today, '請以 HTML 檢視此郵件', { htmlBody: html });
  logAction_('每週情報彙整', '來源 ' + sources.length + '、成功段落 ' + sections.length + '、失敗 ' + errors.length);
}

/* ================= 每日跟進摘要（主動曝光：節奏紀律） ================= */

/**
 * 每日跟進摘要信（時間觸發器：每日 08:00）
 * 內容：今日到期／已逾期的跟進（附鉤子）＋關係降溫警示。沒有事項就不寄。
 */
function dailyFollowUpDigest() {
  const r = api_getDueFollowUps();
  if (!r.due.length && !r.stale.length) {
    logAction_('每日跟進摘要', '今日無待跟進與降溫警示，未寄送');
    return;
  }

  const rowHtml = k =>
    '<tr>' +
    '<td style="padding:6px 10px;border:1px solid #D9DEE6;"><b>' + escapeHtml_(k['姓名']) + '</b><br>' +
    '<span style="color:#5B6472;font-size:12px;">' + escapeHtml_(k['職稱'] || '') + ' · ' + escapeHtml_(k['公司'] || '') + '</span></td>' +
    '<td style="padding:6px 10px;border:1px solid #D9DEE6;text-align:center;">' + tierOf_(k) + '級</td>' +
    '<td style="padding:6px 10px;border:1px solid #D9DEE6;">' + fmtDate_(k['下次跟進日']) + '</td>' +
    '<td style="padding:6px 10px;border:1px solid #D9DEE6;">' + escapeHtml_(k['下次跟進鉤子'] || '—') + '</td>' +
    '</tr>';

  const staleRowHtml = k =>
    '<tr>' +
    '<td style="padding:6px 10px;border:1px solid #D9DEE6;"><b>' + escapeHtml_(k['姓名']) + '</b><br>' +
    '<span style="color:#5B6472;font-size:12px;">' + escapeHtml_(k['職稱'] || '') + ' · ' + escapeHtml_(k['公司'] || '') + '</span></td>' +
    '<td style="padding:6px 10px;border:1px solid #D9DEE6;text-align:center;">' + tierOf_(k) + '級</td>' +
    '<td style="padding:6px 10px;border:1px solid #D9DEE6;color:#B5792B;">' +
    (k['_降溫天數'] === -1 ? '從未記錄接觸' : k['_降溫天數'] + ' 天未接觸') + '</td>' +
    '<td style="padding:6px 10px;border:1px solid #D9DEE6;">' + escapeHtml_(k['下次跟進鉤子'] || '建議：分享一則對方市場的法規動態') + '</td>' +
    '</tr>';

  const th = '<tr style="background:#14213D;color:#fff;font-size:12px;">' +
    '<th style="padding:6px 10px;">KOL</th><th style="padding:6px 10px;">等級</th>' +
    '<th style="padding:6px 10px;">狀態</th><th style="padding:6px 10px;">鉤子／建議動作</th></tr>';

  const today = fmtDate_(new Date());
  const html =
    '<div style="font-family:-apple-system,\'Noto Sans TC\',sans-serif;max-width:720px;color:#14213D;line-height:1.7;">' +
    '<h2 style="font-size:17px;border-bottom:2px solid #14213D;padding-bottom:8px;">📌 今日 KOL 跟進摘要 ' + today + '</h2>' +
    (r.due.length
      ? '<h3 style="font-size:14.5px;color:#0A5D5C;">今日到期／已逾期（' + r.due.length + '）</h3>' +
        '<table style="border-collapse:collapse;width:100%;font-size:13.5px;">' + th + r.due.map(rowHtml).join('') + '</table>'
      : '') +
    (r.stale.length
      ? '<h3 style="font-size:14.5px;color:#B5792B;margin-top:22px;">⚠️ 關係降溫警示（' + r.stale.length + '）</h3>' +
        '<table style="border-collapse:collapse;width:100%;font-size:13.5px;">' + th + r.stale.map(staleRowHtml).join('') + '</table>'
      : '') +
    '<p style="color:#5B6472;font-size:12.5px;margin-top:20px;">到主控台可一鍵產生開發信草稿（話術模板已代入姓名與鉤子）。</p>' +
    '</div>';

  GmailApp.sendEmail(
    ownerEmail_(),
    '【KOL跟進】今日 ' + r.due.length + ' 位到期、' + r.stale.length + ' 位降溫 — ' + today,
    '請以 HTML 檢視此郵件',
    { htmlBody: html }
  );
  logAction_('每日跟進摘要', '到期 ' + r.due.length + '、降溫 ' + r.stale.length);
}

/* ================= 季報模組（被動曝光：季度觸達） ================= */

/** 每月 1 日觸發，僅在 1/4/7/10 月實際執行 */
function quarterlyKickoff() {
  const m = new Date().getMonth(); // 0-based
  if ([0, 3, 6, 9].indexOf(m) === -1) return;
  const r = api_generateQuarterlyReport();
  GmailApp.sendEmail(
    ownerEmail_(),
    '【KOL系統】本季季報文件已建立，請填寫後寄送電子報',
    r.name + '\n' + r.url +
    '\n\n填寫完成後，到主控台「自動化」分頁 → 電子報區塊寄送給 A/B 級訂閱名單。',
    {}
  );
}

function api_generateQuarterlyReport() {
  const rootId = readSetting_('ROOT_FOLDER_ID');
  if (!rootId) throw new Error('系統尚未初始化，請先執行初始化');
  const rootFolder = DriveApp.getFolderById(rootId);
  const templatesFolder = ensureDriveFolder_('範本文件', rootFolder, null);
  const reportsFolder = ensureDriveFolder_('季度動態報告', rootFolder, null);

  const it = templatesFolder.getFilesByName(CONFIG.TEMPLATE_DOC_NAME);
  if (!it.hasNext()) throw new Error('找不到季報範本，請執行「自動修復系統」');
  const template = it.next();

  const now = new Date();
  const q = Math.floor(now.getMonth() / 3) + 1;
  const name = '法規動態季報_' + now.getFullYear() + '_Q' + q;

  const existing = reportsFolder.getFilesByName(name);
  if (existing.hasNext()) {
    const f = existing.next();
    return { name: name, url: f.getUrl(), status: 'existing' };
  }
  const copy = template.makeCopy(name, reportsFolder);
  logAction_('產生季報', name);
  return { name: name, url: copy.getUrl(), status: 'created' };
}

/* ================= 開發信草稿模組（主動曝光） ================= */

function api_getOutreachTemplates() {
  return Object.keys(OUTREACH_TEMPLATES);
}

/**
 * 依話術模板建立 Gmail 草稿（代入姓名/公司/鉤子），寄出前請個人化最後 20%。
 */
function api_draftOutreach(kolId, templateKey) {
  const tpl = OUTREACH_TEMPLATES[templateKey];
  if (!tpl) throw new Error('找不到話術模板：' + templateKey);
  const kol = api_getKolList().find(k => String(k['ID']) === String(kolId));
  if (!kol) throw new Error('找不到此 KOL');

  const fill = s => s
    .replace(/\{姓名\}/g, String(kol['姓名'] || ''))
    .replace(/\{公司\}/g, String(kol['公司'] || '貴公司'))
    .replace(/\{鉤子\}/g, String(kol['下次跟進鉤子'] || '上次談到的議題'))
    .replace(/\{我的姓名\}/g, senderName_());

  GmailApp.createDraft(String(kol['Email'] || ''), fill(tpl.subject), fill(tpl.body));
  logAction_('建立開發信草稿', kol['姓名'] + '／' + templateKey);
  return { status: 'ok', to: kol['Email'] || '（未填Email，草稿收件人為空）' };
}

/* ================= Calendar 同步（主動曝光） ================= */

/**
 * 把未來 60 天內的「下次跟進日」同步為 Google Calendar 全天事件（重複執行不會重複建立）。
 */
function api_syncFollowUpsToCalendar() {
  const cal = CalendarApp.getDefaultCalendar();
  const today = startOfDay_(new Date());
  const horizon = new Date(today.getTime() + 60 * 86400000);
  let created = 0;

  api_getKolList().forEach(k => {
    const next = toDate_(k['下次跟進日']);
    if (!next) return;
    const day = startOfDay_(next);
    if (day < today || day > horizon) return;
    const title = '【KOL跟進】' + k['姓名'];
    const exists = cal.getEventsForDay(day).some(ev => ev.getTitle() === title);
    if (exists) return;
    cal.createAllDayEvent(title, day, {
      description:
        (k['公司'] ? '公司：' + k['公司'] + '\n' : '') +
        '等級：' + tierOf_(k) + '級\n' +
        '鉤子：' + (k['下次跟進鉤子'] || '—')
    });
    created++;
  });

  logAction_('Calendar同步', '建立 ' + created + ' 個跟進事件');
  return { created: created };
}

/* ================= 觸發器管理（程式串聯的開關） ================= */

function activeTriggerHandlers_() {
  return ScriptApp.getProjectTriggers().map(t => t.getHandlerFunction());
}

function api_getTriggerStatus() {
  const active = activeTriggerHandlers_();
  return Object.keys(CONFIG.TRIGGERS).map(h => ({
    handler: h,
    label: CONFIG.TRIGGERS[h],
    enabled: active.indexOf(h) !== -1
  }));
}

function api_setupTriggers() {
  removeManagedTriggers_();
  ScriptApp.newTrigger('dailyFollowUpDigest').timeBased().everyDays(1).atHour(8).create();
  ScriptApp.newTrigger('weeklyIntelDigest').timeBased().everyWeeks(1)
    .onWeekDay(ScriptApp.WeekDay.MONDAY).atHour(8).create();
  ScriptApp.newTrigger('quarterlyKickoff').timeBased().onMonthDay(1).atHour(9).create();
  const enabled = Object.keys(CONFIG.TRIGGERS).map(h => CONFIG.TRIGGERS[h]);
  logAction_('啟用自動化排程', enabled.join('；'));
  return { enabled: enabled };
}

function api_removeTriggers() {
  const removed = removeManagedTriggers_();
  logAction_('停用自動化排程', '移除 ' + removed + ' 個觸發器');
  return { removed: removed };
}

function removeManagedTriggers_() {
  let removed = 0;
  ScriptApp.getProjectTriggers().forEach(t => {
    if (CONFIG.TRIGGERS[t.getHandlerFunction()]) {
      ScriptApp.deleteTrigger(t);
      removed++;
    }
  });
  return removed;
}

/* ================= 公開洞察頁（被動曝光：盡職調查落點） ================= */

function renderInsightsPage_() {
  const tpl = HtmlService.createTemplateFromFile('Insights');
  tpl.data = {
    title: String(readSetting_('PUBLIC_TITLE') || '跨國醫材法規洞察'),
    tagline: String(readSetting_('PUBLIC_TAGLINE') || ''),
    contact: String(readSetting_('PUBLIC_CONTACT_EMAIL') || ''),
    items: getPublishedContent_()
  };
  return tpl.evaluate()
    .setTitle(String(readSetting_('PUBLIC_TITLE') || '跨國醫材法規洞察'))
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

/* ================= 系統狀態 API ================= */

function api_runSelfCheck() { return selfCheck(); }
function api_runAutoFix() { return autoFix(); }

function api_runInitialize() {
  // 側邊欄呼叫時不彈 UI alert，直接執行核心邏輯
  const result = { sheets: [], folders: [], docs: [], errors: [] };
  const ss = ss_();
  allSheetSpecs_().forEach(spec => ensureSheet_(ss, spec.name, spec.headers, result));
  seedIntelSources_();
  const rootFolder = ensureDriveFolder_(CONFIG.DRIVE_ROOT_FOLDER, null, result);
  CONFIG.DRIVE_SUBFOLDERS.forEach(name => ensureDriveFolder_(name, rootFolder, result));
  ensureTemplateDoc_(rootFolder, result);
  writeSetting_('ROOT_FOLDER_ID', rootFolder.getId());
  if (!readSetting_('INIT_DATE')) writeSetting_('INIT_DATE', new Date().toISOString());
  writeSetting_('VERSION', CONFIG.VERSION);
  logAction_('初始化系統(主控台)', JSON.stringify(result));
  return result;
}

function api_getSystemStatus() {
  let webAppUrl = '';
  try {
    webAppUrl = ScriptApp.getService().getUrl() || '';
  } catch (e) { /* 尚未部署為 Web App */ }
  return {
    version: CONFIG.VERSION,
    rootFolderId: readSetting_('ROOT_FOLDER_ID'),
    initDate: readSetting_('INIT_DATE'),
    ownerEmail: ownerEmail_(),
    senderName: senderName_(),
    webAppUrl: webAppUrl,
    remainingQuota: MailApp.getRemainingDailyQuota()
  };
}

function api_saveSettings(settings) {
  ['SENDER_NAME', 'SIGNATURE', 'PUBLIC_TITLE', 'PUBLIC_TAGLINE', 'PUBLIC_CONTACT_EMAIL'].forEach(k => {
    if (settings[k] !== undefined) writeSetting_(k, settings[k]);
  });
  return { status: 'ok' };
}

function api_getSettings() {
  return {
    SENDER_NAME: String(readSetting_('SENDER_NAME') || ''),
    SIGNATURE: String(readSetting_('SIGNATURE') || ''),
    PUBLIC_TITLE: String(readSetting_('PUBLIC_TITLE') || ''),
    PUBLIC_TAGLINE: String(readSetting_('PUBLIC_TAGLINE') || ''),
    PUBLIC_CONTACT_EMAIL: String(readSetting_('PUBLIC_CONTACT_EMAIL') || '')
  };
}
