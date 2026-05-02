import { useState, useRef, useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import { askAdvisor } from '../utils/api';
import { useAppStore } from '../store';
import PageHeader from '../components/common/PageHeader';
import AccuracyBadge from '../components/common/AccuracyBadge';
import Icon from '../components/common/Icon';

const SUGGESTED_QUESTIONS = [
  'Who are the top Kentucky Derby contenders this year?',
  'What horses should I watch heading into the Triple Crown?',
  'Who are the leading trainers in US racing right now?',
  'Explain the Kentucky Derby points system',
  'What is track bias and how does it affect betting?',
  'How do I read a US past performance sheet?',
  'What does each way mean?',
  'What is a trifecta bet?',
  'How should I size my bets for my bankroll?',
  'What is a Beyer Speed Figure?',
  'How does parimutuel betting work?',
  'What is a claiming race?',
];

/** Render inline markdown: **bold**, *italic*, `code` */
function renderInline(text) {
  const parts = [];
  const re = /(\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`)/g;
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    if (m[2]) parts.push(<strong key={m.index}>{m[2]}</strong>);
    else if (m[3]) parts.push(<em key={m.index}>{m[3]}</em>);
    else if (m[4]) parts.push(
      <code key={m.index} style={{ fontFamily: 'var(--font-mono)', fontSize: '0.9em', background: 'rgba(255,255,255,0.07)', padding: '1px 4px', borderRadius: 3 }}>{m[4]}</code>
    );
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

/** Render assistant markdown: headings, bullets, numbered lists, paragraphs */
function MarkdownContent({ text }) {
  const lines = text.split('\n');
  const elements = [];
  let listItems = [];
  let listType = null; // 'ul' | 'ol'
  let key = 0;

  const flushList = () => {
    if (!listItems.length) return;
    const Tag = listType === 'ol' ? 'ol' : 'ul';
    elements.push(
      <Tag key={key++} style={{ margin: '6px 0', paddingLeft: 20 }}>
        {listItems.map((item, i) => (
          <li key={i} style={{ marginBottom: 3, lineHeight: 1.6 }}>{renderInline(item)}</li>
        ))}
      </Tag>
    );
    listItems = [];
    listType = null;
  };

  for (const raw of lines) {
    const line = raw.trimEnd();

    // Heading
    const hMatch = line.match(/^(#{1,3})\s+(.*)/);
    if (hMatch) {
      flushList();
      const level = hMatch[1].length;
      const fs = level === 1 ? 17 : level === 2 ? 15 : 14;
      elements.push(
        <div key={key++} style={{ fontWeight: 700, fontSize: fs, color: 'var(--accent-gold-bright)', margin: '12px 0 4px', lineHeight: 1.3 }}>
          {renderInline(hMatch[2])}
        </div>
      );
      continue;
    }

    // Unordered list
    const ulMatch = line.match(/^[-*•]\s+(.*)/);
    if (ulMatch) {
      if (listType === 'ol') flushList();
      listType = 'ul';
      listItems.push(ulMatch[1]);
      continue;
    }

    // Ordered list
    const olMatch = line.match(/^\d+\.\s+(.*)/);
    if (olMatch) {
      if (listType === 'ul') flushList();
      listType = 'ol';
      listItems.push(olMatch[1]);
      continue;
    }

    flushList();

    // Blank line
    if (!line.trim()) {
      elements.push(<div key={key++} style={{ height: 8 }} />);
      continue;
    }

    // Normal paragraph line
    elements.push(
      <span key={key++} style={{ display: 'block', lineHeight: 1.7 }}>
        {renderInline(line)}
      </span>
    );
  }

  flushList();
  return <div style={{ fontSize: 14 }}>{elements}</div>;
}

function Message({ msg }) {
  const isUser = msg.role === 'user';
  const isError = msg.role === 'error';
  return (
    <div style={{
      display: 'flex',
      justifyContent: isUser ? 'flex-end' : 'flex-start',
      marginBottom: 12,
    }}>
      {!isUser && (
        <div style={{
          width: 28, height: 28,
          borderRadius: '50%',
          background: isError ? 'rgba(192,57,43,0.15)' : 'rgba(201,162,39,0.15)',
          border: `1px solid ${isError ? 'rgba(192,57,43,0.3)' : 'var(--border-gold)'}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          marginRight: 8,
          flexShrink: 0,
          marginTop: 2,
        }}>
          {isError
            ? <Icon name="warning" size={14} color="var(--accent-red-bright)" />
            : <Icon name="robot" size={16} color="var(--accent-gold)" />}
        </div>
      )}
      <div style={{
        maxWidth: '80%',
        padding: '10px 14px',
        borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
        background: isUser
          ? 'rgba(201,162,39,0.15)'
          : isError
            ? 'rgba(192,57,43,0.08)'
            : 'var(--bg-card)',
        border: `1px solid ${isUser ? 'var(--border-gold)' : isError ? 'rgba(192,57,43,0.25)' : 'var(--border-subtle)'}`,
        lineHeight: 1.7,
        color: isError ? 'var(--accent-red-bright)' : 'var(--text-primary)',
      }}>
        {isUser || isError
          ? <span style={{ fontSize: 14 }}>{msg.content}</span>
          : <MarkdownContent text={msg.content} />
        }
      </div>
    </div>
  );
}

export default function AdvisorPage() {
  const { advisorMessages, addAdvisorMessage, clearAdvisorMessages } = useAppStore();
  const [input, setInput] = useState('');
  const bottomRef = useRef(null);

  const askMutation = useMutation({
    mutationFn: (question) => askAdvisor(question),
    onSuccess: (data) => {
      addAdvisorMessage({ role: 'assistant', content: data.answer || data });
    },
    onError: (err) => {
      const detail = err?.response?.data?.detail || '';
      const msg = detail.includes('credit')
        ? 'Secretariat needs Anthropic API credits to respond. Add credits at console.anthropic.com then restart the server.'
        : `Secretariat is unavailable right now${detail || err.message ? ` (${detail || err.message})` : ''}.`;
      addAdvisorMessage({ role: 'error', content: msg });
    },
  });

  const handleSend = () => {
    const q = input.trim();
    if (!q || askMutation.isPending) return;
    addAdvisorMessage({ role: 'user', content: q });
    setInput('');
    askMutation.mutate(q);
  };

  const handleSuggestion = (q) => {
    if (askMutation.isPending) return;
    addAdvisorMessage({ role: 'user', content: q });
    askMutation.mutate(q);
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [advisorMessages, askMutation.isPending]);

  const showSuggestions = advisorMessages.length === 0;

  return (
    <div className="advisor-page" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <PageHeader
        title="SECRETARIAT"
        subtitle="YOUR AI RACING ADVISOR"
        right={
          advisorMessages.length > 0 ? (
            <button
              onClick={clearAdvisorMessages}
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 12 }}
            >
              Clear
            </button>
          ) : null
        }
      />

      <div style={{ flex: 1, overflowY: 'auto', padding: '16px' }}>
        {showSuggestions && (
          <div>
            <AccuracyBadge />
            <div style={{ textAlign: 'center', padding: '24px 0 20px', color: 'var(--text-muted)' }}>
              <div style={{ fontFamily: 'var(--font-display)', fontSize: 22, color: 'var(--accent-gold)', marginBottom: 6 }}>
                Ask Secretariat
              </div>
              <div style={{ fontSize: 13 }}>
                Get expert handicapping advice, bet education, and race breakdowns.
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 8 }}>
              {SUGGESTED_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => handleSuggestion(q)}
                  style={{
                    textAlign: 'left',
                    padding: '10px 14px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-subtle)',
                    background: 'var(--bg-card)',
                    color: 'var(--text-secondary)',
                    fontSize: 13,
                    cursor: 'pointer',
                    fontFamily: 'var(--font-body)',
                    transition: 'all 0.15s',
                  }}
                  onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--accent-gold-dim)'}
                  onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border-subtle)'}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {advisorMessages.map((msg, i) => (
          <Message key={i} msg={msg} />
        ))}

        {askMutation.isPending && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <div style={{
              width: 28, height: 28, borderRadius: '50%',
              background: 'rgba(201,162,39,0.15)',
              border: '1px solid var(--border-gold)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}><Icon name="robot" size={16} color="var(--accent-gold)" /></div>
            <div style={{
              padding: '10px 14px',
              borderRadius: '16px 16px 16px 4px',
              background: 'var(--bg-card)',
              border: '1px solid var(--border-subtle)',
              display: 'flex', gap: 4, alignItems: 'center',
            }}>
              {[0, 1, 2].map((i) => (
                <div key={i} style={{
                  width: 6, height: 6, borderRadius: '50%',
                  background: 'var(--accent-gold)',
                  animation: `pulse 1s infinite ${i * 0.2}s`,
                }} />
              ))}
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div style={{
        padding: '12px 16px',
        paddingBottom: 'calc(12px + env(safe-area-inset-bottom, 0px))',
        borderTop: '1px solid var(--border-subtle)',
        background: 'var(--bg-secondary)',
        display: 'flex',
        gap: 10,
      }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
          placeholder="Ask about racing, horses, bets…"
          disabled={askMutation.isPending}
          style={{ flex: 1, padding: '10px 14px', fontSize: 16, borderRadius: 'var(--radius-md)' }}
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || askMutation.isPending}
          className="btn btn-primary"
          style={{ padding: '10px 16px' }}
        >
          →
        </button>
      </div>
    </div>
  );
}
