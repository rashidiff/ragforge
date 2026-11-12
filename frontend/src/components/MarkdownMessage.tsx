import type { ReactNode } from "react";
import type { Citation } from "../lib/contracts";

interface Props {
  content: string;
  citations: Citation[];
  onCitation: (citation: Citation) => void;
}

export function MarkdownMessage({ content, citations, onCitation }: Props) {
  const lines = content.split(/\r?\n/);
  const blocks: ReactNode[] = [];
  const sources = new Map(
    citations.map((citation) => [citation.chunk_id, citation]),
  );
  let index = 0;
  while (index < lines.length) {
    if (!lines[index].trim()) {
      index += 1;
      continue;
    }
    const fence = lines[index].match(/^\s*```([^`]*)$/);
    if (fence) {
      const code: string[] = [];
      const language = fence[1].trim();
      index += 1;
      while (index < lines.length && !/^\s*```\s*$/.test(lines[index]))
        code.push(lines[index++]);
      if (index < lines.length) index += 1;
      blocks.push(
        <pre className="markdown-code" key={`code-${index}`}>
          <code data-language={language || undefined}>{code.join("\n")}</code>
        </pre>,
      );
      continue;
    }
    const heading = lines[index].match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      const level = heading[1].length;
      const children = inline(heading[2], sources, onCitation);
      blocks.push(
        level === 1 ? (
          <h2 key={`heading-${index}`}>{children}</h2>
        ) : level === 2 ? (
          <h3 key={`heading-${index}`}>{children}</h3>
        ) : (
          <h4 key={`heading-${index}`}>{children}</h4>
        ),
      );
      index += 1;
      continue;
    }
    if (/^\s*>/.test(lines[index])) {
      const quote: string[] = [];
      while (index < lines.length && /^\s*>/.test(lines[index]))
        quote.push(lines[index++].replace(/^\s*>\s?/, ""));
      blocks.push(
        <blockquote key={`quote-${index}`}>
          {inline(quote.join("\n"), sources, onCitation)}
        </blockquote>,
      );
      continue;
    }
    const unordered = lines[index].match(/^\s*[-*+]\s+(.+)$/);
    const ordered = lines[index].match(/^\s*\d+[.)]\s+(.+)$/);
    if (unordered || ordered) {
      const items: string[] = [];
      const isOrdered = Boolean(ordered);
      const pattern = isOrdered ? /^\s*\d+[.)]\s+(.+)$/ : /^\s*[-*+]\s+(.+)$/;
      while (index < lines.length) {
        const item = lines[index].match(pattern);
        if (!item) break;
        items.push(item[1]);
        index += 1;
      }
      const list = items.map((item, itemIndex) => (
        <li key={itemIndex}>{inline(item, sources, onCitation)}</li>
      ));
      blocks.push(
        isOrdered ? (
          <ol key={`list-${index}`}>{list}</ol>
        ) : (
          <ul key={`list-${index}`}>{list}</ul>
        ),
      );
      continue;
    }
    const paragraph: string[] = [];
    while (
      index < lines.length &&
      lines[index].trim() &&
      !/^\s*```/.test(lines[index]) &&
      !/^#{1,6}\s/.test(lines[index]) &&
      !/^\s*>/.test(lines[index]) &&
      !/^\s*[-*+]\s+/.test(lines[index]) &&
      !/^\s*\d+[.)]\s+/.test(lines[index])
    )
      paragraph.push(lines[index++]);
    blocks.push(
      <p key={`paragraph-${index}`}>
        {inline(paragraph.join("\n"), sources, onCitation)}
      </p>,
    );
  }
  return <div className="markdown-message">{blocks}</div>;
}

function inline(
  text: string,
  citations: Map<string, Citation>,
  onCitation: (citation: Citation) => void,
): ReactNode[] {
  const token =
    /(\[\[source:([^\]\s]+)\]\]|`([^`]+)`|\*\*([^*]+)\*\*|\*([^*]+)\*|~~([^~]+)~~|\[([^\]]+)\]\(([^)]+)\))/g;
  const output: ReactNode[] = [];
  let start = 0;
  for (const match of text.matchAll(token)) {
    const position = match.index ?? 0;
    output.push(text.slice(start, position));
    if (match[2]) {
      const citation = citations.get(match[2]);
      output.push(
        citation ? (
          <button
            key={`cite-${position}`}
            className="inline-citation"
            onClick={() => onCitation(citation)}
            aria-label={`Open source ${citation.filename}, page ${citation.page_start}`}
          >
            【{citation.filename}, p. {citation.page_start}】
          </button>
        ) : (
          match[0]
        ),
      );
    } else if (match[3])
      output.push(<code key={`inline-code-${position}`}>{match[3]}</code>);
    else if (match[4])
      output.push(<strong key={`strong-${position}`}>{match[4]}</strong>);
    else if (match[5]) output.push(<em key={`em-${position}`}>{match[5]}</em>);
    else if (match[6])
      output.push(<del key={`del-${position}`}>{match[6]}</del>);
    else if (match[7] && match[8]) {
      const href = safeHref(match[8]);
      output.push(
        href ? (
          <a
            key={`link-${position}`}
            href={href}
            target="_blank"
            rel="noopener noreferrer"
          >
            {match[7]}
          </a>
        ) : (
          match[7]
        ),
      );
    }
    start = position + match[0].length;
  }
  output.push(text.slice(start));
  return output;
}

function safeHref(value: string): string | null {
  try {
    const parsed = new URL(value, "http://127.0.0.1");
    return ["http:", "https:", "mailto:"].includes(parsed.protocol)
      ? value
      : null;
  } catch {
    return null;
  }
}
