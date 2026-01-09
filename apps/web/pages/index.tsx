import { useEffect, useState } from 'react';
import Link from 'next/link';
import { apiUrl } from '../lib/api';

interface NavNode {
  page_id: string;
  url: string;
  title: string;
  parent_url?: string | null;
  children?: NavNode[];
}

export default function Home() {
  const [tree, setTree] = useState<NavNode[]>([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const res = await fetch(apiUrl('/navigation/tree'));
        const data = await res.json();
        setTree(data.tree || []);
        // Раскрываем первый уровень по умолчанию
        const firstLevelIds = (data.tree || []).map((node: NavNode) => node.page_id);
        setExpanded(new Set(firstLevelIds));
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const toggleExpand = (pageId: string) => {
    const newExpanded = new Set(expanded);
    if (newExpanded.has(pageId)) {
      newExpanded.delete(pageId);
    } else {
      newExpanded.add(pageId);
    }
    setExpanded(newExpanded);
  };

  const renderNode = (node: NavNode, level: number = 0): JSX.Element => {
    const hasChildren = node.children && node.children.length > 0;
    const isExpanded = expanded.has(node.page_id);
    const indent = level * 24;

    return (
      <div key={node.page_id} className="nav-node">
        <div
          className="nav-item"
          style={{ paddingLeft: `${indent + 12}px` }}
          onClick={() => hasChildren && toggleExpand(node.page_id)}
        >
          {hasChildren && (
            <span className="nav-toggle">{isExpanded ? '▼' : '▶'}</span>
          )}
          {!hasChildren && <span className="nav-spacer" />}
          <Link href={`/page/${node.page_id}`} className="nav-link">
            {node.title || node.url}
          </Link>
        </div>
        {hasChildren && isExpanded && (
          <div className="nav-children">
            {node.children!.map((child) => renderNode(child, level + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="container">
      <div className="header">
        <h1>UPVS: Навигация</h1>
        <div className="nav">
          <Link href="/">Навигация</Link>
          <Link href="/search">Поиск</Link>
          <Link href="/rag">Вопрос-ответ</Link>
        </div>
      </div>
      {loading ? (
        <p>Загрузка...</p>
      ) : (
        <div className="nav-tree">
          {tree.length === 0 ? (
            <p>Нет данных для отображения</p>
          ) : (
            tree.map((node) => renderNode(node))
          )}
            </div>
      )}
    </div>
  );
}
