import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { apiUrl, mode } from '../lib/api';

interface PageIndexItem {
  page_id: string;
  url: string;
  title: string;
  text_chars_total?: number;
  chunks_count?: number;
  tables_count?: number;
  fetched_at?: string | null;
}

export default function Home() {
  const [query, setQuery] = useState('');
  const [items, setItems] = useState<PageIndexItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(0);
  const limit = 20;

  const filtered = useMemo(() => {
    if (!query) {
      return items;
    }
    const lower = query.toLowerCase();
    return items.filter((item) => item.title?.toLowerCase().includes(lower));
  }, [items, query]);

  const paged = filtered.slice(page * limit, (page + 1) * limit);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const url = mode === 'static' ? apiUrl('/api/static/pages') : apiUrl(`/pages?limit=5000&offset=0`);
        const res = await fetch(url);
        const data = await res.json();
        const list = Array.isArray(data) ? data : data.items || [];
        setItems(list);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  return (
    <div className="container">
      <div className="header">
        <h1>UPVS Viewer</h1>
        <div className="nav">
          <Link href="/">Страницы</Link>
          <Link href="/search">Поиск</Link>
          <Link href="/rag">RAG</Link>
        </div>
        <input
          className="input"
          placeholder="Поиск по названию страницы"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setPage(0);
          }}
        />
      </div>
      {loading ? <p>Загрузка...</p> : null}
      <div className="list">
        {paged.map((item) => (
          <div className="card" key={item.page_id}>
            <h3>
              <Link href={`/page/${item.page_id}`}>{item.title || item.url}</Link>
            </h3>
            <div className="block-meta">
              {item.url}
              {item.chunks_count !== undefined ? ` • чанков: ${item.chunks_count}` : ''}
              {item.tables_count !== undefined ? ` • таблиц: ${item.tables_count}` : ''}
            </div>
          </div>
        ))}
      </div>
      <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
        <button className="button" onClick={() => setPage(Math.max(page - 1, 0))} disabled={page === 0}>
          Назад
        </button>
        <button
          className="button"
          onClick={() => setPage(page + 1)}
          disabled={(page + 1) * limit >= filtered.length}
        >
          Далее
        </button>
      </div>
    </div>
  );
}
