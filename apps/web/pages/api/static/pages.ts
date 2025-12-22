import type { NextApiRequest, NextApiResponse } from 'next';
import fs from 'fs';
import path from 'path';

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  const dataDir = process.env.DATA_DERIVED_DIR || '/app/data/derived';
  const indexPath = path.join(dataDir, 'pages_index.json');

  if (!fs.existsSync(indexPath)) {
    res.status(404).json({ error: 'pages_index.json не найден' });
    return;
  }

  const raw = fs.readFileSync(indexPath, 'utf-8');
  const data = JSON.parse(raw);
  res.status(200).json(data);
}
