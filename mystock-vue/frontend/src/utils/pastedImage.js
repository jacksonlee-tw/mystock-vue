// 投資筆記貼上圖片：把剪貼簿圖片壓縮成 data URI，再以 Markdown 圖片語法內嵌進筆記內容。
// 內容存在 investment_note.content（TEXT），不需要額外的檔案儲存；壓縮是為了讓整篇筆記維持在
// 反向代理的請求大小限制內（見 frontend/nginx.conf 的 client_max_body_size）。

const MAX_WIDTH_STEPS = [1600, 1280, 1024, 800];
const QUALITY_STEPS = [0.9, 0.8, 0.7];
const MAX_DATA_URL_LENGTH = 900 * 1024;
// markdown-it 只放行 gif/png/jpeg/webp 的 data URI（validateLink），其他格式會被當成純文字。
const OUTPUT_TYPES = ['image/webp', 'image/jpeg'];

/** 從 paste 事件取出剪貼簿中的第一張圖片；沒有圖片回傳 null。 */
export function getClipboardImage(event) {
  const items = event.clipboardData?.items;
  if (!items) return null;
  for (const item of items) {
    if (item.kind === 'file' && item.type.startsWith('image/')) return item.getAsFile();
  }
  return null;
}

function loadBitmap(file) {
  return createImageBitmap(file);
}

function canvasToBlob(canvas, type, quality) {
  return new Promise((resolve) => canvas.toBlob(resolve, type, quality));
}

function blobToDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

/**
 * 把圖片檔縮放並壓縮成 data URI（優先 WebP，瀏覽器不支援時退回 JPEG）。
 * 由大到小逐步降低寬度與品質，直到低於 MAX_DATA_URL_LENGTH；仍過大則丟出錯誤，由呼叫端提示使用者。
 */
export async function compressImageToDataUrl(file) {
  const bitmap = await loadBitmap(file);
  try {
    let smallest = null;
    for (const maxWidth of MAX_WIDTH_STEPS) {
      const scale = Math.min(1, maxWidth / bitmap.width);
      const canvas = document.createElement('canvas');
      canvas.width = Math.max(1, Math.round(bitmap.width * scale));
      canvas.height = Math.max(1, Math.round(bitmap.height * scale));
      const ctx = canvas.getContext('2d');
      // JPEG 不支援透明度，先鋪白底避免透明區域變黑
      ctx.fillStyle = '#fff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);

      for (const quality of QUALITY_STEPS) {
        for (const type of OUTPUT_TYPES) {
          const blob = await canvasToBlob(canvas, type, quality);
          // 不支援的輸出格式，toBlob 會靜默退回 PNG（體積大且 type 不符），跳過換下一個格式
          if (!blob || blob.type !== type) continue;
          const dataUrl = await blobToDataUrl(blob);
          if (!smallest || dataUrl.length < smallest.length) smallest = dataUrl;
          if (dataUrl.length <= MAX_DATA_URL_LENGTH) return dataUrl;
          break; // 該品質已有可用格式，只是太大；降低品質／寬度再試
        }
      }
    }
    throw new Error('圖片過大，壓縮後仍超過上限，請裁切後再貼上');
  } finally {
    bitmap.close?.();
  }
}

/**
 * 把圖片以「參考式」Markdown 插進內容：游標處放 `![貼上圖片 N][image-N]`，
 * data URI 定義附在文末，讓原始 Markdown 本文保持可讀，不會夾一大串 base64。
 * 回傳 { content, cursor }，cursor 為插入後應放置的游標位置。
 */
export function insertImageMarkdown(content, selectionStart, selectionEnd, dataUrl) {
  const used = [...content.matchAll(/^\[image-(\d+)\]:/gm)].map((m) => Number(m[1]));
  const n = used.length ? Math.max(...used) + 1 : 1;
  const reference = `![貼上圖片 ${n}][image-${n}]`;
  const before = content.slice(0, selectionStart);
  const after = content.slice(selectionEnd);
  // 圖片獨立成段，前後留空行，避免黏在文字上變成行內圖
  const lead = before && !before.endsWith('\n\n') ? (before.endsWith('\n') ? '\n' : '\n\n') : '';
  const trail = after && !after.startsWith('\n\n') ? (after.startsWith('\n') ? '\n' : '\n\n') : '';
  const body = `${before}${lead}${reference}${trail}${after}`;
  const definition = `[image-${n}]: ${dataUrl}`;
  return {
    content: `${body.replace(/\s+$/, '')}\n\n${definition}\n`,
    cursor: before.length + lead.length + reference.length + trail.length
  };
}
