import { useMemo, useCallback, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';
import rehypeRaw from 'rehype-raw';
import rehypeHighlight from 'rehype-highlight';
import 'katex/dist/katex.min.css';
import 'highlight.js/styles/github.css';

/**
 * Remark plugin: indented code block 비활성화 (fenced code block만 허용)
 */
function remarkDisableIndentedCode() {
  const data = this.data();
  const extensions = data.micromarkExtensions || [];
  extensions.push({ disable: { null: ['codeIndented'] } });
  data.micromarkExtensions = extensions;
}

/**
 * 마크다운 전처리:
 * 1. 코드 펜스 밖의 """ ... """ 블록을 HTML output 블록으로 변환
 * 2. CJK 문자와 CommonMark emphasis 파싱 이슈 수정
 */
function preprocessMarkdown(md) {
  const lines = md.split('\n');
  const result = [];
  let inCodeBlock = false;
  let codeBlockLang = '';
  let codeLines = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const fenceMatch = line.match(/^```(\w*)$/);

    if (fenceMatch && !inCodeBlock) {
      inCodeBlock = true;
      codeBlockLang = fenceMatch[1];
      codeLines = [];
      continue;
    }

    if (line.match(/^```\s*$/) && inCodeBlock) {
      inCodeBlock = false;
      result.push('```' + codeBlockLang);
      result.push(...codeLines);
      result.push('```');
      continue;
    }

    if (inCodeBlock) {
      codeLines.push(line);
    } else {
      result.push(line);
    }
  }

  if (inCodeBlock) {
    result.push('```' + codeBlockLang);
    result.push(...codeLines);
  }

  let output = result.join('\n');
  output = output.replace(/^"""\s*\n([\s\S]*?)\n"""\s*$/gm, (_match, content) => {
    const escaped = escapeHtml(content.trim());
    return `\n<div class="code-output standalone-output"><span class="code-output-label">Output</span><pre><code>${escaped}</code></pre></div>\n\n`;
  });

  // CJK 문자 emphasis 파싱 이슈 수정
  const codeSpans = [];
  output = output.replace(/`[^`]+`/g, (m) => {
    codeSpans.push(m);
    return `\x00CS${codeSpans.length - 1}\x00`;
  });

  output = output.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
  output = output.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

  output = output.replace(/\x00CS(\d+)\x00/g, (_, i) => codeSpans[parseInt(i)]);

  return output;
}

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * Rehype plugin: 헤딩 하위 콘텐츠에 들여쓰기 적용
 */
function rehypeSectionIndent() {
  return (tree) => {
    const newChildren = [];
    let currentLevel = 0;
    let sectionChildren = [];

    function flushSection() {
      if (sectionChildren.length === 0) return;
      const padding = currentLevel - 1;
      if (padding > 0) {
        const wrapper = {
          type: 'element',
          tagName: 'div',
          properties: { style: `padding-left:${padding}rem` },
          children: sectionChildren,
        };
        newChildren.push(wrapper);
      } else {
        newChildren.push(...sectionChildren);
      }
      sectionChildren = [];
    }

    for (const node of tree.children) {
      if (node.type === 'element' && /^h[1-6]$/.test(node.tagName)) {
        flushSection();
        const level = parseInt(node.tagName.charAt(1));
        currentLevel = level;

        const headingPadding = level - 1;
        if (headingPadding > 0) {
          const wrapper = {
            type: 'element',
            tagName: 'div',
            properties: { style: `padding-left:${headingPadding}rem` },
            children: [node],
          };
          newChildren.push(wrapper);
        } else {
          newChildren.push(node);
        }
        continue;
      }

      sectionChildren.push(node);
    }

    flushSection();
    tree.children = newChildren;
  };
}

function CodeBlockWrapper({ children, ...props }) {
  const preRef = useRef(null);
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    const text = preRef.current?.textContent || '';
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, []);

  return (
    <pre ref={preRef} {...props}>
      {children}
      <button
        type="button"
        onClick={handleCopy}
        className="code-copy-btn"
        aria-label="코드 복사"
      >
        {copied ? (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 6L9 17l-5-5" />
          </svg>
        ) : (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
            <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
          </svg>
        )}
      </button>
    </pre>
  );
}

export default function MarkdownPreview({ content, className }) {
  const remarkPlugins = useMemo(() => [remarkDisableIndentedCode, remarkMath, remarkGfm], []);
  const rehypePlugins = useMemo(() => [rehypeKatex, rehypeRaw, rehypeHighlight, rehypeSectionIndent], []);
  const processed = useMemo(() => preprocessMarkdown(content || ''), [content]);

  const components = useMemo(() => ({
    pre({ children, ...props }) {
      return <CodeBlockWrapper {...props}>{children}</CodeBlockWrapper>;
    },
    code({ className: codeClassName, children, ...props }) {
      const match = /language-(\w+)/.exec(codeClassName || '');
      const isBlock = props.node?.position?.start.column === 1;
      if (match && isBlock) {
        return (
          <>
            <span className="code-lang-label">{match[1]}</span>
            <code className={codeClassName} {...props}>{children}</code>
          </>
        );
      }
      return <code className={codeClassName} {...props}>{children}</code>;
    },
    img({ src, alt, ...props }) {
      const altStr = alt || '';
      const srcStr = src || '';
      const parts = altStr.split('|');
      const cleanAlt = parts[0].trim();
      const size = parts[1]?.trim();

      if (!size) {
        return <img src={srcStr} alt={cleanAlt} {...props} />;
      }

      const wxh = size.match(/^(\d+)\s*x\s*(\d+)$/);
      if (wxh) {
        return <img src={srcStr} alt={cleanAlt} style={{ width: `${wxh[1]}px`, height: `${wxh[2]}px` }} />;
      }

      const w = size.match(/^(\d+)(px|%)?$/);
      if (w) {
        const unit = w[2] || 'px';
        return <img src={srcStr} alt={cleanAlt} style={{ width: `${w[1]}${unit}` }} />;
      }

      return <img src={srcStr} alt={cleanAlt} {...props} />;
    },
  }), []);

  return (
    <div className={className ?? 'prose'}>
      <ReactMarkdown
        remarkPlugins={remarkPlugins}
        rehypePlugins={rehypePlugins}
        components={components}
      >
        {processed}
      </ReactMarkdown>
    </div>
  );
}
