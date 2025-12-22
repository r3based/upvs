import { useState } from 'react';
import Link from 'next/link';
import { apiUrl } from '../lib/api';

interface RagSource {
  page_id: string;
  url: string;
  title: string;
  chunk_id: string;
  score: number;
  section_path: string[];
  text: string;
}

export default function RagPage() {
  const [query, setQuery] = useState('');
  const [answer, setAnswer] = useState('');
  const [sources, setSources] = useState<RagSource[]>([]);
  const [loading, setLoading] = useState(false);

  const onAsk = async () => {
    setLoading(true);
    setAnswer('');
    setSources([]);
    try {
      const res = await fetch(apiUrl('/rag'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });
      const data = await res.json();
      setAnswer(data.answer || '');
      setSources(data.sources || []);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container">
      <div className="header">
        <div className="nav">
          <Link href="/">Страницы</Link>
          <Link href="/search">Поиск</Link>
          <Link href="/rag">RAG</Link>
        </div>
        <h1>Вопрос-ответ</h1>
        <input
          className="input"
          placeholder="Введите вопрос"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <button className="button" onClick={onAsk} disabled={!query || loading}>
          {loading ? 'Отвечаю...' : 'Спросить'}
        </button>
      </div>
      {answer ? (
        <div className="card">
          <h3>Ответ</h3>
          <p>{answer}</p>
        </div>
      ) : null}
      {sources.length > 0 ? (
        <div className="card">
          <h3>Источники</h3>
          <ul>
            {sources.map((source) => (
              <li key={source.chunk_id}>
                <Link href={`/page/${source.page_id}`}>{source.title || source.url}</Link>
                <div className="block-meta">{source.section_path?.join(' / ')}</div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
