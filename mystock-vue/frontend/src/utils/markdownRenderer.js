import MarkdownIt from 'markdown-it';
import mermaid from 'mermaid';

const markdown = new MarkdownIt({ html: false, linkify: true, breaks: true });
let diagramSequence = 0;

mermaid.initialize({
  startOnLoad: false,
  securityLevel: 'loose',
  theme: 'neutral',
  flowchart: { useMaxWidth: true }
});

export function renderMarkdown(source) {
  return markdown.render(source || '');
}

export async function renderMermaidDiagrams(root) {
  if (!root) return;

  const codeBlocks = [...root.querySelectorAll('pre > code.language-mermaid')];
  for (const codeBlock of codeBlocks) {
    const pre = codeBlock.parentElement;
    const source = codeBlock.textContent || '';
    const diagramId = `investment-note-mermaid-${Date.now()}-${diagramSequence++}`;

    try {
      const { svg, bindFunctions } = await mermaid.render(diagramId, source);
      if (!root.contains(pre)) continue;

      const figure = document.createElement('figure');
      figure.className = 'mermaid-diagram';
      figure.setAttribute('role', 'img');
      figure.setAttribute('aria-label', 'Mermaid 圖表');
      figure.innerHTML = svg;
      pre.replaceWith(figure);
      bindFunctions?.(figure);
    } catch (error) {
      if (!root.contains(pre)) continue;
      pre.classList.add('mermaid-error-source');
      const message = document.createElement('p');
      message.className = 'mermaid-error-message';
      message.textContent = `Mermaid 圖表語法錯誤：${error?.message || '無法渲染'}`;
      pre.insertAdjacentElement('afterend', message);
    }
  }
}

export async function renderMarkdownWithMermaid(source) {
  const container = document.createElement('div');
  container.innerHTML = renderMarkdown(source);
  await renderMermaidDiagrams(container);
  return container.innerHTML;
}