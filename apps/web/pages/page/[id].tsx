import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { apiUrl, mode } from '../../lib/api';

interface BlockText {
  kind: 'text';
  chunk_id: string;
  source_order: number;
  section_path: string[];
  text: string;
}

interface BlockTable {
  kind: 'table';
  table_id: string;
  source_order: number;
  section_path: string[];
  caption: string | null;
  columns: string[];
  rows: string[][];
}

type Block = BlockText | BlockTable;

interface PageBundle {
  page: {
    page_id: string;
    title: string;
    url: string;
  };
  blocks: Block[];
}

export default function PageView() {
  const router = useRouter();
  const { id } = router.query;
  const [bundle, setBundle] = useState<PageBundle | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!id) return;
    const load = async () => {
      setLoading(true);
      try {
        const url =
          mode === 'static'
            ? apiUrl(`/api/static/page/${id}`)
            : apiUrl(`/pages/${id}/blocks`);
        const res = await fetch(url);
        const data = await res.json();
        if (mode === 'static') {
          setBundle(data);
        } else {
          setBundle({
            page: data.page,
            blocks: data.blocks
          });
        }
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  return (
    <div className="container">
      <div className="header">
        <div className="nav">
          <Link href="/">Страницы</Link>
          <Link href="/search">Поиск</Link>
          <Link href="/rag">RAG</Link>
        </div>
        <h1>{bundle?.page?.title || 'Страница'}</h1>
        {bundle?.page?.url ? <div className="block-meta">{bundle.page.url}</div> : null}
      </div>
      {loading ? <p>Загрузка...</p> : null}
      {bundle?.blocks?.map((block) => {
        if (block.kind === 'text') {
          return (
            <div className="card" key={block.chunk_id}>
              <div className="block-meta">{block.section_path?.join(' / ')}</div>
              <p>{block.text}</p>
            </div>
          );
        }
        return (
          <div className="card" key={block.table_id}>
            <div className="block-meta">{block.section_path?.join(' / ')}</div>
            <strong>{block.caption || 'Таблица'}</strong>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    {block.columns?.map((col, idx) => (
                      <th key={idx}>{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {block.rows?.map((row, rIdx) => (
                    <tr key={rIdx}>
                      {row.map((cell, cIdx) => (
                        <td key={cIdx}>{cell}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}
    </div>
  );
}
