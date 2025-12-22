import { useState } from 'react';
import Link from 'next/link';
import { apiUrl } from '../lib/api';

interface SearchHit {
  chunk_id: string;
  page_id: string;
  url: string;
  score: number;
  section_path: string[];
  text_preview: string;
  title?: string;
}

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [loading, setLoading] = useState(false);

  const onSearch = async () => {
    setLoading(true);
    try {
      const res = await fetch(apiUrl('/search'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, top_k: 8 })
      });
      const data = await res.json();
      setHits(data.hits || []);
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
        <h1>Поиск</h1>
        <input
          className="input"
          placeholder="Введите запрос"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <button className="button" onClick={onSearch} disabled={!query || loading}>
          {loading ? 'Поиск...' : 'Найти'}
        </button>
      </div>
      <div className="list">
        {hits.map((hit) => (
          <div className="card" key={hit.chunk_id}>
            <h3>
              <Link href={`/page/${hit.page_id}`}>{hit.title || hit.url}</Link>
            </h3>
            <div className="block-meta">{hit.section_path?.join(' / ')}</div>
            <p>{hit.text_preview}</p>
            <div className="block-meta">Score: {hit.score.toFixed(3)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
