/**
 * utils.js - 前端共用工具函式
 */

"use strict";

/** 顯示 Toast 通知 */
function showToast(message, duration = 2000) {
  const existing = document.querySelector(".toast");
  if (existing) existing.remove();

  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = message;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), duration);
}

/** 線性插值 */
function lerp(a, b, t) {
  return a + (b - a) * t;
}

/** 向量長度 */
function magnitude(dx, dy) {
  return Math.sqrt(dx * dx + dy * dy);
}

/** 正規化向量，回傳 {dx, dy} */
function normalize(dx, dy) {
  const m = magnitude(dx, dy);
  if (m === 0) return { dx: 0, dy: 0 };
  return { dx: dx / m, dy: dy / m };
}

/** 限制值在 [min, max] 範圍內 */
function clamp(v, min, max) {
  return Math.max(min, Math.min(max, v));
}

/** 節流函式 */
function throttle(fn, ms) {
  let last = 0;
  return function (...args) {
    const now = Date.now();
    if (now - last >= ms) {
      last = now;
      fn.apply(this, args);
    }
  };
}

/** 防抖函式 */
function debounce(fn, ms) {
  let timer;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), ms);
  };
}

/** 格式化時間戳 */
function formatTime(ts) {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString("zh-TW", { hour12: false });
}

// 讓 Node.js 環境也可 require（測試用）
if (typeof module !== "undefined") {
  module.exports = { showToast, lerp, magnitude, normalize, clamp, throttle, debounce, formatTime };
}
