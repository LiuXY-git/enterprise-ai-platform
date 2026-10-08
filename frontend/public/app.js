"use strict";

const byId = (id) => document.getElementById(id);

async function api(path, options = {}, timeoutMs = 185000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`/api${path}`, { ...options, signal: controller.signal });
    if (!response.ok) throw new Error(`请求失败（HTTP ${response.status}），请检查服务日志。`);
    return await response.json();
  } catch (error) {
    if (error.name === "AbortError") throw new Error("等待超时，请检查服务状态。请求可能仍在处理，请勿立即重复上传。");
    if (error instanceof TypeError) throw new Error("无法连接服务，请检查容器是否启动。");
    throw error;
  } finally { clearTimeout(timer); }
}

function message(id, text, error = false) {
  const target = byId(id);
  target.textContent = text;
  target.classList.toggle("error", error);
}

async function checkHealth() {
  byId("refresh").disabled = true;
  message("health", "正在连接后端…");
  try {
    const data = await api("/health", {}, 5000);
    if (data.status !== "ok") throw new Error("后端返回异常状态。");
    message("health", "● 后端已连接");
  } catch (error) { message("health", error.message, true); }
  finally { byId("refresh").disabled = false; }
}

byId("refresh").addEventListener("click", checkHealth);
byId("upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button");
  if (button.disabled) return;
  const file = byId("file").files[0];
  if (!file) return;
  if (!/\.(pdf|docx|md)$/i.test(file.name) || file.size === 0 || file.size >= 10 * 1024 * 1024) {
    message("upload-status", "请选择非空的 PDF、DOCX 或 MD 文件，且小于 10 MB。", true);
    return;
  }
  button.disabled = true;
  message("upload-status", "正在解析文档并建立索引…");
  const body = new FormData();
  body.append("file", file);
  try {
    const data = await api("/upload", { method: "POST", body });
    if (data.status !== "indexed") throw new Error("文档尚未完成索引，请查看服务日志。");
    message("upload-status", `已收录 ${data.filename}，共 ${data.chunk_count} 个片段（文档 #${data.document_id}）。`);
  } catch (error) { message("upload-status", error.message, true); }
  finally { button.disabled = false; }
});

byId("search-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button");
  if (button.disabled) return;
  const question = byId("question").value.trim();
  if (!question) { message("search-status", "请输入要查找的问题。", true); return; }
  button.disabled = true;
  byId("results").replaceChildren();
  message("search-status", "正在检索…");
  try {
    const data = await api("/rag/query", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, top_k: 3 }),
    });
    if (!Array.isArray(data.results)) throw new Error("检索结果格式异常，请查看服务日志。");
    message("search-status", data.results.length ? `找到 ${data.results.length} 个相关片段` : "未找到片段，请先上传文档。");
    for (const [index, item] of data.results.entries()) {
      const article = document.createElement("article");
      article.className = "result";
      const title = document.createElement("h3");
      title.textContent = `${index + 1}. ${item.source}`;
      const meta = document.createElement("small");
      meta.textContent = `片段编号 ${item.chunk_index}`;
      const text = document.createElement("p");
      text.textContent = item.text;
      article.append(title, meta, text);
      byId("results").append(article);
    }
  } catch (error) { message("search-status", error.message, true); }
  finally { button.disabled = false; }
});

checkHealth();
