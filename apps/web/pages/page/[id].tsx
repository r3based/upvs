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

interface NavItem {
  page_id: string;
  url: string;
  title: string;
}

interface PageNavigation {
  current: NavItem;
  parent: NavItem | null;
  siblings: NavItem[];
  children: NavItem[];
}

export default function PageView() {
  const router = useRouter();
  const { id } = router.query;
  const [bundle, setBundle] = useState<PageBundle | null>(null);
  const [navigation, setNavigation] = useState<PageNavigation | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!id) return;
    const load = async () => {
      setLoading(true);
      try {
        const [bundleRes, navRes] = await Promise.all([
          fetch(
          mode === 'static'
            ? apiUrl(`/api/static/page/${id}`)
              : apiUrl(`/pages/${id}/blocks`)
          ),
          fetch(apiUrl(`/navigation/page/${id}`)),
        ]);

        const bundleData = await bundleRes.json();
        const navData = await navRes.json();

        if (mode === 'static') {
          setBundle(bundleData);
        } else {
          setBundle({
            page: bundleData.page,
            blocks: bundleData.blocks,
          });
        }
        setNavigation(navData);
      } catch (error) {
        console.error('Error loading page:', error);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  // Группируем блоки по разделам
  const groupedBlocks = bundle?.blocks.reduce((acc, block) => {
    const sectionPath = block.section_path?.join(' / ') || 'Общее';
    if (!acc[sectionPath]) {
      acc[sectionPath] = [];
    }
    acc[sectionPath].push(block);
    return acc;
  }, {} as Record<string, Block[]>) || {};

  return (
    <div className="page-layout">
      {navigation && (
        <aside className="sidebar">
          <div className="sidebar-content">
            {navigation.parent && (
              <div className="nav-section">
                <div className="nav-section-title">Родительский раздел</div>
                <Link href={`/page/${navigation.parent.page_id}`} className="nav-link">
                  {navigation.parent.title}
                </Link>
              </div>
            )}

            {navigation.siblings.length > 0 && (
              <div className="nav-section">
                <div className="nav-section-title">Соседние разделы</div>
                {navigation.siblings.map((sibling) => (
                  <Link
                    key={sibling.page_id}
                    href={`/page/${sibling.page_id}`}
                    className="nav-link"
                  >
                    {sibling.title}
                  </Link>
                ))}
              </div>
            )}

            {navigation.children.length > 0 && (
              <div className="nav-section">
                <div className="nav-section-title">Подразделы</div>
                {navigation.children.map((child) => (
                  <Link
                    key={child.page_id}
                    href={`/page/${child.page_id}`}
                    className="nav-link"
                  >
                    {child.title}
                  </Link>
                ))}
              </div>
            )}
          </div>
        </aside>
      )}

      <main className="page-content">
      <div className="header">
        <div className="nav">
            <Link href="/">Навигация</Link>
          <Link href="/search">Поиск</Link>
            <Link href="/rag">Вопрос-ответ</Link>
        </div>
        <h1>{bundle?.page?.title || 'Страница'}</h1>
          {bundle?.page?.url && (
            <div className="block-meta">{bundle.page.url}</div>
          )}
      </div>

        {loading ? (
          <p>Загрузка...</p>
        ) : (
          <>
            {Object.entries(groupedBlocks).map(([sectionPath, blocks]) => (
              <div key={sectionPath} className="article-section">
                {sectionPath !== 'Общее' && (
                  <h2 className="section-title">{sectionPath}</h2>
                )}
                {blocks.map((block) => {
        if (block.kind === 'text') {
          return (
            <div className="card" key={block.chunk_id}>
                        <p className="article-text">{block.text}</p>
            </div>
          );
        }
        return (
          <div className="card" key={block.table_id}>
                      <strong className="table-caption">
                        {block.caption || 'Таблица'}
                      </strong>
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
            ))}
          </>
        )}
      </main>
    </div>
  );
}
